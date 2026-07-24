"""
LivestockGuard Alert Engine

Processes incoming events and dispatches notifications through configured channels:
- Email: Amazon SES (af-south-1)
- Push: Firebase Cloud Messaging
- Dashboard: Redis pub/sub → WebSocket
- Webhook: HTTP POST to external URLs
- SMS: (future) Africa's Talking / Amazon SNS

The engine runs as a Redis subscriber, listening for alert events published by
the MQTT writer or other services.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import redis.asyncio as aioredis

from .dispatchers.email_ses import SESEmailDispatcher
from .dispatchers.push_fcm import FCMPushDispatcher
from .dispatchers.dashboard_redis import DashboardRedisDispatcher
from .dispatchers.webhook import WebhookDispatcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("alert_engine")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


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


# Severity → channels mapping
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
    """
    Processes incoming events and dispatches alerts through appropriate channels.

    Uses a cooldown mechanism to prevent alert fatigue — the same device/alert_type
    combination won't fire again within the cooldown period.
    """

    def __init__(self, cooldown_seconds: int = 300):
        self.cooldown_seconds = cooldown_seconds
        self._last_alert_times: dict[str, float] = {}

        # Initialize dispatchers
        self.email_dispatcher = SESEmailDispatcher()
        self.push_dispatcher = FCMPushDispatcher()
        self.dashboard_dispatcher = DashboardRedisDispatcher()
        self.webhook_dispatcher = WebhookDispatcher()

        # Default notification recipients (override per farm in production)
        self.default_email_recipients = self._load_email_recipients()

        logger.info("AlertEngine initialized with dispatchers: SES, FCM, Redis, Webhook")

    def _load_email_recipients(self) -> list[str]:
        """Load default email recipients from env."""
        recipients = os.environ.get("ALERT_EMAIL_RECIPIENTS", "")
        return [e.strip() for e in recipients.split(",") if e.strip()]

    def _cooldown_key(self, event: AlertEvent) -> str:
        """Generate a unique key for cooldown tracking."""
        return f"{event.alert_type.value}:{event.device_id}"

    def should_alert(self, event: AlertEvent) -> bool:
        """Check if an alert should be fired (respecting cooldown period)."""
        key = self._cooldown_key(event)
        last_time = self._last_alert_times.get(key, 0)
        now = time.time()

        if now - last_time < self.cooldown_seconds:
            logger.debug(f"Alert suppressed (cooldown): {key}")
            return False

        return True

    def process_event(self, event: AlertEvent) -> bool:
        """Process an alert event. Returns True if alert was dispatched."""
        if not self.should_alert(event):
            return False

        key = self._cooldown_key(event)
        self._last_alert_times[key] = time.time()

        channels = SEVERITY_CHANNELS.get(event.severity, [NotificationChannel.DASHBOARD])

        logger.info(
            f"Processing alert: type={event.alert_type.value} "
            f"severity={event.severity.value} channels={[c.value for c in channels]}"
        )

        self.dispatch(event, channels)
        return True

    def dispatch(self, event: AlertEvent, channels: list[NotificationChannel]) -> None:
        """Dispatch alert notifications through the specified channels."""
        for channel in channels:
            try:
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
            except Exception as e:
                logger.error(f"Dispatch error ({channel.value}): {e}")

    def _send_push(self, event: AlertEvent) -> None:
        """Send push notification via Firebase Cloud Messaging."""
        # Send to farm topic — all users subscribed to this farm get notified
        topic = f"farm_{event.farm_id}"
        self.push_dispatcher.dispatch(event, topic=topic)

    def _send_sms(self, event: AlertEvent) -> None:
        """Send SMS notification (future: Africa's Talking / Amazon SNS)."""
        # TODO: Wire up Africa's Talking or Amazon SNS for SMS
        logger.info(
            f"SMS dispatch pending implementation: {event.alert_type.value} "
            f"farm={event.farm_id}"
        )

    def _send_email(self, event: AlertEvent) -> None:
        """Send email notification via Amazon SES."""
        # In production: look up farm owner/manager emails from DB
        recipients = self.default_email_recipients
        if recipients:
            self.email_dispatcher.dispatch(event, recipients)
        else:
            logger.debug("No email recipients configured")

    def _send_webhook(self, event: AlertEvent) -> None:
        """Send webhook notification."""
        self.webhook_dispatcher.dispatch(event)

    def _send_dashboard(self, event: AlertEvent) -> None:
        """Publish alert to dashboard via Redis pub/sub."""
        self.dashboard_dispatcher.dispatch(event)


async def run_alert_engine():
    """
    Main event loop — subscribes to Redis for alert events
    and processes them through the alert engine.
    """
    engine = AlertEngine()

    logger.info(f"Connecting to Redis: {REDIS_URL}")
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    await redis_client.ping()
    logger.info("Redis connected — listening for alert events")

    pubsub = redis_client.pubsub()
    # Subscribe to a dedicated alerts channel (MQTT writer publishes here)
    await pubsub.subscribe("alerts:incoming")

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue

        try:
            data = json.loads(message["data"])
            event = AlertEvent(
                alert_type=AlertType(data["alert_type"]),
                severity=AlertSeverity(data.get("severity", "high")),
                device_id=data["device_id"],
                farm_id=data["farm_id"],
                animal_id=data.get("animal_id"),
                message=data.get("message", ""),
                metadata=data.get("metadata", {}),
                timestamp=data.get("timestamp", time.time()),
            )
            engine.process_event(event)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse alert event: {e}")


def main():
    """Entry point for the alert engine service."""
    logger.info("LivestockGuard Alert Engine v1.0 starting...")
    try:
        asyncio.run(run_alert_engine())
    except KeyboardInterrupt:
        logger.info("Alert engine shutting down")


if __name__ == "__main__":
    main()
