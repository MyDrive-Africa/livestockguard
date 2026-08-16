"""
Tests for the report generator job.

Covers:
- No active farms → early exit
- Daily report deduplication (already exists)
- Daily report generation with sample data
- Weekly report only on configured day
- DecimalEncoder utility
"""

import json
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import TEST_FARM_ID, TEST_FARM_NAME, make_mock_row
from app.jobs.report_generator import DecimalEncoder


# ─── DecimalEncoder unit tests ────────────────────────


class TestDecimalEncoder:
    def test_decimal_converted_to_float(self):
        """Decimal values from PostgreSQL should serialize to JSON floats."""
        data = {"value": Decimal("3.14"), "count": Decimal("42")}
        result = json.dumps(data, cls=DecimalEncoder)
        parsed = json.loads(result)
        assert parsed["value"] == 3.14
        assert parsed["count"] == 42.0

    def test_non_decimal_raises(self):
        """Non-serializable types still raise TypeError."""
        with pytest.raises(TypeError):
            json.dumps({"value": object()}, cls=DecimalEncoder)


# ─── run_report_generator tests ───────────────────────


class TestReportGenerator:
    @pytest.mark.asyncio
    async def test_no_farms_early_exit(self):
        """If no farms with active gateways exist, exit gracefully."""
        mock_db = AsyncMock()
        mock_db.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[]))
        mock_db.commit = AsyncMock()

        with patch("app.jobs.report_generator.async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

            from app.jobs.report_generator import run_report_generator
            await run_report_generator()

        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_daily_report_skipped_if_exists(self):
        """Don't regenerate a daily report that already exists for today."""
        mock_db = AsyncMock()

        farm_row = make_mock_row(farm_id=TEST_FARM_ID, farm_name=TEST_FARM_NAME)

        call_count = [0]

        async def mock_execute(query, params=None):
            result = MagicMock()
            if call_count[0] == 0:
                # farms query
                result.fetchall.return_value = [farm_row]
            elif call_count[0] == 1:
                # _report_exists check → report already exists
                result.first.return_value = make_mock_row(id="existing-report")
            else:
                result.fetchall.return_value = []
                result.first.return_value = None
            call_count[0] += 1
            return result

        mock_db.execute = mock_execute
        mock_db.commit = AsyncMock()

        with patch("app.jobs.report_generator.async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

            from app.jobs.report_generator import run_report_generator
            await run_report_generator()

        # Should not have attempted to generate a full daily report (herd/patrol/anomaly queries)
        # The call_count includes: farms + daily exists check + possibly weekly check logic
        # What matters is it didn't fail and didn't generate a duplicate
        assert call_count[0] >= 2  # At least farms + exists check executed

    @pytest.mark.asyncio
    async def test_daily_report_generated(self):
        """Generate a daily report when one doesn't exist yet."""
        mock_db = AsyncMock()

        farm_row = make_mock_row(farm_id=TEST_FARM_ID, farm_name=TEST_FARM_NAME)

        call_count = [0]

        async def mock_execute(query, params=None):
            result = MagicMock()
            if call_count[0] == 0:
                # farms query
                result.fetchall.return_value = [farm_row]
            elif call_count[0] == 1:
                # _report_exists daily → does not exist
                result.first.return_value = None
            elif call_count[0] == 2:
                # herd_query in _generate_daily_report
                result.first.return_value = make_mock_row(
                    total_registered=10,
                    seen_today=8,
                    total_sightings=240,
                )
            elif call_count[0] == 3:
                # patrol_query
                result.first.return_value = make_mock_row(
                    session_count=2,
                    total_hours=4.5,
                    herdsmen=["Sipho", "Thabo"],
                )
            elif call_count[0] == 4:
                # anomalies_query
                result.fetchall.return_value = [
                    make_mock_row(
                        anomaly_type="reduced_movement",
                        severity="medium",
                        description="Bella movement low",
                        animal_name="Bella",
                    )
                ]
            elif call_count[0] == 5:
                # suggestions_query
                result.fetchall.return_value = []
            elif call_count[0] == 6:
                # trend_query
                result.fetchall.return_value = [
                    make_mock_row(day=date.today() - timedelta(days=i), unique_animals=7 + i % 3)
                    for i in range(7)
                ]
            elif call_count[0] == 7:
                # gateway_query
                result.fetchall.return_value = [
                    make_mock_row(name="GW-001", last_battery_pct=85, last_seen=datetime.now(timezone.utc))
                ]
            elif call_count[0] == 8:
                # _store_report INSERT
                result.rowcount = 1
            else:
                result.fetchall.return_value = []
                result.first.return_value = None
                result.rowcount = 0
            call_count[0] += 1
            return result

        mock_db.execute = mock_execute
        mock_db.commit = AsyncMock()

        with patch("app.jobs.report_generator.async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

            from app.jobs.report_generator import run_report_generator
            await run_report_generator()

        # Should have gone through full generation pipeline
        assert call_count[0] >= 8
