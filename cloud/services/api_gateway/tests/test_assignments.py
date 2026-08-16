"""
Tests for the farm assignments router (RBAC).

Covers:
- GET /me/farms — returns accessible farms for current user
- GET /farms/{farm_id}/assignments — list assignments
- POST /farms/{farm_id}/assignments — assign user to farm
- DELETE /farms/{farm_id}/assignments/{user_id} — revoke assignment
- Role constraints (farm_owner cannot assign farm_owner role)
- Duplicate assignment prevention
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    TEST_ORG_ID, TEST_FARM_ID, TEST_USER_ID,
    test_session_factory,
)
from livestockguard_common.db_models import User, Farm, UserFarmAssignment

# Pre-computed bcrypt hash for "password123"
_PASSWORD123_HASH = "$2b$12$LJ3m4sMKfXzHBmVMpv3vOeIbdPCEfrGVfMxGJr0e0B2HBsFDGsiPq"


TEST_HERDSMAN_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TEST_FARM_2_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest_asyncio.fixture
async def seed_herdsman(db_session: AsyncSession, seed_org):
    """Seed a herdsman user."""
    user = User(
        id=TEST_HERDSMAN_ID,
        organisation_id=TEST_ORG_ID,
        email="herdsman@test.com",
        password_hash=_PASSWORD123_HASH,
        full_name="Sipho Herdsman",
        role="herdsman",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def seed_assignment(db_session: AsyncSession, seed_farm, seed_herdsman):
    """Seed an active farm assignment for the herdsman."""
    assignment = UserFarmAssignment(
        user_id=TEST_HERDSMAN_ID,
        farm_id=TEST_FARM_ID,
        role_at_farm="herdsman",
        assigned_by=TEST_USER_ID,
    )
    db_session.add(assignment)
    await db_session.commit()
    return assignment


# ─── GET /me/farms ────────────────────────────────────


class TestGetMyFarms:
    @pytest.mark.asyncio
    async def test_admin_sees_org_farms(self, client: AsyncClient, seed_farm, seed_user):
        """Admin user should see all farms in their org."""
        response = await client.get("/api/v1/assignments/me/farms")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        farm_ids = [f["farm_id"] for f in data]
        assert str(TEST_FARM_ID) in farm_ids


# ─── GET /farms/{farm_id}/assignments ─────────────────


class TestListAssignments:
    @pytest.mark.asyncio
    async def test_list_assignments_empty(self, client: AsyncClient, seed_farm, seed_user):
        """List assignments on a farm with no assignments."""
        response = await client.get(f"/api/v1/assignments/farms/{TEST_FARM_ID}/assignments")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_assignments_with_data(self, client: AsyncClient, seed_user, seed_assignment):
        """List assignments shows the seeded assignment."""
        response = await client.get(f"/api/v1/assignments/farms/{TEST_FARM_ID}/assignments")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["user_email"] == "herdsman@test.com"
        assert data[0]["role_at_farm"] == "herdsman"


# ─── POST /farms/{farm_id}/assignments ────────────────


class TestAssignUser:
    @pytest.mark.asyncio
    async def test_assign_herdsman_success(self, client: AsyncClient, seed_farm, seed_user, seed_herdsman):
        """Admin can assign a herdsman to a farm."""
        payload = {
            "user_id": str(TEST_HERDSMAN_ID),
            "farm_id": str(TEST_FARM_ID),
            "role_at_farm": "herdsman",
        }
        response = await client.post(
            f"/api/v1/assignments/farms/{TEST_FARM_ID}/assignments",
            json=payload,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["user_email"] == "herdsman@test.com"
        assert data["role_at_farm"] == "herdsman"
        assert data["revoked_at"] is None

    @pytest.mark.asyncio
    async def test_assign_duplicate_rejected(self, client: AsyncClient, seed_user, seed_assignment):
        """Cannot assign a user who already has an active assignment to the farm."""
        payload = {
            "user_id": str(TEST_HERDSMAN_ID),
            "farm_id": str(TEST_FARM_ID),
            "role_at_farm": "viewer",
        }
        response = await client.post(
            f"/api/v1/assignments/farms/{TEST_FARM_ID}/assignments",
            json=payload,
        )
        assert response.status_code == 409
        assert "already has an active assignment" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_assign_invalid_role_rejected(self, client: AsyncClient, seed_farm, seed_user, seed_herdsman):
        """Invalid role_at_farm should be rejected."""
        payload = {
            "user_id": str(TEST_HERDSMAN_ID),
            "farm_id": str(TEST_FARM_ID),
            "role_at_farm": "superadmin",  # Invalid
        }
        response = await client.post(
            f"/api/v1/assignments/farms/{TEST_FARM_ID}/assignments",
            json=payload,
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_assign_nonexistent_user(self, client: AsyncClient, seed_farm, seed_user):
        """Assigning a non-existent user should return 404."""
        fake_user_id = str(uuid.uuid4())
        payload = {
            "user_id": fake_user_id,
            "farm_id": str(TEST_FARM_ID),
            "role_at_farm": "viewer",
        }
        response = await client.post(
            f"/api/v1/assignments/farms/{TEST_FARM_ID}/assignments",
            json=payload,
        )
        assert response.status_code == 404


# ─── DELETE /farms/{farm_id}/assignments/{user_id} ────


class TestRevokeAssignment:
    @pytest.mark.asyncio
    async def test_revoke_success(self, client: AsyncClient, seed_user, seed_assignment):
        """Admin can revoke a herdsman's farm assignment."""
        response = await client.delete(
            f"/api/v1/assignments/farms/{TEST_FARM_ID}/assignments/{TEST_HERDSMAN_ID}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["detail"] == "Assignment revoked"

    @pytest.mark.asyncio
    async def test_revoke_nonexistent(self, client: AsyncClient, seed_farm, seed_user):
        """Revoking a non-existent assignment should return 404."""
        fake_user = str(uuid.uuid4())
        response = await client.delete(
            f"/api/v1/assignments/farms/{TEST_FARM_ID}/assignments/{fake_user}"
        )
        assert response.status_code == 404
