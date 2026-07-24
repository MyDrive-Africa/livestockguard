from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class EventType(str, Enum):
    POSITION_UPDATE = "position.update"
    GEOFENCE_BREACH = "geofence.breach"
    GEOFENCE_RETURN = "geofence.return"
    THEFT_DETECTED = "theft.detected"
    DEVICE_ONLINE = "device.online"
    DEVICE_OFFLINE = "device.offline"
    LOW_BATTERY = "device.low_battery"
    ALERT_CREATED = "alert.created"
    ALERT_ACKNOWLEDGED = "alert.acknowledged"
    ALERT_RESOLVED = "alert.resolved"
    ANIMAL_ACTIVITY_CHANGE = "animal.activity_change"


@dataclass
class Event:
    event_type: EventType
    source_id: str
    farm_id: str
    payload: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary for transmission."""
        return {
            "event_type": self.event_type.value,
            "source_id": self.source_id,
            "farm_id": self.farm_id,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """Deserialize event from dictionary."""
        return cls(
            event_type=EventType(data["event_type"]),
            source_id=data["source_id"],
            farm_id=data["farm_id"],
            payload=data.get("payload", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            correlation_id=data.get("correlation_id"),
        )
