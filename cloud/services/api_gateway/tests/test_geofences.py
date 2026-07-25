"""Tests for geofence endpoints (CRUD, point-in-polygon)."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import TEST_FARM_ID, TEST_GEOFENCE_ID

VALID_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[26.200, -29.110], [26.220, -29.110], [26.220, -29.125], [26.200, -29.125], [26.200, -29.110]]],
}


@pytest.mark.asyncio
class TestListGeofences:
    """GET /api/geofences"""

    async def test_list_geofences_empty(self, client: AsyncClient, seed_farm):
        """No geofences returns empty list."""
        resp = await client.get("/api/geofences", params={"farm_id": str(TEST_FARM_ID)})
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_geofences_with_data(self, client: AsyncClient, seed_geofence):
        """Farm with geofences returns them."""
        resp = await client.get("/api/geofences", params={"farm_id": str(TEST_FARM_ID)})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Main Paddock"
        assert data[0]["fence_type"] == "inclusion"
        assert data[0]["active"] is True

    async def test_list_geofences_filter_active(self, client: AsyncClient, seed_geofence):
        """Active filter works."""
        resp = await client.get("/api/geofences", params={
            "farm_id": str(TEST_FARM_ID),
            "active": "true",
        })
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        resp = await client.get("/api/geofences", params={
            "farm_id": str(TEST_FARM_ID),
            "active": "false",
        })
        assert resp.status_code == 200
        assert len(resp.json()) == 0


@pytest.mark.asyncio
class TestCreateGeofence:
    """POST /api/geofences"""

    async def test_create_geofence_success(self, client: AsyncClient, seed_farm):
        """Valid polygon geofence is created."""
        resp = await client.post("/api/geofences", json={
            "name": "New Paddock",
            "farm_id": str(TEST_FARM_ID),
            "geometry": VALID_POLYGON,
            "fence_type": "inclusion",
            "active": True,
            "alert_on_breach": True,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "New Paddock"
        assert data["fence_type"] == "inclusion"
        assert data["active"] is True
        assert "id" in data

    async def test_create_geofence_exclusion(self, client: AsyncClient, seed_farm):
        """Exclusion type geofence created."""
        resp = await client.post("/api/geofences", json={
            "name": "Road Boundary",
            "farm_id": str(TEST_FARM_ID),
            "geometry": VALID_POLYGON,
            "fence_type": "exclusion",
        })
        assert resp.status_code == 201
        assert resp.json()["fence_type"] == "exclusion"

    async def test_create_geofence_invalid_geometry(self, client: AsyncClient, seed_farm):
        """Non-polygon geometry returns 422."""
        resp = await client.post("/api/geofences", json={
            "name": "Bad Geofence",
            "farm_id": str(TEST_FARM_ID),
            "geometry": {"type": "Point", "coordinates": [26.21, -29.12]},
        })
        assert resp.status_code == 422
        assert "Polygon" in resp.json()["detail"]

    async def test_create_geofence_empty_coordinates(self, client: AsyncClient, seed_farm):
        """Polygon with no coordinates returns 422."""
        resp = await client.post("/api/geofences", json={
            "name": "Empty",
            "farm_id": str(TEST_FARM_ID),
            "geometry": {"type": "Polygon", "coordinates": []},
        })
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestGetGeofence:
    """GET /api/geofences/{geofence_id}"""

    async def test_get_geofence_success(self, client: AsyncClient, seed_geofence):
        """Existing geofence returns details."""
        resp = await client.get(f"/api/geofences/{TEST_GEOFENCE_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Main Paddock"

    async def test_get_geofence_not_found(self, client: AsyncClient, seed_farm):
        """Non-existent geofence returns 404."""
        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/geofences/{fake_id}")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestUpdateGeofence:
    """PUT /api/geofences/{geofence_id}"""

    async def test_update_name(self, client: AsyncClient, seed_geofence):
        """Update geofence name."""
        resp = await client.put(f"/api/geofences/{TEST_GEOFENCE_ID}", json={
            "name": "Updated Paddock",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Paddock"

    async def test_update_active_status(self, client: AsyncClient, seed_geofence):
        """Deactivate a geofence."""
        resp = await client.put(f"/api/geofences/{TEST_GEOFENCE_ID}", json={
            "active": False,
        })
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    async def test_update_not_found(self, client: AsyncClient, seed_farm):
        """Non-existent geofence returns 404."""
        fake_id = uuid.uuid4()
        resp = await client.put(f"/api/geofences/{fake_id}", json={"name": "X"})
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestDeleteGeofence:
    """DELETE /api/geofences/{geofence_id}"""

    async def test_delete_success(self, client: AsyncClient, seed_geofence):
        """Delete an existing geofence."""
        resp = await client.delete(f"/api/geofences/{TEST_GEOFENCE_ID}")
        assert resp.status_code == 204

        # Verify it's gone
        get_resp = await client.get(f"/api/geofences/{TEST_GEOFENCE_ID}")
        assert get_resp.status_code == 404

    async def test_delete_not_found(self, client: AsyncClient, seed_farm):
        """Non-existent geofence returns 404."""
        fake_id = uuid.uuid4()
        resp = await client.delete(f"/api/geofences/{fake_id}")
        assert resp.status_code == 404
