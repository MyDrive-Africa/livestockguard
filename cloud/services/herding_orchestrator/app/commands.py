"""Robot command emitter — publishes herding commands to robots over MQTT.

The orchestrator gives robots *intent* (go here, shepherd this animal). The robot
(or the robot simulator) subscribes to ``lg/robot/{serial}/cmd``, decides how to
execute safely, and streams telemetry/acks back. Telemetry ingest is handled by
the mqtt_writer service, not here.

Commands are versioned JSON with a TTL so a robot discards stale orders if it was
briefly offline.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from app import config
from app.assigner import Assignment

logger = logging.getLogger("herding_orchestrator.commands")

# Map an assigner action to the wire ``cmd`` value the robot understands.
_ACTION_TO_CMD = {
    "shepherd": "shepherd",
    "intercept": "move_to",
    "patrol": "patrol",
    "return_home": "return_home",
    "stop": "stop",
}


class CommandBridge:
    """Thin wrapper over a paho MQTT client for publishing robot commands."""

    def __init__(self, host: str | None = None, port: int | None = None):
        self._host = host or config.MQTT_HOST
        self._port = port or config.MQTT_PORT
        self._client = mqtt.Client(client_id="herding_orchestrator")
        self._connected = False

    def connect(self) -> None:
        """Connect to the broker and start the network loop in a background thread."""
        try:
            self._client.connect(self._host, self._port, keepalive=30)
            self._client.loop_start()
            self._connected = True
            logger.info("Command bridge connected to MQTT %s:%s", self._host, self._port)
        except Exception as exc:  # noqa: BLE001 — log and degrade gracefully
            logger.error("MQTT connect failed (%s); commands will be dropped", exc)
            self._connected = False

    def disconnect(self) -> None:
        """Stop the network loop and disconnect."""
        try:
            self._client.loop_stop()
            self._client.disconnect()
        finally:
            self._connected = False

    def build_command(self, assignment: Assignment) -> dict:
        """Serialise an Assignment into a robot command payload."""
        cmd = _ACTION_TO_CMD.get(assignment.action, "patrol")
        payload: dict = {
            "v": 1,
            "cmd": cmd,
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "ttl_sec": config.COMMAND_TTL_SEC,
        }
        target = assignment.target
        if target is not None:
            payload["target"] = {"lat": target.intercept_lat, "lon": target.intercept_lon}
            payload["animal_id"] = target.animal_id
            payload["job_type"] = target.job_type
            # Presence + sound: escalate the deterrent for a breach vs a gentle nudge.
            payload["deterrent"] = "audio_high" if target.job_type == "shepherd" else "audio_low"
        return payload

    def send(self, assignment: Assignment) -> dict:
        """Publish the command for one assignment. Returns the payload sent."""
        payload = self.build_command(assignment)
        topic = config.MQTT_CMD_TOPIC.format(serial=assignment.serial)
        body = json.dumps(payload)
        if self._connected:
            # QoS 2 for stop (safety-critical), QoS 1 otherwise.
            qos = 2 if payload["cmd"] == "stop" else 1
            self._client.publish(topic, body, qos=qos)
            logger.info("-> %s %s", topic, payload["cmd"])
        else:
            logger.warning("MQTT down; would send %s %s", topic, payload["cmd"])
        return payload

    def send_all(self, assignments: list[Assignment]) -> None:
        """Publish commands for every assignment in a planning pass."""
        for a in assignments:
            self.send(a)
