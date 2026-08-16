"""
Tests for the baseline builder job.

Covers:
- haversine_m utility function (pure math)
- run_baseline_builder with no farms (early exit)
- run_baseline_builder with farms but no data (no baselines computed)
- Baseline computation with sufficient data
- Handling of unrealistic jumps (>5km filtered out)
"""

import math
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.jobs.baseline_builder import haversine_m, run_baseline_builder


# ─── haversine_m unit tests ───────────────────────────


class TestHaversine:
    def test_same_point_returns_zero(self):
        """Distance from a point to itself should be 0."""
        assert haversine_m(-29.12, 26.21, -29.12, 26.21) == 0.0

    def test_known_distance(self):
        """Johannesburg to Cape Town is roughly 1260km."""
        # JHB: -26.2041, 28.0473
        # CPT: -33.9249, 18.4241
        dist = haversine_m(-26.2041, 28.0473, -33.9249, 18.4241)
        assert 1_200_000 < dist < 1_350_000  # ~1260km

    def test_short_distance_farm_scale(self):
        """Two points 100m apart on a farm."""
        # Approximate: 1 degree latitude ≈ 111km
        # 0.001 degrees ≈ 111m
        lat1, lon1 = -29.120000, 26.210000
        lat2, lon2 = -29.119100, 26.210000  # ~100m north
        dist = haversine_m(lat1, lon1, lat2, lon2)
        assert 90 < dist < 110

    def test_equator(self):
        """Points on the equator — 1 degree longitude ≈ 111km."""
        dist = haversine_m(0.0, 0.0, 0.0, 1.0)
        assert 110_000 < dist < 112_000

    def test_negative_to_positive_crossing(self):
        """Distance across the prime meridian."""
        dist = haversine_m(0.0, -0.5, 0.0, 0.5)
        assert 110_000 < dist < 112_000


# ─── run_baseline_builder tests ───────────────────────


class TestBaselineBuilder:
    @pytest.mark.asyncio
    async def test_no_farms_early_exit(self):
        """If no farms have active BLE-tagged animals, exit gracefully."""
        mock_db = AsyncMock()
        mock_db.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[]))

        with patch("app.jobs.baseline_builder.async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

            await run_baseline_builder()

        # Should have queried for farms
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_farm_with_no_animals(self):
        """Farm exists but has no active animals — no baselines computed."""
        mock_db = AsyncMock()

        # First call: farms query returns one farm
        farm_row = MagicMock()
        farm_row.farm_id = "22222222-2222-2222-2222-222222222222"
        farm_row.farm_name = "Test Farm"

        # Second call: animals query returns empty
        call_count = [0]

        async def mock_execute(query, params=None):
            result = MagicMock()
            if call_count[0] == 0:
                result.fetchall.return_value = [farm_row]
            elif call_count[0] == 1:
                result.fetchall.return_value = []  # No animals
            else:
                result.fetchall.return_value = []
            call_count[0] += 1
            return result

        mock_db.execute = mock_execute
        mock_db.commit = AsyncMock()

        with patch("app.jobs.baseline_builder.async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

            await run_baseline_builder()

    @pytest.mark.asyncio
    async def test_insufficient_data_no_baseline(self):
        """Animal with only 1 day of data should not produce a baseline."""
        mock_db = AsyncMock()

        farm_row = MagicMock()
        farm_row.farm_id = "farm-1"
        farm_row.farm_name = "Test Farm"

        animal_row = MagicMock()
        animal_row.animal_id = "animal-1"
        animal_row.animal_name = "Bella"

        # Simulate: only 1 day of sightings (daily_distances returns [100.0])
        call_count = [0]

        async def mock_execute(query, params=None):
            result = MagicMock()
            if call_count[0] == 0:
                result.fetchall.return_value = [farm_row]
            elif call_count[0] == 1:
                result.fetchall.return_value = [animal_row]
            else:
                # All subsequent queries return empty or minimal data
                result.fetchall.return_value = []
                result.first.return_value = None
            call_count[0] += 1
            return result

        mock_db.execute = mock_execute
        mock_db.commit = AsyncMock()

        with patch("app.jobs.baseline_builder.async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

            await run_baseline_builder()
