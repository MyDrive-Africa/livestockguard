"""
Shared test fixtures for API gateway tests.

Uses an in-memory SQLite database so tests run without external services.
PostGIS-specific operations are skipped in SQLite mode.
"""

import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Ensure shared lib is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'shared'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from livestockguard_common.db_models import Base, Organisation, Farm, User, Animal, Device, Geofence, Alert
from app.dependencies import get_db, get_current_user

# Pre-computed bcrypt hash for "password123" — avoids runtime dependency on passlib+bcrypt
# which can have compatibility issues across Python versions
_PASSWORD123_HASH = "$2b$12$LJ3m4sMKfXzHBmVMpv3vOeIbdPCEfrGVfMxGJr0e0B2HBsFDGsiPq"


# ─── SQLite Compatibility (PostgreSQL types → SQLite equivalents) ─────────────

from sqlalchemy import event, String, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy import JSON

# ─── SQLite UUID Adapter (Python 3.12+ compatibility) ─────────────

import sqlite3
import uuid as uuid_mod

# Register adapter so SQLite can handle UUID objects as parameters
sqlite3.register_adapter(uuid_mod.UUID, lambda u: str(u))
sqlite3.register_converter("UUID", lambda b: uuid_mod.UUID(b.decode()))


class StringUUID(TypeDecorator):
    """Store UUIDs as strings in SQLite while accepting UUID objects."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return str(value)
        return value


@event.listens_for(Base.metadata, "before_create")
def _patch_pg_types_for_sqlite(target, connection, **kw):
    """Replace PostgreSQL-specific types with SQLite-compatible equivalents."""
    if connection.dialect.name == "sqlite":
        for table in target.tables.values():
            for col in table.columns:
                if isinstance(col.type, JSONB):
                    col.type = JSON()
                elif isinstance(col.type, UUID):
                    col.type = StringUUID()


# ─── Test Database ────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db():
    """Override the get_db dependency for tests."""
    async with test_session_factory() as session:
        yield session


async def override_get_current_user():
    """Override auth dependency for tests — returns a mock admin user."""
    return {
        "user_id": str(TEST_USER_ID),
        "email": "farmer@test.com",
        "role": "admin",
        "organisation_id": str(TEST_ORG_ID),
    }


# ─── Fixtures ─────────────────────────────────────────

@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    """Provide a test database session."""
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    """Provide an async HTTP client with dependency overrides."""
    from app.main import app

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ─── Seed Data Fixtures ──────────────────────────────

TEST_ORG_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
TEST_FARM_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
TEST_USER_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
TEST_ANIMAL_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
TEST_DEVICE_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
TEST_GEOFENCE_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")
TEST_ALERT_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")


@pytest_asyncio.fixture
async def seed_org(db_session: AsyncSession):
    """Seed a test organisation."""
    org = Organisation(id=TEST_ORG_ID, name="Test Farm Co", plan="pro", max_devices=100)
    db_session.add(org)
    await db_session.commit()
    return org


@pytest_asyncio.fixture
async def seed_farm(db_session: AsyncSession, seed_org):
    """Seed a test farm."""
    farm = Farm(id=TEST_FARM_ID, organisation_id=TEST_ORG_ID, name="Boschhoek Farm")
    db_session.add(farm)
    await db_session.commit()
    return farm


@pytest_asyncio.fixture
async def seed_user(db_session: AsyncSession, seed_org):
    """Seed a test user with known credentials."""
    user = User(
        id=TEST_USER_ID,
        organisation_id=TEST_ORG_ID,
        email="farmer@test.com",
        password_hash=_PASSWORD123_HASH,
        full_name="Test Farmer",
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def seed_animal(db_session: AsyncSession, seed_farm):
    """Seed a test animal."""
    animal = Animal(
        id=TEST_ANIMAL_ID,
        farm_id=TEST_FARM_ID,
        name="Bella",
        tag_id="LG-001",
        species="cattle",
        breed="Angus",
    )
    db_session.add(animal)
    await db_session.commit()
    return animal


@pytest_asyncio.fixture
async def seed_device(db_session: AsyncSession, seed_farm):
    """Seed a test device."""
    device = Device(
        id=TEST_DEVICE_ID,
        serial_number="DEV-001",
        device_type="collar",
        firmware_version="1.2.3",
        farm_id=TEST_FARM_ID,
        status="active",
        battery_level=85,
    )
    db_session.add(device)
    await db_session.commit()
    return device


@pytest_asyncio.fixture
async def seed_geofence(db_session: AsyncSession, seed_farm):
    """Seed a test geofence."""
    geofence = Geofence(
        id=TEST_GEOFENCE_ID,
        farm_id=TEST_FARM_ID,
        name="Main Paddock",
        fence_type="inclusion",
        active=True,
        alert_on_breach=True,
    )
    db_session.add(geofence)
    await db_session.commit()
    return geofence


@pytest_asyncio.fixture
async def seed_alert(db_session: AsyncSession, seed_farm, seed_animal):
    """Seed a test alert."""
    alert = Alert(
        id=TEST_ALERT_ID,
        farm_id=TEST_FARM_ID,
        animal_id=TEST_ANIMAL_ID,
        alert_type="geofence_breach",
        severity="high",
        status="active",
        message="Bella has left Main Paddock",
    )
    db_session.add(alert)
    await db_session.commit()
    return alert
