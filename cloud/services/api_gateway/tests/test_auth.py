"""Tests for authentication endpoints (login, register, refresh)."""

import pytest
from httpx import AsyncClient
from jose import jwt

from tests.conftest import TEST_ORG_ID

JWT_SECRET = "dev_secret_change_in_production"
JWT_ALGORITHM = "HS256"


@pytest.mark.asyncio
class TestLogin:
    """POST /api/auth/login"""

    async def test_login_success(self, client: AsyncClient, seed_user):
        """Valid credentials return tokens."""
        resp = await client.post("/api/auth/login", json={
            "email": "farmer@test.com",
            "password": "password123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

        # Verify token payload
        payload = jwt.decode(data["access_token"], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert payload["email"] == "farmer@test.com"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"

    async def test_login_wrong_password(self, client: AsyncClient, seed_user):
        """Wrong password returns 401."""
        resp = await client.post("/api/auth/login", json={
            "email": "farmer@test.com",
            "password": "wrong_password",
        })
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["detail"]

    async def test_login_nonexistent_user(self, client: AsyncClient, seed_org):
        """Unknown email returns 401."""
        resp = await client.post("/api/auth/login", json={
            "email": "nobody@test.com",
            "password": "password123",
        })
        assert resp.status_code == 401

    async def test_login_invalid_email_format(self, client: AsyncClient):
        """Malformed email returns 422 validation error."""
        resp = await client.post("/api/auth/login", json={
            "email": "not-an-email",
            "password": "password123",
        })
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestRegister:
    """POST /api/auth/register"""

    async def test_register_success(self, client: AsyncClient, seed_org):
        """New user registration returns tokens."""
        resp = await client.post("/api/auth/register", json={
            "email": "newfarmer@test.com",
            "password": "securepass456",
            "full_name": "New Farmer",
            "organisation_id": str(TEST_ORG_ID),
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_register_duplicate_email(self, client: AsyncClient, seed_user):
        """Duplicate email returns 409."""
        resp = await client.post("/api/auth/register", json={
            "email": "farmer@test.com",
            "password": "anotherpass",
            "full_name": "Duplicate Farmer",
            "organisation_id": str(TEST_ORG_ID),
        })
        assert resp.status_code == 409
        assert "already registered" in resp.json()["detail"]

    async def test_register_missing_fields(self, client: AsyncClient):
        """Missing required fields returns 422."""
        resp = await client.post("/api/auth/register", json={
            "email": "test@test.com",
        })
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestRefresh:
    """POST /api/auth/refresh"""

    async def test_refresh_token_success(self, client: AsyncClient, seed_user):
        """Valid refresh token returns new token pair."""
        # First login to get a refresh token
        login_resp = await client.post("/api/auth/login", json={
            "email": "farmer@test.com",
            "password": "password123",
        })
        refresh_token = login_resp.json()["refresh_token"]

        # Use refresh token
        resp = await client.post("/api/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_invalid_token(self, client: AsyncClient):
        """Invalid refresh token returns 401."""
        resp = await client.post("/api/auth/refresh", json={
            "refresh_token": "invalid.token.here",
        })
        assert resp.status_code == 401

    async def test_refresh_with_access_token_fails(self, client: AsyncClient, seed_user):
        """Access token used as refresh token fails (wrong type)."""
        login_resp = await client.post("/api/auth/login", json={
            "email": "farmer@test.com",
            "password": "password123",
        })
        access_token = login_resp.json()["access_token"]

        resp = await client.post("/api/auth/refresh", json={
            "refresh_token": access_token,
        })
        assert resp.status_code == 401
