"""Tests for analytics endpoints (stub responses)."""

import uuid

import pytest
from httpx import AsyncClient

FARM_ID = str(uuid.uuid4())


@pytest.mark.asyncio
class TestAnalyticsHeatmap:
    """GET /api/analytics/heatmap"""

    async def test_heatmap_returns_structure(self, client: AsyncClient):
        """Heatmap endpoint returns expected structure."""
        resp = await client.get("/api/analytics/heatmap", params={"farm_id": FARM_ID})
        assert resp.status_code == 200
        data = resp.json()
        assert data["farm_id"] == FARM_ID
        assert "cells" in data
        assert "resolution" in data

    async def test_heatmap_custom_resolution(self, client: AsyncClient):
        """Custom resolution param is accepted."""
        resp = await client.get("/api/analytics/heatmap", params={
            "farm_id": FARM_ID,
            "resolution": 100,
        })
        assert resp.status_code == 200
        assert resp.json()["resolution"] == 100

    async def test_heatmap_missing_farm_id(self, client: AsyncClient):
        """Missing farm_id returns 422."""
        resp = await client.get("/api/analytics/heatmap")
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestAnalyticsActivity:
    """GET /api/analytics/activity"""

    async def test_activity_returns_structure(self, client: AsyncClient):
        """Activity endpoint returns expected structure."""
        resp = await client.get("/api/analytics/activity", params={"farm_id": FARM_ID})
        assert resp.status_code == 200
        data = resp.json()
        assert data["farm_id"] == FARM_ID
        assert "data" in data
        assert "interval" in data


@pytest.mark.asyncio
class TestAnalyticsDistance:
    """GET /api/analytics/distance"""

    async def test_distance_returns_structure(self, client: AsyncClient):
        """Distance endpoint returns expected structure."""
        resp = await client.get("/api/analytics/distance", params={"farm_id": FARM_ID})
        assert resp.status_code == 200
        data = resp.json()
        assert data["farm_id"] == FARM_ID
        assert data["interval"] == "1d"


@pytest.mark.asyncio
class TestAnalyticsCompliance:
    """GET /api/analytics/compliance"""

    async def test_compliance_returns_structure(self, client: AsyncClient):
        """Compliance endpoint returns expected structure."""
        resp = await client.get("/api/analytics/compliance", params={"farm_id": FARM_ID})
        assert resp.status_code == 200
        data = resp.json()
        assert data["farm_id"] == FARM_ID
        assert "overall_compliance" in data
        assert "details" in data
