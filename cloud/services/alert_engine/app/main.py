import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertType(str, Enum):
    GEOFENCE_BREACH = "geofence_breach"
    THEFT_DETECTED = "theft_detected"
    LOW_BATTERY = "low_battery"
    DEVICE_OFFLINE = "device_offline"
    UNUSUAL_ACTIVITY = "unusual_activity"
    TEMPERATURE_ALERT = "temperature_alert"
    NO_MOVEMENT = "no_movement"


class NotificationChannel(str, Enum):
    PUSH = "push"
    SMS = "sms"
    EMAIL = "email"
    WEBHOOK = "webhook"
    DASHBOARD = "dashboard"


# Severity to channels mapping
SEVERITY_CHANNELS: dict[AlertSeverity, list[NotificationChannel]] = {
    AlertSeverity.CRITICAL: [
        NotificationChannel.PUSH,
        NotificationChannel.SMS,
        NotificationChannel.EMAIL,
        NotificationChannel.DASHBOARD,
    ],
    AlertSeverity.HIGH: [
        NotificationChannel.PUSH,
        NotificationChannel.EMAIL,
        NotificationChannel.DASHBOARD,
    ],
    AlertSeverity.MEDIUM: [
        NotificationChannel.PUSH,
        NotificationChannel.DASHBOARD,
    ],
    AlertSeverity.LOW: [
        NotificationChannel.DASHBOARD,
    ],
    AlertSeverity.INFO: [
        NotificationChannel.DASHBOARD,
    ],
}


@dataclass
class AlertEvent:
    alert_type: AlertType
    severity: AlertSeverity
    device_id: str
    farm_id: str
    animal_id: Optional[str] = None
    message: str = ""
    metadata: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class AlertEngine:
    """Processes incoming events and dispatches alerts through appropriate channels."""

    def __init__(self, cooldown_seconds: int = 300):
        self.cooldown_seconds = cooldown_seconds
        self._last_alert_times: dict[str, float] = {}

    def _cooldown_key(self, event: AlertEvent) -> str:
        """Generate a unique key for cooldown tracking."""
        return f"{event.alert_type.value}:{event.device_id}"

    def should_alert(self, event: AlertEvent) -> bool:
        """Check if an alert should be fired (respecting cooldown period)."""
        key = self._cooldown_key(event)
        last_time = self._last_alert_times.get(key, 0)
        now = time.time()

        if now - last_time < self.cooldown_seconds:
            return False

        return True

    def process_event(self, event: AlertEvent) -> bool:
        """Process an alert event. Returns True if alert was dispatched."""
        if not self.should_alert(event):
            return False

        key = self._cooldown_key(event)
        self._last_alert_times[key] = time.time()

        channels = SEVERITY_CHANNELS.get(event.severity, [NotificationChannel.DASHBOARD])
        self.dispatch(event, channels)
        return True

    def dispatch(self, event: AlertEvent, channels: list[NotificationChannel]) -> None:
        """Dispatch alert notifications through the specified channels."""
        for channel in channels:
            if channel == NotificationChannel.PUSH:
                self._send_push(event)
            elif channel == NotificationChannel.SMS:
                self._send_sms(event)
            elif channel == NotificationChannel.EMAIL:
                self._send_email(event)
            elif channel == NotificationChannel.WEBHOOK:
                self._send_webhook(event)
            elif channel == NotificationChannel.DASHBOARD:
                self._send_dashboard(event)

    def _send_push(self, event: AlertEvent) -> None:
        """Send push notification."""
        # TODO: Integrate with FCM/APNs
        pass

    def _send_sms(self, event: AlertEvent) -> None:
        """Send SMS notification."""
        # TODO: Integrate with Twilio/SNS
        pass

    def _send_email(self, event: AlertEvent) -> None:
        """Send email notification."""
        # TODO: Integrate with SES/SendGrid
        pass

    def _send_webhook(self, event: AlertEvent) -> None:
        """Send webhook notification."""
        # TODO: POST to configured webhook URLs
        pass

    def _send_dashboard(self, event: AlertEvent) -> None:
        """Publish alert to dashboard via WebSocket."""
        # TODO: Publish to Redis pub/sub for WebSocket distribution
        pass
