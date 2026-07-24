use thiserror::Error;

use crate::{DeviceTelemetry, Position};

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum MessageType {
    PositionReport = 0x01,
    AlertEvent = 0x02,
    HeartBeat = 0x03,
    ConfigAck = 0x04,
}

impl TryFrom<u8> for MessageType {
    type Error = DecodeError;

    fn try_from(value: u8) -> Result<Self, Self::Error> {
        match value {
            0x01 => Ok(MessageType::PositionReport),
            0x02 => Ok(MessageType::AlertEvent),
            0x03 => Ok(MessageType::HeartBeat),
            0x04 => Ok(MessageType::ConfigAck),
            _ => Err(DecodeError::UnknownMessageType(value)),
        }
    }
}

#[derive(Debug, Error)]
pub enum DecodeError {
    #[error("Payload too short: expected at least {expected} bytes, got {actual}")]
    PayloadTooShort { expected: usize, actual: usize },

    #[error("Invalid hex string: {0}")]
    InvalidHex(String),

    #[error("Unknown message type: 0x{0:02X}")]
    UnknownMessageType(u8),

    #[error("CRC mismatch: expected 0x{expected:04X}, got 0x{actual:04X}")]
    CrcMismatch { expected: u16, actual: u16 },

    #[error("Invalid position data")]
    InvalidPosition,
}

/// Decode an uplink hex payload into structured telemetry data.
///
/// Frame format:
///   [0]     - message type (u8)
///   [1..5]  - device ID (4 bytes, big-endian u32)
///   [5..7]  - sequence number (u16 big-endian)
///   [7]     - position count (u8)
///   [8..N]  - positions (11 bytes each: lat_i32 + lon_i32 + alt_u16 + hdop_u8)
///   [N..N+2]- battery_mv (u16 big-endian)
///   [N+2]   - temperature (i8, offset by +40)
///   [N+3]   - signal RSSI (i8)
///   [last 2]- CRC-16/CCITT
pub fn decode_uplink(hex_payload: &str) -> Result<DeviceTelemetry, DecodeError> {
    let bytes = hex::decode(hex_payload).map_err(|e| DecodeError::InvalidHex(e.to_string()))?;

    // Minimum: header(8) + battery(2) + temp(1) + rssi(1) + crc(2) = 14
    if bytes.len() < 14 {
        return Err(DecodeError::PayloadTooShort {
            expected: 14,
            actual: bytes.len(),
        });
    }

    // Verify CRC (all bytes except last 2)
    let payload_len = bytes.len();
    let crc_received = u16::from_be_bytes([bytes[payload_len - 2], bytes[payload_len - 1]]);
    let crc_computed = crc16_ccitt(&bytes[..payload_len - 2]);

    if crc_received != crc_computed {
        return Err(DecodeError::CrcMismatch {
            expected: crc_computed,
            actual: crc_received,
        });
    }

    // Parse header
    let _msg_type = MessageType::try_from(bytes[0])?;
    let device_id = u32::from_be_bytes([bytes[1], bytes[2], bytes[3], bytes[4]]);
    let sequence_number =
        u32::from(u16::from_be_bytes([bytes[5], bytes[6]]));
    let position_count = bytes[7] as usize;

    // Parse positions
    let mut positions = Vec::with_capacity(position_count);
    let mut offset = 8;

    for _ in 0..position_count {
        if offset + 11 > payload_len - 4 {
            return Err(DecodeError::InvalidPosition);
        }

        let lat_raw = i32::from_be_bytes([
            bytes[offset],
            bytes[offset + 1],
            bytes[offset + 2],
            bytes[offset + 3],
        ]);
        let lon_raw = i32::from_be_bytes([
            bytes[offset + 4],
            bytes[offset + 5],
            bytes[offset + 6],
            bytes[offset + 7],
        ]);
        let alt_raw = u16::from_be_bytes([bytes[offset + 8], bytes[offset + 9]]);
        let hdop_raw = bytes[offset + 10];

        positions.push(Position {
            latitude: lat_raw as f64 / 1_000_000.0,
            longitude: lon_raw as f64 / 1_000_000.0,
            altitude: alt_raw as f32,
            hdop: hdop_raw as f32 / 10.0,
            timestamp: chrono::Utc::now(),
        });

        offset += 11;
    }

    // Parse trailing fields
    let battery_mv = u16::from_be_bytes([bytes[offset], bytes[offset + 1]]);
    let temperature_c = (bytes[offset + 2] as i8 as f32) - 40.0;
    let signal_rssi = bytes[offset + 3] as i8 as i16;

    Ok(DeviceTelemetry {
        device_id: format!("LG-{:08X}", device_id),
        positions,
        battery_mv,
        temperature_c,
        signal_rssi,
        sequence_number,
    })
}

/// CRC-16/CCITT (polynomial 0x1021, initial value 0xFFFF)
pub fn crc16_ccitt(data: &[u8]) -> u16 {
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

// Need hex crate for decode
mod hex {
    pub fn decode(s: &str) -> Result<Vec<u8>, String> {
        if s.len() % 2 != 0 {
            return Err("Odd-length hex string".to_string());
        }
        (0..s.len())
            .step_by(2)
            .map(|i| {
                u8::from_str_radix(&s[i..i + 2], 16)
                    .map_err(|e| format!("Invalid hex at position {}: {}", i, e))
            })
            .collect()
    }
}
