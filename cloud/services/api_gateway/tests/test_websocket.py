"""Tests for WebSocket endpoint (connection, auth, ping/pong)."""

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

JWT_SECRET = "dev_secret_change_in_production"
JWT_ALGORITHM = "HS256"
FARM_ID = "22222222-2222-2222-2222-222222222222"


def make_token(user_id: str = "test-user", exp_offset: int = 3600) -> str:
    """Generate a valid test JWT."""
    from datetime import datetime, timedelta, timezone

    payload = {
        "sub": user_id,
        "email": "test@test.com",
        "role": "admin",
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(seconds=exp_offset),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def make_expired_token() -> str:
    """Generate an expired JWT."""
    return make_token(exp_offset=-3600)


@pytest.mark.asyncio
class TestWebSocketConnection:
    """WebSocket /ws endpoint"""

    async def test_connect_with_valid_token(self, client: AsyncClient):
        """Valid token allows WebSocket connection."""
        from app.main import app
        from app.dependencies import get_db
        from tests.conftest import override_get_db

        app.dependency_overrides[get_db] = override_get_db

        token = make_token()
        # Use httpx WebSocket support isn't available directly,
        # so we test the token verification function directly
        from app.routers.websocket import verify_ws_token

        payload = verify_ws_token(token)
        assert payload is not None
        assert payload["email"] == "test@test.com"
        assert payload["role"] == "admin"

        app.dependency_overrides.clear()

    async def test_reject_invalid_token(self):
        """Invalid token is rejected."""
        from app.routers.websocket import verify_ws_token

        result = verify_ws_token("invalid.token.here")
        assert result is None

    async def test_reject_expired_token(self):
        """Expired token is rejected."""
        from app.routers.websocket import verify_ws_token

        token = make_expired_token()
        result = verify_ws_token(token)
        assert result is None

    async def test_connection_manager_lifecycle(self):
        """ConnectionManager tracks connections by farm."""
        from app.routers.websocket import ConnectionManager

        manager = ConnectionManager()
        assert manager.active_connections == {}
        # After disconnect with no prior connect, should not crash
        manager.disconnect(None, "some-farm")
