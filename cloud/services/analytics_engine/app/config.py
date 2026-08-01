"""Analytics Engine configuration — thresholds, schedules, and feature flags."""

import os

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://livestockguard:livestockguard@postgres:5432/livestockguard"
)

# Schedule (cron-style)
BASELINE_CRON_HOUR = int(os.getenv("BASELINE_CRON_HOUR", "2"))  # 02:00
ANOMALY_CHECK_INTERVAL_HOURS = int(os.getenv("ANOMALY_CHECK_INTERVAL_HOURS", "2"))
DAILY_REPORT_HOUR = int(os.getenv("DAILY_REPORT_HOUR", "18"))  # 18:00
WEEKLY_REPORT_DAY = os.getenv("WEEKLY_REPORT_DAY", "sun")  # APScheduler day_of_week
WEEKLY_REPORT_HOUR = int(os.getenv("WEEKLY_REPORT_HOUR", "19"))

# Baseline parameters
BASELINE_WINDOW_DAYS = int(os.getenv("BASELINE_WINDOW_DAYS", "7"))
MIN_SIGHTINGS_FOR_BASELINE = int(os.getenv("MIN_SIGHTINGS_FOR_BASELINE", "20"))

# Anomaly thresholds
REDUCED_MOVEMENT_Z_THRESHOLD = float(os.getenv("REDUCED_MOVEMENT_Z_THRESHOLD", "-2.0"))
ISOLATION_HOURS_THRESHOLD = float(os.getenv("ISOLATION_HOURS_THRESHOLD", "4"))
PATROL_GAP_DAYS_THRESHOLD = int(os.getenv("PATROL_GAP_DAYS_THRESHOLD", "3"))
NIGHT_MOVEMENT_START_HOUR = int(os.getenv("NIGHT_MOVEMENT_START_HOUR", "22"))
NIGHT_MOVEMENT_END_HOUR = int(os.getenv("NIGHT_MOVEMENT_END_HOUR", "4"))

# Herd cohesion
COHESION_COMPANION_THRESHOLD = float(os.getenv("COHESION_COMPANION_THRESHOLD", "0.6"))

# Suggestions
SUGGESTION_EXPIRY_DAYS = int(os.getenv("SUGGESTION_EXPIRY_DAYS", "7"))

# Run-on-startup: useful for dev/demo — run all jobs immediately at boot
RUN_ON_STARTUP = os.getenv("RUN_ON_STARTUP", "true").lower() in ("true", "1", "yes")
