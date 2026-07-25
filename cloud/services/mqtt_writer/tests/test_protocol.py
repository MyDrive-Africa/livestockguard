"""
Tests for MQTT Writer protocol decoding:
- CRC-16/CCITT verification
- Header decoding
- Position record decoding
- Full message parsing (on_message dispatch)
"""

import os
import struct
import sys
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mqtt_writer import (
    crc16_ccitt,
    decode_header,
    decode_position_record,
    on_message,
    PROTOCOL_VERSION,
    MSG_POSITION_BATCH,
    MSG_GEOFENCE_ALERT,
    MSG_THEFT_ALERT,
    MSG_HEARTBEAT,
)


# ─── CRC-16 ──────────────────────────────────────────

class TestCRC16:
    """CRC-16/CCITT calculation."""

    def test_empty_bytes(self):
        result = crc16_ccitt(b"")
        assert result == 0xFFFF  # Initial value with no data

    def test_known_value(self):
        """CRC of 'hello' should be deterministic."""
        result = crc16_ccitt(b"hello")
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFF

    def test_different_data_different_crc(self):
        crc1 = crc16_ccitt(b"hello")
        crc2 = crc16_ccitt(b"world")
        assert crc1 != crc2

    def test_same_data_same_crc(self):
        data = b"\x01\x02\x03\x04\x05"
        assert crc16_ccitt(data) == crc16_ccitt(data)

    def test_single_bit_flip_changes_crc(self):
        data1 = b"\x01\x02\x03"
        data2 = b"\x01\x02\x04"  # Last byte differs
        assert crc16_ccitt(data1) != crc16_ccitt(data2)


# ─── Header Decoding ─────────────────────────────────

class TestDecodeHeader:
    """Message header (11 bytes) decoding."""

    def _make_header(self, version=PROTOCOL_VERSION, msg_type=MSG_POSITION_BATCH,
                     priority=0, device_id=1, timestamp=1700000000,
                     sequence=0, payload_len=16):
        return struct.pack('<BBBHIBb', version, msg_type, priority,
                          device_id, timestamp, sequence, payload_len)

    def test_valid_header(self):
        data = self._make_header(device_id=0x1234, msg_type=MSG_POSITION_BATCH)
        result = decode_header(data)
        assert result is not None
        assert result["version"] == PROTOCOL_VERSION
        assert result["msg_type"] == MSG_POSITION_BATCH
        assert result["device_id"] == 0x1234

    def test_wrong_version_returns_none(self):
        data = self._make_header(version=0xFF)
        result = decode_header(data)
        assert result is None

    def test_too_short_returns_none(self):
        data = b"\x01\x02\x03"  # Only 3 bytes
        result = decode_header(data)
        assert result is None

    def test_all_message_types_decode(self):
        for msg_type in [MSG_POSITION_BATCH, MSG_GEOFENCE_ALERT, MSG_THEFT_ALERT, MSG_HEARTBEAT]:
            data = self._make_header(msg_type=msg_type)
            result = decode_header(data)
            assert result is not None
            assert result["msg_type"] == msg_type

    def test_device_id_range(self):
        """Device ID is a 16-bit unsigned int."""
        data = self._make_header(device_id=0xFFFF)
        result = decode_header(data)
        assert result["device_id"] == 0xFFFF

    def test_timestamp_decoded(self):
        ts = int(time.time())
        data = self._make_header(timestamp=ts)
        result = decode_header(data)
        assert result["timestamp"] == ts


# ─── Position Record Decoding ─────────────────────────

class TestDecodePositionRecord:
    """Position record (16 bytes) decoding."""

    def _make_position(self, ts=1700000000, lat=-291200000, lon=262100000,
                       speed=5, heading=128, hdop=15, flags=0):
        # Pack: timestamp(4), lat_offset(4), lon_offset(4), speed(1), heading(1), hdop(1), flags(1)
        return struct.pack('<iiiBBBB', ts, lat, lon, speed, heading, hdop, flags)

    def test_valid_position(self):
        data = self._make_position()
        result = decode_position_record(data)
        assert result is not None
        assert result["latitude"] == pytest.approx(-29.12, abs=0.01)
        assert result["longitude"] == pytest.approx(26.21, abs=0.01)
        assert result["speed"] == 5.0
        assert result["hdop"] == 1.5

    def test_too_short_returns_none(self):
        data = b"\x00" * 10  # Only 10 bytes (need 16)
        result = decode_position_record(data)
        assert result is None

    def test_offset_position_decoding(self):
        """Decode from an offset within a larger buffer."""
        padding = b"\xFF" * 8
        position = self._make_position()
        data = padding + position
        result = decode_position_record(data, offset=8)
        assert result is not None
        assert result["latitude"] == pytest.approx(-29.12, abs=0.01)

    def test_heading_conversion(self):
        """Heading byte 0-255 maps to 0-360 degrees."""
        data = self._make_position(heading=0)
        result = decode_position_record(data)
        assert result["heading"] == 0.0

        data = self._make_position(heading=255)
        result = decode_position_record(data)
        assert result["heading"] == pytest.approx(360.0, abs=1.5)

    def test_zero_coordinates(self):
        data = self._make_position(lat=0, lon=0)
        result = decode_position_record(data)
        assert result["latitude"] == 0.0
        assert result["longitude"] == 0.0

    def test_timestamp_conversion(self):
        """Valid unix timestamp converts to datetime."""
        ts = 1700000000
        data = self._make_position(ts=ts)
        result = decode_position_record(data)
        assert result["timestamp"] == datetime.fromtimestamp(ts, tz=timezone.utc)


# ─── Full Message Processing ─────────────────────────

class TestOnMessage:
    """on_message callback — full decode pipeline."""

    def _build_message(self, msg_type=MSG_POSITION_BATCH, device_id=0x0001, payload=b""):
        """Build a complete binary message with header + payload + CRC."""
        ts = int(time.time())
        header = struct.pack('<BBBHIBb', PROTOCOL_VERSION, msg_type, 0,
                            device_id, ts, 0, len(payload))
        body = header + payload
        crc = crc16_ccitt(body)
        return body + struct.pack('>H', crc)

    def _make_position_payload(self):
        """Build a single 16-byte position record."""
        return struct.pack('<iiiBBBB', int(time.time()), -291200000, 262100000, 5, 128, 15, 0)

    def test_valid_position_message_dispatches(self):
        """Position batch message triggers write_position."""
        payload = self._make_position_payload()
        raw = self._build_message(msg_type=MSG_POSITION_BATCH, payload=payload)

        msg = MagicMock()
        msg.payload = raw

        with patch('mqtt_writer.loop') as mock_loop, \
             patch('mqtt_writer.asyncio') as mock_asyncio:
            mock_asyncio.run_coroutine_threadsafe = MagicMock()
            on_message(None, None, msg)
            mock_asyncio.run_coroutine_threadsafe.assert_called()

    def test_geofence_alert_dispatches(self):
        """Geofence alert message triggers write_alert."""
        raw = self._build_message(msg_type=MSG_GEOFENCE_ALERT, device_id=0xABCD)

        msg = MagicMock()
        msg.payload = raw

        with patch('mqtt_writer.loop') as mock_loop, \
             patch('mqtt_writer.asyncio') as mock_asyncio:
            mock_asyncio.run_coroutine_threadsafe = MagicMock()
            on_message(None, None, msg)
            mock_asyncio.run_coroutine_threadsafe.assert_called()

    def test_theft_alert_dispatches(self):
        """Theft alert message triggers write_alert."""
        raw = self._build_message(msg_type=MSG_THEFT_ALERT, device_id=0x0042)

        msg = MagicMock()
        msg.payload = raw

        with patch('mqtt_writer.loop') as mock_loop, \
             patch('mqtt_writer.asyncio') as mock_asyncio:
            mock_asyncio.run_coroutine_threadsafe = MagicMock()
            on_message(None, None, msg)
            mock_asyncio.run_coroutine_threadsafe.assert_called()

    def test_invalid_crc_rejected(self):
        """Message with bad CRC is silently dropped."""
        payload = self._make_position_payload()
        raw = self._build_message(msg_type=MSG_POSITION_BATCH, payload=payload)
        # Corrupt the CRC (last 2 bytes)
        corrupted = raw[:-2] + b"\xFF\xFF"

        msg = MagicMock()
        msg.payload = corrupted

        import mqtt_writer
        initial_errors = mqtt_writer.stats["errors"]

        with patch('mqtt_writer.loop'), patch('mqtt_writer.asyncio') as mock_asyncio:
            mock_asyncio.run_coroutine_threadsafe = MagicMock()
            on_message(None, None, msg)
            # Should NOT dispatch
            mock_asyncio.run_coroutine_threadsafe.assert_not_called()

        assert mqtt_writer.stats["errors"] > initial_errors

    def test_too_short_message_ignored(self):
        """Message shorter than minimum (13 bytes) is ignored."""
        msg = MagicMock()
        msg.payload = b"\x01\x02\x03"  # Only 3 bytes

        with patch('mqtt_writer.asyncio') as mock_asyncio:
            mock_asyncio.run_coroutine_threadsafe = MagicMock()
            on_message(None, None, msg)
            mock_asyncio.run_coroutine_threadsafe.assert_not_called()

    def test_heartbeat_does_not_write(self):
        """Heartbeat messages don't trigger write_position or write_alert."""
        raw = self._build_message(msg_type=MSG_HEARTBEAT, device_id=0x0001)

        msg = MagicMock()
        msg.payload = raw

        with patch('mqtt_writer.loop'), patch('mqtt_writer.asyncio') as mock_asyncio:
            mock_asyncio.run_coroutine_threadsafe = MagicMock()
            on_message(None, None, msg)
            # Heartbeat should not dispatch any coroutines
            mock_asyncio.run_coroutine_threadsafe.assert_not_called()

    def test_multiple_positions_in_batch(self):
        """Batch with 3 position records dispatches 3 writes."""
        pos = self._make_position_payload()
        payload = pos + pos + pos  # 3 records

        raw = self._build_message(msg_type=MSG_POSITION_BATCH, payload=payload)

        msg = MagicMock()
        msg.payload = raw

        with patch('mqtt_writer.loop'), patch('mqtt_writer.asyncio') as mock_asyncio:
            mock_asyncio.run_coroutine_threadsafe = MagicMock()
            on_message(None, None, msg)
            assert mock_asyncio.run_coroutine_threadsafe.call_count == 3
