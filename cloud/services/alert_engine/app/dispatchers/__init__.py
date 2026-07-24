"""
Alert dispatchers — send notifications through various channels.

Each dispatcher is an async callable that takes an AlertEvent and delivers it
to its respective channel (email, push, SMS, webhook, dashboard).
"""

from .email_ses import SESEmailDispatcher
from .push_fcm import FCMPushDispatcher
from .dashboard_redis import DashboardRedisDispatcher
from .webhook import WebhookDispatcher

__all__ = [
    "SESEmailDispatcher",
    "FCMPushDispatcher",
    "DashboardRedisDispatcher",
    "WebhookDispatcher",
]
