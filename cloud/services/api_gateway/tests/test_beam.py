"""
Tests for the beam sensor router.

Covers:
- Beam registration (success, duplicate serial, invalid beam_type/severity)
- List beams (empty, with data, filter by farm)
- Get one beam (success, not found)
- Crossing event ingestion (accepted + alert created, unknown beam, no-alert
  when alert_on_crossing is False, invalid direction)

Runs against the in-memory SQLite harness. The Redis publish in the /event
handler is wrapped in try/except, so it is a safe no-op without a live Redis.
Beam registration is tested WITHOUT span endpoints so the PostGIS ST_MakeLine
update (which SQLite lacks) is not exercised; a separate test confirms that
supplying span endpoints still returns 201 (the PostGIS update fails silently).
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TEST_FARM_ID
from livestockguard_common.db_models import BeamSensor


TEST_BEAM_ID = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001")


@pytest_asyncio.fixture
async def seed_beam(db_session: AsyncSession, seed_farm):
    """Seed an active beam sensor that alerts on crossing."""
    beam = BeamSensor(
        id=TEST_BEAM_ID,
        farm_id=TEST_FARM_ID,
        serial_number="BEAM-TEST-001",
        name="Main Gate Beam",
        beam_type="infrared",
        latitude=-25.3612,
        longitude=25.3577,
        breach_severity="high",
        alert_on_crossing=True,
        status="active",
    )
    db_session.add(beam)
    await db_session.commit()
    return beam


# ─── Beam Registration ────────────────────────────────


class TestBeamRegistration:
    @pytest.mark.asyncio
    async def test_register_beam_success(self, client: AsyncClient, seed_farm):
        """Register a new beam sensor (no span endpoints — avoids PostGIS)."""
        payload = {
            "farm_id": str(TEST_FARM_ID),
            "serial_number": "BEAM-NEW-001",
            "name": "North Fence Gap",
            "beam_type": "microwave",
            "latitude": -25.3549,
            "longitude": 25.3620,
            "breach_severity": "critical",
        }
        response = await client.post("/api/v1/beam/register", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["serial_number"] == "BEAM-NEW-001"
        assert data["beam_type"] == "microwave"
        assert data["breach_severity"] == "critical"
        assert data["alert_on_crossing"] is True
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_register_beam_with_span(self, client: AsyncClient, seed_farm):
        """Supplying span endpoints still succeeds (PostGIS update fails silently on SQLite)."""
        payload = {
            "farm_id": str(TEST_FARM_ID),
            "serial_number": "BEAM-SPAN-001",
            "name": "Loading Ramp Beam",
            "latitude": -25.3612,
            "longitude": 25.3634,
            "span_start_latitude": -25.36125,
            "span_start_longitude": 25.3634,
            "span_end_latitude": -25.36115,
            "span_end_longitude": 25.3634,
            "span_length_m": 6.0,
        }
        response = await client.post("/api/v1/beam/register", json=payload)
        assert response.status_code == 201
        assert response.json()["serial_number"] == "BEAM-SPAN-001"

    @pytest.mark.asyncio
    async def test_register_beam_duplicate_serial(self, client: AsyncClient, seed_beam):
        """Reject a duplicate beam serial number."""
        payload = {
            "farm_id": str(TEST_FARM_ID),
            "serial_number": "BEAM-TEST-001",  # already exists
            "name": "Duplicate",
            "latitude": -25.0,
            "longitude": 25.0,
        }
        response = await client.post("/api/v1/beam/register", json=payload)
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_register_beam_invalid_type(self, client: AsyncClient, seed_farm):
        """Reject an invalid beam_type."""
        payload = {
            "farm_id": str(TEST_FARM_ID),
            "serial_number": "BEAM-BAD-001",
            "name": "Bad Type",
            "beam_type": "sonar",  # not allowed
            "latitude": -25.0,
            "longitude": 25.0,
        }
        response = await client.post("/api/v1/beam/register", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_beam_invalid_severity(self, client: AsyncClient, seed_farm):
        """Reject an invalid breach_severity."""
        payload = {
            "farm_id": str(TEST_FARM_ID),
            "serial_number": "BEAM-BAD-002",
            "name": "Bad Severity",
            "latitude": -25.0,
            "longitude": 25.0,
            "breach_severity": "urgent",  # not allowed
        }
        response = await client.post("/api/v1/beam/register", json=payload)
        assert response.status_code == 422


# ─── List / Get ───────────────────────────────────────


class TestListBeams:
    @pytest.mark.asyncio
    async def test_list_beams_empty(self, client: AsyncClient, seed_farm):
        """List beams when none exist for the farm."""
        response = await client.get(f"/api/v1/beam?farm_id={TEST_FARM_ID}")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_beams_with_data(self, client: AsyncClient, seed_beam):
        """List returns the seeded beam."""
        response = await client.get(f"/api/v1/beam?farm_id={TEST_FARM_ID}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["serial_number"] == "BEAM-TEST-001"

    @pytest.mark.asyncio
    async def test_get_beam_success(self, client: AsyncClient, seed_beam):
        """Get a single beam by serial."""
        response = await client.get("/api/v1/beam/BEAM-TEST-001")
        assert response.status_code == 200
        assert response.json()["name"] == "Main Gate Beam"

    @pytest.mark.asyncio
    async def test_get_beam_not_found(self, client: AsyncClient, seed_farm):
        """Unknown serial returns 404."""
        response = await client.get("/api/v1/beam/NOPE-999")
        assert response.status_code == 404


# ─── Crossing Event Ingestion ─────────────────────────


class TestBeamEvent:
    @pytest.mark.asyncio
    async def test_event_creates_alert(self, client: AsyncClient, seed_beam):
        """A crossing on an alerting beam is accepted and creates an alert."""
        payload = {
            "beam_serial": "BEAM-TEST-001",
            "direction": "out",
            "confidence": 0.92,
            "battery_pct": 88,
        }
        response = await client.post("/api/v1/beam/event", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["accepted"] is True
        assert data["alert_created"] is True
        assert data["alert_id"]

    @pytest.mark.asyncio
    async def test_event_persists_crossing_and_alert(self, client: AsyncClient, seed_beam):
        """The crossing row and beam_crossing alert are persisted."""
        payload = {"beam_serial": "BEAM-TEST-001", "direction": "in", "confidence": 0.8}
        response = await client.post("/api/v1/beam/event", json=payload)
        assert response.status_code == 200

        # Query the DB directly via the test session factory.
        from tests.conftest import test_session_factory
        async with test_session_factory() as db:
            n_cross = (await db.execute(text("SELECT COUNT(*) FROM beam_crossings"))).scalar_one()
            alert = (await db.execute(text(
                "SELECT alert_type, severity FROM alerts WHERE alert_type = 'beam_crossing'"
            ))).first()
        assert n_cross >= 1
        assert alert is not None
        assert alert[0] == "beam_crossing"
        assert alert[1] == "high"

    @pytest.mark.asyncio
    async def test_event_unknown_beam(self, client: AsyncClient, seed_farm):
        """A crossing from an unregistered beam is rejected."""
        payload = {"beam_serial": "GHOST-BEAM", "direction": "unknown"}
        response = await client.post("/api/v1/beam/event", json=payload)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_event_no_alert_when_disabled(self, client: AsyncClient, db_session, seed_farm):
        """A beam with alert_on_crossing=False stores the crossing but creates no alert."""
        beam = BeamSensor(
            farm_id=TEST_FARM_ID,
            serial_number="BEAM-QUIET-001",
            name="Silent Beam",
            beam_type="infrared",
            latitude=-25.0,
            longitude=25.0,
            breach_severity="low",
            alert_on_crossing=False,
            status="active",
        )
        db_session.add(beam)
        await db_session.commit()

        payload = {"beam_serial": "BEAM-QUIET-001", "direction": "out"}
        response = await client.post("/api/v1/beam/event", json=payload)
        assert response.status_code == 200
        assert response.json()["alert_created"] is False

    @pytest.mark.asyncio
    async def test_event_invalid_direction(self, client: AsyncClient, seed_beam):
        """An invalid direction is rejected."""
        payload = {"beam_serial": "BEAM-TEST-001", "direction": "sideways"}
        response = await client.post("/api/v1/beam/event", json=payload)
        assert response.status_code == 422
