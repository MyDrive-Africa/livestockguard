---
inclusion: fileMatch
fileMatchPattern: "**/*.rs"
---

# Rust Service Patterns

When working on Rust files in this project, follow these patterns.

## Services

Two Rust services exist in `cloud/services/`:

### Ingestion Service (`cloud/services/ingestion/`)

High-throughput binary message decoder for production scale.

- **Purpose**: Decode binary MQTT messages, validate, route to TimescaleDB
- **Target**: 5,000 messages/sec
- **Runtime**: Tokio (multi-threaded async)
- **Protocol**: Custom binary with CRC-16 CCITT integrity check

```rust
// Binary protocol header (11 bytes)
struct MessageHeader {
    version: u8,        // Protocol version (0x01)
    msg_type: u8,       // 0x01=position, 0x02=geofence_alert, 0x03=theft_alert
    priority: u8,       // 1=normal, 3=critical
    device_id: u16,     // Device identifier
    timestamp: u32,     // Unix timestamp
    sequence: u8,       // Sequence number (0-255)
    payload_len: i8,    // Payload length
}
```

### Geofence Engine (`cloud/services/geofence_engine/`)

Spatial breach detection using R-tree indexing.

- **Purpose**: Evaluate positions against active geofences
- **Algorithm**: Point-in-polygon with R-tree for O(log n) lookup
- **Crate**: `rstar` for spatial indexing, `geo` for geometry operations

## Project Structure

```
cloud/services/<rust_service>/
├── Cargo.toml
├── Cargo.lock
├── src/
│   ├── main.rs           # Entry point (#[tokio::main])
│   ├── config.rs         # Environment-based configuration
│   ├── protocol.rs       # Binary message decoding
│   ├── handler.rs        # Message processing logic
│   └── db.rs             # Database operations
└── tests/
    └── integration_test.rs
```

## Conventions

### Error Handling
```rust
use anyhow::{Context, Result};
use thiserror::Error;

#[derive(Error, Debug)]
pub enum ProtocolError {
    #[error("invalid CRC: expected {expected:#06x}, got {actual:#06x}")]
    InvalidCrc { expected: u16, actual: u16 },
    #[error("unsupported protocol version: {0}")]
    UnsupportedVersion(u8),
    #[error("payload too short: need {need} bytes, got {got}")]
    PayloadTooShort { need: usize, got: usize },
}
```

### Async Pattern
```rust
use tokio::net::TcpListener;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::init();
    let config = Config::from_env()?;
    // ...
    Ok(())
}
```

### Binary Decoding
```rust
use byteorder::{LittleEndian, ReadBytesExt};
use std::io::Cursor;

fn decode_header(data: &[u8]) -> Result<MessageHeader, ProtocolError> {
    if data.len() < 11 {
        return Err(ProtocolError::PayloadTooShort { need: 11, got: data.len() });
    }
    let mut cursor = Cursor::new(data);
    Ok(MessageHeader {
        version: cursor.read_u8()?,
        msg_type: cursor.read_u8()?,
        // ...
    })
}
```

### CRC-16 CCITT
```rust
fn crc16_ccitt(data: &[u8]) -> u16 {
    let mut crc: u16 = 0xFFFF;
    for &byte in data {
        crc ^= (byte as u16) << 8;
        for _ in 0..8 {
            if crc & 0x8000 != 0 {
                crc = (crc << 1) ^ 0x1021;
            } else {
                crc <<= 1;
            }
        }
    }
    crc
}
```

## Testing

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_crc16_known_value() {
        let data = b"hello";
        assert_eq!(crc16_ccitt(data), 0xD26E);
    }

    #[tokio::test]
    async fn test_message_processing() {
        // ...
    }
}
```

Run: `cargo test --verbose`

## Key Crates

| Crate | Purpose |
|-------|---------|
| tokio | Async runtime |
| serde / serde_json | Serialization |
| byteorder | Binary encoding/decoding |
| rstar | R-tree spatial index |
| geo | Geometry types + algorithms |
| anyhow | Application error handling |
| thiserror | Library error types |
| tracing | Structured logging |
| sqlx | Async PostgreSQL (if used) |

## CI

Tested in GitHub Actions with `cargo test --verbose` for both services.
Rust toolchain: stable (via `dtolnay/rust-toolchain@stable`).
Cache: `Swatinem/rust-cache@v2` with workspace paths.
