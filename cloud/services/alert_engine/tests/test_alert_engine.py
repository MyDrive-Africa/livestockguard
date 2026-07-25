"""
Tests for the Alert Engine core logic:
- AlertEvent construction
- Cooldown / deduplication
- Severity → channel routing
- process_event dispatch decisions
"""

import os
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.main import (
    AlertEngine,
    AlertEvent,
    AlertSeverity,
    AlertType,
    NotificationChannel,
    SEVERITY_CHANNELS,
)


# ─── AlertEvent Construction ─────────────────────────

class TestAlertEvent:
    """AlertEvent dataclass behavior."""

    def test_create_event_with_required_fields(self):
        event = AlertEvent(
            alert_type=AlertType.GEOFENCE_BREACH,
            severity=AlertSeverity.HIGH,
            device_id="ABCD",
            farm_id="farm-123",
        )
        assert event.alert_type == AlertType.GEOFENCE_BREACH
        assert event.severity == AlertSeverity.HIGH
        assert event.device_id == "ABCD"
        assert event.farm_id == "farm-123"
        assert event.animal_id is None
        assert event.message == ""
        assert event.metadata == {}
        assert event.timestamp > 0

    def test_create_event_with_all_fields(self):
        event = AlertEvent(
            alert_type=AlertType.THEFT_DETECTED,
            severity=AlertSeverity.CRITICAL,
            device_id="1234",
            farm_id="farm-456",
            animal_id="animal-789",
            message="Vehicle speed detected",
            metadata={"alert_id": "abc-123", "animal_name": "Bella"},
            timestamp=1700000000.0,
        )
        assert event.animal_id == "animal-789"
        assert event.message == "Vehicle speed detected"
        assert event.metadata["animal_name"] == "Bella"
        assert event.timestamp == 1700000000.0


# ─── Severity → Channel Mapping ──────────────────────

class TestSeverityRouting:
    """Verify severity-to-channel mapping is correct."""

    def test_critical_routes_to_all_channels(self):
        channels = SEVERITY_CHANNELS[AlertSeverity.CRITICAL]
        assert NotificationChannel.PUSH in channels
        assert NotificationChannel.SMS in channels
        assert NotificationChannel.EMAIL in channels
        assert NotificationChannel.DASHBOARD in channels

    def test_high_routes_to_push_email_dashboard(self):
        channels = SEVERITY_CHANNELS[AlertSeverity.HIGH]
        assert NotificationChannel.PUSH in channels
        assert NotificationChannel.EMAIL in channels
        assert NotificationChannel.DASHBOARD in channels
        assert NotificationChannel.SMS not in channels

    def test_medium_routes_to_push_dashboard(self):
        channels = SEVERITY_CHANNELS[AlertSeverity.MEDIUM]
        assert NotificationChannel.PUSH in channels
        assert NotificationChannel.DASHBOARD in channels
        assert NotificationChannel.EMAIL not in channels

    def test_low_routes_to_dashboard_only(self):
        channels = SEVERITY_CHANNELS[AlertSeverity.LOW]
        assert channels == [NotificationChannel.DASHBOARD]

    def test_info_routes_to_dashboard_only(self):
        channels = SEVERITY_CHANNELS[AlertSeverity.INFO]
        assert channels == [NotificationChannel.DASHBOARD]


# ─── Cooldown / Deduplication ─────────────────────────

class TestCooldown:
    """AlertEngine cooldown prevents alert fatigue."""

    def test_first_alert_is_allowed(self):
        engine = AlertEngine(cooldown_seconds=300)
        event = AlertEvent(
            alert_type=AlertType.GEOFENCE_BREACH,
            severity=AlertSeverity.HIGH,
            device_id="DEV1",
            farm_id="farm-1",
        )
        assert engine.should_alert(event) is True

    def test_same_event_within_cooldown_is_suppressed(self):
        engine = AlertEngine(cooldown_seconds=300)
        event = AlertEvent(
            alert_type=AlertType.GEOFENCE_BREACH,
            severity=AlertSeverity.HIGH,
            device_id="DEV1",
            farm_id="farm-1",
        )
        # First time — record the cooldown
        engine._last_alert_times[engine._cooldown_key(event)] = time.time()

        # Immediately after — should be suppressed
        assert engine.should_alert(event) is False

    def test_same_event_after_cooldown_is_allowed(self):
        engine = AlertEngine(cooldown_seconds=10)
        event = AlertEvent(
            alert_type=AlertType.GEOFENCE_BREACH,
            severity=AlertSeverity.HIGH,
            device_id="DEV1",
            farm_id="farm-1",
        )
        # Set last alert to 20 seconds ago (past 10s cooldown)
        engine._last_alert_times[engine._cooldown_key(event)] = time.time() - 20

        assert engine.should_alert(event) is True

    def test_different_device_same_type_not_suppressed(self):
        engine = AlertEngine(cooldown_seconds=300)
        event1 = AlertEvent(
            alert_type=AlertType.GEOFENCE_BREACH,
            severity=AlertSeverity.HIGH,
            device_id="DEV1",
            farm_id="farm-1",
        )
        event2 = AlertEvent(
            alert_type=AlertType.GEOFENCE_BREACH,
            severity=AlertSeverity.HIGH,
            device_id="DEV2",
            farm_id="farm-1",
        )
        engine._last_alert_times[engine._cooldown_key(event1)] = time.time()

        # Different device — not suppressed
        assert engine.should_alert(event2) is True

    def test_same_device_different_type_not_suppressed(self):
        engine = AlertEngine(cooldown_seconds=300)
        event1 = AlertEvent(
            alert_type=AlertType.GEOFENCE_BREACH,
            severity=AlertSeverity.HIGH,
            device_id="DEV1",
            farm_id="farm-1",
        )
        event2 = AlertEvent(
            alert_type=AlertType.THEFT_DETECTED,
            severity=AlertSeverity.CRITICAL,
            device_id="DEV1",
            farm_id="farm-1",
        )
        engine._last_alert_times[engine._cooldown_key(event1)] = time.time()

        # Different alert type — not suppressed
        assert engine.should_alert(event2) is True

    def test_cooldown_key_format(self):
        engine = AlertEngine()
        event = AlertEvent(
            alert_type=AlertType.LOW_BATTERY,
            severity=AlertSeverity.MEDIUM,
            device_id="ABC",
            farm_id="farm-x",
        )
        key = engine._cooldown_key(event)
        assert key == "low_battery:ABC"


# ─── Process Event (Integration) ─────────────────────

class TestProcessEvent:
    """AlertEngine.process_event orchestration."""

    def test_process_event_calls_dispatch_when_allowed(self):
        engine = AlertEngine(cooldown_seconds=0)
        engine.dispatch = MagicMock()

        event = AlertEvent(
            alert_type=AlertType.THEFT_DETECTED,
            severity=AlertSeverity.CRITICAL,
            device_id="DEV1",
            farm_id="farm-1",
            message="Theft!",
        )
        result = engine.process_event(event)

        assert result is True
        engine.dispatch.assert_called_once()
        call_args = engine.dispatch.call_args
        assert call_args[0][0] == event
        assert NotificationChannel.PUSH in call_args[0][1]

    def test_process_event_returns_false_when_suppressed(self):
        engine = AlertEngine(cooldown_seconds=9999)
        event = AlertEvent(
            alert_type=AlertType.GEOFENCE_BREACH,
            severity=AlertSeverity.HIGH,
            device_id="DEV1",
            farm_id="farm-1",
        )
        # Pre-suppress
        engine._last_alert_times[engine._cooldown_key(event)] = time.time()

        result = engine.process_event(event)
        assert result is False

    def test_process_event_records_timestamp(self):
        engine = AlertEngine(cooldown_seconds=0)
        engine.dispatch = MagicMock()

        event = AlertEvent(
            alert_type=AlertType.DEVICE_OFFLINE,
            severity=AlertSeverity.LOW,
            device_id="DEV9",
            farm_id="farm-1",
        )
        engine.process_event(event)

        key = engine._cooldown_key(event)
        assert key in engine._last_alert_times
        assert time.time() - engine._last_alert_times[key] < 2
