"""
Tests for Alert Serializers
"""

import uuid

import pytest
from rest_framework.exceptions import ValidationError

from apps.alerts.models import AlertNotification, AlertRule, NotificationChannel
from apps.alerts.serializers import (
    AlertAcknowledgeSerializer,
    AlertResolveSerializer,
    AlertRuleDetailSerializer,
    AlertRuleSerializer,
    AlertRuleTestSerializer,
    AlertSerializer,
    AlertStatisticsSerializer,
    NotificationChannelSerializer,
    NotificationSerializer,
)


@pytest.mark.django_db
class TestAlertRuleSerializer:
    """Tests for AlertRuleSerializer"""

    def test_alert_rule_serialization(self):
        """Test serializing an alert rule"""
        company_id = uuid.uuid4()
        rule = AlertRule.objects.create(
            name="Test Rule",
            description="Test alert rule",
            company_id=company_id,
            metric_type="test_metric",
            condition={"operator": "gt", "value": 100},
            threshold_value=100,
            check_interval_minutes=60,
            is_active=True,
        )

        serializer = AlertRuleSerializer(rule)
        data = serializer.data

        assert data["name"] == "Test Rule"
        assert data["metric_type"] == "test_metric"
        assert data["is_active"] is True

    def test_alert_rule_deserialization(self):
        """Test deserializing alert rule data"""
        company_id = uuid.uuid4()
        data = {
            "name": "New Rule",
            "description": "New test rule",
            "company_id": str(company_id),
            "metric_type": "cpu_usage",
            "condition": {"operator": "gte", "value": 80},
            "threshold_value": 80,
            "check_interval_minutes": 30,
            "is_active": True,
        }

        serializer = AlertRuleSerializer(data=data)
        assert serializer.is_valid()
        rule = serializer.save()

        assert rule.name == "New Rule"
        assert rule.metric_type == "cpu_usage"

    def test_validate_condition_valid(self):
        """Test condition validation with valid data"""
        serializer = AlertRuleSerializer()

        valid_conditions = [
            {"operator": "gt", "value": 50},
            {"operator": "lt", "value": 30},
            {"operator": "eq", "value": 100},
            {"operator": "between", "min": 10, "max": 90},
            {"operator": "trend_up", "window": 5},
        ]

        for condition in valid_conditions:
            result = serializer.validate_condition(condition)
            assert result == condition

    def test_validate_condition_invalid_type(self):
        """Test condition validation with invalid type"""
        serializer = AlertRuleSerializer()

        with pytest.raises(ValidationError) as exc:
            serializer.validate_condition("invalid")

        assert "Condition must be a JSON object" in str(exc.value)

    def test_validate_condition_missing_operator(self):
        """Test condition validation without operator"""
        serializer = AlertRuleSerializer()

        with pytest.raises(ValidationError) as exc:
            serializer.validate_condition({"value": 100})

        assert "operator" in str(exc.value)

    def test_validate_condition_invalid_operator(self):
        """Test condition validation with invalid operator"""
        serializer = AlertRuleSerializer()

        with pytest.raises(ValidationError) as exc:
            serializer.validate_condition({"operator": "invalid_op"})

        assert "Invalid operator" in str(exc.value)

    def test_create_with_notification_channels(self):
        """Test creating alert rule with notification channels"""
        company_id = uuid.uuid4()
        channel = NotificationChannel.objects.create(
            name="Test Channel",
            type="email",
            config={"recipients": ["test@example.com"]},
            company_id=company_id,
        )

        data = {
            "name": "Rule with Channels",
            "company_id": str(company_id),
            "metric_type": "test",
            "condition": {"operator": "gt", "value": 10},
            "threshold_value": 10,
            "check_interval_minutes": 30,
            "notification_channels": [channel.id],
        }

        serializer = AlertRuleSerializer(data=data)
        assert serializer.is_valid()
        rule = serializer.save()

        assert rule.notification_channels.count() == 1

    def test_update_with_notification_channels(self):
        """Test updating alert rule with notification channels"""
        company_id = uuid.uuid4()
        rule = AlertRule.objects.create(
            name="Original Rule",
            company_id=company_id,
            metric_type="test",
            condition={"operator": "gt", "value": 10},
            threshold_value=10,
            check_interval_minutes=30,
        )

        channel = NotificationChannel.objects.create(
            name="New Channel",
            type="email",
            config={"recipients": ["new@example.com"]},
            company_id=company_id,
        )

        data = {
            "name": "Updated Rule",
            "company_id": str(company_id),
            "metric_type": "test",
            "condition": {"operator": "lt", "value": 5},
            "threshold_value": 5,
            "check_interval_minutes": 15,
            "notification_channels": [channel.id],
        }

        serializer = AlertRuleSerializer(rule, data=data)
        assert serializer.is_valid()
        updated_rule = serializer.save()

        assert updated_rule.name == "Updated Rule"
        assert updated_rule.notification_channels.count() == 1


@pytest.mark.django_db
class TestAlertRuleDetailSerializer:
    """Tests for AlertRuleDetailSerializer"""

    def test_detailed_serialization_with_channels(self):
        """Test detailed serialization includes channel details"""
        company_id = uuid.uuid4()
        channel = NotificationChannel.objects.create(
            name="Email Channel",
            type="email",
            config={"recipients": ["admin@example.com"]},
            company_id=company_id,
        )

        rule = AlertRule.objects.create(
            name="Detailed Rule",
            company_id=company_id,
            metric_type="test",
            condition={"operator": "gt", "value": 100},
            threshold_value=100,
            check_interval_minutes=60,
        )
        rule.notification_channels.add(channel)

        serializer = AlertRuleDetailSerializer(rule)
        data = serializer.data

        assert "notification_channels" in data
        assert len(data["notification_channels"]) == 1
        assert data["notification_channels"][0]["name"] == "Email Channel"


@pytest.mark.django_db
class TestAlertSerializer:
    """Tests for AlertSerializer"""

    def test_alert_serialization(self):
        """Test serializing an alert"""
        company_id = uuid.uuid4()
        rule = AlertRule.objects.create(
            name="Test Rule",
            company_id=company_id,
            metric_type="test",
            condition={"operator": "gt", "value": 10},
            threshold_value=10,
            check_interval_minutes=30,
        )

        alert = AlertNotification.objects.create(
            rule=rule,
            triggered_for_user_id=uuid.uuid4(),
            severity="high",
            title="Test Alert",
            message="Test message",
            status="pending",
            company_id=company_id,
        )

        serializer = AlertSerializer(alert)
        data = serializer.data

        assert data["title"] == "Test Alert"
        assert data["severity"] == "high"
        assert data["alert_rule_name"] == "Test Rule"


@pytest.mark.django_db
class TestAlertAcknowledgeSerializer:
    """Tests for AlertAcknowledgeSerializer"""

    def test_valid_acknowledge_data(self):
        """Test acknowledging alerts with valid data"""
        alert_ids = [uuid.uuid4(), uuid.uuid4()]
        data = {"alert_ids": [str(aid) for aid in alert_ids]}

        serializer = AlertAcknowledgeSerializer(data=data)
        assert serializer.is_valid()
        assert len(serializer.validated_data["alert_ids"]) == 2

    def test_invalid_acknowledge_data(self):
        """Test acknowledging alerts with invalid data"""
        data = {"alert_ids": ["not-a-uuid"]}

        serializer = AlertAcknowledgeSerializer(data=data)
        assert not serializer.is_valid()


@pytest.mark.django_db
class TestAlertResolveSerializer:
    """Tests for AlertResolveSerializer"""

    def test_valid_resolve_data(self):
        """Test resolving alerts with valid data"""
        alert_ids = [uuid.uuid4()]
        data = {"alert_ids": [str(aid) for aid in alert_ids]}

        serializer = AlertResolveSerializer(data=data)
        assert serializer.is_valid()


@pytest.mark.django_db
class TestNotificationChannelSerializer:
    """Tests for NotificationChannelSerializer"""

    def test_notification_channel_serialization(self):
        """Test serializing a notification channel"""
        company_id = uuid.uuid4()
        channel = NotificationChannel.objects.create(
            name="Email Channel",
            type="email",
            config={"recipients": ["test@example.com"]},
            company_id=company_id,
        )

        serializer = NotificationChannelSerializer(channel)
        data = serializer.data

        assert data["name"] == "Email Channel"
        assert data["channel_type"] == "email"

    def test_validate_config_email_valid(self):
        """Test email config validation with valid data"""
        data = {
            "name": "Email",
            "channel_type": "email",
            "config": {"recipients": ["admin@example.com", "dev@example.com"]},
            "company_id": str(uuid.uuid4()),
        }

        serializer = NotificationChannelSerializer(data=data)
        assert serializer.is_valid()

    def test_validate_config_email_missing_recipients(self):
        """Test email config validation without recipients"""
        data = {
            "name": "Email",
            "channel_type": "email",
            "config": {"other_field": "value"},
            "company_id": str(uuid.uuid4()),
        }

        serializer = NotificationChannelSerializer(data=data)
        assert not serializer.is_valid()
        assert "recipients" in str(serializer.errors)

    def test_validate_config_email_invalid_recipients_type(self):
        """Test email config validation with wrong recipients type"""
        data = {
            "name": "Email",
            "channel_type": "email",
            "config": {"recipients": "not-a-list"},
            "company_id": str(uuid.uuid4()),
        }

        serializer = NotificationChannelSerializer(data=data)
        assert not serializer.is_valid()

    def test_validate_config_slack_valid(self):
        """Test Slack config validation with valid data"""
        data = {
            "name": "Slack",
            "channel_type": "slack",
            "config": {"webhook_url": "https://hooks.slack.com/services/xxx"},
            "company_id": str(uuid.uuid4()),
        }

        serializer = NotificationChannelSerializer(data=data)
        assert serializer.is_valid()

    def test_validate_config_slack_missing_webhook(self):
        """Test Slack config validation without webhook_url"""
        data = {
            "name": "Slack",
            "channel_type": "slack",
            "config": {"channel": "#alerts"},
            "company_id": str(uuid.uuid4()),
        }

        serializer = NotificationChannelSerializer(data=data)
        assert not serializer.is_valid()
        assert "webhook_url" in str(serializer.errors)

    def test_validate_config_webhook_valid(self):
        """Test webhook config validation with valid data"""
        data = {
            "name": "Webhook",
            "channel_type": "webhook",
            "config": {"url": "https://example.com/webhook"},
            "company_id": str(uuid.uuid4()),
        }

        serializer = NotificationChannelSerializer(data=data)
        assert serializer.is_valid()

    def test_validate_config_webhook_missing_url(self):
        """Test webhook config validation without url"""
        data = {
            "name": "Webhook",
            "channel_type": "webhook",
            "config": {"method": "POST"},
            "company_id": str(uuid.uuid4()),
        }

        serializer = NotificationChannelSerializer(data=data)
        assert not serializer.is_valid()
        assert "url" in str(serializer.errors)

    def test_validate_config_invalid_type(self):
        """Test config validation with non-dict value"""
        data = {
            "name": "Invalid",
            "channel_type": "email",
            "config": "not-a-dict",
            "company_id": str(uuid.uuid4()),
        }

        serializer = NotificationChannelSerializer(data=data)
        assert not serializer.is_valid()


@pytest.mark.django_db
class TestAlertStatisticsSerializer:
    """Tests for AlertStatisticsSerializer"""

    def test_statistics_serialization(self):
        """Test serializing alert statistics"""
        stats = {
            "total_alerts": 100,
            "active_alerts": 20,
            "acknowledged_alerts": 50,
            "resolved_alerts": 30,
            "muted_alerts": 0,
            "critical_alerts": 5,
            "high_alerts": 15,
            "medium_alerts": 30,
            "low_alerts": 50,
            "alerts_by_type": {"metric": 80, "threshold": 20},
            "alerts_by_target": {"user": 60, "team": 40},
        }

        serializer = AlertStatisticsSerializer(stats)
        data = serializer.data

        assert data["total_alerts"] == 100
        assert data["active_alerts"] == 20
        assert data["alerts_by_type"]["metric"] == 80


@pytest.mark.django_db
class TestAlertRuleTestSerializer:
    """Tests for AlertRuleTestSerializer"""

    def test_valid_test_data(self):
        """Test alert rule test with valid data"""
        rule_id = uuid.uuid4()
        data = {
            "rule_id": str(rule_id),
            "test_data": {"metric_value": 150},
        }

        serializer = AlertRuleTestSerializer(data=data)
        assert serializer.is_valid()

    def test_test_data_without_optional_field(self):
        """Test alert rule test without optional test_data"""
        rule_id = uuid.uuid4()
        data = {"rule_id": str(rule_id)}

        serializer = AlertRuleTestSerializer(data=data)
        assert serializer.is_valid()
