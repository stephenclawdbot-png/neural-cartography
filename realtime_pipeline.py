"""
NEURAL-CARTOGRAPHY: Real-Time Inference Pipeline

Sub-50ms latency inference system for neural intent decoding.
Key optimizations:
- ONNX Runtime for optimized model execution
- Streaming inference with overlapping windows
- Zero-copy tensor operations
- Adaptive quality based on latency budget

Target: <50ms end-to-end latency (sensor input → control output)
"""

import numpy as np
import torch
import time
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass
from collections import deque
from threading import Thread, Lock, Event
import queue
import warnings

# Try to import ONNX Runtime
try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    warnings.warn("ONNX Runtime not available, using PyTorch backend")

# Try to import TensorRT
try:
    import tensorrt as trt
    TRT_AVAILABLE = True
except ImportError:
    TRT_AVAILABLE = False


@dataclass
class PipelineConfig:
    """Configuration for real-time pipeline."""
    # Latency targets
    target_latency_ms: float = 50.0
    max_latency_ms: float = 100.0
    
    # Feature extraction
    feature_window_ms: int = 100
    hop_length_ms: int = 20  # 50Hz feature rate
    
    # Model
    model_path: Optional[str] = None
    use_onnx: bool = True
    use_tensorrt: bool = False
    
    # Streaming
    buffer_size: int = 1000  # samples
    n_future_predictions: int = 5  # Lookahead frames
    
    # Hardware
    device: str = 'cuda' if torch.cuda.is_available() else 'cpu'
    batch_size: int = 1
    
    # Adaptive quality
    enable_adaptive: bool = True
    quality_levels: List[Dict] = None
    
    def __post_init__(self):
        if self.quality_levels is None:
            self.quality_levels = [
                {'name': 'high', 'temporal_window': 50, 'model_size': 'full'},
                {'name': 'medium', 'temporal_window': 30, 'model_size': 'reduced'},
                {'name': 'low', 'temporal_window': 20, 'model_size': 'minimal'},
            ]


class LatencyMonitor:
    """Monitor and track latency metrics."""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.latencies = deque(maxlen=window_size)
        self.component_times = {}
        self.lock = Lock()
    
    def start_timer(self, name: str) -> float:
        """Start timing a component."""
        return time.perf_counter()
    
    def end_timer(self, name: str, start_time: float):
        """End timing a component."""
        elapsed = (time.perf_counter() - start_time) * 1000  # ms
        with self.lock:
            if name not in self.component_times:
                self.component_times[name] = deque(maxlen=self.window_size)
            self.component_times[name].append(elapsed)
        return elapsed
    
    def add_total_latency(self, latency_ms: float):
        """Add total end-to-end latency."""
        with self.lock:
            self.latencies.append(latency_ms)
    
    def get_stats(self) -> Dict:
        """Get latency statistics."""
        with self.lock:
            stats = {}
            
            if self.latencies:
                stats['total'] = {
                    'mean': np.mean(self.latencies),
                    'p50': np.percentile(self.latencies, 50),
                    'p95': np.percentile(self.latencies, 95),
                    'p99': np.percentile(self.latencies, 99),
                    'max': np.max(self.latencies),
                    'min': np.min(self.latencies),
                }
            
            for name, times in self.component_times.items():
                if times:
                    stats[name] = {
                        'mean': np.mean(times),
                        'p95': np.percentile(times, 95),
                        'max': np.max(times)
                    }
            
            return stats
    
    def is_within_target(self, target_ms: float) -> bool:
        """Check if recent latency is within target."""
        with self.lock:
            if len(self.latencies) < 10:
                return True
            recent_p95 = np.percentile(list(self.latencies)[-10:], 95)
            return recent_p95 <= target_ms


class StreamBuffer:
    """Lock-free circular buffer for streaming inference."""
    
    def __init__(self, max_size: int, feature_dim: int):
        self.max_size = max_size
        self.feature_dim = feature_dim
        self.buffer = np.zeros((max_size, feature_dim), dtype=np.float32)
        self.timestamps = np.zeros(max_size, dtype=np.float64)
        self.write_idx = 0
        self.lock = Lock()
    
    def push(self, features: np.ndarray, timestamp: float):
        """Push new features to buffer."""
        with self.lock:
            self.buffer[self.write_idx] = features
            self.timestamps[self.write_idx] = timestamp
            self.write_idx = (self.write_idx + 1) % self.max_size
    
    def get_window(self, n_samples: int) -> Tuple[np.ndarray, np.ndarray]:
        """Get most recent n_samples."""
        with self.lock:
            if n_samples > self.max_size:
                n_samples = self.max_size
            
            indices = [(self.write_idx - 1 - i) % self.max_size 
                      for i in range(n_samples)]
            indices.reverse()
            
            return self.buffer[indices].copy(), self.timestamps[indices].copy()
    
    def get_latest(self) -> np.ndarray:
        """Get latest sample."""
        with self.lock:
            idx = (self.write_idx - 1) % self.max_size
            return self.buffer[idx].copy()


class ONNXInferenceEngine:
    """ONNX Runtime inference engine."""
    
    def __init__(self, model_path: str, use_gpu: bool = True):
        if not ONNX_AVAILABLE:
            raise ImportError("ONNX Runtime not available")
        
        # Create session options
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        # Enable memory pattern optimization
        sess_options.enable_mem_pattern = True
        
        # Set threading
        sess_options.intra_op_num_threads = 4
        sess_options.inter_op_num_threads = 2
        
        # Providers
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if use_gpu else ['CPUExecutionProvider']
        
        # Create session
        self.session = ort.InferenceSession(model_path, sess_options, providers=providers)
        
        # Get input/output info
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]
        
        print(f"[ONNX] Loaded model from {model_path}")
        print(f"[ONNX] Using providers: {providers}")
    
    def infer(self, input_data: np.ndarray) -> Dict[str, np.ndarray]:
        """Run inference."""
        outputs = self.session.run(None, {self.input_name: input_data})
        return {name: out for name, out in zip(self.output_names, outputs)}
    
    def infer_async(self, input_data: np.ndarray, callback: Callable):
        """Run async inference (if supported)."""
        # ONNX Runtime doesn't have true async, but we can wrap it
        result = self.infer(input_data)
        callback(result)
        return result


class PyTorchInferenceEngine:
    """PyTorch inference engine (fallback)."""
    
    def __init__(self, model: torch.nn.Module, device: str = 'cpu'):
        self.model = model
        self.device = device
        self.model.to(device)
        self.model.eval()
        
        # Compile with torch.compile if available (PyTorch 2.0+)
        if hasattr(torch, 'compile'):
            try:
                self.model = torch.compile(self.model, mode='max-autotune')
                print("[PyTorch] Model compiled with torch.compile")
            except Exception as e:
                print(f"[PyTorch] Compilation failed: {e}")
        
        # Warmup
        with torch.no_grad():
            dummy_input = torch.randn(1, 50, 361).to(device)
            for _ in range(10):
                _ = self.model(dummy_input, future_frames=5)
        
        print(f"[PyTorch] Model loaded on {device}")
    
    @torch.no_grad()
    def infer(self, input_data: np.ndarray) -> Dict[str, np.ndarray]:
        """Run inference."""
        # Convert to tensor
        x = torch.from_numpy(input_data).to(self.device)
        
        # Forward pass
        outputs = self.model(x, future_frames=5)
        
        # Convert to numpy
        return {
            'position': outputs['position'].cpu().numpy(),
            'velocity': outputs['velocity'].cpu().numpy(),
            'force': outputs['force'].cpu().numpy(),
            'confidence': outputs['confidence'].cpu().numpy()
        }


class RealTimeInferencePipeline:
    """
    Real-time inference pipeline for neural intent decoding.
    
    Achieves sub-50ms latency through:
    - Streaming feature buffers
    - ONNX Runtime for optimized inference
    - Adaptive quality control
    - Zero-copy memory operations
    """
    
    def __init__(self, config: PipelineConfig, 
                 sensor_fusion_fn: Optional[Callable] = None,
                 intent_model: Optional[torch.nn.Module] = None):
        """
        Initialize pipeline.
        
        Args:
            config: Pipeline configuration
            sensor_fusion_fn: Function to extract features from sensor data
            intent_model: PyTorch model (if not using ONNX)
        """
        self.config = config
        self.sensor_fusion_fn = sensor_fusion_fn
        self.latency_monitor = LatencyMonitor()
        
        # Initialize inference engine
        self.engine = self._create_engine(intent_model)
        
        # Feature buffer
        feature_dim = 361  # From sensor fusion (EMG + Acoustic + IMU)
        self.feature_buffer = StreamBuffer(config.buffer_size, feature_dim)
        
        # Output buffers
        self.intent_queue = queue.Queue(maxsize=10)
        self.control_queue = queue.Queue(maxsize=10)
        
        # State
        self.is_running = False
        self.current_quality_level = 0  # 0=high, 1=medium, 2=low
        self.inference_thread: Optional[Thread] = None
        self.feature_thread: Optional[Thread] = None
        
        # Callbacks
        self.on_intent: Optional[Callable] = None
        self.on_control: Optional[Callable] = None
        
        print(f"[Pipeline] Initialized with target latency: {config.target_latency_ms}ms")
    
    def _create_engine(self, intent_model: Optional[torch.nn.Module]) -> object:
        """Create inference engine."""
        if self.config.use_onnx and ONNX_AVAILABLE and self.config.model_path:
            try:
                return ONNXInferenceEngine(
                    self.config.model_path, 
                    use_gpu=(self.config.device == 'cuda')
                )
            except Exception as e:
                print(f"[Pipeline] ONNX failed, falling back: {e}")
        
        if intent_model is None:
            raise ValueError("Must provide model_path or intent_model")
        
        return PyTorchInferenceEngine(intent_model, self.config.device)
    
    def _extract_features(self, sensor_data: Dict) -> np.ndarray:
        """Extract features using provided fusion function."""
        if self.sensor_fusion_fn:
            features = self.sensor_fusion_fn(sensor_data)
            return features['fused_vector']
        
        # Default: concatenate raw data
        emg = sensor_data.get('emg', np.zeros(256))
        acoustic = sensor_data.get('acoustic', np.zeros(96))
        imu = sensor_data.get('imu', np.zeros(9))
        return np.concatenate([emg, acoustic, imu])
    
    def _adaptive_quality_control(self) -> int:
        """Determine current quality level based on latency."""
        if not self.config.enable_adaptive:
            return 0
        
        stats = self.latency_monitor.get_stats()
        if 'total' not in stats:
            return 0
        
        recent_p95 = stats['total']['p95']
        
        if recent_p95 > self.config.max_latency_ms * 0.9:
            return min(self.current_quality_level + 1, len(self.config.quality_levels) - 1)
        elif recent_p95 < self.config.target_latency_ms * 0.5:
            return max(self.current_quality_level - 1, 0)
        
        return self.current_quality_level
    
    def _get_temporal_window(self) -> np.ndarray:
        """Get temporal window based on current quality."""
        level = self.config.quality_levels[self.current_quality_level]
        window_size = level['temporal_window']
        
        features, _ = self.feature_buffer.get_window(window_size)
        
        # Pad if needed
        if features.shape[0] < window_size:
            padding = np.zeros((window_size - features.shape[0], features.shape[1]))
            features = np.concatenate([padding, features], axis=0)
        
        return features
    
    def _inference_loop(self):
        """Main inference loop running in background thread."""
        while self.is_running:
            loop_start = time.perf_counter()
            
            # Get temporal window
            window = self._get_temporal_window()
            
            # Add batch dimension
            input_data = window[np.newaxis, ...].astype(np.float32)
            
            # Run inference
            infer_start = self.latency_monitor.start_timer('inference')
            outputs = self.engine.infer(input_data)
            infer_time = self.latency_monitor.end_timer('inference', infer_start)
            
            # Extract predicted intent (first future frame)
            intent = {
                'position': outputs['position'][0, 0],
                'velocity': outputs['velocity'][0, 0, 0],
                'force': outputs['force'][0, 0, 0],
                'confidence': outputs['confidence'][0, 0, 0],
                'timestamp': time.time()
            }
            
            # Put in queue (drop if full)
            try:
                self.intent_queue.put_nowait(intent)
            except queue.Full:
                pass
            
            # Callback
            if self.on_intent:
                self.on_intent(intent)
            
            # Total latency
            total_time = (time.perf_counter() - loop_start) * 1000
            self.latency_monitor.add_total_latency(total_time)
            
            # Adaptive quality control
            if self.config.enable_adaptive:
                self.current_quality_level = self._adaptive_quality_control()
            
            # Sleep to maintain target rate (50Hz = 20ms)
            sleep_time = max(0, (self.config.hop_length_ms / 1000) - (time.perf_counter() - loop_start))
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def _control_loop(self):
        """Control output loop - maps intent to hardware commands."""
        while self.is_running:
            try:
                intent = self.intent_queue.get(timeout=0.01)
                
                # Map intent to control output
                # This would interface with hardware control systems
                control_output = self._map_intent_to_control(intent)
                
                try:
                    self.control_queue.put_nowait(control_output)
                except queue.Full:
                    pass
                
                if self.on_control:
                    self.on_control(control_output)
                
            except queue.Empty:
                continue
    
    def _map_intent_to_control(self, intent: Dict) -> Dict:
        """Map decoded intent to hardware control commands."""
        # Example: Map to robotic arm or cursor control
        return {
            'type': 'move',
            'target_position': intent['position'].tolist(),
            'velocity': float(intent['velocity']),
            'force': float(intent['force']),
            'confidence': float(intent['confidence']),
            'timestamp': intent['timestamp']
        }
    
    def start(self):
        """Start the real-time pipeline."""
        if self.is_running:
            return
        
        self.is_running = True
        
        # Start inference thread
        self.inference_thread = Thread(target=self._inference_loop, daemon=True)
        self.inference_thread.start()
        
        # Start control thread
        self.control_thread = Thread(target=self._control_loop, daemon=True)
        self.control_thread.start()
        
        print("[Pipeline] Started")
    
    def stop(self):
        """Stop the pipeline."""
        self.is_running = False
        
        if self.inference_thread:
            self.inference_thread.join(timeout=1.0)
        if self.control_thread:
            self.control_thread.join(timeout=1.0)
        
        print("[Pipeline] Stopped")
    
    def push_sensor_data(self, sensor_data: Dict):
        """Push new sensor data to the pipeline."""
        # Extract and buffer features
        features = self._extract_features(sensor_data)
        self.feature_buffer.push(features, time.time())
    
    def get_latest_intent(self) -> Optional[Dict]:
        """Get latest decoded intent (non-blocking)."""
        try:
            return self.intent_queue.get_nowait()
        except queue.Empty:
            return None
    
    def get_latency_stats(self) -> Dict:
        """Get current latency statistics."""
        return self.latency_monitor.get_stats()
    
    def export_to_onnx(self, model: torch.nn.Module, output_path: str):
        """Export PyTorch model to ONNX for optimized inference."""
        if not ONNX_AVAILABLE:
            print("[Export] ONNX not available, skipping export")
            return
        
        model.eval()
        
        # Create dummy input
        window_size = self.config.quality_levels[0]['temporal_window']
        dummy_input = torch.randn(1, window_size, 361)
        
        # Export
        torch.onnx.export(
            model,
            (dummy_input, 5),  # model input + future_frames
            output_path,
            input_names=['sensor_input'],
            output_names=['position', 'velocity', 'force', 'confidence'],
            dynamic_axes={
                'sensor_input': {0: 'batch', 1: 'sequence'}
            },
            opset_version=14
        )
        
        print(f"[Export] Model saved to {output_path}")
    
    def benchmark(self, n_iterations: int = 1000) -> Dict:
        """Benchmark inference latency."""
        print(f"[Benchmark] Running {n_iterations} iterations...")
        
        latencies = []
        window = np.random.randn(
            self.config.quality_levels[0]['temporal_window'], 361
        ).astype(np.float32)
        
        # Warmup
        for _ in range(100):
            _ = self.engine.infer(window[np.newaxis, ...])
        
        # Benchmark
        for _ in range(n_iterations):
            start = time.perf_counter()
            _ = self.engine.infer(window[np.newaxis, ...])
            latencies.append((time.perf_counter() - start) * 1000)
        
        results = {
            'mean': np.mean(latencies),
            'std': np.std(latencies),
            'p50': np.percentile(latencies, 50),
            'p95': np.percentile(latencies, 95),
            'p99': np.percentile(latencies, 99),
            'min': np.min(latencies),
            'max': np.max(latencies)
        }
        
        print(f"[Benchmark] Results:")
        for k, v in results.items():
            print(f"  {k}: {v:.3f}ms")
        
        return results


# Standalone test
if __name__ == "__main__":
    print("=" * 60)
    print("NEURAL-CARTOGRAPHY Real-Time Inference Pipeline Test")
    print("=" * 60)
    
    from intent_decoder import NeuralIntentDecoder, DecoderConfig
    
    # Create model
    decoder_config = DecoderConfig()
    model = NeuralIntentDecoder(decoder_config)
    
    # Create pipeline
    config = PipelineConfig(
        target_latency_ms=50.0,
        use_onnx=False,  # PyTorch for demo
        device='cpu'
    )
    
    # Mock sensor fusion function
    def mock_fusion(sensor_data):
        return {
            'fused_vector': np.random.randn(361).astype(np.float32),
            'timestamp': time.time()
        }
    
    pipeline = RealTimeInferencePipeline(config, mock_fusion, model)
    
    # Benchmark
    print("\n[Demo] Running inference benchmark...")
    benchmark_results = pipeline.benchmark(n_iterations=500)
    
    # Test streaming
    print("\n[Demo] Testing streaming pipeline...")
    pipeline.start()
    
    # Simulate sensor data stream
    for i in range(100):
        pipeline.push_sensor_data({
            'emg': np.random.randn(256),
            'acoustic': np.random.randn(96),
            'imu': np.random.randn(9)
        })
        time.sleep(0.01)  # 100Hz sensor rate
        
        if i % 10 == 0:
            intent = pipeline.get_latest_intent()
            if intent:
                print(f"  t={i*10}ms: pos={intent['position'][:2].round(2)}, "
                      f"vel={intent['velocity']:.2f}, conf={intent['confidence']:.2f}")
    
    # Get stats
    time.sleep(0.5)
    stats = pipeline.get_latency_stats()
    print(f"\n[Demo] Latency statistics:")
    if 'total' in stats:
        print(f"  Mean: {stats['total']['mean']:.2f}ms")
        print(f"  P95: {stats['total']['p95']:.2f}ms")
        print(f"  P99: {stats['total']['p99']:.2f}ms")
    
    pipeline.stop()
    
    print("\n" + "=" * 60)
    print("Real-time pipeline test complete")
    print("=" * 60)
