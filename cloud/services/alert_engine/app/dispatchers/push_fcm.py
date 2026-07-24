"""
Firebase Cloud Messaging (FCM) push notification dispatcher.

Uses the Firebase Admin SDK to send push notifications to farm owners/managers
when alerts are triggered. Supports both individual device tokens and topic-based
messaging (subscribe devices to farm topics).
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import firebase_admin — graceful fallback if not installed
try:
    import firebase_admin
    from firebase_admin import credentials, messaging

    FCM_AVAILABLE = True
except ImportError:
    FCM_AVAILABLE = False
    logger.warning("firebase-admin not installed — push notifications disabled")


# FCM priority mapping based on alert severity
SEVERITY_PRIORITY = {
    "critical": "high",
    "high": "high",
    "medium": "normal",
    "low": "normal",
    "info": "normal",
}

# Alert type to notification icon/color
ALERT_DISPLAY = {
    "geofence_breach": {"icon": "fence_alert", "color": "#ea580c"},
    "theft_detected": {"icon": "theft_alert", "color": "#dc2626"},
    "low_battery": {"icon": "battery_low", "color": "#f59e0b"},
    "device_offline": {"icon": "device_offline", "color": "#6b7280"},
    "unusual_activity": {"icon": "activity_alert", "color": "#8b5cf6"},
    "no_movement": {"icon": "no_movement", "color": "#3b82f6"},
}


class FCMPushDispatcher:
    """Sends push notifications via Firebase Cloud Messaging."""

    def __init__(self, credentials_path: Optional[str] = None):
        self.credentials_path = credentials_path or os.environ.get(
            "FIREBASE_CREDENTIALS_PATH", "/app/config/firebase-credentials.json"
        )
        self._initialized = False
        self._init_firebase()

    def _init_firebase(self):
        """Initialize Firebase Admin SDK."""
        if not FCM_AVAILABLE:
            return

        try:
            # Check if already initialized
            firebase_admin.get_app()
            self._initialized = True
        except ValueError:
            # Not initialized yet
            if os.path.exists(self.credentials_path):
                cred = credentials.Certificate(self.credentials_path)
                firebase_admin.initialize_app(cred)
                self._initialized = True
                logger.info("Firebase Admin SDK initialized")
            else:
                # Try Application Default Credentials (works on GCP/AWS with configured identity)
                try:
                    firebase_admin.initialize_app()
                    self._initialized = True
                    logger.info("Firebase initialized with default credentials")
                except Exception:
                    logger.warning(
                        f"Firebase credentials not found at {self.credentials_path} "
                        "— push notifications disabled"
                    )

    def dispatch(
        self,
        event,
        device_tokens: Optional[list[str]] = None,
        topic: Optional[str] = None,
    ) -> bool:
        """
        Send a push notification for an alert event.

        Args:
            event: AlertEvent dataclass instance
            device_tokens: List of FCM device registration tokens
            topic: FCM topic name (e.g., "farm_<uuid>") for broadcast

        Returns:
            True if notification was sent successfully
        """
        if not self._initialized:
            logger.warning(
                f"FCM not initialized — would send push for {event.alert_type.value} "
                f"tokens={len(device_tokens or [])} topic={topic}"
            )
            return False

        display = ALERT_DISPLAY.get(
            event.alert_type.value,
            {"icon": "alert", "color": "#16a34a"},
        )

        # Build notification
        notification = messaging.Notification(
            title=self._build_title(event),
            body=event.message or f"{event.alert_type.value} detected",
        )

        # Build data payload (for client-side processing)
        data = {
            "alert_type": event.alert_type.value,
            "severity": event.severity.value,
            "device_id": event.device_id,
            "farm_id": event.farm_id,
            "animal_id": event.animal_id or "",
            "timestamp": str(int(event.timestamp)),
            "click_action": "https://app.livestockguard.co.za/alerts",
        }

        # Android-specific config
        android = messaging.AndroidConfig(
            priority=SEVERITY_PRIORITY.get(event.severity.value, "normal"),
            notification=messaging.AndroidNotification(
                icon=display["icon"],
                color=display["color"],
                channel_id=(
                    "critical_alerts"
                    if event.severity.value in ("critical", "high")
                    else "general_alerts"
                ),
                sound="alert_sound" if event.severity.value == "critical" else "default",
            ),
        )

        # Web push config
        webpush = messaging.WebpushConfig(
            notification=messaging.WebpushNotification(
                icon="/icons/alert-icon-192.png",
                badge="/icons/badge-72.png",
                actions=[
                    messaging.WebpushNotificationAction(
                        action="view", title="View Alert"
                    ),
                    messaging.WebpushNotificationAction(
                        action="acknowledge", title="Acknowledge"
                    ),
                ],
            ),
        )

        try:
            sent_count = 0

            # Send to topic (farm-wide broadcast)
            if topic:
                message = messaging.Message(
                    notification=notification,
                    data=data,
                    android=android,
                    webpush=webpush,
                    topic=topic,
                )
                response = messaging.send(message)
                logger.info(f"FCM topic message sent: {response} topic={topic}")
                sent_count += 1

            # Send to individual device tokens
            if device_tokens:
                message = messaging.MulticastMessage(
                    notification=notification,
                    data=data,
                    android=android,
                    webpush=webpush,
                    tokens=device_tokens,
                )
                response = messaging.send_each_for_multicast(message)
                sent_count += response.success_count
                if response.failure_count > 0:
                    logger.warning(
                        f"FCM multicast: {response.success_count} sent, "
                        f"{response.failure_count} failed"
                    )

            logger.info(
                f"Push sent: type={event.alert_type.value} "
                f"severity={event.severity.value} delivered={sent_count}"
            )
            return sent_count > 0

        except Exception as e:
            logger.error(f"FCM dispatch error: {e}")
            return False

    def _build_title(self, event) -> str:
        """Build notification title from alert event."""
        titles = {
            "geofence_breach": "Geofence Breach",
            "theft_detected": "THEFT ALERT",
            "low_battery": "Low Battery Warning",
            "device_offline": "Device Offline",
            "unusual_activity": "Unusual Activity",
            "no_movement": "No Movement Detected",
        }
        prefix = "🚨 " if event.severity.value in ("critical", "high") else "⚠️ "
        title = titles.get(event.alert_type.value, event.alert_type.value.replace("_", " ").title())
        return f"{prefix}LivestockGuard: {title}"

    def subscribe_to_farm(self, device_tokens: list[str], farm_id: str) -> bool:
        """Subscribe device tokens to a farm topic for broadcast alerts."""
        if not self._initialized or not device_tokens:
            return False

        topic = f"farm_{farm_id}"
        try:
            response = messaging.subscribe_to_topic(device_tokens, topic)
            logger.info(
                f"Subscribed {response.success_count} tokens to topic {topic}"
            )
            return response.success_count > 0
        except Exception as e:
            logger.error(f"FCM subscribe error: {e}")
            return False
