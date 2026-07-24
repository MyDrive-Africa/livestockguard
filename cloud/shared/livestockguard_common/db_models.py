"""
SQLAlchemy ORM models matching the database schema.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index,
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
    date_of_birth = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    farm = relationship("Farm", back_populates="animals")
    device = relationship("Device", foreign_keys=[device_id], uselist=False)


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
