"""
Tests for alert dispatchers:
- WebhookDispatcher: URL loading, payload format, HTTP calls
- DashboardRedisDispatcher: channel naming, message format
- SESEmailDispatcher: template selection, format vars
- FCMPushDispatcher: title building, priority mapping
"""

import os
import sys
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.main import AlertEvent, AlertSeverity, AlertType


# ─── Webhook Dispatcher ──────────────────────────────

class TestWebhookDispatcher:
    """WebhookDispatcher tests."""

    def _make_event(self, **kwargs):
        defaults = dict(
            alert_type=AlertType.GEOFENCE_BREACH,
            severity=AlertSeverity.HIGH,
            device_id="DEV1",
            farm_id="farm-123",
            animal_id="animal-456",
            message="Bella left paddock",
            metadata={"alert_id": "a1"},
            timestamp=1700000000.0,
        )
        defaults.update(kwargs)
        return AlertEvent(**defaults)

    def test_no_urls_returns_false(self):
        from app.dispatchers.webhook import WebhookDispatcher

        dispatcher = WebhookDispatcher(webhook_urls=[])
        event = self._make_event()
        assert dispatcher.dispatch(event) is False

    def test_load_urls_from_env(self):
        from app.dispatchers.webhook import WebhookDispatcher

        with patch.dict(os.environ, {"WEBHOOK_URLS": "http://a.com/hook, http://b.com/hook"}):
            dispatcher = WebhookDispatcher()
            assert len(dispatcher.webhook_urls) == 2
            assert "http://a.com/hook" in dispatcher.webhook_urls

    @patch("app.dispatchers.webhook.httpx")
    def test_dispatch_posts_json_payload(self, mock_httpx):
        from app.dispatchers.webhook import WebhookDispatcher

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_httpx.Client.return_value = mock_client

        dispatcher = WebhookDispatcher(webhook_urls=["http://test.com/webhook"])
        event = self._make_event()
        result = dispatcher.dispatch(event)

        assert result is True
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == "http://test.com/webhook"
        payload = call_kwargs[1]["json"]
        assert payload["event"] == "alert.created"
        assert payload["alert_type"] == "geofence_breach"
        assert payload["severity"] == "high"
        assert payload["farm_id"] == "farm-123"

    @patch("app.dispatchers.webhook.httpx")
    def test_dispatch_handles_failed_response(self, mock_httpx):
        from app.dispatchers.webhook import WebhookDispatcher

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_httpx.Client.return_value = mock_client

        dispatcher = WebhookDispatcher(webhook_urls=["http://fail.com/hook"])
        event = self._make_event()
        result = dispatcher.dispatch(event)

        assert result is False


# ─── Dashboard Redis Dispatcher ──────────────────────

class TestDashboardRedisDispatcher:
    """DashboardRedisDispatcher tests."""

    def _make_event(self, **kwargs):
        defaults = dict(
            alert_type=AlertType.THEFT_DETECTED,
            severity=AlertSeverity.CRITICAL,
            device_id="DEV2",
            farm_id="farm-abc",
            message="Theft detected",
            metadata={"alert_id": "x1", "animal_name": "Duke"},
            timestamp=1700000000.0,
        )
        defaults.update(kwargs)
        return AlertEvent(**defaults)

    def test_dispatch_without_redis_returns_false(self):
        from app.dispatchers.dashboard_redis import DashboardRedisDispatcher

        dispatcher = DashboardRedisDispatcher()
        dispatcher._client = None  # Force no connection

        event = self._make_event()
        # Mock the client property to return None
        with patch.object(type(dispatcher), 'client', new_callable=PropertyMock, return_value=None):
            result = dispatcher.dispatch(event)
            assert result is False

    def test_dispatch_publishes_to_farm_channel(self):
        from app.dispatchers.dashboard_redis import DashboardRedisDispatcher

        mock_redis = MagicMock()
        mock_redis.publish.return_value = 2  # 2 subscribers

        dispatcher = DashboardRedisDispatcher()
        dispatcher._client = mock_redis

        event = self._make_event()
        with patch.object(type(dispatcher), 'client', new_callable=PropertyMock, return_value=mock_redis):
            result = dispatcher.dispatch(event)

        assert result is True
        mock_redis.publish.assert_called_once()
        channel = mock_redis.publish.call_args[0][0]
        assert channel == "farm:farm-abc"

        # Verify message format
        import json
        message = json.loads(mock_redis.publish.call_args[0][1])
        assert message["type"] == "alert.created"
        assert message["payload"]["alert_type"] == "theft_detected"
        assert message["payload"]["severity"] == "critical"
        assert message["payload"]["animal_name"] == "Duke"


# ─── SES Email Dispatcher ────────────────────────────

class TestSESEmailDispatcher:
    """SESEmailDispatcher tests."""

    def _make_event(self, **kwargs):
        defaults = dict(
            alert_type=AlertType.GEOFENCE_BREACH,
            severity=AlertSeverity.HIGH,
            device_id="DEV3",
            farm_id="farm-xyz",
            animal_id="animal-1",
            message="Bella has left Main Paddock",
            metadata={},
            timestamp=1700000000.0,
        )
        defaults.update(kwargs)
        return AlertEvent(**defaults)

    def test_no_recipients_returns_false(self):
        from app.dispatchers.email_ses import SESEmailDispatcher

        dispatcher = SESEmailDispatcher()
        event = self._make_event()
        result = dispatcher.dispatch(event, recipient_emails=[])
        assert result is False

    def test_no_client_returns_false(self):
        from app.dispatchers.email_ses import SESEmailDispatcher

        dispatcher = SESEmailDispatcher()
        dispatcher._client = None

        event = self._make_event()
        with patch.object(type(dispatcher), 'client', new_callable=PropertyMock, return_value=None):
            result = dispatcher.dispatch(event, recipient_emails=["test@test.com"])
            assert result is False

    def test_dispatch_calls_ses_send_email(self):
        from app.dispatchers.email_ses import SESEmailDispatcher

        mock_ses = MagicMock()
        mock_ses.send_email.return_value = {"MessageId": "msg-123"}

        dispatcher = SESEmailDispatcher()
        dispatcher._client = mock_ses

        event = self._make_event()
        with patch.object(type(dispatcher), 'client', new_callable=PropertyMock, return_value=mock_ses):
            result = dispatcher.dispatch(event, recipient_emails=["farmer@test.com"])

        assert result is True
        mock_ses.send_email.assert_called_once()
        call_kwargs = mock_ses.send_email.call_args[1]
        assert call_kwargs["Destination"]["ToAddresses"] == ["farmer@test.com"]
        assert "Geofence Breach" in call_kwargs["Message"]["Subject"]["Data"]

    def test_theft_template_used_for_theft_alert(self):
        from app.dispatchers.email_ses import SESEmailDispatcher, EMAIL_TEMPLATES

        template = EMAIL_TEMPLATES["theft_detected"]
        assert "THEFT ALERT" in template["subject"]
        assert "IMMEDIATE ACTION" in template["body_template"]

    def test_html_wrap_produces_valid_html(self):
        from app.dispatchers.email_ses import SESEmailDispatcher

        dispatcher = SESEmailDispatcher()
        html = dispatcher._html_wrap("Test Subject", "Test body\nLine 2")
        assert "<html>" in html
        assert "Test Subject" in html
        assert "Test body<br/>Line 2" in html
        assert "LivestockGuard" in html


# ─── FCM Push Dispatcher ─────────────────────────────

class TestFCMPushDispatcher:
    """FCMPushDispatcher tests."""

    def _make_event(self, **kwargs):
        defaults = dict(
            alert_type=AlertType.THEFT_DETECTED,
            severity=AlertSeverity.CRITICAL,
            device_id="DEV4",
            farm_id="farm-999",
            message="Vehicle speed detected",
            metadata={},
            timestamp=1700000000.0,
        )
        defaults.update(kwargs)
        return AlertEvent(**defaults)

    def test_not_initialized_returns_false(self):
        from app.dispatchers.push_fcm import FCMPushDispatcher

        dispatcher = FCMPushDispatcher.__new__(FCMPushDispatcher)
        dispatcher._initialized = False

        event = self._make_event()
        result = dispatcher.dispatch(event, topic="farm_test")
        assert result is False

    def test_build_title_critical(self):
        from app.dispatchers.push_fcm import FCMPushDispatcher

        dispatcher = FCMPushDispatcher.__new__(FCMPushDispatcher)
        dispatcher._initialized = False

        event = self._make_event(
            alert_type=AlertType.THEFT_DETECTED,
            severity=AlertSeverity.CRITICAL,
        )
        title = dispatcher._build_title(event)
        assert "🚨" in title
        assert "THEFT ALERT" in title

    def test_build_title_low_severity(self):
        from app.dispatchers.push_fcm import FCMPushDispatcher

        dispatcher = FCMPushDispatcher.__new__(FCMPushDispatcher)
        dispatcher._initialized = False

        event = self._make_event(
            alert_type=AlertType.LOW_BATTERY,
            severity=AlertSeverity.LOW,
        )
        title = dispatcher._build_title(event)
        assert "⚠️" in title
        assert "Low Battery" in title

    def test_severity_priority_mapping(self):
        from app.dispatchers.push_fcm import SEVERITY_PRIORITY

        assert SEVERITY_PRIORITY["critical"] == "high"
        assert SEVERITY_PRIORITY["high"] == "high"
        assert SEVERITY_PRIORITY["medium"] == "normal"
        assert SEVERITY_PRIORITY["low"] == "normal"
