# LivestockGuard Firmware Specification

## Platform & Toolchain

- **Language**: C11 (GNU extensions where needed)
- **RTOS**: Zephyr (nRF platforms), FreeRTOS (STM32/ESP32)
- **Build**: CMake + West (Zephyr), PlatformIO (ESP32)
- **Hardware Abstraction Layer (HAL)**: Unified API across platforms

## Supported Hardware

| Platform | MCU | Role | Connectivity |
|----------|-----|------|-------------|
| nRF9160 | Cortex-M33 | Collar (primary) | LTE-M/NB-IoT + GPS |
| nRF52840 | Cortex-M4F | Ear-tag (low-cost) | BLE 5.0 + LoRaWAN |
| STM32WLE5 | Cortex-M4 | Ear-tag (LoRa SoC) | LoRaWAN integrated |
| ESP32-S3 | Xtensa LX7 | Gateway/dev-kit | Wi-Fi + BLE |

## State Machine

Event-driven architecture with 6 primary states:

```
INIT → SLEEP → GPS_ACQUIRE → PROCESS → COMMS → SLEEP
                                          ↓
                                        PANIC (breach/SOS)
```

- **INIT**: Hardware self-test, load config, restore state from NVS
- **SLEEP**: Deep sleep with RTC wake (configurable 1-60 min intervals)
- **GPS_ACQUIRE**: Power GPS, acquire fix (timeout 90s, min 4 satellites)
- **PROCESS**: Run geofence check, activity classification, battery monitor
- **COMMS**: Transmit pending messages, receive commands, check OTA
- **PANIC**: Immediate alert mode, increased reporting frequency (30s)

## On-Device Geofencing

- **Algorithm**: Ray-casting point-in-polygon (max 32 vertices per fence)
- **Storage**: Up to 8 geofences in device flash (downloaded from cloud)
- **Breach State Machine**: INSIDE → GRACE_PERIOD (configurable 30-300s) → BREACHED
- **Grace period** prevents false alerts from GPS drift near boundaries
- **Hysteresis buffer**: 10m inside boundary before returning to INSIDE state

## Power Management

- **Target**: 2 years (collar, 3000mAh), 5 years (ear-tag, coin cell)
- **Adaptive duty cycling**: Increase GPS rate when moving, reduce when stationary
- **Sleep current**: <5µA (nRF9160 PSM), <1µA (nRF52840 System OFF)
- **GPS strategy**: Cached ephemeris, hot-start when possible (<10s fix)
- **Comms budget**: Batch messages, transmit only on schedule or breach

## Sensor Fusion & Activity Classification

- Accelerometer (LSM6DSO): 3-axis, 12.5-52 Hz sampling
- Classification: RESTING, GRAZING, WALKING, RUNNING, DISTRESS
- Algorithm: Threshold-based with sliding window (energy + variance)
- Temperature: Ambient + skin-contact for health anomaly detection

## Binary Message Protocol

- **Header**: 4 bytes (device_id[2] + msg_type[1] + seq_num[1])
- **Payload**: Variable length, type-dependent
- **Footer**: CRC-16/CCITT for integrity
- **Types**: Position (18B), Heartbeat (8B), Alert (12B), Batch (variable)
- **Encoding**: Little-endian, fixed-point coordinates (1e-7 degree resolution)

## Store-and-Forward Buffer

- **Storage**: 64KB external SPI flash (ring buffer)
- **Capacity**: ~1700 position messages (41 days at 15-min intervals)
- **Prioritization**: Alerts sent first, then newest positions, then backfill
- **Acknowledgement**: Cloud ACKs trigger buffer cleanup

## OTA Updates

- **Scheme**: A/B partition with rollback on boot failure
- **Transport**: Chunked transfer over MQTT (1KB blocks)
- **Validation**: SHA-256 full-image hash + RSA-2048 signature
- **Rollback**: Hardware watchdog triggers revert after 3 failed boots
- **Delta updates**: bsdiff patches for bandwidth-constrained links
