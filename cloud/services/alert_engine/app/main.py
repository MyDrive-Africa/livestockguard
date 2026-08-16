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
from .dispatchers.sms_africastalking import AfricasTalkingSMSDispatcher

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
        self.sms_dispatcher = AfricasTalkingSMSDispatcher()

        # Default notification recipients (override per farm in production)
        self.default_email_recipients = self._load_email_recipients()
        self.default_sms_recipients = self._load_sms_recipients()

        logger.info("AlertEngine initialized with dispatchers: SES, FCM, Redis, Webhook, SMS(AT)")

    def _load_email_recipients(self) -> list[str]:
        """
        Load default email recipients from the ALERT_EMAIL_RECIPIENTS env variable.

        Returns:
            List of email address strings (comma-separated in env). Empty list if unset.
        """
        recipients = os.environ.get("ALERT_EMAIL_RECIPIENTS", "")
        return [e.strip() for e in recipients.split(",") if e.strip()]

    def _load_sms_recipients(self) -> list[str]:
        """
        Load default SMS recipients from the ALERT_SMS_RECIPIENTS env variable.

        Returns:
            List of phone number strings in E.164 format (e.g., '+27821234567').
            Empty list if unset.
        """
        recipients = os.environ.get("ALERT_SMS_RECIPIENTS", "")
        return [p.strip() for p in recipients.split(",") if p.strip()]

    def _cooldown_key(self, event: AlertEvent) -> str:
        """
        Generate a unique cooldown tracking key for deduplication.

        Args:
            event: The alert event to generate a key for.

        Returns:
            String key in format '{alert_type}:{device_id}' used to look up
            the last fire time in the cooldown dictionary.
        """
        return f"{event.alert_type.value}:{event.device_id}"

    def should_alert(self, event: AlertEvent) -> bool:
        """
        Determine whether an alert should fire, respecting the cooldown period.

        Args:
            event: The incoming alert event to evaluate.

        Returns:
            True if the alert should be dispatched (no recent firing for this
            device+type combo within cooldown_seconds). False if suppressed.
        """
        key = self._cooldown_key(event)
        last_time = self._last_alert_times.get(key, 0)
        now = time.time()

        if now - last_time < self.cooldown_seconds:
            logger.debug(f"Alert suppressed (cooldown): {key}")
            return False

        return True

    def process_event(self, event: AlertEvent) -> bool:
        """
        Process an alert event through the full dispatch pipeline.

        Args:
            event: The alert event to process.

        Returns:
            True if the alert was dispatched to at least one channel.
            False if suppressed by cooldown.

        Side Effects:
            - Updates the cooldown timestamp for this device+type.
            - Dispatches to channels determined by the event's severity level.
        """
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
        """
        Dispatch alert notifications through the specified channels.

        Args:
            event: The alert event containing all notification context.
            channels: List of notification channels to send through
                      (push, sms, email, webhook, dashboard).

        Notes:
            Each channel dispatch is independent — if one fails, others still fire.
            Errors are logged but do not raise exceptions.
        """
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
        """
        Send push notification via Firebase Cloud Messaging.

        Args:
            event: Alert event to notify about. Sends to the FCM topic
                   'farm_{farm_id}' so all subscribed users receive it.
        """
        # Send to farm topic — all users subscribed to this farm get notified
        topic = f"farm_{event.farm_id}"
        self.push_dispatcher.dispatch(event, topic=topic)

    def _send_sms(self, event: AlertEvent) -> None:
        """
        Send SMS notification via Africa's Talking.

        Args:
            event: Alert event to format into an SMS body. Only fires for
                   critical severity when recipients are configured.
        """
        recipients = self.default_sms_recipients
        if recipients:
            self.sms_dispatcher.dispatch(event, recipients)
        else:
            logger.debug("No SMS recipients configured")

    def _send_email(self, event: AlertEvent) -> None:
        """
        Send email notification via Amazon SES.

        Args:
            event: Alert event to format into an email body. Recipients are
                   loaded from ALERT_EMAIL_RECIPIENTS env (or per-farm in production).
        """
        # In production: look up farm owner/manager emails from DB
        recipients = self.default_email_recipients
        if recipients:
            self.email_dispatcher.dispatch(event, recipients)
        else:
            logger.debug("No email recipients configured")

    def _send_webhook(self, event: AlertEvent) -> None:
        """
        Send webhook notification to configured HTTP endpoints.

        Args:
            event: Alert event serialized as JSON POST body to WEBHOOK_URLS.
        """
        self.webhook_dispatcher.dispatch(event)

    def _send_dashboard(self, event: AlertEvent) -> None:
        """
        Publish alert to the dashboard via Redis pub/sub.

        Args:
            event: Alert event published to Redis for WebSocket fan-out
                   to connected dashboard clients.
        """
        self.dashboard_dispatcher.dispatch(event)


async def run_alert_engine():
    """
    Main event loop — subscribes to Redis 'alerts:incoming' channel and
    processes events through the AlertEngine dispatch pipeline.

    Lifecycle:
        1. Initialise AlertEngine with all dispatcher plugins.
        2. Connect to Redis and subscribe to the alerts channel.
        3. For each incoming message, parse JSON → AlertEvent → process_event().
        4. Runs indefinitely until interrupted (Ctrl+C or container stop).

    The MQTT writer and other services publish to 'alerts:incoming' whenever
    they detect alert-worthy conditions (geofence breach, theft, etc.).
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
