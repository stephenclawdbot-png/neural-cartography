"""
NEURAL-CARTOGRAPHY: Intent Decoder

Transformer-based neural architecture for decoding pre-motor intent from
fused sensor data. Maps pre-motor cortex activity to motor intent vectors
(position, velocity, force) before muscle activation.

Architecture:
- Multi-scale temporal encoding
- Cross-modal attention (EMG + Acoustic + IMU)
- Pre-motor temporal lookahead (100-300ms)
- Motor intent prediction head
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import numpy as np
from typing import Dict, List, Tuple, Optional
import math
from dataclasses import dataclass


@dataclass
class DecoderConfig:
    """Configuration for intent decoder."""
    # Input dimensions
    input_dim: int = (64 * 4) + (32 * 3) + 8  # EMG + Acoustic + IMU + sync
    temporal_window: int = 50  # 50 time steps (1s at 50Hz)
    
    # Transformer architecture
    d_model: int = 256
    n_heads: int = 8
    n_encoder_layers: int = 4
    n_decoder_layers: int = 2
    d_ff: int = 1024
    dropout: float = 0.1
    
    # Output dimensions
    intent_dim: int = 6  # [target_x, target_y, target_z, velocity_mag, force, confidence]
    
    # Training
    learning_rate: float = 1e-4
    batch_size: int = 32
    lookahead_ms: int = 150  # Predict 150ms ahead (pre-motor)


class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding for temporal information."""
    
    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        
        # Create positional encoding matrix
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * 
                            (-math.log(10000.0) / d_model))
        
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        
        self.register_buffer('pe', pe.unsqueeze(0))
    
    def forward(self, x):
        """Add positional encoding to input."""
        x = x + self.pe[:, :x.size(1), :]
        return self.dropout(x)


class ModalityEmbedding(nn.Module):
    """
    Embed fused sensor features into model dimension.
    Handles different feature groups (EMG, Acoustic, IMU) with modality tokens.
    """
    
    def __init__(self, input_dim: int, d_model: int):
        super().__init__()
        self.input_dim = input_dim
        self.d_model = d_model
        
        # Project input to model dimension
        self.input_projection = nn.Sequential(
            nn.Linear(input_dim, d_model),
            nn.LayerNorm(d_model),
            nn.GELU(),
            nn.Dropout(0.1)
        )
        
        # Modality type embeddings
        self.modality_embedding = nn.Embedding(4, d_model)  # EMG, Acoustic, IMU, Sync
        
        # Learnable temporal embeddings for different time scales
        self.temporal_scales = nn.ModuleList([
            nn.Linear(d_model, d_model) for _ in range(3)  # 20ms, 100ms, 500ms
        ])
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Input: (batch, seq_len, input_dim)
        Output: (batch, seq_len, d_model)
        """
        # Project to model dimension
        x = self.input_projection(x)
        
        # Add temporal scale information (positional encoding handles absolute time)
        # Here we could add multi-scale convolutions if needed
        
        return x


class CrossModalAttention(nn.Module):
    """
    Cross-modal attention mechanism to fuse information across sensor types.
    EMG provides muscle-level intent, Acoustic provides neural-level intent.
    """
    
    def __init__(self, d_model: int, n_heads: int, dropout: float = 0.1):
        super().__init__()
        self.d_model = d_model
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads
        
        # Separate queries for each modality
        self.q_emg = nn.Linear(d_model, d_model)
        self.q_acoustic = nn.Linear(d_model, d_model)
        self.q_imu = nn.Linear(d_model, d_model)
        
        # Shared keys and values
        self.k_proj = nn.Linear(d_model, d_model)
        self.v_proj = nn.Linear(d_model, d_model)
        
        self.out_proj = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)
        self.scale = self.head_dim ** -0.5
    
    def forward(self, emg_repr: torch.Tensor, acoustic_repr: torch.Tensor,
                imu_repr: torch.Tensor) -> torch.Tensor:
        """
        Fuse cross-modal representations.
        
        Args:
            emg_repr: (batch, seq, d_model) - EMG features
            acoustic_repr: (batch, seq, d_model) - Ultrasound features
            imu_repr: (batch, seq, d_model) - IMU features
        """
        batch_size, seq_len, _ = emg_repr.shape
        
        # Compute queries per modality
        Q_emg = self.q_emg(emg_repr).view(batch_size, seq_len, self.n_heads, self.head_dim).transpose(1, 2)
        Q_acoustic = self.q_acoustic(acoustic_repr).view(batch_size, seq_len, self.n_heads, self.head_dim).transpose(1, 2)
        Q_imu = self.q_imu(imu_repr).view(batch_size, seq_len, self.n_heads, self.head_dim).transpose(1, 2)
        
        # Concatenate keys/values from all modalities
        combined = torch.stack([emg_repr, acoustic_repr, imu_repr], dim=2)  # (batch, seq, 3, d_model)
        combined = combined.view(batch_size, seq_len * 3, self.d_model)
        
        K = self.k_proj(combined).view(batch_size, seq_len * 3, self.n_heads, self.head_dim).transpose(1, 2)
        V = self.v_proj(combined).view(batch_size, seq_len * 3, self.n_heads, self.head_dim).transpose(1, 2)
        
        # Multi-head attention for each modality query
        def attend(Q):
            scores = torch.matmul(Q, K.transpose(-2, -1)) * self.scale
            attn = F.softmax(scores, dim=-1)
            attn = self.dropout(attn)
            return torch.matmul(attn, V)
        
        # Attend from each modality perspective
        O_emg = attend(Q_emg)
        O_acoustic = attend(Q_acoustic)
        O_imu = attend(Q_imu)
        
        # Combine outputs
        O_combined = (O_emg + O_acoustic + O_imu) / 3
        O_combined = O_combined.transpose(1, 2).contiguous().view(batch_size, seq_len, self.d_model)
        
        return self.out_proj(O_combined)


class PreMotorDecoderBlock(nn.Module):
    """
    Transformer decoder block with pre-motor temporal lookahead.
    Predicts future motor state based on current neural activity.
    """
    
    def __init__(self, d_model: int, n_heads: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        
        # Self-attention (causal for autoregressive prediction)
        self.self_attn = nn.MultiheadAttention(d_model, n_heads, dropout=dropout, batch_first=True)
        
        # Cross-attention to encoder
        self.cross_attn = nn.MultiheadAttention(d_model, n_heads, dropout=dropout, batch_first=True)
        
        # Feed-forward
        self.ffn = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_ff, d_model),
            nn.Dropout(dropout)
        )
        
        # Layer norms
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.norm3 = nn.LayerNorm(d_model)
        
        # Causal mask
        self.register_buffer('causal_mask', None)
    
    def get_causal_mask(self, size: int, device: torch.device):
        """Create causal mask for autoregressive prediction."""
        if self.causal_mask is None or self.causal_mask.size(0) < size:
            mask = torch.triu(torch.ones(size, size, device=device), diagonal=1)
            mask = mask.masked_fill(mask == 1, float('-inf'))
            self.register_buffer('causal_mask', mask)
        return self.causal_mask[:size, :size]
    
    def forward(self, tgt: torch.Tensor, memory: torch.Tensor) -> torch.Tensor:
        """
        tgt: (batch, seq, d_model) - target sequence (motor intent)
        memory: (batch, seq, d_model) - encoder output (neural activity)
        """
        # Self-attention with causal mask
        tgt2 = self.self_attn(
            tgt, tgt, tgt,
            attn_mask=self.get_causal_mask(tgt.size(1), tgt.device),
            need_weights=False
        )[0]
        tgt = self.norm1(tgt + tgt2)
        
        # Cross-attention to encoder
        tgt2 = self.cross_attn(tgt, memory, memory, need_weights=False)[0]
        tgt = self.norm2(tgt + tgt2)
        
        # Feed-forward
        tgt2 = self.ffn(tgt)
        tgt = self.norm3(tgt + tgt2)
        
        return tgt


class IntentPredictionHead(nn.Module):
    """
    Prediction head for motor intent: target position, velocity, force.
    """
    
    def __init__(self, d_model: int, intent_dim: int, dropout: float = 0.1):
        super().__init__()
        
        self.mlp = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.LayerNorm(d_model // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 2, d_model // 4),
            nn.LayerNorm(d_model // 4),
            nn.GELU(),
            nn.Dropout(dropout)
        )
        
        # Separate heads for different intent components
        self.position_head = nn.Linear(d_model // 4, 3)  # target_x, target_y, target_z
        self.velocity_head = nn.Linear(d_model // 4, 1)  # velocity magnitude
        self.force_head = nn.Linear(d_model // 4, 1)     # force (grip pressure)
        self.confidence_head = nn.Linear(d_model // 4, 1)  # prediction confidence
    
    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Input: (batch, seq, d_model) - final decoder output
        Output: Dict with intent predictions
        """
        features = self.mlp(x)
        
        return {
            'position': self.position_head(features),       # (batch, seq, 3)
            'velocity': F.relu(self.velocity_head(features)),  # (batch, seq, 1), always positive
            'force': F.relu(self.force_head(features)),     # (batch, seq, 1)
            'confidence': torch.sigmoid(self.confidence_head(features))  # (batch, seq, 1)
        }


class NeuralIntentDecoder(nn.Module):
    """
    Complete transformer-based intent decoder.
    
    Architecture:
    1. Input embedding with modality encoding
    2. Spatial attention per modality
    3. Cross-modal fusion
    4. Temporal transformer encoder
    5. Pre-motor decoder with lookahead
    6. Intent prediction heads
    """
    
    def __init__(self, config: DecoderConfig):
        super().__init__()
        self.config = config
        
        # Input embedding
        self.embedding = ModalityEmbedding(config.input_dim, config.d_model)
        self.pos_encoding = PositionalEncoding(config.d_model, dropout=config.dropout)
        
        # Modality-specific processing
        self.emg_encoder = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model=config.d_model, nhead=config.n_heads,
                dim_feedforward=config.d_ff, dropout=config.dropout,
                batch_first=True
            ),
            num_layers=2
        )
        
        self.acoustic_encoder = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model=config.d_model, nhead=config.n_heads,
                dim_feedforward=config.d_ff, dropout=config.dropout,
                batch_first=True
            ),
            num_layers=2
        )
        
        self.imu_encoder = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model=config.d_model, nhead=config.n_heads,
                dim_feedforward=config.d_ff, dropout=config.dropout,
                batch_first=True
            ),
            num_layers=1
        )
        
        # Cross-modal attention
        self.cross_modal_fusion = CrossModalAttention(
            config.d_model, config.n_heads, config.dropout
        )
        
        # Temporal transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.d_model, nhead=config.n_heads,
            dim_feedforward=config.d_ff, dropout=config.dropout,
            batch_first=True
        )
        self.temporal_encoder = nn.TransformerEncoder(
            encoder_layer, num_layers=config.n_encoder_layers
        )
        
        # Pre-motor decoder
        self.decoder_layers = nn.ModuleList([
            PreMotorDecoderBlock(config.d_model, config.n_heads, config.d_ff, config.dropout)
            for _ in range(config.n_decoder_layers)
        ])
        
        # Intent prediction
        self.prediction_head = IntentPredictionHead(
            config.d_model, config.intent_dim, config.dropout
        )
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        """Initialize weights with Xavier/He initialization."""
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)
    
    def extract_modalities(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Extract modality-specific features from concatenated input.
        
        Input structure (from sensor_fusion.py):
        - EMG: 64 channels * 4 features = 256
        - Acoustic: 32 channels * 3 features = 96
        - IMU: 8 features
        - Sync: 1 feature
        Total: 361 (config.input_dim)
        """
        # Split by known dimensions
        emg_end = 64 * 4
        acoustic_end = emg_end + 32 * 3
        
        emg = x[..., :emg_end]
        acoustic = x[..., emg_end:acoustic_end]
        imu = x[..., acoustic_end:acoustic_end + 8]
        
        # Project each to d_model (already done in embedding, but we want separate paths)
        # For now, assume input is already pre-processed per-modality
        return emg, acoustic, imu
    
    def forward(self, sensor_input: torch.Tensor,
                future_frames: int = 5) -> Dict[str, torch.Tensor]:
        """
        Forward pass through intent decoder.
        
        Args:
            sensor_input: (batch, seq_len, input_dim) - fused sensor features
            future_frames: number of future timesteps to predict
        
        Returns:
            Dictionary with intent predictions for T+1 to T+future_frames
        """
        batch_size, seq_len, _ = sensor_input.shape
        
        # Embed input
        x = self.embedding(sensor_input)
        x = self.pos_encoding(x)
        
        # Separate modality processing
        emg_part = x.clone()
        acoustic_part = x.clone()
        imu_part = x.clone()
        
        # Modality-specific temporal encoding
        emg_encoded = self.emg_encoder(emg_part)
        acoustic_encoded = self.acoustic_encoder(acoustic_part)
        imu_encoded = self.imu_encoder(imu_part)
        
        # Cross-modal fusion
        fused = self.cross_modal_fusion(emg_encoded, acoustic_encoded, imu_encoded)
        
        # Temporal encoding
        memory = self.temporal_encoder(fused)
        
        # Pre-motor decoder with lookahead
        # Initialize decoder input with last encoded state
        decoder_input = memory[:, -1:, :].repeat(1, future_frames, 1)
        decoder_input = self.pos_encoding(decoder_input)
        
        # Add learnable lookahead embeddings
        lookahead_embed = nn.Parameter(torch.randn(1, future_frames, self.config.d_model))
        decoder_input = decoder_input + lookahead_embed
        
        # Decode through layers
        for layer in self.decoder_layers:
            decoder_input = layer(decoder_input, memory)
        
        # Predict intent
        intent = self.prediction_head(decoder_input)
        
        return intent


class IntentLoss(nn.Module):
    """Combined loss for intent prediction."""
    
    def __init__(self, position_weight: float = 1.0,
                 velocity_weight: float = 1.0,
                 force_weight: float = 0.5,
                 confidence_weight: float = 0.1):
        super().__init__()
        self.position_weight = position_weight
        self.velocity_weight = velocity_weight
        self.force_weight = force_weight
        self.confidence_weight = confidence_weight
    
    def forward(self, pred: Dict[str, torch.Tensor],
                target: Dict[str, torch.Tensor]) -> torch.Tensor:
        """Compute weighted loss."""
        
        # Position loss (MSE)
        pos_loss = F.mse_loss(pred['position'], target['position'])
        
        # Velocity loss (smooth L1)
        vel_loss = F.smooth_l1_loss(pred['velocity'], target['velocity'])
        
        # Force loss
        force_loss = F.mse_loss(pred['force'], target['force'])
        
        # Confidence (BCE with logits, target is 1 if prediction is good)
        with torch.no_grad():
            pos_error = torch.norm(pred['position'] - target['position'], dim=-1, keepdim=True)
            vel_error = torch.abs(pred['velocity'] - target['velocity'])
            target_conf = torch.exp(-(pos_error + vel_error))
        
        conf_loss = F.binary_cross_entropy(pred['confidence'], target_conf)
        
        total = (self.position_weight * pos_loss +
                self.velocity_weight * vel_loss +
                self.force_weight * force_loss +
                self.confidence_weight * conf_loss)
        
        return total


class SyntheticIntentDataset(Dataset):
    """Generate synthetic training data for intent prediction."""
    
    def __init__(self, config: DecoderConfig, n_samples: int = 10000):
        self.config = config
        self.n_samples = n_samples
        
    def __len__(self):
        return self.n_samples
    
    def __getitem__(self, idx):
        """Generate one training sample."""
        seq_len = self.config.temporal_window
        
        # Simulate sensor data with motor intent
        # Generate a reach movement: start position -> target position
        
        # Random reach parameters
        start_pos = np.random.randn(3) * 10  # cm
        target_pos = start_pos + np.random.randn(3) * 20  # 20cm reach
        duration = 0.5 + np.random.rand() * 0.5  # 0.5-1s movement
        max_vel = 30 + np.random.rand() * 50  # cm/s
        peak_force = 5 + np.random.rand() * 15  # N
        
        # Generate ground truth trajectory
        t = np.linspace(0, duration, seq_len)
        
        # Minimum jerk trajectory
        tau = t / duration
        pos = start_pos[:, None] + (target_pos[:, None] - start_pos[:, None]) * (
            10 * tau**3 - 15 * tau**4 + 6 * tau**5
        )
        
        vel = np.gradient(pos, t, axis=1)
        vel_mag = np.linalg.norm(vel, axis=0, keepdims=True).T
        
        force = np.sin(np.pi * tau) * peak_force  # Bell-shaped force profile
        
        # Simulate sensor inputs based on trajectory
        # EMG: proportional to velocity and force
        emg = np.random.randn(64 * 4, seq_len) * 0.1
        for i in range(seq_len):
            emg[:64, i] += vel_mag[i, 0] * 0.01 + force[i] * 0.01
        
        # Acoustic: proportional to upcoming movement (neural activation)
        acoustic = np.random.randn(32 * 3, seq_len) * 0.1
        future_activation = np.zeros(seq_len)
        for i in range(seq_len - 5):
            future_activation[i] = vel_mag[i + 5, 0]  # Look ahead
        for i in range(seq_len):
            acoustic[:32, i] += future_activation[i] * 0.01
        
        # IMU: actual position and orientation
        imu = np.random.randn(8, seq_len) * 0.1
        imu[:3, :] = pos / 100  # Normalize position
        
        # Combine features
        sensor_input = np.concatenate([emg, acoustic, imu], axis=0).T  # (seq_len, features)
        
        # Target: next N future states
        future_target = {
            'position': torch.tensor(pos[:, -5:].T, dtype=torch.float32),      # (5, 3)
            'velocity': torch.tensor(vel_mag[-5:], dtype=torch.float32),        # (5, 1)
            'force': torch.tensor(force[-5:, None], dtype=torch.float32),       # (5, 1)
        }
        
        return torch.tensor(sensor_input, dtype=torch.float32), future_target


def train_decoder(config: DecoderConfig = None, epochs: int = 10):
    """Train the intent decoder on synthetic data."""
    if config is None:
        config = DecoderConfig()
    
    print("=" * 60)
    print("NEURAL-CARTOGRAPHY Intent Decoder Training")
    print("=" * 60)
    
    # Create model
    model = NeuralIntentDecoder(config)
    print(f"\nModel parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Create dataset
    train_dataset = SyntheticIntentDataset(config, n_samples=5000)
    train_loader = DataLoader(train_dataset, batch_size=config.batch_size, shuffle=True)
    
    # Optimizer and loss
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate)
    criterion = IntentLoss()
    
    # Training loop
    model.train()
    for epoch in range(epochs):
        total_loss = 0
        n_batches = 0
        
        for batch_idx, (inputs, targets) in enumerate(train_loader):
            optimizer.zero_grad()
            
            # Forward pass
            outputs = model(inputs, future_frames=5)
            
            # Compute loss
            loss = criterion(outputs, targets)
            
            # Backward pass
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            
            total_loss += loss.item()
            n_batches += 1
            
            if batch_idx % 50 == 0:
                print(f"  Epoch {epoch+1}/{epochs}, Batch {batch_idx}, Loss: {loss.item():.4f}")
        
        avg_loss = total_loss / n_batches
        print(f"Epoch {epoch+1} complete - Average loss: {avg_loss:.4f}")
    
    print("\nTraining complete!")
    return model


# Standalone test
if __name__ == "__main__":
    print("=" * 60)
    print("NEURAL-CARTOGRAPHY Intent Decoder Test")
    print("=" * 60)
    
    config = DecoderConfig()
    
    # Create model
    model = NeuralIntentDecoder(config)
    print(f"\nModel created with {sum(p.numel() for p in model.parameters()):,} parameters")
    
    # Test forward pass
    print("\n[Demo] Testing forward pass with synthetic data...")
    batch_size = 2
    seq_len = config.temporal_window
    
    # Random input
    test_input = torch.randn(batch_size, seq_len, config.input_dim)
    
    with torch.no_grad():
        output = model(test_input, future_frames=5)
    
    print(f"  Input shape: {test_input.shape}")
    print(f"  Output shapes:")
    print(f"    Position: {output['position'].shape}")
    print(f"    Velocity: {output['velocity'].shape}")
    print(f"    Force: {output['force'].shape}")
    print(f"    Confidence: {output['confidence'].shape}")
    
    # Sample prediction
    print(f"\n[Demo] Sample prediction (first batch, first future frame):")
    print(f"  Target position: {output['position'][0, 0].numpy()}")
    print(f"  Velocity: {output['velocity'][0, 0].item():.3f}")
    print(f"  Force: {output['force'][0, 0].item():.3f}")
    print(f"  Confidence: {output['confidence'][0, 0].item():.3f}")
    
    print("\n" + "=" * 60)
    print("Intent decoder test complete")
    print("=" * 60)
