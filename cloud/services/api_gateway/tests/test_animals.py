"""Tests for animals endpoints (CRUD, history)."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import TEST_FARM_ID, TEST_ANIMAL_ID


@pytest.mark.asyncio
class TestListAnimals:
    """GET /api/animals"""

    async def test_list_animals_empty(self, client: AsyncClient, seed_farm):
        """Empty farm returns empty list."""
        resp = await client.get("/api/animals", params={"farm_id": str(TEST_FARM_ID)})
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_animals_with_data(self, client: AsyncClient, seed_animal):
        """Farm with animals returns them."""
        resp = await client.get("/api/animals", params={"farm_id": str(TEST_FARM_ID)})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Bella"
        assert data[0]["tag_id"] == "LG-001"
        assert data[0]["species"] == "cattle"
        assert data[0]["breed"] == "Angus"

    async def test_list_animals_filter_by_species(self, client: AsyncClient, seed_animal):
        """Species filter works."""
        resp = await client.get("/api/animals", params={
            "farm_id": str(TEST_FARM_ID),
            "species": "sheep",
        })
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_animals_pagination(self, client: AsyncClient, seed_animal):
        """Limit and offset work."""
        resp = await client.get("/api/animals", params={
            "farm_id": str(TEST_FARM_ID),
            "limit": 1,
            "offset": 0,
        })
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        resp = await client.get("/api/animals", params={
            "farm_id": str(TEST_FARM_ID),
            "limit": 1,
            "offset": 10,
        })
        assert resp.status_code == 200
        assert len(resp.json()) == 0


@pytest.mark.asyncio
class TestCreateAnimal:
    """POST /api/animals"""

    async def test_create_animal_success(self, client: AsyncClient, seed_farm):
        """Valid payload creates an animal."""
        resp = await client.post("/api/animals", json={
            "name": "Duke",
            "tag_id": "LG-002",
            "species": "cattle",
            "breed": "Hereford",
            "farm_id": str(TEST_FARM_ID),
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Duke"
        assert data["tag_id"] == "LG-002"
        assert data["breed"] == "Hereford"
        assert "id" in data

    async def test_create_animal_minimal_fields(self, client: AsyncClient, seed_farm):
        """Only required fields creates successfully."""
        resp = await client.post("/api/animals", json={
            "name": "Rosie",
            "tag_id": "LG-003",
            "farm_id": str(TEST_FARM_ID),
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["species"] == "cattle"  # default
        assert data["breed"] is None

    async def test_create_animal_missing_name(self, client: AsyncClient, seed_farm):
        """Missing required field returns 422."""
        resp = await client.post("/api/animals", json={
            "tag_id": "LG-004",
            "farm_id": str(TEST_FARM_ID),
        })
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestGetAnimal:
    """GET /api/animals/{animal_id}"""

    async def test_get_animal_success(self, client: AsyncClient, seed_animal):
        """Existing animal returns details."""
        resp = await client.get(f"/api/animals/{TEST_ANIMAL_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Bella"
        assert data["id"] == str(TEST_ANIMAL_ID)

    async def test_get_animal_not_found(self, client: AsyncClient, seed_farm):
        """Non-existent animal returns 404."""
        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/animals/{fake_id}")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
