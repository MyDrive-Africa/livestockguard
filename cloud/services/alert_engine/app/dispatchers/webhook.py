"""
Webhook dispatcher — POST alert payloads to configured webhook URLs.

Useful for integrating with external systems (Slack, Teams, custom dashboards).
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class WebhookDispatcher:
    """Sends alert payloads to configured webhook URLs."""

    def __init__(self, webhook_urls: Optional[list[str]] = None, timeout: float = 10.0):
        self.webhook_urls = webhook_urls or self._load_urls_from_env()
        self.timeout = timeout

    def _load_urls_from_env(self) -> list[str]:
        """Load webhook URLs from WEBHOOK_URLS env var (comma-separated)."""
        urls = os.environ.get("WEBHOOK_URLS", "")
        return [u.strip() for u in urls.split(",") if u.strip()]

    def dispatch(self, event) -> bool:
        """
        POST the alert event to all configured webhook URLs.

        Args:
            event: AlertEvent dataclass instance

        Returns:
            True if at least one webhook was delivered successfully
        """
        if not self.webhook_urls:
            logger.debug("No webhook URLs configured, skipping")
            return False

        if not HTTPX_AVAILABLE:
            logger.warning("httpx not installed — webhook dispatch disabled")
            return False

        payload = {
            "event": "alert.created",
            "alert_type": event.alert_type.value,
            "severity": event.severity.value,
            "device_id": event.device_id,
            "farm_id": event.farm_id,
            "animal_id": event.animal_id,
            "message": event.message,
            "metadata": event.metadata,
            "timestamp": datetime.fromtimestamp(
                event.timestamp, tz=timezone.utc
            ).isoformat(),
        }

        success_count = 0
        for url in self.webhook_urls:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    if response.status_code < 300:
                        success_count += 1
                        logger.info(f"Webhook delivered: {url} status={response.status_code}")
                    else:
                        logger.warning(
                            f"Webhook failed: {url} status={response.status_code}"
                        )
            except Exception as e:
                logger.error(f"Webhook error for {url}: {e}")

        return success_count > 0
