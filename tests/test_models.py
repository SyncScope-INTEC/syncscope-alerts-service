"""
Tests for Alert models
"""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.alerts.models import AlertNotification, AlertRule, Notification, NotificationChannel


@pytest.mark.django_db
class TestAlertRule:
    """Tests for AlertRule model"""

    def test_create_alert_rule(self):
        """Test creating an alert rule"""
        company_id = uuid.uuid4()
        rule = AlertRule.objects.create(
            name="Test Rule",
            description="Test alert rule",
            company_id=company_id,
            metric_type="test_metric",
            condition="greater_than",
            threshold_value=100,
            check_interval_minutes=60,
            is_active=True,
        )

        assert rule.name == "Test Rule"
        assert rule.is_active is True
        assert rule.check_interval_minutes == 60
        assert rule.company_id == company_id


@pytest.mark.django_db
class TestAlertNotification:
    """Tests for AlertNotification model"""

    def test_create_alert_notification(self, alert_rule):
        """Test creating an alert notification"""
        user_id = uuid.uuid4()
        alert = AlertNotification.objects.create(
            rule=alert_rule,
            triggered_for_user_id=user_id,
            severity="high",
            title="Test Alert",
            message="This is a test alert",
            status="pending",
        )

        assert alert.title == "Test Alert"
        assert alert.status == "pending"
        assert alert.severity == "high"
        assert alert.triggered_for_user_id == user_id

    def test_acknowledge_alert(self, alert_notification):
        """Test acknowledging an alert notification"""
        user_id = uuid.uuid4()
        alert_notification.acknowledge(user_id)

        assert alert_notification.is_read is True
        assert alert_notification.status == "acknowledged"
        assert alert_notification.acknowledged_by == user_id
        assert alert_notification.acknowledged_at is not None

    def test_mark_as_read(self, alert_notification):
        """Test marking alert notification as read"""
        alert_notification.mark_as_read()

        assert alert_notification.is_read is True

    def test_resolve_alert(self, alert_notification):
        """Test resolving an alert notification"""
        user_id = uuid.uuid4()
        alert_notification.resolve(user_id)

        assert alert_notification.status == "resolved"
        assert alert_notification.is_read is True

    def test_mute_alert(self, alert_notification):
        """Test muting an alert notification"""
        alert_notification.mute()

        assert alert_notification.status == "muted"


@pytest.mark.django_db
class TestAlertRuleMethods:
    """Tests for AlertRule methods"""

    def test_get_last_alert_time(self, alert_rule):
        """Test getting last alert time"""
        # Initially no alerts
        last_time = alert_rule.get_last_alert_time()
        assert last_time is None

        # Create an alert
        user_id = uuid.uuid4()
        AlertNotification.objects.create(
            rule=alert_rule,
            triggered_for_user_id=user_id,
            severity="high",
            title="Test Alert",
            message="Test message",
            status="pending",
        )

        # Now should have a last alert time
        last_time = alert_rule.get_last_alert_time()
        assert last_time is not None

    def test_is_in_cooldown(self, alert_rule):
        """Test cooldown period check"""
        # Initially not in cooldown
        assert alert_rule.is_in_cooldown() is False

        # Create a recent alert
        user_id = uuid.uuid4()
        AlertNotification.objects.create(
            rule=alert_rule,
            triggered_for_user_id=user_id,
            severity="high",
            title="Test Alert",
            message="Test message",
            status="pending",
        )

        # Should be in cooldown
        assert alert_rule.is_in_cooldown() is True


@pytest.mark.django_db
class TestNotification:
    """Tests for Notification model"""

    def test_mark_sent(self, notification):
        """Test marking notification as sent"""
        notification.mark_sent()

        assert notification.status == "sent"
        assert notification.sent_at is not None

    def test_mark_read(self, notification):
        """Test marking notification as read"""
        notification.mark_read()

        assert notification.read_at is not None

    def test_mark_failed(self, notification):
        """Test marking notification as failed"""
        notification.mark_failed("Test error")

        assert notification.status == "failed"
        assert "error" in notification.delivery_metadata
        assert notification.delivery_metadata["error"] == "Test error"

    def test_mark_retrying(self, notification):
        """Test marking notification as retrying"""
        notification.mark_retrying()

        assert notification.status == "retrying"
        assert notification.delivery_metadata.get("retry_count") == 1

        # Retry again
        notification.mark_retrying()
        assert notification.delivery_metadata.get("retry_count") == 2


@pytest.fixture
def alert_rule():
    """Fixture for creating an alert rule"""
    company_id = uuid.uuid4()
    return AlertRule.objects.create(
        name="Test Rule",
        description="Test alert rule",
        company_id=company_id,
        metric_type="test_metric",
        condition="greater_than",
        threshold_value=100,
        check_interval_minutes=60,
        is_active=True,
    )


@pytest.fixture
def alert_notification(alert_rule):
    """Fixture for creating an alert notification"""
    user_id = uuid.uuid4()
    return AlertNotification.objects.create(
        rule=alert_rule,
        triggered_for_user_id=user_id,
        severity="high",
        title="Test Alert",
        message="This is a test alert",
        status="pending",
    )


@pytest.fixture
def notification(alert_notification):
    """Fixture for creating a notification"""
    user_id = uuid.uuid4()
    return Notification.objects.create(
        user_id=user_id,
        alert=alert_notification,
        notification_type="email",
        message="Test notification message",
        status="pending",
    )
