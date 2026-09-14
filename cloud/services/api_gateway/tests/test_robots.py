"""
Tests for the herding robots router.

Covers:
- Robot registration (success, duplicate serial, invalid model)
- List robots (empty, with data, filter by farm)
- Get one robot (success, not found)
- Manual command (accepted; move_to without coords rejected; unknown robot 404)
- Herding status summary and stop-all

Runs against the in-memory SQLite harness. The MQTT publish in the command
handlers is wrapped so it is a safe no-op without a live broker — commands are
accepted and reported as published=False when no broker is reachable.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TEST_FARM_ID
from livestockguard_common.db_models import HerdingRobot


TEST_ROBOT_ID = uuid.UUID("cccccccc-0000-0000-0000-000000000001")


@pytest_asyncio.fixture
async def seed_robot(db_session: AsyncSession, seed_farm):
    """Seed one active herding robot."""
    robot = HerdingRobot(
        id=TEST_ROBOT_ID,
        farm_id=TEST_FARM_ID,
        serial_number="ROBO-TEST-01",
        name="Herder 1",
        model="wheeled",
        status="patrolling",
        last_latitude=-26.7191,
        last_longitude=27.7098,
        battery_pct=88,
        max_speed_mps=2.0,
    )
    db_session.add(robot)
    await db_session.commit()
    return robot


class TestRobotRegistration:
    @pytest.mark.asyncio
    async def test_register_robot_success(self, client: AsyncClient, seed_farm):
        payload = {
            "farm_id": str(TEST_FARM_ID),
            "serial_number": "ROBO-NEW-01",
            "name": "Herder 2",
            "model": "quadruped",
            "home_latitude": -26.72,
            "home_longitude": 27.71,
        }
        response = await client.post("/api/v1/robots/register", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["serial_number"] == "ROBO-NEW-01"
        assert data["model"] == "quadruped"
        assert data["status"] == "offline"

    @pytest.mark.asyncio
    async def test_register_duplicate_serial(self, client: AsyncClient, seed_robot):
        payload = {
            "farm_id": str(TEST_FARM_ID),
            "serial_number": "ROBO-TEST-01",
            "name": "Dup",
        }
        response = await client.post("/api/v1/robots/register", json=payload)
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_register_invalid_model(self, client: AsyncClient, seed_farm):
        payload = {
            "farm_id": str(TEST_FARM_ID),
            "serial_number": "ROBO-BAD-01",
            "name": "Bad",
            "model": "spider",
        }
        response = await client.post("/api/v1/robots/register", json=payload)
        assert response.status_code == 422


class TestRobotRead:
    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient, seed_farm):
        response = await client.get("/api/v1/robots")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_with_data_and_farm_filter(self, client: AsyncClient, seed_robot):
        response = await client.get(f"/api/v1/robots?farm_id={TEST_FARM_ID}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["serial_number"] == "ROBO-TEST-01"

    @pytest.mark.asyncio
    async def test_get_robot_success(self, client: AsyncClient, seed_robot):
        response = await client.get("/api/v1/robots/ROBO-TEST-01")
        assert response.status_code == 200
        assert response.json()["battery_pct"] == 88

    @pytest.mark.asyncio
    async def test_get_robot_not_found(self, client: AsyncClient, seed_farm):
        response = await client.get("/api/v1/robots/NOPE")
        assert response.status_code == 404


class TestRobotCommand:
    @pytest.mark.asyncio
    async def test_command_accepted(self, client: AsyncClient, seed_robot):
        response = await client.post(
            "/api/v1/robots/ROBO-TEST-01/command",
            json={"command": "return_home"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["accepted"] is True
        assert data["command"] == "return_home"
        # published may be False when no broker is running — that's fine.
        assert "published" in data

    @pytest.mark.asyncio
    async def test_move_to_requires_coords(self, client: AsyncClient, seed_robot):
        response = await client.post(
            "/api/v1/robots/ROBO-TEST-01/command",
            json={"command": "move_to"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_command_unknown_robot(self, client: AsyncClient, seed_farm):
        response = await client.post(
            "/api/v1/robots/NOPE/command",
            json={"command": "stop"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_command(self, client: AsyncClient, seed_robot):
        response = await client.post(
            "/api/v1/robots/ROBO-TEST-01/command",
            json={"command": "dance"},
        )
        assert response.status_code == 422


class TestHerdingStatus:
    @pytest.mark.asyncio
    async def test_status_summary(self, client: AsyncClient, seed_robot):
        response = await client.get(f"/api/v1/robots/herding/status?farm_id={TEST_FARM_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["robots_total"] == 1
        assert data["active_jobs"] == 0

    @pytest.mark.asyncio
    async def test_stop_all(self, client: AsyncClient, seed_robot):
        response = await client.post(f"/api/v1/robots/herding/stop-all?farm_id={TEST_FARM_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["robots"] == 1
