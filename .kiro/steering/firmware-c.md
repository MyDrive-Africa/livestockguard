---
inclusion: fileMatch
fileMatchPattern: "firmware/**/*.{c,h}"
---

# Firmware Patterns (C11 / Zephyr)

When working on firmware C files, follow these patterns.

## Architecture

The firmware targets Nordic Semiconductor chips using Zephyr RTOS:

| Target | Chip | Role |
|--------|------|------|
| GPS Collar | nRF9160 | Full tracker (GPS + LTE-M/NB-IoT) |
| BLE Ear Tag | nRF52840 | Passive BLE beacon |

## Directory Structure

```
firmware/
├── CMakeLists.txt              # Top-level build
├── hal/include/                # Hardware Abstraction Layer
│   ├── hal_gnss.h              # GPS module interface
│   ├── hal_radio.h             # Radio (LTE, LoRa, BLE, Satellite)
│   ├── hal_accel.h             # Accelerometer interface
│   ├── hal_power.h             # Battery/sleep/charging
│   └── hal_types.h             # Common types
├── src/
│   ├── main.c                  # Entry point
│   ├── app/                    # Application state machine
│   └── services/
│       ├── gnss_service/       # GPS fix acquisition, duty cycle
│       ├── comms_service/      # Multi-protocol radio management
│       ├── power_service/      # Battery monitoring, adaptive sleep
│       ├── sensor_service/     # Accelerometer, temperature
│       └── config_service/     # Remote config, OTA triggers
├── lib/
│   ├── geofence/               # On-device point-in-polygon
│   ├── protocol/               # Binary wire protocol encoder
│   └── collections/            # Ring buffer, linked list
└── platforms/
    ├── nrf9160_collar/         # GPS collar board config
    └── nrf52840_eartag/        # BLE ear tag board config
```

## Naming Conventions

- **Public functions**: `lg_` prefix + snake_case: `lg_geofence_check()`, `lg_protocol_encode()`
- **Static/private**: plain snake_case without prefix
- **Types**: `lg_` prefix + snake_case + `_t`: `lg_position_t`, `lg_alert_type_t`
- **Constants/enums**: UPPER_SNAKE: `LG_MAX_GEOFENCE_VERTICES`, `LG_MSG_POSITION`
- **Macros**: UPPER_SNAKE: `LG_CRC16_INIT`

## State Machine

The collar firmware runs a duty-cycled state machine:

```
SLEEP → WAKE → GPS_FIX → TRANSMIT → SLEEP
         ↓                    ↓
    ACCELEROMETER       STORE_FORWARD (if no signal)
    (motion check)
```

- **Adaptive duty cycling**: Fix interval adjusts based on movement + battery
  - Resting: fix every 15 min
  - Walking: fix every 5 min
  - Running/vehicle: fix every 30s (alert mode)
  - Low battery: fix every 30 min

## Binary Protocol

Matches the MQTT Writer decoder and simulator encoder exactly:

```c
// Header (11 bytes, little-endian)
typedef struct __attribute__((packed)) {
    uint8_t  version;      // 0x01
    uint8_t  msg_type;     // MSG_POSITION_BATCH, MSG_GEOFENCE_ALERT, etc.
    uint8_t  priority;     // 1=normal, 3=critical
    uint16_t device_id;    // Unique device ID
    uint32_t timestamp;    // Unix epoch seconds
    uint8_t  sequence;     // Rolling 0-255
    int8_t   payload_len;  // Payload byte count
} lg_msg_header_t;

// Position record
typedef struct __attribute__((packed)) {
    int32_t timestamp;
    int32_t lat_offset;    // lat * 1e7
    int32_t lon_offset;    // lon * 1e7
    int8_t  speed;         // km/h (capped at 127)
    int8_t  heading;       // 0-255 mapped to 0-360
    int8_t  hdop_x10;     // HDOP * 10
    int8_t  flags;         // Fix quality flags
} lg_position_record_t;
```

## CRC-16 CCITT

```c
#define LG_CRC16_INIT 0xFFFF
#define LG_CRC16_POLY 0x1021

uint16_t lg_crc16_ccitt(const uint8_t *data, size_t len) {
    uint16_t crc = LG_CRC16_INIT;
    for (size_t i = 0; i < len; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (int j = 0; j < 8; j++) {
            if (crc & 0x8000)
                crc = (crc << 1) ^ LG_CRC16_POLY;
            else
                crc <<= 1;
        }
    }
    return crc;
}
```

## On-Device Geofencing

Uses winding-number algorithm for point-in-polygon:

```c
// Returns true if point is inside polygon
bool lg_geofence_point_in_polygon(
    int32_t lat, int32_t lon,
    const lg_geofence_vertex_t *vertices,
    uint8_t vertex_count
);
```

- Polygon vertices stored in flash (downloaded via config service)
- Evaluated after each GPS fix
- If breach detected: immediate alert message (priority=CRITICAL)

## Store-and-Forward

Ring buffer in `lib/collections/` stores positions when cellular is unavailable:

```c
typedef struct {
    uint8_t *buffer;
    size_t capacity;
    size_t head;
    size_t tail;
    size_t count;
} lg_ring_buffer_t;

bool lg_ring_buffer_push(lg_ring_buffer_t *rb, const void *data, size_t len);
bool lg_ring_buffer_pop(lg_ring_buffer_t *rb, void *data, size_t len);
```

When signal returns, flush oldest-first.

## HAL Interface Pattern

```c
// hal/include/hal_gnss.h
typedef struct {
    int32_t latitude;   // degrees * 1e7
    int32_t longitude;  // degrees * 1e7
    int16_t altitude;   // metres
    uint8_t hdop_x10;   // HDOP * 10
    uint8_t fix_type;   // 0=none, 2=2D, 3=3D
} lg_gnss_fix_t;

// Platform-independent interface
int lg_gnss_init(void);
int lg_gnss_request_fix(uint32_t timeout_ms);
int lg_gnss_get_fix(lg_gnss_fix_t *fix);
void lg_gnss_power_off(void);
```

## Build

```bash
# Requires nRF Connect SDK / Zephyr toolchain
west build -b nrf9160dk_nrf9160 firmware/
west flash
```

For host-based unit tests (without hardware):
```bash
cd firmware && mkdir build && cd build
cmake .. -DPLATFORM=host
make && ctest
```
