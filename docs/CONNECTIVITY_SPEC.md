# LivestockGuard Connectivity Specification

## Protocol Overview

| Protocol | Range | Power | Data Rate | Use Case |
|----------|-------|-------|-----------|----------|
| LTE-M/NB-IoT | Cellular coverage | Medium | 100kbps/50kbps | Primary (collar) |
| LoRaWAN | 10-15 km (rural) | Very Low | 0.3-11 kbps | Ear-tags, no cellular |
| Satellite | Global | High | 9 bytes/msg | Emergency fallback |
| BLE 5.0 | 100-400m | Very Low | 2 Mbps | Proximity + gateways |

## LTE-M / NB-IoT

- **Carrier**: Vodacom South Africa (Band 8, 900 MHz)
- **Protocol**: MQTT 5.0 over TLS 1.3 (port 8883)
- **Power Saving**: PSM (Power Saving Mode) + eDRX
  - PSM TAU timer: 4 hours (configurable)
  - Active time: 20 seconds after transmission
  - eDRX cycle: 40.96s (for downlink commands)
- **SIM**: Multi-IMSI eSIM (Vodacom primary, MTN fallback)
- **Fallback**: Automatic NB-IoT if LTE-M unavailable
- **RICA**: All SIMs registered per SA regulations

## LoRaWAN

- **Frequency**: EU868 band (South Africa regulatory)
- **Network Server**: ChirpStack (self-hosted on AWS)
- **Device Class**: Class A (battery-optimised)
- **Spreading Factor**: SF7 (near gateway) to SF12 (maximum range)
- **Range**: 10-15 km line-of-sight, 3-5 km in bushveld
- **ADR**: Adaptive Data Rate enabled for automatic SF optimisation
- **Gateway density**: 1 per farm (solar-powered, LTE backhaul)
- **Payload**: 12 bytes (lat[4] + lon[4] + alt[2] + battery[1] + status[1])
- **Join**: OTAA with per-device AppKey stored in secure element

## Satellite (Globalstar Simplex)

- **Service**: Globalstar STX3 simplex transmitter
- **Payload**: 9 bytes maximum per message
- **Encoding**: Compressed format:
  - Lat/Lon: 3 bytes each (±0.001° resolution, ~111m)
  - Status: 2 bytes (battery[4bit] + alert[4bit] + activity[4bit] + reserved[4bit])
  - Sequence: 1 byte
- **Frequency**: Every 4 hours (normal) / 15 min (panic mode)
- **Use case**: Last-resort when all terrestrial links fail
- **Cost**: ~R5 per message, budgeted for emergency use only

## BLE 5.0

- **Roles**: 
  - Peripheral (ear-tags): Broadcast beacon + connectable for config
  - Central (collars/gateways): Scan, collect, relay
- **Proximity**: RSSI-based distance estimation for herd cohesion alerts
- **Gateway mode**: BLE→LTE relay for ear-tags near collar/base-station
- **Advertising interval**: 1s (normal), 100ms (alert mode)
- **Data transfer**: GATT characteristics for config, bulk log download via L2CAP

## Connectivity Fallback Decision Tree

```
1. Try LTE-M → success? → MQTT publish
   ↓ fail (no signal / timeout 30s)
2. Try NB-IoT → success? → MQTT publish
   ↓ fail (no signal / timeout 60s)
3. Try LoRaWAN → success? → LoRa uplink
   ↓ fail (no gateway / join fail)
4. Buffer message → wait for BLE gateway proximity
   ↓ if PANIC alert:
5. Satellite transmit (9-byte compressed)
```

- Fallback state persisted across sleep cycles
- Automatic retry of higher-priority link every N cycles
- Cloud reconciles out-of-order messages via sequence numbers

## Store-and-Forward

- **Buffer**: 64 KB external SPI flash (W25Q512, ring buffer layout)
- **Capacity**: ~1700 position records (38 bytes each)
- **Duration**: 41 days at 15-minute intervals
- **Priority queue**: PANIC > ALERT > POSITION > HEARTBEAT
- **Delivery**: Batch upload on successful connection (up to 50 per session)
- **Acknowledgement**: Per-batch ACK from cloud triggers pointer advance

## Delta Compression

- **Technique**: Encode position as delta from previous fix
- **Savings**: Typical delta = 8 bytes vs 18 bytes full position
- **Batch encoding**: Header (full position) + N deltas
- **Compression ratio**: ~77% payload reduction for 10-message batches
- **Fallback**: Full position if delta exceeds encoding range (>1km movement)
