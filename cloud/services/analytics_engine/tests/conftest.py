"""
Shared test fixtures for analytics engine tests.

Patches the async_session in app.db to use an in-memory SQLite database.
Since analytics jobs use raw SQL (text()), tests mock at the session level.
"""

import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Ensure app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Override config before importing app modules
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["RUN_ON_STARTUP"] = "false"

# Patch app.db module before any job imports it
# The real db.py calls create_async_engine with pool_size/max_overflow which SQLite rejects.
# We replace the module-level engine and session factory with a mock.
import types

mock_db_module = types.ModuleType("app.db")
mock_db_module.async_session = MagicMock()  # Will be overridden in tests
mock_db_module.engine = MagicMock()
sys.modules["app.db"] = mock_db_module


# ─── Test Data ────────────────────────────────────────

TEST_FARM_ID = "22222222-2222-2222-2222-222222222222"
TEST_FARM_NAME = "Test Farm"
TEST_ANIMAL_ID_1 = "44444444-4444-4444-4444-444444444444"
TEST_ANIMAL_ID_2 = "44444444-4444-4444-4444-444444444445"
TEST_ANIMAL_NAME_1 = "Bella"
TEST_ANIMAL_NAME_2 = "Daisy"
TEST_GATEWAY_ID = "55555555-5555-5555-5555-555555555555"


def make_mock_row(**kwargs):
    """Create a mock database row with attribute access."""
    row = MagicMock()
    for key, value in kwargs.items():
        setattr(row, key, value)
    return row


def make_mock_result(rows):
    """Create a mock query result that supports fetchall() and first()."""
    result = MagicMock()
    result.fetchall.return_value = rows
    result.first.return_value = rows[0] if rows else None
    return result
