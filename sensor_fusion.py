"""
NEURAL-CARTOGRAPHY: Sensor Fusion Pipeline

Combines EMG, acoustic (ultrasound doppler), and inertial (IMU) data streams
into synchronized feature vectors for neural intent decoding.

Key features:
- Temporal alignment with sub-millisecond precision
- Cross-modal feature extraction
- Multi-scale temporal windowing
- Real-time streaming architecture
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass
from collections import deque
import torch
import torch.nn as nn
from scipy import signal
from scipy.spatial.transform import Rotation
import time
from threading import Lock


@dataclass
class SensorConfig:
    """Configuration for sensor fusion pipeline."""
    # EMG parameters
    emg_channels: int = 64
    emg_fs: float = 2000.0  # Hz
    emg_buffer_ms: int = 300  # ms of history
    
    # Ultrasound parameters
    usc_channels: int = 32
    usc_fs: float = 1000.0  # Hz (doppler envelope)
    usc_buffer_ms: int = 300  # ms
    
    # IMU parameters
    imu_channels: int = 9  # 3x accel, 3x gyro, 3x mag (or fused quaternion)
    imu_fs: float = 1000.0  # Hz
    imu_buffer_ms: int = 300  # ms
    
    # Fusion parameters
    feature_window_ms: int = 100  # ms per feature window
    hop_length_ms: int = 20  # ms between windows
    alignment_tolerance_us: int = 500  # microseconds


class CircularBuffer:
    """Thread-safe circular buffer for streaming sensor data."""
    
    def __init__(self, channels: int, max_samples: int, dtype=np.float32):
        self.buffer = np.zeros((channels, max_samples), dtype=dtype)
        self.timestamps = np.zeros(max_samples, dtype=np.float64)
        self.max_samples = max_samples
        self.channels = channels
        self.write_idx = 0
        self.lock = Lock()
        self.dtype = dtype
    
    def push(self, data: np.ndarray, timestamp: float):
        """Push new data to buffer. Data shape: (channels,) or (channels, n_samples)."""
        with self.lock:
            if data.ndim == 1:
                data = data[:, np.newaxis]
            n_samples = data.shape[1]
            
            for i in range(n_samples):
                self.buffer[:, self.write_idx] = data[:, i]
                self.timestamps[self.write_idx] = timestamp + i / (self.max_samples / 1000)
                self.write_idx = (self.write_idx + 1) % self.max_samples
    
    def get_recent(self, n_samples: int) -> Tuple[np.ndarray, np.ndarray]:
        """Get most recent n_samples from buffer."""
        with self.lock:
            if n_samples > self.max_samples:
                n_samples = self.max_samples
            
            start_idx = (self.write_idx - n_samples) % self.max_samples
            
            if start_idx + n_samples <= self.max_samples:
                data = self.buffer[:, start_idx:start_idx + n_samples]
                ts = self.timestamps[start_idx:start_idx + n_samples]
            else:
                # Wrap around
                n_first = self.max_samples - start_idx
                data = np.concatenate([
                    self.buffer[:, start_idx:],
                    self.buffer[:, :n_samples - n_first]
                ], axis=1)
                ts = np.concatenate([
                    self.timestamps[start_idx:],
                    self.timestamps[:n_samples - n_first]
                ])
            
            return data.copy(), ts.copy()
    
    def get_time_range(self, start_time: float, end_time: float) -> Tuple[np.ndarray, np.ndarray]:
        """Get data within time range."""
        with self.lock:
            mask = (self.timestamps >= start_time) & (self.timestamps <= end_time)
            indices = np.where(mask)[0]
            if len(indices) == 0:
                return np.array([]), np.array([])
            return self.buffer[:, indices].copy(), self.timestamps[indices].copy()


class EMGProcessor:
    """Process raw EMG signals into features."""
    
    def __init__(self, config: SensorConfig):
        self.config = config
        self.n_channels = config.emg_channels
        self.fs = config.emg_fs
        
        # Bandpass filter: 10-500 Hz (typical EMG bandwidth)
        nyq = self.fs / 2
        low = 10 / nyq
        high = 500 / nyq
        self.b_band, self.a_band = signal.butter(4, [low, high], btype='band')
        
        # Notch filter: 50/60 Hz mains interference
        self.notch_freq = 60  # Hz (US) - change to 50 for EU
        self.b_notch, self.a_notch = signal.iirnotch(self.notch_freq, 30, self.fs)
        
        # Rectification and envelope detection
        self.window_samples = int(0.05 * self.fs)  # 50ms smoothing
        
        # State for streaming
        self.zi_band = np.zeros((self.n_channels, 4))
        self.zi_notch = np.zeros((self.n_channels, 4))
    
    def process(self, raw_emg: np.ndarray) -> np.ndarray:
        """
        Process raw EMG to extract features.
        
        Input: (channels, samples)
        Output: (channels, features) - features per channel
        """
        # 1. Bandpass filter
        filtered, self.zi_band = signal.lfilter(
            self.b_band, self.a_band, raw_emg, axis=1, zi=self.zi_band
        )
        
        # 2. Notch filter
        filtered, self.zi_notch = signal.lfilter(
            self.b_notch, self.a_notch, filtered, axis=1, zi=self.zi_notch
        )
        
        # 3. Rectification (full-wave)
        rectified = np.abs(filtered)
        
        # 4. Linear envelope (moving average)
        window = np.ones(self.window_samples) / self.window_samples
        envelope = np.apply_along_axis(
            lambda x: np.convolve(x, window, mode='same'), 1, rectified
        )
        
        # 5. Feature extraction per channel
        features = []
        for ch in range(self.n_channels):
            ch_data = envelope[ch]
            features.extend([
                np.mean(ch_data),           # Mean activation
                np.std(ch_data),            # Variability
                np.max(ch_data),            # Peak activation
                np.percentile(ch_data, 95), # Robust max
            ])
        
        return np.array(features)
    
    def get_csp_features(self, emg_data: np.ndarray, n_csp: int = 4) -> np.ndarray:
        """
        Extract Common Spatial Pattern (CSP) features for motor imagery.
        Note: Requires pre-computed CSP filters (omitted for streaming version).
        """
        # Placeholder for CSP-based feature extraction
        # In practice, this uses pre-trained spatial filters
        var = np.var(emg_data, axis=1)
        return np.log(var + 1e-10)


class AcousticProcessor:
    """Process ultrasound doppler signals."""
    
    def __init__(self, config: SensorConfig):
        self.config = config
        self.n_channels = config.usc_channels
        self.fs = config.usc_fs
        
        # Blood flow velocity features
        self.velocity_bins = np.linspace(-0.5, 0.5, 16)  # m/s
        
        # Temporal smoothing
        self.smooth_window = int(0.1 * self.fs)  # 100ms
    
    def process(self, doppler_envelope: np.ndarray) -> np.ndarray:
        """
        Process doppler envelope to extract neurovascular features.
        
        Input: (channels, samples) - doppler power envelope
        Output: (features,) - spatial and temporal features
        """
        features = []
        
        for ch in range(self.n_channels):
            ch_data = doppler_envelope[ch]
            
            # 1. Perfusion intensity (total blood volume)
            perfusion = np.mean(ch_data)
            
            # 2. Pulsatility index (cardiac cycle variation)
            if np.mean(ch_data) > 1e-6:
                pi = (np.max(ch_data) - np.min(ch_data)) / np.mean(ch_data)
            else:
                pi = 0
            
            # 3. Spectral features
            # Simple frequency analysis of envelope
            if len(ch_data) > 10:
                fft = np.fft.rfft(ch_data)
                power = np.abs(fft) ** 2
                freqs = np.fft.rfftfreq(len(ch_data), 1/self.fs)
                
                # Total power in cardiac range (0.5-2 Hz)
                cardiac_mask = (freqs >= 0.5) & (freqs <= 2.0)
                cardiac_power = np.sum(power[cardiac_mask]) if np.any(cardiac_mask) else 0
                
                features.extend([perfusion, pi, cardiac_power])
            else:
                features.extend([perfusion, pi, 0])
        
        return np.array(features)
    
    def localize_activation(self, doppler_spatial: np.ndarray) -> Tuple[float, float]:
        """
        Localize region of maximum neural activation using spatial interpolation.
        
        Returns: (x, y) coordinates in transducer array frame
        """
        # Simple centroid calculation
        grid_size = int(np.sqrt(self.n_channels))
        if grid_size * grid_size != self.n_channels:
            return (0.0, 0.0)
        
        spatial_grid = doppler_spatial.reshape(grid_size, grid_size)
        
        # Weighted centroid
        x_idx, y_idx = np.meshgrid(range(grid_size), range(grid_size))
        total = np.sum(spatial_grid)
        
        if total > 0:
            cx = np.sum(x_idx * spatial_grid) / total
            cy = np.sum(y_idx * spatial_grid) / total
        else:
            cx, cy = grid_size / 2, grid_size / 2
        
        return (cx, cy)


class InertialProcessor:
    """Process IMU data for context and motion compensation."""
    
    def __init__(self, config: SensorConfig):
        self.config = config
        self.n_channels = config.imu_channels
        self.fs = config.imu_fs
        
        # Orientation estimation (complementary filter)
        self.quaternion = np.array([1, 0, 0, 0])  # w, x, y, z
        self.alpha = 0.98  # Complementary filter coefficient
        
        # Calibration
        self.accel_bias = np.zeros(3)
        self.gyro_bias = np.zeros(3)
    
    def update_orientation(self, accel: np.ndarray, gyro: np.ndarray, 
                           magnet: Optional[np.ndarray] = None, dt: float = 0.001):
        """Update orientation quaternion using complementary filter."""
        # Gyro integration
        gyro_norm = np.linalg.norm(gyro)
        if gyro_norm > 1e-6:
            delta_angle = gyro_norm * dt
            delta_q = np.array([
                np.cos(delta_angle / 2),
                gyro[0] / gyro_norm * np.sin(delta_angle / 2),
                gyro[1] / gyro_norm * np.sin(delta_angle / 2),
                gyro[2] / gyro_norm * np.sin(delta_angle / 2)
            ])
            self.quaternion = self.quaternion_multiply(self.quaternion, delta_q)
            self.quaternion /= np.linalg.norm(self.quaternion)
        
        # Accelerometer correction
        accel_norm = accel / (np.linalg.norm(accel) + 1e-10)
        
        # Update with magnetometer if available (not critical for short-term)
    
    def quaternion_multiply(self, q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
        """Multiply two quaternions."""
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        return np.array([
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2
        ])
    
    def process(self, imu_data: np.ndarray) -> np.ndarray:
        """
        Process IMU data to extract features.
        Input: (9, samples) - [accel(3), gyro(3), mag(3)]
        Output: (features,) - orientation, motion, etc.
        """
        accel = imu_data[0:3, -1]  # Latest sample
        gyro = imu_data[3:6, -1]
        magnet = imu_data[6:9, -1]
        
        # Update orientation
        self.update_orientation(accel, gyro, magnet, dt=1/self.fs)
        
        # Extract features
        features = [
            # Orientation (quaternion)
            self.quaternion[0],  # w
            self.quaternion[1],  # x
            self.quaternion[2],  # y
            self.quaternion[3],  # z
            # Linear acceleration magnitude
            np.linalg.norm(accel - self.accel_bias),
            # Angular velocity magnitude
            np.linalg.norm(gyro - self.gyro_bias),
            # Movement jerk (derivative of accel)
        ]
        
        if imu_data.shape[1] > 1:
            jerk = np.diff(imu_data[0:3, -2:], axis=1).squeeze()
            features.append(np.linalg.norm(jerk) * self.fs)
        else:
            features.append(0)
        
        return np.array(features)


class SensorFusionPipeline:
    """
    Main sensor fusion pipeline combining all modalities.
    
    Usage:
        pipeline = SensorFusionPipeline()
        pipeline.start()
        
        # In data acquisition threads:
        pipeline.push_emg(emg_data, timestamp)
        pipeline.push_ultrasound(us_data, timestamp)
        pipeline.push_imu(imu_data, timestamp)
        
        # Get fused features:
        features = pipeline.get_fused_features()
    """
    
    def __init__(self, config: Optional[SensorConfig] = None):
        self.config = config or SensorConfig()
        
        # Circular buffers for each modality
        emg_samples = int(self.config.emg_fs * self.config.emg_buffer_ms / 1000)
        us_samples = int(self.config.usc_fs * self.config.usc_buffer_ms / 1000)
        imu_samples = int(self.config.imu_fs * self.config.imu_buffer_ms / 1000)
        
        print(f"[Fusion] EMG buffer: {emg_samples} samples")
        print(f"[Fusion] US buffer: {us_samples} samples")
        print(f"[Fusion] IMU buffer: {imu_samples} samples")
        
        self.emg_buffer = CircularBuffer(
            self.config.emg_channels, emg_samples
        )
        self.us_buffer = CircularBuffer(
            self.config.usc_channels, us_samples
        )
        self.imu_buffer = CircularBuffer(
            self.config.imu_channels, imu_samples
        )
        
        # Feature processors
        self.emg_processor = EMGProcessor(self.config)
        self.acoustic_processor = AcousticProcessor(self.config)
        self.inertial_processor = InertialProcessor(self.config)
        
        # Synchronization reference
        self.start_time = time.time()
        self.last_sync_time = 0
        
        # Output buffer
        self.feature_history = deque(maxlen=1000)  # ~20 seconds at 50Hz
    
    def push_emg(self, data: np.ndarray, timestamp: Optional[float] = None):
        """Push EMG data to buffer."""
        if timestamp is None:
            timestamp = time.time() - self.start_time
        self.emg_buffer.push(data, timestamp)
    
    def push_ultrasound(self, data: np.ndarray, timestamp: Optional[float] = None):
        """Push ultrasound doppler data to buffer."""
        if timestamp is None:
            timestamp = time.time() - self.start_time
        self.us_buffer.push(data, timestamp)
    
    def push_imu(self, data: np.ndarray, timestamp: Optional[float] = None):
        """Push IMU data to buffer."""
        if timestamp is None:
            timestamp = time.time() - self.start_time
        self.imu_buffer.push(data, timestamp)
    
    def get_fused_features(self, window_ms: Optional[int] = None) -> Dict[str, np.ndarray]:
        """
        Extract and fuse features from all modalities over a time window.
        
        Returns a dictionary with:
            - emg_features: EMG-derived features
            - acoustic_features: Ultrasound-derived features
            - imu_features: IMU-derived features
            - fused_vector: Concatenated feature vector
            - timestamp: Reference timestamp
        """
        if window_ms is None:
            window_ms = self.config.feature_window_ms
        
        # Calculate sample counts
        emg_samples = int(self.config.emg_fs * window_ms / 1000)
        us_samples = int(self.config.usc_fs * window_ms / 1000)
        imu_samples = int(self.config.imu_fs * window_ms / 1000)
        
        # Retrieve data
        emg_data, emg_ts = self.emg_buffer.get_recent(emg_samples)
        us_data, us_ts = self.us_buffer.get_recent(us_samples)
        imu_data, imu_ts = self.imu_buffer.get_recent(imu_samples)
        
        # Check if we have enough data
        if emg_data.size == 0 or us_data.size == 0 or imu_data.size == 0:
            return {
                'emg_features': np.array([]),
                'acoustic_features': np.array([]),
                'imu_features': np.array([]),
                'fused_vector': np.array([]),
                'timestamp': time.time() - self.start_time
            }
        
        # Process each modality
        emg_features = self.emg_processor.process(emg_data)
        acoustic_features = self.acoustic_processor.process(us_data)
        imu_features = self.inertial_processor.process(imu_data)
        
        # Temporal alignment check
        emg_center = np.median(emg_ts) if len(emg_ts) > 0 else 0
        us_center = np.median(us_ts) if len(us_ts) > 0 else 0
        imu_center = np.median(imu_ts) if len(imu_ts) > 0 else 0
        
        alignment_error = max(abs(emg_center - us_center), 
                              abs(emg_center - imu_center))
        
        # Fuse into single vector
        fused = np.concatenate([
            emg_features,
            acoustic_features,
            imu_features,
            np.array([alignment_error])  # Include sync quality
        ])
        
        result = {
            'emg_features': emg_features,
            'acoustic_features': acoustic_features,
            'imu_features': imu_features,
            'fused_vector': fused,
            'timestamp': emg_center,
            'alignment_error': alignment_error
        }
        
        self.feature_history.append(result)
        return result
    
    def get_temporal_window(self, n_windows: int = 10) -> np.ndarray:
        """
        Get a temporal sequence of fused features for transformer input.
        
        Returns: (n_windows, feature_dim) array
        """
        if len(self.feature_history) < n_windows:
            n_windows = len(self.feature_history)
        
        if n_windows == 0:
            return np.array([])
        
        vectors = [h['fused_vector'] for h in list(self.feature_history)[-n_windows:]]
        return np.stack(vectors, axis=0)
    
    def reset(self):
        """Reset all buffers and processors."""
        self.__init__(self.config)
        print("[Fusion] Pipeline reset")


class SimulatedSensorSource:
    """Generate synthetic sensor data for testing."""
    
    def __init__(self, config: SensorConfig):
        self.config = config
        self.t = 0
        self.fs_base = 1000  # Base rate 1kHz
    
    def generate_emg(self, n_samples: int, 
                     motor_intent: Optional[np.ndarray] = None) -> np.ndarray:
        """Generate synthetic EMG with motor unit action potentials."""
        # Baseline noise
        emg = np.random.randn(self.config.emg_channels, n_samples) * 0.01
        
        if motor_intent is not None:
            # Simulate muscle activation based on intent
            for i in range(min(len(motor_intent), self.config.emg_channels)):
                if motor_intent[i] > 0.3:  # Activation threshold
                    # Generate motor unit spikes
                    rate = 20 + motor_intent[i] * 30  # 20-50 Hz
                    spike_times = np.random.poisson(rate * n_samples / self.config.emg_fs, n_samples)
                    
                    for t in np.where(spike_times > 0)[0]:
                        # MUAP shape
                        t_vec = np.arange(20)
                        muap = np.sin(t_vec * 0.5) * np.exp(-t_vec * 0.1) * motor_intent[i]
                        if t + 20 < n_samples:
                            emg[i, t:t+20] += muap
        
        return emg
    
    def generate_ultrasound(self, n_samples: int,
                           neural_activity: Optional[float] = None) -> np.ndarray:
        """Generate synthetic doppler signals from neurovascular coupling."""
        # Baseline flow
        us = np.ones((self.config.usc_channels, n_samples)) * 0.1
        
        if neural_activity is not None:
            # Neurovascular response (delayed ~1-2s, smoothed)
            delay_samples = int(np.random.uniform(1000, 2000))  # 1-2s at 1kHz
            
            # Spatial pattern (center activation)
            grid_size = int(np.sqrt(self.config.usc_channels))
            center = grid_size // 2
            
            for i in range(self.config.usc_channels):
                row, col = i // grid_size, i % grid_size
                dist = np.sqrt((row - center)**2 + (col - center)**2)
                spatial_weight = np.exp(-dist / (grid_size / 2))
                
                # Doppler signal
                us[i] += spatial_weight * neural_activity * 0.5 * (
                    1 + 0.3 * np.sin(2 * np.pi * 1.2 * np.arange(n_samples) / self.config.usc_fs)
                )
        
        us = np.maximum(us, 0)  # Power can't be negative
        return us
    
    def generate_imu(self, n_samples: int, 
                    movement: Optional[np.ndarray] = None) -> np.ndarray:
        """Generate IMU data."""
        # Static pose with noise
        imu = np.random.randn(self.config.imu_channels, n_samples) * 0.01
        
        # Gravity
        imu[0:3, :] = [0, 0, 9.81]  # z-up
        
        if movement is not None:
            # Add acceleration and gyro
            imu[0:3, :] += np.random.randn(3, n_samples) * 0.5
            imu[3:6, :] = np.random.randn(3, n_samples) * 0.1
        
        return imu
    
    def step(self, dt: float = 0.001) -> Dict[str, np.ndarray]:
        """Generate one timestep of data."""
        emg = self.generate_emg(int(self.config.emg_fs * dt))
        us = self.generate_ultrasound(int(self.config.usc_fs * dt))
        imu = self.generate_imu(int(self.config.imu_fs * dt))
        
        self.t += dt
        
        return {
            'emg': emg,
            'ultrasound': us,
            'imu': imu,
            'timestamp': self.t
        }


# Standalone test
if __name__ == "__main__":
    print("=" * 60)
    print("NEURAL-CARTOGRAPHY Sensor Fusion Pipeline Test")
    print("=" * 60)
    
    # Create pipeline
    config = SensorConfig()
    pipeline = SensorFusionPipeline(config)
    
    # Create simulated source
    sim = SimulatedSensorSource(config)
    
    # Simulate data streaming
    print("\n[Demo] Simulating 2 seconds of data...")
    
    for i in range(2000):  # 2 seconds at 1ms steps
        data = sim.step(dt=0.001)
        
        # Push to pipeline
        pipeline.push_emg(data['emg'], data['timestamp'])
        pipeline.push_ultrasound(data['ultrasound'], data['timestamp'])
        pipeline.push_imu(data['imu'], data['timestamp'])
        
        # Extract features every 100ms
        if i % 100 == 0 and i > 0:
            features = pipeline.get_fused_features()
            if len(features['fused_vector']) > 0:
                print(f"  t={data['timestamp']:.3f}s | "
                      f"EMG features: {len(features['emg_features'])} | "
                      f"Acoustic features: {len(features['acoustic_features'])} | "
                      f"IMU features: {len(features['imu_features'])} | "
                      f"Total dim: {len(features['fused_vector'])}")
    
    # Get temporal window for transformer
    temporal = pipeline.get_temporal_window(n_windows=10)
    print(f"\n[Demo] Temporal window shape: {temporal.shape}")
    print(f"       Ready for transformer input: {temporal.shape[0]} x {temporal.shape[1]}")
    
    print("\n" + "=" * 60)
    print("Sensor fusion pipeline test complete")
    print("=" * 60)
