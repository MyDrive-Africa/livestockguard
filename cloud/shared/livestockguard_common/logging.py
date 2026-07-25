"""
Structured JSON logging for all LivestockGuard services.

Provides consistent log format across API Gateway, Alert Engine, and MQTT Writer.
Outputs JSON in production, human-readable in development.

Usage:
    from livestockguard_common.logging import setup_logging, get_logger

    setup_logging(service="api_gateway")
    logger = get_logger(__name__)
    logger.info("Request processed", extra={"user_id": "abc", "latency_ms": 42})
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON lines for structured log aggregation."""

    def __init__(self, service: str = "unknown"):
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "service": self.service,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add source location
        if record.levelno >= logging.WARNING:
            log_entry["source"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Add exception info
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields (user_id, request_id, latency, etc.)
        standard_attrs = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'pathname',
            'process', 'processName', 'relativeCreated', 'stack_info',
            'thread', 'threadName', 'exc_info', 'exc_text', 'msecs',
            'message', 'taskName',
        }
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in standard_attrs and not k.startswith('_')
        }
        if extras:
            log_entry["context"] = extras

        return json.dumps(log_entry, default=str)


class DevFormatter(logging.Formatter):
    """Human-readable colored formatter for development."""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[1;31m',  # Bold Red
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, '')
        ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        msg = f"{color}{ts} [{record.levelname[0]}]{self.RESET} {record.name}: {record.getMessage()}"

        if record.exc_info:
            msg += f"\n{self.formatException(record.exc_info)}"

        return msg


def setup_logging(
    service: str = "livestockguard",
    level: Optional[str] = None,
    json_output: Optional[bool] = None,
) -> None:
    """
    Configure structured logging for a service.

    Args:
        service: Service name (appears in all log entries)
        level: Log level (default: from LOG_LEVEL env or INFO)
        json_output: Force JSON output (default: auto-detect from environment)
    """
    log_level = level or os.environ.get("LOG_LEVEL", "INFO")
    use_json = json_output if json_output is not None else os.environ.get("LOG_FORMAT") == "json"

    # Auto-detect: use JSON in production (when not a TTY)
    if json_output is None and not sys.stderr.isatty():
        use_json = True

    root = logging.getLogger()
    root.setLevel(log_level.upper())

    # Remove existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    if use_json:
        handler.setFormatter(JSONFormatter(service=service))
    else:
        handler.setFormatter(DevFormatter())

    root.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(name)
