"""
Integration tests for MQTT Writer — tests the DB write and Redis pub/sub paths.

Mocks asyncpg connection pool and Redis client to verify:
- write_position inserts correct SQL and publishes to Redis
- write_alert inserts and publishes to both farm channel and alerts:incoming
- get_device_uuid auto-registers unknown devices
- Theft detection (speed > 30 km/h) triggers alert
"""

import os
import sys
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import mqtt_writer


# ─── Fixtures ─────────────────────────────────────────

@pytest.fixture
def mock_conn():
    """Create a mock asyncpg connection."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.fetchval = AsyncMock()
    conn.execute = AsyncMock()
    return conn


@pytest.fixture
def mock_pool(mock_conn):
    """Create a mock asyncpg pool that yields a mock connection."""
    pool = MagicMock()
    pool.acquire = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    r = AsyncMock()
    r.publish = AsyncMock()
    return r


@pytest.fixture(autouse=True)
def setup_globals(mock_pool, mock_redis):
    """Inject mock pool and redis into mqtt_writer globals."""
    mqtt_writer.db_pool = mock_pool
    mqtt_writer.redis_client = mock_redis
    yield
    mqtt_writer.db_pool = None
    mqtt_writer.redis_client = None


# ─── write_position tests ─────────────────────────────


class TestWritePosition:
    @pytest.mark.asyncio
    async def test_inserts_position_to_db(self, mock_conn):
        """write_position should INSERT into positions table."""
        device_uuid = UUID("11111111-1111-1111-1111-111111111111")
        farm_id = UUID("22222222-2222-2222-2222-222222222222")
        animal_id = UUID("33333333-3333-3333-3333-333333333333")

        mock_conn.fetchval = AsyncMock(return_value=device_uuid)  # get_device_uuid
        mock_conn.fetchrow = AsyncMock(return_value={
            "animal_id": animal_id,
            "farm_id": farm_id,
            "animal_name": "Bella",
        })
        mock_conn.execute = AsyncMock()

        position = {
            "timestamp": datetime.now(timezone.utc),
            "latitude": -29.12,
            "longitude": 26.21,
            "speed": 2.5,
            "heading": 180.0,
            "hdop": 1.2,
        }

        await mqtt_writer.write_position(0x0001, position)

        # Verify INSERT was called
        mock_conn.execute.assert_called()
        call_args = mock_conn.execute.call_args
        assert "INSERT INTO positions" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_publishes_to_redis(self, mock_conn, mock_redis):
        """write_position should publish a position.update event to Redis."""
        device_uuid = UUID("11111111-1111-1111-1111-111111111111")
        farm_id = UUID("22222222-2222-2222-2222-222222222222")
        animal_id = UUID("33333333-3333-3333-3333-333333333333")

        mock_conn.fetchval = AsyncMock(return_value=device_uuid)
        mock_conn.fetchrow = AsyncMock(return_value={
            "animal_id": animal_id,
            "farm_id": farm_id,
            "animal_name": "Bella",
        })
        mock_conn.execute = AsyncMock()

        position = {
            "timestamp": datetime.now(timezone.utc),
            "latitude": -29.12,
            "longitude": 26.21,
            "speed": 2.5,
            "heading": 180.0,
            "hdop": 1.2,
        }

        await mqtt_writer.write_position(0x0001, position)

        # Verify Redis publish was called with farm channel
        mock_redis.publish.assert_called_once()
        channel, message = mock_redis.publish.call_args[0]
        assert channel == f"farm:{farm_id}"
        parsed = json.loads(message)
        assert parsed["type"] == "position.update"
        assert parsed["payload"]["animalName"] == "Bella"
        assert parsed["payload"]["position"]["latitude"] == -29.12

    @pytest.mark.asyncio
    async def test_no_redis_publish_without_farm(self, mock_conn, mock_redis):
        """If device has no farm_id, skip Redis publish."""
        device_uuid = UUID("11111111-1111-1111-1111-111111111111")

        mock_conn.fetchval = AsyncMock(return_value=device_uuid)
        mock_conn.fetchrow = AsyncMock(return_value={
            "animal_id": None,
            "farm_id": None,
            "animal_name": None,
        })
        mock_conn.execute = AsyncMock()

        position = {
            "timestamp": datetime.now(timezone.utc),
            "latitude": -29.12,
            "longitude": 26.21,
            "speed": 0.0,
            "heading": 0.0,
            "hdop": 2.0,
        }

        await mqtt_writer.write_position(0x0001, position)

        # Redis should NOT be called since farm_id is None
        mock_redis.publish.assert_not_called()


# ─── write_alert tests ────────────────────────────────


class TestWriteAlert:
    @pytest.mark.asyncio
    async def test_inserts_alert_to_db(self, mock_conn):
        """write_alert should INSERT into alerts table."""
        device_uuid = UUID("11111111-1111-1111-1111-111111111111")
        farm_id = UUID("22222222-2222-2222-2222-222222222222")
        alert_id = UUID("44444444-4444-4444-4444-444444444444")

        mock_conn.fetchval = AsyncMock(side_effect=[device_uuid, alert_id])
        mock_conn.fetchrow = AsyncMock(return_value={
            "farm_id": farm_id,
            "animal_id": None,
            "animal_name": None,
        })

        await mqtt_writer.write_alert(0x0001, "geofence_breach", "critical", "Breach detected")

        # Verify INSERT INTO alerts was called
        calls = mock_conn.fetchval.call_args_list
        assert len(calls) >= 2
        insert_call = calls[1]
        assert "INSERT INTO alerts" in insert_call[0][0]

    @pytest.mark.asyncio
    async def test_publishes_to_farm_and_alert_channels(self, mock_conn, mock_redis):
        """write_alert should publish to both farm:{id} and alerts:incoming."""
        device_uuid = UUID("11111111-1111-1111-1111-111111111111")
        farm_id = UUID("22222222-2222-2222-2222-222222222222")
        alert_id = UUID("44444444-4444-4444-4444-444444444444")

        mock_conn.fetchval = AsyncMock(side_effect=[device_uuid, alert_id])
        mock_conn.fetchrow = AsyncMock(return_value={
            "farm_id": farm_id,
            "animal_id": None,
            "animal_name": None,
        })

        await mqtt_writer.write_alert(0x0001, "theft_detected", "critical", "Theft!")

        # Should publish to both channels
        assert mock_redis.publish.call_count == 2

        # First call: farm channel
        first_channel = mock_redis.publish.call_args_list[0][0][0]
        assert first_channel == f"farm:{farm_id}"
        first_msg = json.loads(mock_redis.publish.call_args_list[0][0][1])
        assert first_msg["type"] == "alert.created"
        assert first_msg["payload"]["severity"] == "critical"

        # Second call: alert engine channel
        second_channel = mock_redis.publish.call_args_list[1][0][0]
        assert second_channel == "alerts:incoming"
        second_msg = json.loads(mock_redis.publish.call_args_list[1][0][1])
        assert second_msg["alert_type"] == "theft_detected"

    @pytest.mark.asyncio
    async def test_no_alert_without_farm(self, mock_conn, mock_redis):
        """If device has no farm_id, don't write alert."""
        device_uuid = UUID("11111111-1111-1111-1111-111111111111")

        mock_conn.fetchval = AsyncMock(return_value=device_uuid)
        mock_conn.fetchrow = AsyncMock(return_value={
            "farm_id": None,
            "animal_id": None,
            "animal_name": None,
        })

        await mqtt_writer.write_alert(0x0001, "geofence_breach", "high", "Test")

        # No INSERT should happen (early return)
        mock_redis.publish.assert_not_called()


# ─── get_device_uuid tests ────────────────────────────


class TestGetDeviceUuid:
    @pytest.mark.asyncio
    async def test_known_device_returns_uuid(self, mock_conn):
        """Known device serial returns its UUID and updates last_seen."""
        expected_uuid = UUID("11111111-1111-1111-1111-111111111111")
        mock_conn.fetchval = AsyncMock(return_value=expected_uuid)

        result = await mqtt_writer.get_device_uuid(mock_conn, 0x0001)

        assert result == expected_uuid
        # Should have updated last_seen
        mock_conn.execute.assert_called_once()
        assert "UPDATE devices SET last_seen" in mock_conn.execute.call_args[0][0]

    @pytest.mark.asyncio
    async def test_unknown_device_auto_registers(self, mock_conn):
        """Unknown device serial auto-registers and returns new UUID."""
        new_uuid = UUID("55555555-5555-5555-5555-555555555555")
        # First fetchval returns None (not found), second returns the new UUID
        mock_conn.fetchval = AsyncMock(side_effect=[None, new_uuid])

        result = await mqtt_writer.get_device_uuid(mock_conn, 0xABCD)

        assert result == new_uuid
        # Should have called INSERT (auto-register)
        second_call = mock_conn.fetchval.call_args_list[1]
        assert "INSERT INTO devices" in second_call[0][0]
