"""Tests for Africa's Talking SMS dispatcher."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.main import AlertEvent, AlertSeverity, AlertType


def _make_event(**kwargs):
    defaults = dict(
        alert_type=AlertType.GEOFENCE_BREACH,
        severity=AlertSeverity.CRITICAL,
        device_id="DEV1",
        farm_id="farm-123",
        animal_id="animal-1",
        message="Bella has left Main Paddock",
        metadata={"animal_name": "Bella"},
        timestamp=1700000000.0,
    )
    defaults.update(kwargs)
    return AlertEvent(**defaults)


class TestAfricasTalkingSMSDispatcher:
    """SMS dispatcher unit tests."""

    def test_no_phone_numbers_returns_false(self):
        from app.dispatchers.sms_africastalking import AfricasTalkingSMSDispatcher

        dispatcher = AfricasTalkingSMSDispatcher(username="", api_key="")
        event = _make_event()
        assert dispatcher.dispatch(event, phone_numbers=[]) is False

    def test_not_initialized_returns_false(self):
        from app.dispatchers.sms_africastalking import AfricasTalkingSMSDispatcher

        dispatcher = AfricasTalkingSMSDispatcher(username="", api_key="")
        event = _make_event()
        result = dispatcher.dispatch(event, phone_numbers=["+27821234567"])
        assert result is False

    def test_format_message_critical(self):
        from app.dispatchers.sms_africastalking import AfricasTalkingSMSDispatcher

        dispatcher = AfricasTalkingSMSDispatcher(username="", api_key="")
        event = _make_event(severity=AlertSeverity.CRITICAL)
        msg = dispatcher._format_message(event)
        assert "CRITICAL" in msg
        assert "Geofence Breach" in msg
        assert "Bella" in msg
        assert "LivestockGuard" in msg

    def test_format_message_high(self):
        from app.dispatchers.sms_africastalking import AfricasTalkingSMSDispatcher

        dispatcher = AfricasTalkingSMSDispatcher(username="", api_key="")
        event = _make_event(severity=AlertSeverity.HIGH)
        msg = dispatcher._format_message(event)
        assert "ALERT" in msg
        assert "Bella" in msg

    def test_format_message_default_severity(self):
        from app.dispatchers.sms_africastalking import AfricasTalkingSMSDispatcher

        dispatcher = AfricasTalkingSMSDispatcher(username="", api_key="")
        event = _make_event(severity=AlertSeverity.LOW)
        msg = dispatcher._format_message(event)
        assert "LivestockGuard" in msg

    def test_format_message_unknown_alert_type(self):
        from app.dispatchers.sms_africastalking import AfricasTalkingSMSDispatcher

        dispatcher = AfricasTalkingSMSDispatcher(username="", api_key="")
        event = _make_event(alert_type=AlertType.UNUSUAL_ACTIVITY)
        msg = dispatcher._format_message(event)
        assert "Unusual Activity" in msg

    def test_env_loading(self):
        from app.dispatchers.sms_africastalking import AfricasTalkingSMSDispatcher

        with patch.dict(os.environ, {
            "AT_USERNAME": "testuser",
            "AT_API_KEY": "testkey123",
            "AT_SENDER_ID": "MYFARM",
            "AT_ENVIRONMENT": "production",
        }):
            dispatcher = AfricasTalkingSMSDispatcher()
            assert dispatcher.username == "testuser"
            assert dispatcher.api_key == "testkey123"
            assert dispatcher.sender_id == "MYFARM"
            assert dispatcher.environment == "production"

    def test_check_balance_not_initialized(self):
        from app.dispatchers.sms_africastalking import AfricasTalkingSMSDispatcher

        dispatcher = AfricasTalkingSMSDispatcher(username="", api_key="")
        assert dispatcher.check_balance() is None
