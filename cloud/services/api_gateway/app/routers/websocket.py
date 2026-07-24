"""
WebSocket endpoint for real-time position and alert updates.

Architecture:
  MQTT Writer → Redis Pub/Sub → This WebSocket endpoint → Dashboard clients

Each client subscribes to a farm channel. When the MQTT writer publishes
a position update or alert to Redis, this endpoint picks it up and
broadcasts to all connected clients on that farm.
"""

import asyncio
import json
import os
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

router = APIRouter()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev_secret_change_in_production")
JWT_ALGORITHM = "HS256"


class ConnectionManager:
    """Manages active WebSocket connections, grouped by farm."""

    def __init__(self):
        # farm_id -> set of WebSocket connections
        self.active_connections: dict[str, set[WebSocket]] = {}
        self._redis_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket, farm_id: str):
        await websocket.accept()
        if farm_id not in self.active_connections:
            self.active_connections[farm_id] = set()
        self.active_connections[farm_id].add(websocket)

        # Start Redis listener if not running
        if self._redis_task is None or self._redis_task.done():
            self._redis_task = asyncio.create_task(self._redis_listener())

    def disconnect(self, websocket: WebSocket, farm_id: str):
        if farm_id in self.active_connections:
            self.active_connections[farm_id].discard(websocket)
            if not self.active_connections[farm_id]:
                del self.active_connections[farm_id]

    async def broadcast_to_farm(self, farm_id: str, message: str):
        """Send a message to all clients connected to a farm."""
        connections = self.active_connections.get(farm_id, set())
        disconnected = set()
        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.add(connection)
        # Clean up dead connections
        for conn in disconnected:
            self.active_connections.get(farm_id, set()).discard(conn)

    async def _redis_listener(self):
        """Subscribe to all active farm channels on Redis and distribute messages."""
        try:
            redis = aioredis.from_url(REDIS_URL, decode_responses=True)
            pubsub = redis.pubsub()

            while True:
                # Subscribe to channels for all currently connected farms
                current_farms = set(self.active_connections.keys())
                if not current_farms:
                    await asyncio.sleep(1)
                    continue

                channels = [f"farm:{farm_id}" for farm_id in current_farms]
                await pubsub.subscribe(*channels)

                try:
                    async for message in pubsub.listen():
                        if message["type"] == "message":
                            channel = message["channel"]
                            # Extract farm_id from channel name "farm:<uuid>"
                            farm_id = channel.replace("farm:", "")
                            await self.broadcast_to_farm(farm_id, message["data"])

                        # Check if farm subscriptions changed
                        new_farms = set(self.active_connections.keys())
                        if new_farms != current_farms:
                            # Unsubscribe and re-subscribe with updated channels
                            await pubsub.unsubscribe()
                            break
                except Exception:
                    await pubsub.unsubscribe()
                    await asyncio.sleep(1)

        except Exception as e:
            print(f"Redis listener error: {e}")
            await asyncio.sleep(5)
            # Restart listener
            self._redis_task = asyncio.create_task(self._redis_listener())


manager = ConnectionManager()


def verify_ws_token(token: str) -> Optional[dict]:
    """Verify JWT token from WebSocket query parameter."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    farm: str = Query(...),
):
    """
    WebSocket endpoint for real-time updates.

    Clients connect with ?token=<jwt>&farm=<farm_uuid>.
    Server subscribes to the farm's Redis pub/sub channel
    and forwards position.update and alert.created events.
    """
    # Verify JWT
    payload = verify_ws_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="Invalid token")
        return

    farm_id = farm
    await manager.connect(websocket, farm_id)

    try:
        while True:
            # Keep connection alive; handle client messages (subscribe/unsubscribe)
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except (json.JSONDecodeError, KeyError):
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket, farm_id)
    except Exception:
        manager.disconnect(websocket, farm_id)
