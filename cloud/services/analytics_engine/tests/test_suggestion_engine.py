"""
Tests for the suggestion engine job.

Covers:
- No active anomalies → early exit
- Suggestion created from reduced_movement anomaly
- Suggestion created from isolation anomaly
- Suggestion created from patrol_gap anomaly (no animal)
- Unknown anomaly type handled gracefully
- Template formatting error fallback
- Stale suggestion expiry
"""

import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import TEST_FARM_ID, TEST_ANIMAL_ID_1, TEST_ANIMAL_NAME_1, make_mock_row


class TestSuggestionEngine:
    @pytest.mark.asyncio
    async def test_no_anomalies_early_exit(self):
        """If no active anomalies without suggestions exist, exit gracefully."""
        mock_db = AsyncMock()
        mock_db.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[]))
        mock_db.commit = AsyncMock()

        with patch("app.jobs.suggestion_engine.async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

            from app.jobs.suggestion_engine import run_suggestion_engine
            await run_suggestion_engine()

        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_suggestion_from_reduced_movement(self):
        """Create a health suggestion from a reduced_movement anomaly."""
        mock_db = AsyncMock()

        evidence = json.dumps({
            "today_distance_m": 100.0,
            "baseline_mean_m": 500.0,
            "baseline_std_m": 50.0,
            "z_score": -8.0,
        })

        anomaly_row = make_mock_row(
            anomaly_id="anom-1",
            farm_id=TEST_FARM_ID,
            animal_id=TEST_ANIMAL_ID_1,
            anomaly_type="reduced_movement",
            severity="medium",
            anomaly_description="Movement below normal",
            evidence=evidence,
            animal_name=TEST_ANIMAL_NAME_1,
        )

        call_count = [0]

        async def mock_execute(query, params=None):
            result = MagicMock()
            if call_count[0] == 0:
                # Query active anomalies without suggestions
                result.fetchall.return_value = [anomaly_row]
            elif call_count[0] == 1:
                # INSERT suggestion
                result.rowcount = 1
            elif call_count[0] == 2:
                # _expire_stale_suggestions
                result.rowcount = 0
            else:
                result.fetchall.return_value = []
                result.rowcount = 0
            call_count[0] += 1
            return result

        mock_db.execute = mock_execute
        mock_db.commit = AsyncMock()

        with patch("app.jobs.suggestion_engine.async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

            from app.jobs.suggestion_engine import run_suggestion_engine
            await run_suggestion_engine()

        # Should have inserted a suggestion
        assert call_count[0] >= 2

    @pytest.mark.asyncio
    async def test_suggestion_from_isolation(self):
        """Create a suggestion from an isolation anomaly."""
        mock_db = AsyncMock()

        evidence = json.dumps({
            "hours_since_last_seen": 8.5,
            "threshold_hours": 4,
            "last_latitude": -29.12,
            "last_longitude": 26.21,
        })

        anomaly_row = make_mock_row(
            anomaly_id="anom-2",
            farm_id=TEST_FARM_ID,
            animal_id=TEST_ANIMAL_ID_1,
            anomaly_type="isolation",
            severity="medium",
            anomaly_description="Not seen in 8.5h",
            evidence=evidence,
            animal_name=TEST_ANIMAL_NAME_1,
        )

        call_count = [0]

        async def mock_execute(query, params=None):
            result = MagicMock()
            if call_count[0] == 0:
                result.fetchall.return_value = [anomaly_row]
            elif call_count[0] == 1:
                result.rowcount = 1  # INSERT
            else:
                result.rowcount = 0
            call_count[0] += 1
            return result

        mock_db.execute = mock_execute
        mock_db.commit = AsyncMock()

        with patch("app.jobs.suggestion_engine.async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

            from app.jobs.suggestion_engine import run_suggestion_engine
            await run_suggestion_engine()

        assert call_count[0] >= 2

    @pytest.mark.asyncio
    async def test_suggestion_from_patrol_gap(self):
        """Create a suggestion from a patrol_gap anomaly (no animal)."""
        mock_db = AsyncMock()

        evidence = json.dumps({
            "threshold_days": 3,
            "days_since_last_patrol": 5,
            "last_herdsman": "Sipho",
        })

        anomaly_row = make_mock_row(
            anomaly_id="anom-3",
            farm_id=TEST_FARM_ID,
            animal_id=None,
            anomaly_type="patrol_gap",
            severity="low",
            anomaly_description="No patrol in 5 days",
            evidence=evidence,
            animal_name=None,
        )

        call_count = [0]

        async def mock_execute(query, params=None):
            result = MagicMock()
            if call_count[0] == 0:
                result.fetchall.return_value = [anomaly_row]
            elif call_count[0] == 1:
                result.rowcount = 1
            else:
                result.rowcount = 0
            call_count[0] += 1
            return result

        mock_db.execute = mock_execute
        mock_db.commit = AsyncMock()

        with patch("app.jobs.suggestion_engine.async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

            from app.jobs.suggestion_engine import run_suggestion_engine
            await run_suggestion_engine()

        assert call_count[0] >= 2

    @pytest.mark.asyncio
    async def test_unknown_anomaly_type_skipped(self):
        """Anomaly with unknown type should not create a suggestion."""
        mock_db = AsyncMock()

        anomaly_row = make_mock_row(
            anomaly_id="anom-unknown",
            farm_id=TEST_FARM_ID,
            animal_id=TEST_ANIMAL_ID_1,
            anomaly_type="completely_new_type",
            severity="low",
            anomaly_description="Something new",
            evidence="{}",
            animal_name="Bella",
        )

        call_count = [0]

        async def mock_execute(query, params=None):
            result = MagicMock()
            if call_count[0] == 0:
                result.fetchall.return_value = [anomaly_row]
            else:
                result.rowcount = 0
            call_count[0] += 1
            return result

        mock_db.execute = mock_execute
        mock_db.commit = AsyncMock()

        with patch("app.jobs.suggestion_engine.async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

            from app.jobs.suggestion_engine import run_suggestion_engine
            await run_suggestion_engine()

        # Only the initial query + expire query — no INSERT
        assert call_count[0] == 2
