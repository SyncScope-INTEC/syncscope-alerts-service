"""
Tests for Alert models
"""

import pytest
from django.utils import timezone

from apps.alerts.models import Alert, AlertRule, NotificationChannel


@pytest.mark.django_db
class TestAlertRule:
    """Tests for AlertRule model"""

    def test_create_alert_rule(self):
        """Test creating an alert rule"""
        rule = AlertRule.objects.create(
            name="Test Rule",
            description="Test alert rule",
            rule_type="threshold_breach",
            metric_type="test_metric",
            condition={"operator": "gt"},
            threshold_value=100,
            severity="high",
            target_type="user",
            company_id="00000000-0000-0000-0000-000000000001",
            created_by="00000000-0000-0000-0000-000000000002",
        )

        assert rule.name == "Test Rule"
        assert rule.is_active is True
        assert rule.cooldown_minutes == 60


@pytest.mark.django_db
class TestAlert:
    """Tests for Alert model"""

    def test_create_alert(self, alert_rule):
        """Test creating an alert"""
        alert = Alert.objects.create(
            alert_rule=alert_rule,
            state="active",
            severity="high",
            title="Test Alert",
            message="This is a test alert",
            target_type="user",
            target_id="00000000-0000-0000-0000-000000000001",
            company_id="00000000-0000-0000-0000-000000000001",
        )

        assert alert.title == "Test Alert"
        assert alert.state == "active"

    def test_acknowledge_alert(self, alert):
        """Test acknowledging an alert"""
        user_id = "00000000-0000-0000-0000-000000000002"
        alert.acknowledge(user_id)

        assert alert.state == "acknowledged"
        assert alert.acknowledged_by == user_id
        assert alert.acknowledged_at is not None


@pytest.fixture
def alert_rule():
    """Fixture for creating an alert rule"""
    return AlertRule.objects.create(
        name="Test Rule",
        description="Test alert rule",
        rule_type="threshold_breach",
        metric_type="test_metric",
        condition={"operator": "gt"},
        threshold_value=100,
        severity="high",
        target_type="user",
        company_id="00000000-0000-0000-0000-000000000001",
        created_by="00000000-0000-0000-0000-000000000002",
    )


@pytest.fixture
def alert(alert_rule):
    """Fixture for creating an alert"""
    return Alert.objects.create(
        alert_rule=alert_rule,
        state="active",
        severity="high",
        title="Test Alert",
        message="This is a test alert",
        target_type="user",
        target_id="00000000-0000-0000-0000-000000000001",
        company_id="00000000-0000-0000-0000-000000000001",
    )
