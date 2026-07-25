"""
SQLAlchemy ORM models matching the database schema.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey, Index,
    Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Organisation(Base):
    __tablename__ = "organisations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    plan = Column(String(50), nullable=False, default="basic")
    max_devices = Column(Integer, nullable=False, default=50)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    farms = relationship("Farm", back_populates="organisation")
    users = relationship("User", back_populates="organisation")


class Farm(Base):
    __tablename__ = "farms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    timezone = Column(String(50), nullable=False, default="Africa/Johannesburg")
    # Location details (migration 004)
    province = Column(String(100))
    district = Column(String(255))
    plot_number = Column(String(50))
    address = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    area_hectares = Column(Float)
    contact_name = Column(String(255))
    contact_phone = Column(String(50))
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    organisation = relationship("Organisation", back_populates="farms")
    animals = relationship("Animal", back_populates="farm")
    devices = relationship("Device", back_populates="farm")
    geofences = relationship("Geofence", back_populates="farm")
    alerts = relationship("Alert", back_populates="farm")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="viewer")
    active = Column(Boolean, nullable=False, default=True)
    last_login = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    organisation = relationship("Organisation", back_populates="users")


class Device(Base):
    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    serial_number = Column(String(100), unique=True, nullable=False)
    device_type = Column(String(50), nullable=False)
    firmware_version = Column(String(50))
    farm_id = Column(UUID(as_uuid=True), ForeignKey("farms.id"))
    animal_id = Column(UUID(as_uuid=True), ForeignKey("animals.id"))
    status = Column(String(50), nullable=False, default="inactive")
    last_seen = Column(DateTime(timezone=True))
    battery_level = Column(Integer)
    config = Column(JSONB, nullable=False, default=dict)
    activated_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    farm = relationship("Farm", back_populates="devices")
    animal = relationship("Animal", foreign_keys=[animal_id], uselist=False)


class Animal(Base):
    __tablename__ = "animals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id = Column(UUID(as_uuid=True), ForeignKey("farms.id"), nullable=False)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"))
    name = Column(String(255), nullable=False)
    tag_id = Column(String(100), nullable=False)
    species = Column(String(50), nullable=False, default="cattle")
    breed = Column(String(100))
    date_of_birth = Column(Date)
    notes = Column(Text)
    # Inventory fields (migration 003)
    gender = Column(String(10))  # 'male' or 'female'
    photo_url = Column(Text)
    description = Column(Text)
    colour = Column(String(100))
    weight_kg = Column(Float)
    status = Column(String(20), nullable=False, default="active")  # active/sold/deceased/transferred
    mother_id = Column(UUID(as_uuid=True), ForeignKey("animals.id"))
    father_id = Column(UUID(as_uuid=True), ForeignKey("animals.id"))
    acquired_date = Column(Date)
    removed_date = Column(Date)
    removal_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    farm = relationship("Farm", back_populates="animals")
    device = relationship("Device", foreign_keys=[device_id], uselist=False)
    mother = relationship("Animal", foreign_keys=[mother_id], remote_side="Animal.id", uselist=False)
    father = relationship("Animal", foreign_keys=[father_id], remote_side="Animal.id", uselist=False)


class Geofence(Base):
    __tablename__ = "geofences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id = Column(UUID(as_uuid=True), ForeignKey("farms.id"), nullable=False)
    name = Column(String(255), nullable=False)
    fence_type = Column(String(50), nullable=False, default="inclusion")
    active = Column(Boolean, nullable=False, default=True)
    alert_on_breach = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    farm = relationship("Farm", back_populates="geofences")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id = Column(UUID(as_uuid=True), ForeignKey("farms.id"), nullable=False)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"))
    animal_id = Column(UUID(as_uuid=True), ForeignKey("animals.id"))
    geofence_id = Column(UUID(as_uuid=True), ForeignKey("geofences.id"))
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    message = Column(Text)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    acknowledged_at = Column(DateTime(timezone=True))
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    resolved_at = Column(DateTime(timezone=True))
    resolution_notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=func.now())

    farm = relationship("Farm", back_populates="alerts")


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    farm_id = Column(UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False)

    # Channel toggles
    push_enabled = Column(Boolean, nullable=False, default=True)
    email_enabled = Column(Boolean, nullable=False, default=True)
    sms_enabled = Column(Boolean, nullable=False, default=False)
    webhook_enabled = Column(Boolean, nullable=False, default=False)

    # Severity filter
    min_severity = Column(String(20), nullable=False, default="medium")

    # Quiet hours
    quiet_start = Column(String(5))  # HH:MM
    quiet_end = Column(String(5))    # HH:MM

    # Contact overrides
    sms_phone = Column(String(20))
    webhook_url = Column(Text)

    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())


# ─── Herdsman Gateway Models (Migration 007) ─────────────────────────────────


class GatewayDevice(Base):
    """Gateway device carried by a herdsman — collects BLE pings from ear tags."""
    __tablename__ = "gateway_devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id = Column(UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False)
    serial_number = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    device_type = Column(String(50), nullable=False, default="phone")
    herdsman_name = Column(String(255))
    herdsman_phone = Column(String(50))
    status = Column(String(50), nullable=False, default="active")
    firmware_version = Column(String(50))
    last_seen = Column(DateTime(timezone=True))
    last_latitude = Column(Float)
    last_longitude = Column(Float)
    last_battery_pct = Column(Integer)
    ble_scan_interval_ms = Column(Integer, nullable=False, default=5000)
    report_interval_sec = Column(Integer, nullable=False, default=30)
    max_ble_range_m = Column(Integer, nullable=False, default=100)
    config = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    farm = relationship("Farm")
    sessions = relationship("HerdsmanSession", back_populates="gateway")


class BleEarTag(Base):
    """Passive BLE beacon attached to cattle — cheap, long battery, no GPS."""
    __tablename__ = "ble_ear_tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id = Column(UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False)
    animal_id = Column(UUID(as_uuid=True), ForeignKey("animals.id", ondelete="SET NULL"))
    mac_address = Column(String(17), unique=True, nullable=False)
    tag_name = Column(String(100))
    manufacturer = Column(String(100))
    battery_type = Column(String(50), default="CR2032")
    estimated_battery_months = Column(Integer, default=36)
    installed_date = Column(Date)
    status = Column(String(50), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    farm = relationship("Farm")
    animal = relationship("Animal")


class BleSighting(Base):
    """Single BLE advertisement received by a gateway — stored as time-series."""
    __tablename__ = "ble_sightings"

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    gateway_id = Column(UUID(as_uuid=True), ForeignKey("gateway_devices.id", ondelete="CASCADE"), primary_key=True, nullable=False)
    ble_tag_id = Column(UUID(as_uuid=True), ForeignKey("ble_ear_tags.id", ondelete="SET NULL"))
    mac_address = Column(String(17), nullable=False)
    animal_id = Column(UUID(as_uuid=True), ForeignKey("animals.id", ondelete="SET NULL"))
    rssi = Column(Integer, nullable=False)
    estimated_distance_m = Column(Float)
    gateway_latitude = Column(Float, nullable=False)
    gateway_longitude = Column(Float, nullable=False)
    gateway_altitude = Column(Float)
    gateway_speed = Column(Float)
    gateway_battery_pct = Column(Integer)


class HerdsmanSession(Base):
    """Tracks a herdsman patrol shift — start/end, animals seen, distance."""
    __tablename__ = "herdsman_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gateway_id = Column(UUID(as_uuid=True), ForeignKey("gateway_devices.id", ondelete="CASCADE"), nullable=False)
    farm_id = Column(UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False)
    herdsman_name = Column(String(255))
    started_at = Column(DateTime(timezone=True), default=func.now())
    ended_at = Column(DateTime(timezone=True))
    start_latitude = Column(Float)
    start_longitude = Column(Float)
    end_latitude = Column(Float)
    end_longitude = Column(Float)
    animals_seen = Column(Integer, default=0)
    total_sightings = Column(Integer, default=0)
    distance_walked_m = Column(Float)
    notes = Column(Text)
    status = Column(String(20), nullable=False, default="active")

    gateway = relationship("GatewayDevice", back_populates="sessions")
    farm = relationship("Farm")
