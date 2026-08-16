"""
Structured JSON logging for all LivestockGuard services.

In production/staging: outputs JSON lines (CloudWatch/ELK compatible).
In development: outputs human-readable colored text.

Usage:
    from livestockguard_common.logging import setup_logging
    setup_logging()  # Call once at service startup
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone


ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").lower()


class JsonFormatter(logging.Formatter):
    """Format log records as JSON for structured logging in production."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": os.environ.get("SERVICE_NAME", "livestockguard"),
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        return json.dumps(log_entry, default=str)


class DevFormatter(logging.Formatter):
    """Human-readable colored formatter for development."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        timestamp = datetime.now().strftime("%H:%M:%S")
        return f"{color}{timestamp} [{record.levelname:>7}]{self.RESET} {record.name}: {record.getMessage()}"


def setup_logging(level: str = "INFO", service_name: str | None = None):
    """
    Configure logging for the entire application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        service_name: Override SERVICE_NAME env var
    """
    if service_name:
        os.environ["SERVICE_NAME"] = service_name

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    if ENVIRONMENT in ("production", "staging"):
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(DevFormatter())

    root_logger.addHandler(handler)

    # Quieten noisy libraries
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
