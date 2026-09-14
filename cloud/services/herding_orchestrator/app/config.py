"""Herding Orchestrator configuration — control loop, thresholds, MQTT, feature flags.

All values are read from environment variables with dev-friendly defaults so the
service runs under Docker Compose without extra setup (matches analytics_engine).
"""

import os

# --- Database ---
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://livestockguard:livestockguard@postgres:5432/livestockguard",
)

# --- Redis (live position cache + fleet/job fan-out to the dashboard) ---
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# --- MQTT (command delivery to robots, telemetry ingest is done by mqtt_writer) ---
MQTT_HOST = os.getenv("MQTT_HOST", "emqx")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
# Topic templates. {serial} is the robot's serial_number.
MQTT_CMD_TOPIC = os.getenv("MQTT_CMD_TOPIC", "lg/robot/{serial}/cmd")

# --- Control loop ---
# How often the sense -> plan -> assign -> command loop runs, in seconds.
LOOP_INTERVAL_SEC = float(os.getenv("HERDING_LOOP_INTERVAL_SEC", "3.0"))

# Global operating mode default when a farm has no explicit override.
#   auto   — orchestrator plans and commands robots autonomously
#   manual — orchestrator observes only; commands come from the API (operator)
#   paused — no planning, no commands (fleet holds position)
DEFAULT_MODE = os.getenv("HERDING_DEFAULT_MODE", "auto")

# --- Containment thresholds ---
# An animal within this many metres of the boundary edge is APPROACHING.
# (Falls back to per-geofence buffer_m when that is set; this is the global default.)
DEFAULT_BUFFER_M = float(os.getenv("HERDING_DEFAULT_BUFFER_M", "15.0"))

# Ignore stale positions older than this (seconds) — a cow we haven't heard from
# recently should not trigger a dispatch on outdated data.
MAX_POSITION_AGE_SEC = float(os.getenv("HERDING_MAX_POSITION_AGE_SEC", "120"))

# --- Assignment / dispatch ---
# Don't send a robot below this battery to a new job; route it home to charge.
MIN_BATTERY_FOR_JOB_PCT = int(os.getenv("HERDING_MIN_BATTERY_FOR_JOB_PCT", "20"))

# Merge targets closer than this into a single shepherding job (one robot, cluster).
CLUSTER_MERGE_RADIUS_M = float(os.getenv("HERDING_CLUSTER_MERGE_RADIUS_M", "40"))

# Command time-to-live: robot discards a command older than this.
COMMAND_TTL_SEC = int(os.getenv("HERDING_COMMAND_TTL_SEC", "60"))

# --- Run-on-startup: run one loop immediately at boot (useful for dev/demo) ---
RUN_ON_STARTUP = os.getenv("RUN_ON_STARTUP", "true").lower() in ("true", "1", "yes")
