"""Tests for device endpoints (list, get, command)."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import TEST_FARM_ID, TEST_DEVICE_ID


@pytest.mark.asyncio
class TestListDevices:
    """GET /api/devices"""

    async def test_list_devices_empty(self, client: AsyncClient, seed_farm):
        """No devices returns empty list."""
        resp = await client.get("/api/devices", params={"farm_id": str(TEST_FARM_ID)})
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_devices_with_data(self, client: AsyncClient, seed_device):
        """Farm with devices returns them."""
        resp = await client.get("/api/devices", params={"farm_id": str(TEST_FARM_ID)})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["serial_number"] == "DEV-001"
        assert data[0]["device_type"] == "collar"
        assert data[0]["status"] == "active"
        assert data[0]["battery_level"] == 85

    async def test_list_devices_filter_status(self, client: AsyncClient, seed_device):
        """Status filter works."""
        resp = await client.get("/api/devices", params={
            "farm_id": str(TEST_FARM_ID),
            "status": "active",
        })
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        resp = await client.get("/api/devices", params={
            "farm_id": str(TEST_FARM_ID),
            "status": "offline",
        })
        assert resp.status_code == 200
        assert len(resp.json()) == 0


@pytest.mark.asyncio
class TestGetDevice:
    """GET /api/devices/{device_id}"""

    async def test_get_device_success(self, client: AsyncClient, seed_device):
        """Existing device returns details."""
        resp = await client.get(f"/api/devices/{TEST_DEVICE_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["serial_number"] == "DEV-001"
        assert data["firmware_version"] == "1.2.3"

    async def test_get_device_not_found(self, client: AsyncClient, seed_farm):
        """Non-existent device returns 404."""
        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/devices/{fake_id}")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestDeviceCommand:
    """POST /api/devices/{device_id}/command"""

    async def test_send_command_success(self, client: AsyncClient, seed_device):
        """Valid command is queued."""
        resp = await client.post(f"/api/devices/{TEST_DEVICE_ID}/command", json={
            "command": "reboot",
            "priority": "high",
            "params": {"delay_seconds": 5},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "queued"
        assert data["command"] == "reboot"
        assert data["device_id"] == str(TEST_DEVICE_ID)

    async def test_send_command_minimal(self, client: AsyncClient, seed_device):
        """Command with only required field works."""
        resp = await client.post(f"/api/devices/{TEST_DEVICE_ID}/command", json={
            "command": "ping",
        })
        assert resp.status_code == 200
        assert resp.json()["command"] == "ping"
