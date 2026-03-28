# NEURAL-CARTOGRAPHY Hardware Specification

## Overview

The sensor array combines three non-contact sensing modalities to capture pre-motor neural intent:
1. **High-density surface EMG** (muscle-level electrical activity)
2. **Ultrasound micro-doppler array** (neurovascular coupling detection)
3. **Inertial Measurement Unit (IMU)** (context/feedback)

---

## 1. EMG Sensor Array

### Specifications

| Parameter | Value | Notes |
|-----------|-------|-------|
| Channels | 64 (expandable to 256) | 8x8 grid per limb |
| Electrode spacing | 10mm | Matches muscle fiber density |
| Sampling rate | 2,000 Hz | Nyquist for EMG signals |
| Resolution | 24-bit ADC | Precision for weak signals |
| Input impedance | >10 GΩ | Minimal loading |
| CMRR | >100 dB | Reject common-mode noise |
| Contact type | Dry capacitive | No gel required |

### Array Configuration

```
Limb Coverage (8x8 grid per major muscle group):

Forearm Array (64 channels):
┌──┬──┬──┬──┬──┬──┬──┬──┐
│ 1│ 2│ 3│ 4│ 5│ 6│ 7│ 8│  ← Flexor digitorum superficialis
├──┼──┼──┼──┼──┼──┼──┼──┤
│ 9│10│11│12│13│14│15│16│
├──┼──┼──┼──┼──┼──┼──┼──┤
│17│18│19│20│21│22│23│24│  ← Flexor digitorum profundus
├──┼──┼──┼──┼──┼──┼──┼──┤
│25│26│27│28│29│30│31│32│
├──┼──┼──┼──┼──┼──┼──┼──┤
│33│34│35│36│37│38│39│40│  ← Extensor digitorum
├──┼──┼──┼──┼──┼──┼──┼──┤
│41│42│43│44│45│46│47│48│
├──┼──┼──┼──┼──┼──┼──┼──┤
│49│50│51│52│53│54│55│56│  ← Brachioradialis/Pronator
├──┼──┼──┼──┼──┼──┼──┼──┤
│57│58│59│60│61│62│63│64│
└──┴──┴──┴──┴──┴──┴──┴──┘

Dimensions: 80mm x 80mm x 3mm (flexible PCB)
```

### Component Selection

| Component | Part Number | Specs |
|-----------|-------------|-------|
| ADC | Texas Instruments ADS131M04 | 4-ch, 24-bit, 32kSPS |
| Instrumentation Amp | TI INA333 | Zero-drift, rail-to-rail |
| Multiplexer | Analog ADG1206 | 16:1, low charge injection |
| MCU | STM32H743 | 480MHz, FPU, DSP |

---

## 2. Acoustic Neural Imaging Array

### Principle

Ultrasound micro-doppler detects blood velocity changes in cortical vessels. Neural activation increases local metabolism → vasodilation → blood flow changes. This neurovascular coupling provides a delayed but high-resolution view of cortical activity.

### Transducer Specifications

| Parameter | Value | Notes |
|-----------|-------|-------|
| Frequency | 10 MHz | Penetration ~2cm, resolution ~0.15mm |
| Elements | 32 (phased array) | Electronic beam steering |
| Aperture | 25.6mm x 25.6mm | 8x8 element grid |
| Element pitch | 0.8mm | 0.64λ at 10MHz in soft tissue |
| Bandwidth | >60% | Pulse-echo quality |
| Sensitivity | >-60dB | Detect micro-flows |

### Array Configuration

```
Phased Array (8x8 elements):

Target: Pre-motor cortex (superior frontal gyrus)
Placement: Forehead band, 2-3cm above brow ridge

Array Layout:
┌──┬──┬──┬──┬──┬──┬──┬──┐
│T1│T2│T3│T4│T5│T6│T7│T8│  ← Row 1: Most superior
├──┼──┼──┼──┼──┼──┼──┼──┤
│  │  │  │  │  │  │  │  │
├──┼──┼──┼──┼──┼──┼──┼──┤
│  │  │  │  │  │  │  │  │     Coverage: ~50mm x 50mm
├──┼──┼──┼──┼──┼──┼──┼──┤     Penetration: 15-25mm (cortex)
│  │  │  │  │  │  │  │  │
├──┼──┼──┼──┼──┼──┼──┼──┤
│  │  │  │  │  │  │  │  │
├──┼──┼──┼──┼──┼──┼──┼──┤
│  │  │  │  │  │  │  │  │
├──┼──┼──┼──┼──┼──┼──┼──┤
│T57│  │  │  │  │  │  │T64│
└──┴──┴──┴──┴──┴──┴──┴──┘
      ↑ Beam steering enables
        virtual scanning
```

### Doppler Processing

```
Raw RF → Demodulation → Wall Filter → Doppler FFT → Power Doppler
(sample)  (I/Q sep.)    (clutter)    (velocity)   (perfusion)
 40MHz     10MHz         100Hz        128-pt       1000 Hz
                              cutoff       FFT          update
```

| Parameter | Value |
|-----------|-------|
| PRF (Pulse Repetition Frequency) | 5-10 kHz |
| Velocity range | ±50 cm/s |
| Velocity resolution | 0.8 mm/s |
| Update rate | 1,000 Hz (Power Doppler envelope) |
| Dynamic range | >40 dB |

### Component Selection

| Component | Part Number | Specs |
|-----------|-------------|-------|
| Transducer | Custom/Vermon | 10MHz, 32-element |
| Pulser-Receiver | Olympus 5073PR or custom | 200V, 10dB NF |
| ADC | AD9680 | Dual 14-bit, 1GSPS |
| FPGA | Xilinx Zynq-7000 | Beamforming, Doppler processing |

---

## 3. Inertial Measurement Unit (IMU)

### Specifications

| Parameter | Value | Purpose |
|-----------|-------|---------|
| Accelerometer range | ±16g | Motion tracking |
| Gyroscope range | ±2000°/s | Rotation tracking |
| Magnetometer | ±4800µT | Orientation reference |
| Sampling rate | 1,000 Hz | Sync with EMG |
| Resolution | 16-bit | Sufficient precision |
| Placement | Wrist/forearm | Limb segment tracking |

### Component Selection

| Component | Part Number | Interface |
|-----------|-------------|-----------|
| IMU | Bosch BMI088 + BMM150 | SPI, 1kHz |
| MCU | Same as EMG (shared) | - |

---

## 4. Synchronization Architecture

### Time Synchronization

All modalities synchronized to a common 1MHz clock:

```
                    ┌─────────────┐
       ┌───────────►│   GPS-DO    │◄──────────┐
       │            │  (10MHz)    │           │
       │            └──────┬──────┘           │
       │                   │                 │
       │    ┌──────────────┼──────────────┐  │
       │    │              │              │  │
       ▼    ▼              ▼              ▼  │
   ┌────────┐        ┌────────┐      ┌──────┴─┐
   │ EMG    │        │Ultrasound│     │  IMU   │
   │ 2kHz   │        │ 40MHz   │     │ 1kHz   │
   └────┬───┘        └────┬───┘      └───┬────┘
        │                 │              │
        │         ┌────────┘              │
        │         │    Timestamp Sync     │
        └─────────┼───────────────────────┘
                  │
                  ▼
           ┌─────────────┐
           │  Fusion Hub │ (Raspberry Pi 5 / Jetson)
           │  PTP/gPTP   │
           └─────────────┘
```

| Sync Target | Accuracy | Method |
|-------------|----------|--------|
| EMG-Ultrasound | ±50µs | Hardware trigger |
| EMG-IMU | ±100µs | SPI timestamp |
| All to system | ±1ms | PTP over Ethernet |

---

## 5. Physical Integration

### Wearable Form Factor

```
Headband Configuration:

    ┌────────────────────────────┐
    │ ◯ ◯ ◯ ◯ ◯ ◯ ◯ ◯ ◯ ◯ ◯ ◯  │  ← Ultrasound array
    │   (pre-motor cortex)       │     (forehead)
    └────────────────────────────┘
              │     │
         ┌────┘     └────┐
         │   ┌─────┐      │
         └──►│ Hub │◄─────┘  ← Processing unit
             │     │          (Raspberry Pi / Jetson)
             └──┬──┘
                │ USB-C / Wireless
                ▼
           ┌─────────┐
           │  Host   │ (Laptop / Embedded)
           └─────────┘

Armband Configuration:

    ┌─────────────────────────────┐
    │ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │  ← EMG array
    │  (forearm muscle groups)    │    (64 ch grid)
    └─────────────────────────────┘
         │                   │
    ┌────┘                   └────┐
    │   ┌───┐    ┌───┐    ┌───┐  │
    └──►│Hub│◄──►│IMU│    │Batt│  │
        └───┘    └───┘    └───┘  │
             └────────┘
                  │
                  ▼ Wrist-worn
           [ Smartwatch form ]
```

### Power Budget

| Component | Peak Current | Typical | Sleep |
|-----------|--------------|---------|-------|
| EMG Array (64ch) | 150mA | 80mA | 5mA |
| Ultrasound TX/RX | 500mA | 300mA | 10mA |
| FPGA Processing | 1,000mA | 600mA | 50mA |
| IMU | 10mA | 5mA | 10µA |
| Hub (RPi5) | 1,500mA | 800mA | - |
| **Total** | **~3.2A** | **~1.8A** | **~65mA** |

**Battery: 5,000mAh LiPo = ~2.5 hours continuous operation**

---

## 6. Signal Specifications Summary

| Stream | Sample Rate | Resolution | Bandwidth | Latency |
|--------|-------------|------------|-----------|---------|
| EMG | 2,000 Hz | 24-bit | 500Hz | 0.5ms |
| Ultrasound RF | 40 MHz | 14-bit | 20MHz | 0.025ms |
| Doppler Envelope | 1,000 Hz | 32-bit float | 500Hz | 1ms |
| IMU | 1,000 Hz | 16-bit | 500Hz | 1ms |
| Fused Output | 1,000 Hz | 32-bit float | - | <50ms |

---

## 7. Manufacturing Notes

### EMG Electrodes
- **Material**: Ag/AgCl sintered, dry contact
- **Substrate**: Flexible polyimide (Kapton)
- **Connector**: FPC/FFC 0.5mm pitch
- **ESD**: All channels protected with TVS diodes

### Ultrasound Transducer
- **Housing**: 3D printed SLA (resin)
- **Matching layers**: Parylene C + epoxy
- **Backing**: Epoxy-loaded tungsten
- **Cable**: Shielded coaxial bundle, impedance-matched

### Assembly
- **Cleanroom**: Not required (medical device class I)
- **Testing**: Every channel individually calibrated
- **Burn-in**: 24-hour continuous operation before shipment

---

## 8. Safety Considerations

### Ultrasound Exposure
- **I_SPTA** (Spatial Peak Temporal Average): <100 mW/cm²
- **Mechanical Index**: <0.5
- **Thermal Index**: <0.5
- **Compliance**: FDA 510(k) guidance for diagnostic ultrasound

### EMG Safety
- **Isolation**: 5kV galvanic isolation from mains
- **Patient leakage**: <10µA (IEC 60601-1)
- **ESD**: IEC 61000-4-2 Level 4 (8kV contact, 15kV air)

### RF Emissions
- **Wireless**: Bluetooth 5.2 + WiFi 6
- **Compliance**: FCC Part 15, CE RED

---

## References

1. [1] Maceira-Elvira et al. (2023). fNIRS and neural interfaces. *NeuroImage*.
2. [2] Krnjević & Phillis (2019). Ultrasound imaging of the brain. *IEEE Trans UFFC*.
3. [3] Farina & Negro (2012). Accessing the neural drive to muscle. *J Physiol*.
4. [4] Liao et al. (2012). Ultrasound localization microscopy. *Nature*.

---

**Version:** 0.1 — Research Specification  
**Last Updated:** 2026-03-28
