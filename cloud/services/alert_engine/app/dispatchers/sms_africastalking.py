"""
Africa's Talking SMS dispatcher for LivestockGuard alerts.

Uses the Africa's Talking SMS gateway — widely available across
South Africa and Sub-Saharan Africa with competitive pricing for
bulk SMS delivery.

Supports:
- Single and bulk SMS sends
- Delivery status callbacks
- Sender ID customisation (e.g. "LGGUARD")
- Graceful fallback when credentials not configured (dev mode)
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import africastalking

    AT_AVAILABLE = True
except ImportError:
    AT_AVAILABLE = False
    logger.warning("africastalking SDK not installed — SMS dispatch disabled")


# SMS templates by alert severity
SMS_TEMPLATES = {
    "critical": (
        "🚨 CRITICAL: {alert_type_display}\n"
        "{message}\n"
        "Animal: {animal_name}\n"
        "Action required NOW.\n"
        "— LivestockGuard"
    ),
    "high": (
        "⚠️ ALERT: {alert_type_display}\n"
        "{message}\n"
        "Animal: {animal_name}\n"
        "— LivestockGuard"
    ),
    "default": (
        "LivestockGuard: {alert_type_display}\n"
        "{message}\n"
        "— LivestockGuard"
    ),
}

ALERT_TYPE_DISPLAY = {
    "geofence_breach": "Geofence Breach",
    "theft_detected": "Theft Detected",
    "low_battery": "Low Battery",
    "device_offline": "Device Offline",
    "unusual_activity": "Unusual Activity",
    "no_movement": "No Movement",
    "temperature_alert": "Temperature Alert",
}


class AfricasTalkingSMSDispatcher:
    """Sends alert SMS via Africa's Talking gateway."""

    def __init__(
        self,
        username: Optional[str] = None,
        api_key: Optional[str] = None,
        sender_id: Optional[str] = None,
        environment: Optional[str] = None,
    ):
        self.username = username or os.environ.get("AT_USERNAME", "")
        self.api_key = api_key or os.environ.get("AT_API_KEY", "")
        self.sender_id = sender_id or os.environ.get("AT_SENDER_ID", "LGGUARD")
        self.environment = environment or os.environ.get("AT_ENVIRONMENT", "sandbox")
        self._sms = None
        self._initialized = False
        self._init_sdk()

    def _init_sdk(self):
        """Initialize Africa's Talking SDK."""
        if not AT_AVAILABLE:
            return

        if not self.username or not self.api_key:
            logger.warning(
                "Africa's Talking credentials not configured "
                "(set AT_USERNAME and AT_API_KEY) — SMS dispatch disabled"
            )
            return

        try:
            africastalking.initialize(self.username, self.api_key)
            self._sms = africastalking.SMS
            self._initialized = True
            logger.info(
                f"Africa's Talking SMS initialized: "
                f"username={self.username}, env={self.environment}, sender={self.sender_id}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Africa's Talking: {e}")

    def dispatch(self, event, phone_numbers: list[str]) -> bool:
        """
        Send an SMS alert to the specified phone numbers.

        Args:
            event: AlertEvent dataclass instance
            phone_numbers: List of phone numbers in E.164 format (e.g. +27821234567)

        Returns:
            True if SMS was sent successfully to at least one recipient
        """
        if not phone_numbers:
            logger.debug("No phone numbers configured, skipping SMS dispatch")
            return False

        if not self._initialized:
            logger.warning(
                f"SMS not configured — would send to {len(phone_numbers)} recipients: "
                f"type={event.alert_type.value} severity={event.severity.value}"
            )
            return False

        # Build message from template
        message = self._format_message(event)

        try:
            response = self._sms.send(
                message=message,
                recipients=phone_numbers,
                sender_id=self.sender_id if self.environment != "sandbox" else None,
            )

            # Parse response
            sms_data = response.get("SMSMessageData", {})
            recipients_result = sms_data.get("Recipients", [])
            sent_count = sum(
                1 for r in recipients_result if r.get("statusCode") == 101
            )
            failed_count = len(recipients_result) - sent_count

            if sent_count > 0:
                logger.info(
                    f"SMS sent via Africa's Talking: "
                    f"sent={sent_count} failed={failed_count} "
                    f"type={event.alert_type.value}"
                )
                return True
            else:
                logger.warning(
                    f"SMS dispatch failed: no successful deliveries. "
                    f"Response: {sms_data.get('Message', 'unknown')}"
                )
                return False

        except Exception as e:
            logger.error(f"Africa's Talking SMS error: {e}")
            return False

    def _format_message(self, event) -> str:
        """Format the SMS message from event data."""
        severity = event.severity.value
        template = SMS_TEMPLATES.get(severity, SMS_TEMPLATES["default"])

        alert_type_display = ALERT_TYPE_DISPLAY.get(
            event.alert_type.value,
            event.alert_type.value.replace("_", " ").title(),
        )
        animal_name = event.metadata.get("animal_name", "Unknown")

        return template.format(
            alert_type_display=alert_type_display,
            message=event.message or "Alert triggered",
            animal_name=animal_name,
        )

    def check_balance(self) -> Optional[str]:
        """Check remaining SMS balance (useful for monitoring)."""
        if not self._initialized or not AT_AVAILABLE:
            return None

        try:
            app_data = africastalking.Application
            response = app_data.fetch_application_data()
            balance = response.get("UserData", {}).get("balance", "unknown")
            logger.info(f"Africa's Talking balance: {balance}")
            return balance
        except Exception as e:
            logger.error(f"Failed to check balance: {e}")
            return None
