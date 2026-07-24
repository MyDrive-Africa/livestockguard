from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class Position:
    latitude: float
    longitude: float
    altitude: float = 0.0
    hdop: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    device_id: Optional[str] = None


@dataclass
class DeviceTelemetry:
    device_id: str
    positions: list[Position] = field(default_factory=list)
    battery_mv: int = 0
    temperature_c: float = 0.0
    signal_rssi: int = 0
    sequence_number: int = 0
    received_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class GeofenceAlert:
    alert_id: str
    device_id: str
    animal_id: str
    farm_id: str
    geofence_id: str
    geofence_name: str
    fence_type: str  # "inclusion" | "exclusion"
    position: Position
    severity: str = "high"
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TheftAlert:
    alert_id: str
    device_id: str
    animal_id: str
    farm_id: str
    position: Position
    confidence: float = 0.0
    indicators: list[str] = field(default_factory=list)
    severity: str = "critical"
    timestamp: datetime = field(default_factory=datetime.utcnow)
