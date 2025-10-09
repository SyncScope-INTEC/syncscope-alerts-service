"""
Tests for Alert models
"""

import uuid

import pytest
from django.utils import timezone

from apps.alerts.models import AlertNotification, AlertRule, NotificationChannel


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
