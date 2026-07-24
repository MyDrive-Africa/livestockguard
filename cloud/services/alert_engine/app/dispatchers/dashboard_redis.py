"""
Dashboard (Redis pub/sub) dispatcher.

Publishes alerts to Redis pub/sub so the WebSocket endpoint in the API gateway
can broadcast them to connected dashboard clients in real-time.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis package not installed — dashboard dispatch disabled")


class DashboardRedisDispatcher:
    """Publishes alerts to Redis pub/sub for WebSocket distribution."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self._client = None

    @property
    def client(self):
        """Lazy-initialize Redis client."""
        if self._client is None and REDIS_AVAILABLE:
            try:
                self._client = redis.from_url(self.redis_url, decode_responses=True)
                self._client.ping()
                logger.info("Redis connected for dashboard dispatch")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                self._client = None
        return self._client

    def dispatch(self, event) -> bool:
        """
        Publish an alert to the farm's Redis pub/sub channel.

        The WebSocket endpoint in the API gateway subscribes to these channels
        and forwards the message to connected clients.

        Args:
            event: AlertEvent dataclass instance

        Returns:
            True if published successfully
        """
        if self.client is None:
            logger.warning(
                f"Redis not available — would publish alert to dashboard: "
                f"type={event.alert_type.value} farm={event.farm_id}"
            )
            return False

        channel = f"farm:{event.farm_id}"
        message = {
            "type": "alert.created",
            "payload": {
                "id": event.metadata.get("alert_id", ""),
                "alert_type": event.alert_type.value,
                "severity": event.severity.value,
                "status": "active",
                "message": event.message,
                "animal_name": event.metadata.get("animal_name"),
                "created_at": datetime.fromtimestamp(
                    event.timestamp, tz=timezone.utc
                ).isoformat(),
            },
        }

        try:
            subscribers = self.client.publish(channel, json.dumps(message))
            logger.info(
                f"Dashboard alert published: channel={channel} "
                f"subscribers={subscribers} type={event.alert_type.value}"
            )
            return True
        except Exception as e:
            logger.error(f"Redis publish failed: {e}")
            return False
