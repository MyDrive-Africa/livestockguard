"""
Amazon SES email dispatcher for LivestockGuard alerts.

Uses boto3 async-compatible SES client to send alert emails.
Falls back to logging if SES is not configured (dev mode).
"""

import logging
import os
from typing import Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

# Email templates by alert type
EMAIL_TEMPLATES = {
    "geofence_breach": {
        "subject": "🚨 LivestockGuard: Geofence Breach Alert",
        "body_template": (
            "GEOFENCE BREACH DETECTED\n\n"
            "Animal: {animal_id}\n"
            "Device: {device_id}\n"
            "Farm: {farm_id}\n"
            "Time: {timestamp}\n\n"
            "Details: {message}\n\n"
            "Please check the LivestockGuard dashboard for more information.\n"
            "https://app.livestockguard.co.za/alerts"
        ),
    },
    "theft_detected": {
        "subject": "🚨 CRITICAL: LivestockGuard Theft Alert",
        "body_template": (
            "THEFT ALERT - IMMEDIATE ACTION REQUIRED\n\n"
            "Animal: {animal_id}\n"
            "Device: {device_id}\n"
            "Farm: {farm_id}\n"
            "Time: {timestamp}\n\n"
            "Details: {message}\n\n"
            "An animal is moving at vehicle speed. This may indicate theft.\n"
            "Please check the LivestockGuard dashboard immediately.\n"
            "https://app.livestockguard.co.za/alerts"
        ),
    },
    "low_battery": {
        "subject": "⚠️ LivestockGuard: Low Battery Warning",
        "body_template": (
            "LOW BATTERY WARNING\n\n"
            "Device: {device_id}\n"
            "Animal: {animal_id}\n"
            "Farm: {farm_id}\n\n"
            "Details: {message}\n\n"
            "Please schedule a battery replacement or recharge.\n"
        ),
    },
    "default": {
        "subject": "LivestockGuard Alert: {alert_type}",
        "body_template": (
            "ALERT NOTIFICATION\n\n"
            "Type: {alert_type}\n"
            "Severity: {severity}\n"
            "Device: {device_id}\n"
            "Animal: {animal_id}\n"
            "Farm: {farm_id}\n"
            "Time: {timestamp}\n\n"
            "Details: {message}\n"
        ),
    },
}


class SESEmailDispatcher:
    """Sends alert emails via Amazon SES."""

    def __init__(
        self,
        sender_email: Optional[str] = None,
        aws_region: Optional[str] = None,
    ):
        self.sender_email = sender_email or os.environ.get(
            "SES_SENDER_EMAIL", "alerts@livestockguard.co.za"
        )
        self.aws_region = aws_region or os.environ.get("AWS_REGION", "af-south-1")
        self._client = None

    @property
    def client(self):
        """Lazy-initialize SES client."""
        if self._client is None:
            try:
                self._client = boto3.client("ses", region_name=self.aws_region)
            except NoCredentialsError:
                logger.warning("AWS credentials not configured — email dispatch disabled")
                self._client = None
        return self._client

    def dispatch(self, event, recipient_emails: list[str]) -> bool:
        """
        Send an alert email to the specified recipients.

        Args:
            event: AlertEvent dataclass instance
            recipient_emails: List of email addresses to notify

        Returns:
            True if email was sent successfully, False otherwise
        """
        if not recipient_emails:
            logger.debug("No recipient emails configured, skipping email dispatch")
            return False

        if self.client is None:
            logger.warning(
                f"SES not configured — would send email for {event.alert_type.value} "
                f"to {recipient_emails}"
            )
            return False

        # Select template
        template = EMAIL_TEMPLATES.get(
            event.alert_type.value, EMAIL_TEMPLATES["default"]
        )

        # Format subject and body
        from datetime import datetime

        format_vars = {
            "alert_type": event.alert_type.value,
            "severity": event.severity.value,
            "device_id": event.device_id,
            "animal_id": event.animal_id or "Unknown",
            "farm_id": event.farm_id,
            "message": event.message,
            "timestamp": datetime.fromtimestamp(event.timestamp).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            ),
        }

        subject = template["subject"].format(**format_vars)
        body = template["body_template"].format(**format_vars)

        try:
            response = self.client.send_email(
                Source=self.sender_email,
                Destination={"ToAddresses": recipient_emails},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": body, "Charset": "UTF-8"},
                        "Html": {
                            "Data": self._html_wrap(subject, body),
                            "Charset": "UTF-8",
                        },
                    },
                },
                Tags=[
                    {"Name": "alert_type", "Value": event.alert_type.value},
                    {"Name": "severity", "Value": event.severity.value},
                    {"Name": "farm_id", "Value": event.farm_id},
                ],
            )
            message_id = response["MessageId"]
            logger.info(
                f"Email sent via SES: {message_id} | "
                f"type={event.alert_type.value} recipients={len(recipient_emails)}"
            )
            return True

        except ClientError as e:
            logger.error(f"SES send failed: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"Email dispatch error: {e}")
            return False

    def _html_wrap(self, subject: str, body: str) -> str:
        """Wrap plain text body in minimal HTML email template."""
        body_html = body.replace("\n", "<br/>")
        return f"""
        <html>
        <head></head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 20px; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;">
                <div style="background: #16a34a; color: white; padding: 16px 24px;">
                    <h2 style="margin: 0; font-size: 18px;">LivestockGuard</h2>
                </div>
                <div style="padding: 24px;">
                    <h3 style="color: #111; margin-top: 0;">{subject}</h3>
                    <p style="line-height: 1.6; color: #555;">{body_html}</p>
                </div>
                <div style="background: #f9fafb; padding: 12px 24px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #9ca3af;">
                    This is an automated alert from LivestockGuard. Do not reply to this email.
                </div>
            </div>
        </body>
        </html>
        """
