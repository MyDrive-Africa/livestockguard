"""Tests for alert endpoints (list, acknowledge, resolve)."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import TEST_FARM_ID, TEST_ALERT_ID


@pytest.mark.asyncio
class TestListAlerts:
    """GET /api/alerts"""

    async def test_list_alerts_empty(self, client: AsyncClient, seed_farm):
        """No alerts returns empty list."""
        resp = await client.get("/api/alerts", params={"farm_id": str(TEST_FARM_ID)})
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_alerts_with_data(self, client: AsyncClient, seed_alert):
        """Farm with alerts returns them."""
        resp = await client.get("/api/alerts", params={"farm_id": str(TEST_FARM_ID)})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["alert_type"] == "geofence_breach"
        assert data[0]["severity"] == "high"
        assert data[0]["status"] == "active"
        assert data[0]["animal_name"] == "Bella"

    async def test_list_alerts_filter_severity(self, client: AsyncClient, seed_alert):
        """Severity filter returns matching alerts."""
        resp = await client.get("/api/alerts", params={
            "farm_id": str(TEST_FARM_ID),
            "severity": "high",
        })
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        resp = await client.get("/api/alerts", params={
            "farm_id": str(TEST_FARM_ID),
            "severity": "low",
        })
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    async def test_list_alerts_filter_status(self, client: AsyncClient, seed_alert):
        """Status filter returns matching alerts."""
        resp = await client.get("/api/alerts", params={
            "farm_id": str(TEST_FARM_ID),
            "status": "active",
        })
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        resp = await client.get("/api/alerts", params={
            "farm_id": str(TEST_FARM_ID),
            "status": "resolved",
        })
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    async def test_list_alerts_pagination(self, client: AsyncClient, seed_alert):
        """Limit and offset work."""
        resp = await client.get("/api/alerts", params={
            "farm_id": str(TEST_FARM_ID),
            "limit": 1,
            "offset": 0,
        })
        assert resp.status_code == 200
        assert len(resp.json()) == 1


@pytest.mark.asyncio
class TestAcknowledgeAlert:
    """PUT /api/alerts/{alert_id}/acknowledge"""

    async def test_acknowledge_success(self, client: AsyncClient, seed_alert):
        """Active alert can be acknowledged."""
        resp = await client.put(f"/api/alerts/{TEST_ALERT_ID}/acknowledge")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "acknowledged"
        assert data["id"] == str(TEST_ALERT_ID)

        # Verify state change persisted
        list_resp = await client.get("/api/alerts", params={
            "farm_id": str(TEST_FARM_ID),
            "status": "acknowledged",
        })
        assert len(list_resp.json()) == 1

    async def test_acknowledge_not_found(self, client: AsyncClient, seed_farm):
        """Non-existent alert returns 404."""
        fake_id = uuid.uuid4()
        resp = await client.put(f"/api/alerts/{fake_id}/acknowledge")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestResolveAlert:
    """PUT /api/alerts/{alert_id}/resolve"""

    async def test_resolve_success(self, client: AsyncClient, seed_alert):
        """Active alert can be resolved."""
        resp = await client.put(f"/api/alerts/{TEST_ALERT_ID}/resolve")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["id"] == str(TEST_ALERT_ID)

    async def test_resolve_not_found(self, client: AsyncClient, seed_farm):
        """Non-existent alert returns 404."""
        fake_id = uuid.uuid4()
        resp = await client.put(f"/api/alerts/{fake_id}/resolve")
        assert resp.status_code == 404
