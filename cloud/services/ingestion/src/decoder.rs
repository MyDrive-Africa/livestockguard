//! Binary protocol decoder for LivestockGuard GPS collar telemetry.
//!
//! This module handles the compact binary wire format used by GPS collar
//! devices over MQTT, LoRaWAN, and satellite links. The format prioritises
//! minimal byte count for constrained radio channels while maintaining
//! data integrity via CRC-16/CCITT.
//!
//! # Wire Format Overview
//!
//! ```text
//! ┌──────────┬───────────┬─────┬──────────┬──────────┬─────────┬──────┬─────┐
//! │ msg_type │ device_id │ seq │ pos_cnt  │positions │ battery │ temp │ CRC │
//! │  1 byte  │  4 bytes  │ 2B  │  1 byte  │ N×11B    │  2B     │ 1+1B │ 2B  │
//! └──────────┴───────────┴─────┴──────────┴──────────┴─────────┴──────┴─────┘
//! ```
//!
//! All multi-byte integers are big-endian. Positions encode latitude and
//! longitude as `i32` microdegrees (value × 1,000,000).

use thiserror::Error;

use crate::{DeviceTelemetry, Position};

/// Type discriminator for uplink messages from collar devices.
///
/// Each message type uses the same outer frame (header + CRC) but carries
/// different payload semantics. Currently only [`PositionReport`](Self::PositionReport)
/// is fully decoded; other types are recognised but their payloads are not yet parsed.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum MessageType {
    /// Batch of GPS position fixes (normal telemetry).
    PositionReport = 0x01,
    /// Device-generated alert (geofence breach, theft, low battery).
    AlertEvent = 0x02,
    /// Periodic keep-alive with battery and signal status only.
    HeartBeat = 0x03,
    /// Acknowledgement of a configuration update pushed to the device.
    ConfigAck = 0x04,
}

impl TryFrom<u8> for MessageType {
    type Error = DecodeError;

    /// Convert a raw byte to a known message type.
    ///
    /// # Errors
    ///
    /// Returns [`DecodeError::UnknownMessageType`] if the byte does not
    /// match any defined message type.
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

/// Errors that can occur during binary frame decoding.
#[derive(Debug, Error)]
pub enum DecodeError {
    /// The payload is shorter than the minimum required frame length.
    #[error("Payload too short: expected at least {expected} bytes, got {actual}")]
    PayloadTooShort { expected: usize, actual: usize },

    /// The hex string could not be parsed into raw bytes.
    #[error("Invalid hex string: {0}")]
    InvalidHex(String),

    /// The message type byte does not match any known type.
    #[error("Unknown message type: 0x{0:02X}")]
    UnknownMessageType(u8),

    /// The CRC-16/CCITT checksum does not match, indicating data corruption.
    #[error("CRC mismatch: expected 0x{expected:04X}, got 0x{actual:04X}")]
    CrcMismatch { expected: u16, actual: u16 },

    /// A position record within the payload has invalid or truncated data.
    #[error("Invalid position data")]
    InvalidPosition,
}

/// Decode an uplink hex payload into structured telemetry data.
///
/// This is the primary entry point for all binary frame decoding. It handles
/// CRC verification, header parsing, position extraction, and device health
/// field decoding in a single pass.
///
/// # Arguments
///
/// * `hex_payload` — The full frame as a hex-encoded string (e.g., from MQTT or webhook body).
///
/// # Returns
///
/// A [`DeviceTelemetry`] struct containing the decoded device ID, position batch,
/// battery voltage, temperature, and signal strength.
///
/// # Errors
///
/// - [`DecodeError::InvalidHex`] — Input is not valid hexadecimal.
/// - [`DecodeError::PayloadTooShort`] — Frame is shorter than the 14-byte minimum.
/// - [`DecodeError::CrcMismatch`] — Data integrity check failed (corruption in transit).
/// - [`DecodeError::UnknownMessageType`] — Unrecognised message type byte.
/// - [`DecodeError::InvalidPosition`] — Position record is truncated.
///
/// # Frame Format
///
/// ```text
///   [0]     - message type (u8)
///   [1..5]  - device ID (4 bytes, big-endian u32)
///   [5..7]  - sequence number (u16 big-endian)
///   [7]     - position count (u8)
///   [8..N]  - positions (11 bytes each: lat_i32 + lon_i32 + alt_u16 + hdop_u8)
///   [N..N+2]- battery_mv (u16 big-endian)
///   [N+2]   - temperature (i8, offset by +40)
///   [N+3]   - signal RSSI (i8)
///   [last 2]- CRC-16/CCITT
/// ```
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

/// Compute CRC-16/CCITT checksum over a byte slice.
///
/// Uses polynomial `0x1021` with initial value `0xFFFF` (no final XOR).
/// This matches the CRC computed by the firmware encoder and the Python
/// MQTT writer decoder.
///
/// # Arguments
///
/// * `data` — The byte slice to checksum (typically the full frame minus the trailing 2 CRC bytes).
///
/// # Returns
///
/// The 16-bit CRC value.
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

/// Minimal hex-decoding utility (avoids external `hex` crate dependency).
mod hex {
    /// Decode a hex-encoded string into raw bytes.
    ///
    /// # Arguments
    ///
    /// * `s` — A string of hexadecimal characters (case-insensitive, even length).
    ///
    /// # Errors
    ///
    /// Returns an error string if the input has odd length or contains invalid hex characters.
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

#[cfg(test)]
mod tests {
    use super::*;

    // ─── CRC-16 Tests ────────────────────────────────

    #[test]
    fn test_crc16_empty() {
        assert_eq!(crc16_ccitt(&[]), 0xFFFF);
    }

    #[test]
    fn test_crc16_deterministic() {
        let data = b"hello";
        let crc1 = crc16_ccitt(data);
        let crc2 = crc16_ccitt(data);
        assert_eq!(crc1, crc2);
    }

    #[test]
    fn test_crc16_different_data_different_result() {
        assert_ne!(crc16_ccitt(b"hello"), crc16_ccitt(b"world"));
    }

    #[test]
    fn test_crc16_single_bit_flip() {
        assert_ne!(crc16_ccitt(&[0x01, 0x02, 0x03]), crc16_ccitt(&[0x01, 0x02, 0x04]));
    }

    // ─── Hex Decode Tests ────────────────────────────

    #[test]
    fn test_hex_decode_valid() {
        assert_eq!(hex::decode("48656c6c6f").unwrap(), b"Hello");
    }

    #[test]
    fn test_hex_decode_empty() {
        assert_eq!(hex::decode("").unwrap(), Vec::<u8>::new());
    }

    #[test]
    fn test_hex_decode_odd_length() {
        assert!(hex::decode("abc").is_err());
    }

    #[test]
    fn test_hex_decode_invalid_chars() {
        assert!(hex::decode("ZZZZ").is_err());
    }

    // ─── MessageType Tests ───────────────────────────

    #[test]
    fn test_message_type_from_valid() {
        assert_eq!(MessageType::try_from(0x01).unwrap(), MessageType::PositionReport);
        assert_eq!(MessageType::try_from(0x02).unwrap(), MessageType::AlertEvent);
        assert_eq!(MessageType::try_from(0x03).unwrap(), MessageType::HeartBeat);
        assert_eq!(MessageType::try_from(0x04).unwrap(), MessageType::ConfigAck);
    }

    #[test]
    fn test_message_type_from_invalid() {
        assert!(MessageType::try_from(0x00).is_err());
        assert!(MessageType::try_from(0xFF).is_err());
    }

    // ─── decode_uplink Tests ─────────────────────────

    fn build_valid_payload(position_count: u8, lat: i32, lon: i32) -> String {
        let mut bytes: Vec<u8> = Vec::new();

        // Header: msg_type(1) + device_id(4) + seq(2) + pos_count(1) = 8
        bytes.push(0x01); // PositionReport
        bytes.extend_from_slice(&0x00001234u32.to_be_bytes()); // device_id
        bytes.extend_from_slice(&0x0001u16.to_be_bytes()); // sequence
        bytes.push(position_count);

        // Positions: 11 bytes each (lat_i32 + lon_i32 + alt_u16 + hdop_u8)
        for _ in 0..position_count {
            bytes.extend_from_slice(&lat.to_be_bytes());
            bytes.extend_from_slice(&lon.to_be_bytes());
            bytes.extend_from_slice(&1500u16.to_be_bytes()); // altitude
            bytes.push(15); // hdop * 10
        }

        // Trailing: battery(2) + temp(1) + rssi(1)
        bytes.extend_from_slice(&3700u16.to_be_bytes());
        bytes.push(65); // temp: 65 - 40 = 25°C
        bytes.push((-72i8) as u8); // RSSI

        // CRC
        let crc = crc16_ccitt(&bytes);
        bytes.extend_from_slice(&crc.to_be_bytes());

        // Convert to hex string
        bytes.iter().map(|b| format!("{:02x}", b)).collect()
    }

    #[test]
    fn test_decode_uplink_valid_single_position() {
        let hex = build_valid_payload(1, -29_120_000, 26_210_000);
        let result = decode_uplink(&hex).unwrap();

        assert_eq!(result.device_id, "LG-00001234");
        assert_eq!(result.sequence_number, 1);
        assert_eq!(result.positions.len(), 1);
        assert!((result.positions[0].latitude - (-29.12)).abs() < 0.001);
        assert!((result.positions[0].longitude - 26.21).abs() < 0.001);
        assert_eq!(result.battery_mv, 3700);
        assert!((result.temperature_c - 25.0).abs() < 0.1);
        assert_eq!(result.signal_rssi, -72);
    }

    #[test]
    fn test_decode_uplink_multiple_positions() {
        let hex = build_valid_payload(3, -29_120_000, 26_210_000);
        let result = decode_uplink(&hex).unwrap();
        assert_eq!(result.positions.len(), 3);
    }

    #[test]
    fn test_decode_uplink_too_short() {
        let result = decode_uplink("0102");
        assert!(matches!(result, Err(DecodeError::PayloadTooShort { .. })));
    }

    #[test]
    fn test_decode_uplink_invalid_hex() {
        let result = decode_uplink("ZZZZ");
        assert!(matches!(result, Err(DecodeError::InvalidHex(_))));
    }

    #[test]
    fn test_decode_uplink_crc_mismatch() {
        let hex = build_valid_payload(1, -29_120_000, 26_210_000);
        // Corrupt last byte of CRC
        let mut corrupted = hex.clone();
        let len = corrupted.len();
        corrupted.replace_range(len-2..len, "ff");
        let result = decode_uplink(&corrupted);
        assert!(matches!(result, Err(DecodeError::CrcMismatch { .. })));
    }

    #[test]
    fn test_decode_uplink_zero_positions() {
        let hex = build_valid_payload(0, 0, 0);
        let result = decode_uplink(&hex).unwrap();
        assert_eq!(result.positions.len(), 0);
        assert_eq!(result.battery_mv, 3700);
    }

    #[test]
    fn test_decode_uplink_device_id_format() {
        let hex = build_valid_payload(0, 0, 0);
        let result = decode_uplink(&hex).unwrap();
        assert!(result.device_id.starts_with("LG-"));
        assert_eq!(result.device_id.len(), 11); // "LG-" + 8 hex chars
    }
}