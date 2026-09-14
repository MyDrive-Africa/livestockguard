"""
Redis pub/sub helper for the analytics engine.

The analytics engine primarily writes to Postgres, but some jobs (the
missing-animal detector) need to hand alert events to the alert_engine, which
listens on the Redis `alerts:incoming` channel. This module owns a lazily-created
async Redis client so jobs can publish without each managing a connection.

Publish failures are logged and swallowed — a Redis hiccup must not abort an
analysis run or leave a DB transaction half-applied.
"""

import json
import logging
import os
from typing import Optional

import redis.asyncio as aioredis

logger = logging.getLogger("analytics_engine.redis_bus")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
ALERTS_INCOMING_CHANNEL = "alerts:incoming"

_client: Optional[aioredis.Redis] = None


async def _get_client() -> Optional[aioredis.Redis]:
    """Return a shared async Redis client, creating it on first use."""
    global _client
    if _client is None:
        try:
            _client = aioredis.from_url(REDIS_URL, decode_responses=True)
            await _client.ping()
            logger.info(f"Redis connected for alert publishing: {REDIS_URL}")
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}) — alert dispatch will be skipped")
            _client = None
    return _client


async def publish_alert_incoming(event: dict) -> bool:
    """
    Publish an alert event to the alert_engine's `alerts:incoming` channel.

    Args:
        event: dict matching the alert_engine AlertEvent schema (alert_type,
               severity, device_id, farm_id, animal_id, message, metadata, timestamp).

    Returns:
        True if published, False if Redis was unavailable or the publish failed.
    """
    client = await _get_client()
    if client is None:
        return False
    try:
        await client.publish(ALERTS_INCOMING_CHANNEL, json.dumps(event))
        return True
    except Exception as e:
        logger.warning(f"Failed to publish alert to {ALERTS_INCOMING_CHANNEL}: {e}")
        return False


async def close():
    """Close the shared Redis client (used on shutdown)."""
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        except Exception:
            pass
        _client = None
