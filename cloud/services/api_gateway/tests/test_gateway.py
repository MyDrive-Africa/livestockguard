"""
Tests for the BLE gateway router.

Covers:
- Gateway registration (success, duplicate serial)
- BLE tag registration (success, duplicate MAC)
- Batch sighting ingestion (success, unknown gateway, MAC resolution)
- List gateways
- Session start/end
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    TEST_ORG_ID, TEST_FARM_ID, TEST_ANIMAL_ID,
    test_session_factory,
)
from livestockguard_common.db_models import (
    GatewayDevice, BleEarTag, BleSighting, HerdsmanSession, Animal,
)


TEST_GATEWAY_ID = uuid.UUID("88888888-8888-8888-8888-888888888888")
TEST_BLE_TAG_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")


@pytest_asyncio.fixture
async def seed_gateway(db_session: AsyncSession, seed_farm):
    """Seed a gateway device for a farm."""
    gateway = GatewayDevice(
        id=TEST_GATEWAY_ID,
        farm_id=TEST_FARM_ID,
        serial_number="GW-TEST-001",
        name="Test Gateway",
        device_type="phone",
        herdsman_name="Sipho",
        status="active",
    )
    db_session.add(gateway)
    await db_session.commit()
    return gateway


@pytest_asyncio.fixture
async def seed_ble_tag(db_session: AsyncSession, seed_farm, seed_animal):
    """Seed a BLE ear tag linked to the test animal."""
    tag = BleEarTag(
        id=TEST_BLE_TAG_ID,
        farm_id=TEST_FARM_ID,
        animal_id=TEST_ANIMAL_ID,
        mac_address="AA:BB:CC:DD:EE:01",
        tag_name="Tag-001",
        status="active",
    )
    db_session.add(tag)
    await db_session.commit()
    return tag


# ─── Gateway Registration ─────────────────────────────


class TestGatewayRegistration:
    @pytest.mark.asyncio
    async def test_register_gateway_success(self, client: AsyncClient, seed_farm):
        """Register a new gateway device."""
        payload = {
            "farm_id": str(TEST_FARM_ID),
            "serial_number": "GW-NEW-001",
            "name": "New Gateway",
            "device_type": "phone",
            "herdsman_name": "Thabo",
            "ble_scan_interval_ms": 5000,
            "report_interval_sec": 30,
        }
        response = await client.post("/api/v1/gateway/register", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["serial_number"] == "GW-NEW-001"
        assert data["name"] == "New Gateway"
        assert data["herdsman_name"] == "Thabo"
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_register_gateway_duplicate_serial(self, client: AsyncClient, seed_gateway):
        """Reject duplicate gateway serial number."""
        payload = {
            "farm_id": str(TEST_FARM_ID),
            "serial_number": "GW-TEST-001",  # Already exists
            "name": "Another Gateway",
            "device_type": "phone",
        }
        response = await client.post("/api/v1/gateway/register", json=payload)
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]


# ─── BLE Tag Registration ─────────────────────────────


class TestBleTagRegistration:
    @pytest.mark.asyncio
    async def test_register_tag_success(self, client: AsyncClient, seed_farm, seed_animal):
        """Register a new BLE ear tag linked to an animal."""
        payload = {
            "farm_id": str(TEST_FARM_ID),
            "animal_id": str(TEST_ANIMAL_ID),
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "tag_name": "Tag-New",
        }
        response = await client.post("/api/v1/gateway/tags", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["mac_address"] == "AA:BB:CC:DD:EE:FF"
        assert data["animal_name"] == "Bella"
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_register_tag_duplicate_mac(self, client: AsyncClient, seed_ble_tag):
        """Reject duplicate BLE MAC address."""
        payload = {
            "farm_id": str(TEST_FARM_ID),
            "mac_address": "AA:BB:CC:DD:EE:01",  # Already exists
        }
        response = await client.post("/api/v1/gateway/tags", json=payload)
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_tags(self, client: AsyncClient, seed_ble_tag):
        """List BLE tags for a farm."""
        response = await client.get(f"/api/v1/gateway/tags?farm_id={TEST_FARM_ID}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["mac_address"] == "AA:BB:CC:DD:EE:01"


# ─── Batch Sighting Ingestion ─────────────────────────


class TestBatchIngestion:
    @pytest.mark.asyncio
    async def test_batch_unknown_gateway(self, client: AsyncClient, seed_farm):
        """Reject batch from unregistered gateway."""
        payload = {
            "gateway_serial": "UNKNOWN-GW",
            "latitude": -29.12,
            "longitude": 26.21,
            "sightings": [
                {"mac_address": "AA:BB:CC:DD:EE:01", "rssi": -65}
            ],
        }
        response = await client.post("/api/v1/gateway/batch", json=payload)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_batch_success_with_resolved_mac(self, client: AsyncClient, seed_gateway, seed_ble_tag):
        """Successfully ingest a batch with a known BLE MAC that resolves to an animal."""
        payload = {
            "gateway_serial": "GW-TEST-001",
            "latitude": -29.12,
            "longitude": 26.21,
            "battery_pct": 80,
            "sightings": [
                {"mac_address": "AA:BB:CC:DD:EE:01", "rssi": -65},
            ],
        }
        response = await client.post("/api/v1/gateway/batch", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["accepted"] == 1
        assert data["resolved"] == 1
        assert data["unresolved_macs"] == []

    @pytest.mark.asyncio
    async def test_batch_with_unresolved_mac(self, client: AsyncClient, seed_gateway):
        """Unregistered MAC should be reported as unresolved."""
        payload = {
            "gateway_serial": "GW-TEST-001",
            "latitude": -29.12,
            "longitude": 26.21,
            "sightings": [
                {"mac_address": "FF:FF:FF:FF:FF:FF", "rssi": -70},
            ],
        }
        response = await client.post("/api/v1/gateway/batch", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["accepted"] == 1
        assert data["resolved"] == 0
        assert "FF:FF:FF:FF:FF:FF" in data["unresolved_macs"]

    @pytest.mark.asyncio
    async def test_batch_empty_sightings(self, client: AsyncClient, seed_gateway):
        """Batch with empty sightings list should still succeed."""
        payload = {
            "gateway_serial": "GW-TEST-001",
            "latitude": -29.12,
            "longitude": 26.21,
            "sightings": [],
        }
        response = await client.post("/api/v1/gateway/batch", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["accepted"] == 0
        assert data["resolved"] == 0


# ─── List Gateways ───────────────────────────────────


class TestListGateways:
    @pytest.mark.asyncio
    async def test_list_gateways_empty(self, client: AsyncClient, seed_farm):
        """List gateways when none exist for the farm."""
        response = await client.get(f"/api/v1/gateway?farm_id={TEST_FARM_ID}")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_gateways_with_data(self, client: AsyncClient, seed_gateway):
        """List gateways returns seeded gateway."""
        response = await client.get(f"/api/v1/gateway?farm_id={TEST_FARM_ID}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["serial_number"] == "GW-TEST-001"


# ─── Sessions ─────────────────────────────────────────


class TestSessions:
    @pytest.mark.asyncio
    async def test_start_session_success(self, client: AsyncClient, seed_gateway):
        """Start a new herdsman patrol session."""
        payload = {
            "gateway_serial": "GW-TEST-001",
            "latitude": -29.12,
            "longitude": 26.21,
            "herdsman_name": "Sipho",
        }
        response = await client.post("/api/v1/gateway/sessions/start", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert data["herdsman_name"] == "Sipho"

    @pytest.mark.asyncio
    async def test_start_session_unknown_gateway(self, client: AsyncClient, seed_farm):
        """Starting a session with unknown gateway fails."""
        payload = {
            "gateway_serial": "NONEXISTENT",
            "latitude": -29.12,
            "longitude": 26.21,
        }
        response = await client.post("/api/v1/gateway/sessions/start", json=payload)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_end_session_success(self, client: AsyncClient, seed_gateway):
        """End an active session."""
        # Start a session first
        start_payload = {
            "gateway_serial": "GW-TEST-001",
            "latitude": -29.12,
            "longitude": 26.21,
        }
        start_response = await client.post("/api/v1/gateway/sessions/start", json=start_payload)
        session_id = start_response.json()["session_id"]

        # End it
        end_payload = {
            "latitude": -29.13,
            "longitude": 26.22,
            "notes": "All clear",
        }
        response = await client.post(f"/api/v1/gateway/sessions/{session_id}/end", json=end_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_end_session_not_found(self, client: AsyncClient, seed_farm):
        """Ending a non-existent session fails."""
        fake_id = str(uuid.uuid4())
        response = await client.post(
            f"/api/v1/gateway/sessions/{fake_id}/end",
            json={"latitude": -29.12, "longitude": 26.21},
        )
        assert response.status_code == 404
