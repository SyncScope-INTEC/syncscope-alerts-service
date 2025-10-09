"""
Tests for Alert Views
"""

import uuid
from unittest.mock import Mock, patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.alerts.models import AlertNotification, AlertRule, NotificationChannel


@pytest.fixture
def api_client():
    """Fixture for API client"""
    return APIClient()


@pytest.fixture
def mock_user():
    """Fixture for authenticated user"""
    user = Mock()
    user.id = uuid.uuid4()
    user.company_id = uuid.uuid4()
    user.email = "test@example.com"
    user.is_authenticated = True
    return user


@pytest.fixture
def company_id():
    """Fixture for company ID"""
    return uuid.uuid4()


@pytest.fixture
def alert_rule(company_id):
    """Fixture for creating an alert rule"""
    return AlertRule.objects.create(
        name="Test Rule",
        description="Test alert rule",
        company_id=company_id,
        metric_type="test_metric",
        condition={"operator": "gt", "value": 100},
        threshold_value=100,
        check_interval_minutes=60,
        is_active=True,
    )


@pytest.fixture
def alert_notification(alert_rule, company_id):
    """Fixture for creating an alert notification"""
    user_id = uuid.uuid4()
    return AlertNotification.objects.create(
        rule=alert_rule,
        triggered_for_user_id=user_id,
        severity="high",
        title="Test Alert",
        message="This is a test alert",
        status="pending",
        company_id=company_id,
    )


@pytest.fixture
def notification_channel(company_id):
    """Fixture for creating a notification channel"""
    return NotificationChannel.objects.create(
        name="Test Channel",
        type="email",
        config={"email": "test@example.com"},
        is_active=True,
        company_id=company_id,
    )


@pytest.mark.django_db
class TestAPIHome:
    """Tests for API home endpoint"""

    def test_api_home(self, api_client):
        """Test API home endpoint returns correct info"""
        response = api_client.get("/api/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["service"] == "SyncScope Alerts Service"
        assert data["version"] == "1.0.0"
        assert data["status"] == "operational"
        assert "endpoints" in data


@pytest.mark.django_db
class TestAlertRuleViewSet:
    """Tests for AlertRule ViewSet"""

    def test_list_alert_rules(self, api_client, mock_user, alert_rule):
        """Test listing alert rules"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = alert_rule.company_id

        response = api_client.get("/api/rules/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_create_alert_rule(self, api_client, mock_user, company_id):
        """Test creating an alert rule"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = company_id

        data = {
            "name": "New Test Rule",
            "description": "New alert rule",
            "metric_type": "cpu_usage",
            "condition": {"operator": "gt", "value": 80},
            "threshold_value": 80,
            "check_interval_minutes": 30,
            "is_active": True,
        }

        response = api_client.post("/api/rules/", data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "New Test Rule"
        assert str(response.data["company_id"]) == str(company_id)

    def test_retrieve_alert_rule(self, api_client, mock_user, alert_rule):
        """Test retrieving a specific alert rule"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = alert_rule.company_id

        response = api_client.get(f"/api/rules/{alert_rule.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(alert_rule.id)
        assert response.data["name"] == alert_rule.name

    def test_update_alert_rule(self, api_client, mock_user, alert_rule):
        """Test updating an alert rule"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = alert_rule.company_id

        data = {
            "name": "Updated Rule Name",
            "description": alert_rule.description,
            "metric_type": alert_rule.metric_type,
            "condition": alert_rule.condition,
            "threshold_value": alert_rule.threshold_value,
            "check_interval_minutes": alert_rule.check_interval_minutes,
            "is_active": alert_rule.is_active,
        }

        response = api_client.put(f"/api/rules/{alert_rule.id}/", data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Updated Rule Name"

    def test_delete_alert_rule(self, api_client, mock_user, alert_rule):
        """Test deleting an alert rule"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = alert_rule.company_id

        response = api_client.delete(f"/api/rules/{alert_rule.id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not AlertRule.objects.filter(id=alert_rule.id).exists()

    @patch("apps.alerts.views.evaluate_single_alert_rule.delay")
    def test_test_alert_rule(self, mock_task, api_client, mock_user, alert_rule):
        """Test triggering alert rule evaluation"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = alert_rule.company_id
        mock_task.return_value.id = "test-task-id"

        response = api_client.post(f"/api/rules/{alert_rule.id}/test/", {"test_data": {}}, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "task_id" in response.data
        mock_task.assert_called_once()

    def test_activate_alert_rule(self, api_client, mock_user, alert_rule):
        """Test activating an alert rule"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = alert_rule.company_id
        alert_rule.is_active = False
        alert_rule.save()

        response = api_client.post(f"/api/rules/{alert_rule.id}/activate/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_active"] is True

        alert_rule.refresh_from_db()
        assert alert_rule.is_active is True

    def test_deactivate_alert_rule(self, api_client, mock_user, alert_rule):
        """Test deactivating an alert rule"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = alert_rule.company_id

        response = api_client.post(f"/api/rules/{alert_rule.id}/deactivate/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_active"] is False

        alert_rule.refresh_from_db()
        assert alert_rule.is_active is False

    def test_filter_alert_rules_by_type(self, api_client, mock_user, company_id):
        """Test filtering alert rules by type"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = company_id

        # Create rules with different types
        AlertRule.objects.create(
            name="CPU Rule",
            company_id=company_id,
            metric_type="cpu_usage",
            condition={"operator": "gt", "value": 80},
            threshold_value=80,
            check_interval_minutes=30,
            is_active=True,
        )

        response = api_client.get("/api/rules/?rule_type=metric")

        # Should work without errors (filtering logic may vary)
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestAlertViewSet:
    """Tests for Alert ViewSet"""

    def test_list_alerts(self, api_client, mock_user, alert_notification):
        """Test listing alerts"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = alert_notification.company_id

        response = api_client.get("/api/alerts/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_retrieve_alert(self, api_client, mock_user, alert_notification):
        """Test retrieving a specific alert"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = alert_notification.company_id

        response = api_client.get(f"/api/alerts/{alert_notification.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(alert_notification.id)

    @patch("apps.alerts.views.AlertPermissions.can_acknowledge_alert")
    def test_acknowledge_alerts(self, mock_perm, api_client, mock_user, alert_notification):
        """Test acknowledging alerts"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = alert_notification.company_id
        mock_perm.return_value = True

        data = {"alert_ids": [str(alert_notification.id)]}

        response = api_client.post("/api/alerts/acknowledge/", data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["acknowledged_count"] == 1

    @patch("apps.alerts.views.AlertPermissions.can_acknowledge_alert")
    def test_resolve_alerts(self, mock_perm, api_client, mock_user, alert_notification):
        """Test resolving alerts"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = alert_notification.company_id
        mock_perm.return_value = True

        data = {"alert_ids": [str(alert_notification.id)]}

        response = api_client.post("/api/alerts/resolve/", data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["resolved_count"] == 1

    @patch("apps.alerts.views.AlertPermissions.can_acknowledge_alert")
    def test_mute_alert(self, mock_perm, api_client, mock_user, alert_notification):
        """Test muting an alert"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = alert_notification.company_id
        mock_perm.return_value = True

        response = api_client.post(f"/api/alerts/{alert_notification.id}/mute/")

        assert response.status_code == status.HTTP_200_OK
        assert "state" in response.data

    def test_alert_statistics(self, api_client, mock_user, alert_notification):
        """Test getting alert statistics"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = alert_notification.company_id

        response = api_client.get("/api/alerts/statistics/")

        assert response.status_code == status.HTTP_200_OK
        assert "total_alerts" in response.data
        assert response.data["total_alerts"] >= 1

    def test_filter_alerts_by_severity(self, api_client, mock_user, company_id):
        """Test filtering alerts by severity"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = company_id

        # Create alert rule first
        rule = AlertRule.objects.create(
            name="Test Rule",
            company_id=company_id,
            metric_type="test",
            condition={"operator": "gt", "value": 10},
            threshold_value=10,
            check_interval_minutes=30,
        )

        # Create alerts with different severities
        AlertNotification.objects.create(
            rule=rule,
            triggered_for_user_id=uuid.uuid4(),
            severity="critical",
            title="Critical Alert",
            message="Critical",
            status="pending",
            company_id=company_id,
        )

        response = api_client.get("/api/alerts/?severity=critical")

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestNotificationChannelViewSet:
    """Tests for NotificationChannel ViewSet"""

    @patch("apps.alerts.views.AlertPermissions.can_manage_notification_channels")
    def test_list_notification_channels(self, mock_perm, api_client, mock_user, notification_channel):
        """Test listing notification channels"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = notification_channel.company_id
        mock_perm.return_value = True

        response = api_client.get("/api/channels/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    @patch("apps.alerts.views.AlertPermissions.can_manage_notification_channels")
    def test_create_notification_channel(self, mock_perm, api_client, mock_user, company_id):
        """Test creating a notification channel"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = company_id
        mock_perm.return_value = True

        data = {
            "name": "New Email Channel",
            "type": "email",
            "config": {"email": "notifications@example.com"},
            "is_active": True,
        }

        response = api_client.post("/api/channels/", data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "New Email Channel"

    @patch("apps.alerts.views.AlertPermissions.can_manage_notification_channels")
    def test_create_notification_channel_permission_denied(self, mock_perm, api_client, mock_user, company_id):
        """Test creating a notification channel without permission"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = company_id
        mock_perm.return_value = False

        data = {
            "name": "New Channel",
            "type": "email",
            "config": {"email": "test@example.com"},
        }

        response = api_client.post("/api/channels/", data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("apps.alerts.views.test_notification_channel.delay")
    def test_test_notification_channel(self, mock_task, api_client, mock_user, notification_channel):
        """Test triggering notification channel test"""
        api_client.force_authenticate(user=mock_user)
        mock_user.company_id = notification_channel.company_id
        mock_task.return_value.id = "test-task-id"

        response = api_client.post(f"/api/channels/{notification_channel.id}/test/")

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "task_id" in response.data
        mock_task.assert_called_once()


@pytest.mark.django_db
class TestNotificationLogViewSet:
    """Tests for NotificationLog ViewSet"""

    def test_list_notifications(self, api_client, mock_user):
        """Test listing notification logs"""
        api_client.force_authenticate(user=mock_user)

        response = api_client.get("/api/notifications/")

        # Should return 200 even if empty
        assert response.status_code == status.HTTP_200_OK
