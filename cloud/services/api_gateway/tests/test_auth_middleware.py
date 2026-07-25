"""Tests for auth middleware — verifies protected endpoints reject unauthenticated requests."""

import os
import sys

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'shared'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.dependencies import get_db
from tests.conftest import override_get_db, test_engine, test_session_factory
from livestockguard_common.db_models import Base


@pytest_asyncio.fixture
async def unauthed_client():
    """Client WITHOUT auth override — tests real auth enforcement."""
    from app.main import app

    # Only override DB, NOT auth
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
class TestUnauthenticatedRejection:
    """Endpoints reject requests without valid Bearer token."""

    async def test_animals_requires_auth(self, unauthed_client: AsyncClient):
        resp = await unauthed_client.get("/api/animals")
        assert resp.status_code == 401

    async def test_devices_requires_auth(self, unauthed_client: AsyncClient):
        resp = await unauthed_client.get("/api/devices")
        assert resp.status_code == 401

    async def test_alerts_requires_auth(self, unauthed_client: AsyncClient):
        resp = await unauthed_client.get("/api/alerts")
        assert resp.status_code == 401

    async def test_geofences_requires_auth(self, unauthed_client: AsyncClient):
        resp = await unauthed_client.get("/api/geofences")
        assert resp.status_code == 401

    async def test_analytics_requires_auth(self, unauthed_client: AsyncClient):
        resp = await unauthed_client.get("/api/analytics/heatmap?farm_id=11111111-1111-1111-1111-111111111111")
        assert resp.status_code == 401

    async def test_health_is_public(self, unauthed_client: AsyncClient):
        """Health endpoint remains public."""
        resp = await unauthed_client.get("/health")
        assert resp.status_code == 200

    async def test_login_is_public(self, unauthed_client: AsyncClient):
        """Auth endpoints remain public."""
        resp = await unauthed_client.post("/api/auth/login", json={
            "email": "test@test.com",
            "password": "test",
        })
        # 401 from invalid creds, not from missing auth header
        assert resp.status_code == 401
        assert "Invalid email or password" in resp.json()["detail"]

    async def test_invalid_token_rejected(self, unauthed_client: AsyncClient):
        """Malformed token returns 401."""
        resp = await unauthed_client.get(
            "/api/animals",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401

    async def test_expired_token_rejected(self, unauthed_client: AsyncClient):
        """Expired token returns 401."""
        from jose import jwt
        from datetime import datetime, timedelta, timezone

        expired_payload = {
            "sub": "user-1",
            "email": "test@test.com",
            "role": "admin",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        expired_token = jwt.encode(expired_payload, "dev_secret_change_in_production", algorithm="HS256")

        resp = await unauthed_client.get(
            "/api/animals",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401

    async def test_valid_token_accepted(self, unauthed_client: AsyncClient):
        """Valid access token passes auth middleware."""
        from jose import jwt
        from datetime import datetime, timedelta, timezone

        valid_payload = {
            "sub": "user-1",
            "email": "test@test.com",
            "role": "admin",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        valid_token = jwt.encode(valid_payload, "dev_secret_change_in_production", algorithm="HS256")

        resp = await unauthed_client.get(
            "/api/animals",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        # Should pass auth (200 with empty list, not 401)
        assert resp.status_code == 200
