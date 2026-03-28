# NEURAL-CARTOGRAPHY 🧠

> **Real-time Brain-to-Hardware Mapping Through Non-Invasive Neural Cartography**

## Vision

Current brain-computer interfaces force a choice: invasive implants that read neurons directly, or surface-level EMG that only captures muscle signals. We're building the third path—**true pre-motor neural decoding** without surgery, without headsets, without contact.

NEURAL-CARTOGRAPHY combines:
- **SILENT-style high-density surface EMG** (muscle-level signals)
- **Acoustic neural imaging** (ultrasound micro-doppler of blood flow changes)
- **Transformer-based intent prediction** (decode motor intent *before* muscle activation)
- **Sub-50ms inference** (real-time hardware control)

We bridge the gap between muscle-level EMG and neural-level BCI—all without breaking the skin.

---

## The Problem

| Approach | Invasiveness | Signal Quality | Latency | Status |
|----------|-------------|--------------|---------|--------|
| Invasive BCI (Neuralink) | Surgical implant | Direct neuron recordings | ~10ms | Experimental, risky |
| Non-invasive EEG | None | Poor spatial resolution | ~100ms | Limited utility |
| SILENT EMG | None | Muscle signals only | ~20ms | Proven, but not neural |
| **NEURAL-CARTOGRAPHY** | **None** | **Pre-motor neural intent** | **<50ms** | **This project** |

The key insight: **motor intent manifests in the pre-motor cortex and propagates through the corticospinal tract milliseconds BEFORE muscle activation.** By fusing multiple non-contact sensing modalities, we can capture and decode this pre-motor signal.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SENSOR ARRAY (Non-Contact)                    │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  EMG Array      │ Acoustic Array  │   Inertial (IMU)            │
│  64+ channels   │ 32+ ultrasound  │   9-DOF reference           │
│  2kHz sample    │ micro-doppler   │   motion compensation       │
│                 │ 10MHz, 1kHz     │                             │
└────────┬────────┴────────┬────────┴────────────┬────────────────┘
         │                 │                      │
         ▼                 ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SENSOR FUSION PIPELINE                        │
│  • Temporal alignment (±50µs)                                   │
│  • Cross-modal calibration                                      │
│  • Feature extraction per modality                              │
│  • Multi-scale temporal windows                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 TRANSFORMER INTENT DECODER                       │
│  • Pre-motor cortex signal mapping                               │
│  • Multi-head attention across modalities                        │
│  • Temporal attention (100-300ms lookback)                       │
│  • Output: Motor intent vectors (position, velocity, force)     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              REAL-TIME INFERENCE PIPELINE (<50ms)                │
│  • Optimized model (ONNX/TensorRT)                               │
│  • Streaming inference with sliding window                       │
│  • Hardware abstraction layer (HID, serial, BLE)                │
│  • Latency monitoring & adaptive quality                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     CONTROLLED HARDWARE                          │
│           (Robotic arm, exoskeleton, computer cursor)           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Innovations

### 1. Acoustic Neural Imaging
Ultrasound micro-doppler detects blood flow changes in the cortical vasculature induced by neural activity (neurovascular coupling). This gives us a "window" into brain activity without electrodes.

### 2. Pre-Motor Decoding
Traditional BCIs decode motor cortex activity concurrent with movement. We target the **pre-motor and supplementary motor areas**, where intent forms 100-300ms before execution. This enables predictive control.

### 3. Multi-Modal Fusion
EMG captures the periphery (muscle signals), ultrasound captures central activation (blood flow), and IMU provides context ( limb position). The transformer learns cross-modal correlations invisible to any single sensor.

### 4. Contactless Operation
All sensors work without skin contact—EMG through thin clothing, ultrasound through air gap (or gels), enabling practical daily use.

---

## Project Structure

```
NEURAL-CARTOGRAPHY/
├── README.md                   # This file
├── hardware_spec.md            # Sensor array specifications
├── sensor_fusion.py            # Multi-modal signal fusion
├── intent_decoder.py           # Transformer model + training
├── realtime_pipeline.py        # Sub-50ms inference system
├── prototype_v0.py             # Proof of concept (simulated data)
├── requirements.txt            # Dependencies
└── models/                     # Trained model artifacts
```

---

## Roadmap

### Phase 0: Simulation (Current)
- [x] Architecture design
- [x] Simulated data pipeline
- [x] Transformer model definition
- [x] Real-time inference framework

### Phase 1: Sensor Validation (Q2 2026)
- [ ] EMG array prototype (16 channels)
- [ ] Ultrasound doppler validation
- [ ] Cross-modal synchronization testing
- [ ] Noise characterization

### Phase 2: Model Training (Q3 2026)
- [ ] Human subject data collection (10 subjects)
- [ ] Motor task paradigms (reach, grasp, pinch)
- [ ] Transformer training and optimization
- [ ] Latency benchmarking

### Phase 3: Hardware Integration (Q4 2026)
- [ ] Custom PCB for sensor array
- [ ] Embedded inference (NVIDIA Jetson/Intel NUC)
- [ ] Robotic arm control demos
- [ ] Clinical validation protocol

### Phase 4: Productization (2027)
- [ ] Miniaturized sensor headband
- [ ] Consumer SDK and APIs
- [ ] FDA/CE regulatory pathway
- [ ] Partnerships with assistive device manufacturers

---

## The Science

### Neurovascular Coupling
Neural activity increases local metabolic demand, triggering blood flow changes within 1-2 seconds. While slower than electrical signals, the **spatial resolution** of ultrasound (sub-millimeter) exceeds EEG, and the signal contains rich information about cortical activation patterns.

### Corticospinal Tract Propagation
Motor commands propagate from cortex → brainstem → spinal cord → peripheral nerves → muscles. Total latency: ~50-100ms. By monitoring the cortical origin, we can predict the peripheral outcome before it executes.

### Cross-Modal Learning
The transformer learns that:
- Pre-motor ultrasound doppler shift correlates with EMG envelope 100ms later
- Muscle co-activation patterns predict intended movement direction
- Inertial motion of the limb provides feedback for model refinement

---

## Why This Matters

**For paralysis patients:** Control wheelchairs, robotic arms, or computers without implants.

**For amputees:** Intuitive prosthetic control with neural-level precision.

**For everyone:** A new interface modality—thought as input.

---

## Team & Credits

This is an open research project. We welcome collaborations in:
- Neuroscience: Motor control, neurovascular coupling
- Engineering: Ultrasound hardware, signal processing
- ML: Transformers for time series, real-time inference
- Clinical: User studies with patient populations

---

## License

Research Use License - See LICENSE for details.

---

> *"The brain is not a vessel to be filled but a fire to be kindled."* — We're learning to read the flame.
