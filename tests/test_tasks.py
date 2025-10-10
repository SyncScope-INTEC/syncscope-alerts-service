"""
Tests for Celery Tasks
"""

import uuid
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.conf import settings
from django.utils import timezone

from apps.alerts.models import AlertNotification, AlertRule, Notification, NotificationChannel
from apps.alerts.tasks import (
    cleanup_old_resolved_alerts,
    evaluate_all_active_alert_rules,
    evaluate_single_alert_rule,
    retry_failed_notifications,
    send_alert_notifications,
    send_test_notification,
)


@pytest.mark.django_db
class TestEvaluateAllActiveAlertRules:
    """Tests for evaluate_all_active_alert_rules task"""

    @patch("apps.alerts.tasks.alert_engine.trigger_alert")
    @patch("apps.alerts.tasks.alert_engine.evaluate_rule")
    @patch("apps.alerts.tasks.AlertRule.objects.filter")
    def test_evaluates_all_active_rules(self, mock_filter, mock_evaluate, mock_trigger):
        """Test task evaluates all active alert rules"""
        # Create mock rules
        rule1 = Mock(spec=AlertRule)
        rule1.id = uuid.uuid4()
        rule2 = Mock(spec=AlertRule)
        rule2.id = uuid.uuid4()

        mock_filter.return_value = [rule1, rule2]
        mock_evaluate.return_value = (False, {})

        result = evaluate_all_active_alert_rules()

        assert result["evaluated"] == 2
        assert result["triggered"] == 0
        assert mock_evaluate.call_count == 2

    @patch("apps.alerts.tasks.alert_engine.trigger_alert")
    @patch("apps.alerts.tasks.alert_engine.evaluate_rule")
    @patch("apps.alerts.tasks.AlertRule.objects.filter")
    def test_triggers_alerts_when_conditions_met(self, mock_filter, mock_evaluate, mock_trigger):
        """Test task triggers alerts when conditions are met"""
        # Create mock rule
        rule = Mock(spec=AlertRule)
        rule.id = uuid.uuid4()

        mock_filter.return_value = [rule]
        mock_evaluate.return_value = (True, {"current_value": 150})

        # Mock alert creation
        mock_alert = Mock(spec=AlertNotification)
        mock_alert.id = uuid.uuid4()
        mock_trigger.return_value = mock_alert

        result = evaluate_all_active_alert_rules()

        assert result["evaluated"] == 1
        assert result["triggered"] == 1
        mock_trigger.assert_called_once_with(rule, {"current_value": 150})

    @patch("apps.alerts.tasks.alert_engine.evaluate_rule")
    @patch("apps.alerts.tasks.AlertRule.objects.filter")
    def test_handles_evaluation_errors(self, mock_filter, mock_evaluate):
        """Test task handles evaluation errors gracefully"""
        # Create mock rules
        rule1 = Mock(spec=AlertRule)
        rule1.id = uuid.uuid4()
        rule2 = Mock(spec=AlertRule)
        rule2.id = uuid.uuid4()

        mock_filter.return_value = [rule1, rule2]

        # First rule raises exception, second succeeds
        mock_evaluate.side_effect = [Exception("Test error"), (False, {})]

        result = evaluate_all_active_alert_rules()

        # Should continue despite error
        assert result["evaluated"] == 1
        assert result["triggered"] == 0

    @patch("apps.alerts.tasks.AlertRule.objects.filter")
    def test_handles_query_errors(self, mock_filter):
        """Test task handles database query errors"""
        mock_filter.side_effect = Exception("Database error")

        result = evaluate_all_active_alert_rules()

        assert "error" in result
        assert "Database error" in result["error"]


@pytest.mark.django_db
class TestEvaluateSingleAlertRule:
    """Tests for evaluate_single_alert_rule task"""

    @patch("apps.alerts.tasks.alert_engine.trigger_alert")
    @patch("apps.alerts.tasks.alert_engine.evaluate_rule")
    @patch("apps.alerts.tasks.AlertRule.objects.get")
    def test_evaluates_single_rule(self, mock_get, mock_evaluate, mock_trigger):
        """Test task evaluates a single rule"""
        rule_id = uuid.uuid4()
        mock_rule = Mock(spec=AlertRule)
        mock_rule.id = rule_id

        mock_get.return_value = mock_rule
        mock_evaluate.return_value = (False, {})

        result = evaluate_single_alert_rule(str(rule_id))

        assert result["triggered"] is False
        mock_evaluate.assert_called_once_with(mock_rule)

    @patch("apps.alerts.tasks.alert_engine.trigger_alert")
    @patch("apps.alerts.tasks.alert_engine.evaluate_rule")
    @patch("apps.alerts.tasks.AlertRule.objects.get")
    def test_triggers_alert_when_condition_met(self, mock_get, mock_evaluate, mock_trigger):
        """Test task triggers alert when condition is met"""
        rule_id = uuid.uuid4()
        mock_rule = Mock(spec=AlertRule)
        mock_rule.id = rule_id

        mock_get.return_value = mock_rule
        mock_evaluate.return_value = (True, {"current_value": 150})

        mock_alert = Mock(spec=AlertNotification)
        alert_id = uuid.uuid4()
        mock_alert.id = alert_id
        mock_trigger.return_value = mock_alert

        result = evaluate_single_alert_rule(str(rule_id))

        assert result["triggered"] is True
        assert result["alert_id"] == str(alert_id)
        mock_trigger.assert_called_once_with(mock_rule, {"current_value": 150})

    @patch("apps.alerts.tasks.AlertRule.objects.get")
    def test_handles_rule_not_found(self, mock_get):
        """Test task handles rule not found error"""
        rule_id = uuid.uuid4()
        mock_get.side_effect = AlertRule.DoesNotExist()

        result = evaluate_single_alert_rule(str(rule_id))

        assert "error" in result
        assert "not found" in result["error"]

    @patch("apps.alerts.tasks.alert_engine.evaluate_rule")
    @patch("apps.alerts.tasks.AlertRule.objects.get")
    def test_handles_evaluation_errors(self, mock_get, mock_evaluate):
        """Test task handles evaluation errors"""
        rule_id = uuid.uuid4()
        mock_rule = Mock(spec=AlertRule)
        mock_rule.id = rule_id

        mock_get.return_value = mock_rule
        mock_evaluate.side_effect = Exception("Evaluation error")

        result = evaluate_single_alert_rule(str(rule_id))

        assert "error" in result
        assert "Evaluation error" in result["error"]


@pytest.mark.django_db
class TestSendAlertNotifications:
    """Tests for send_alert_notifications task"""

    @patch("apps.alerts.tasks.send_notification")
    @patch("apps.alerts.tasks.AlertNotification.objects.get")
    def test_sends_notifications_to_all_channels(self, mock_get_alert, mock_send):
        """Test task sends notifications to all active channels"""
        alert_id = uuid.uuid4()
        mock_alert = Mock(spec=AlertNotification)
        mock_alert.id = alert_id

        # Mock channels
        channel1 = Mock(spec=NotificationChannel)
        channel1.name = "Email"
        channel2 = Mock(spec=NotificationChannel)
        channel2.name = "Slack"

        mock_channels = Mock()
        mock_channels.filter.return_value = mock_channels
        mock_channels.exists.return_value = True
        mock_channels.__iter__ = Mock(return_value=iter([channel1, channel2]))

        mock_alert.alert_rule = Mock()
        mock_alert.alert_rule.notification_channels = mock_channels

        mock_get_alert.return_value = mock_alert

        # Mock successful notifications
        mock_notification_log = Mock(spec=Notification)
        mock_notification_log.status = "sent"
        mock_send.return_value = mock_notification_log

        result = send_alert_notifications(str(alert_id))

        assert result["sent"] == 2
        assert result["failed"] == 0
        assert mock_send.call_count == 2

    @patch("apps.alerts.tasks.send_notification")
    @patch("apps.alerts.tasks.AlertNotification.objects.get")
    def test_tracks_failed_notifications(self, mock_get_alert, mock_send):
        """Test task tracks failed notifications"""
        alert_id = uuid.uuid4()
        mock_alert = Mock(spec=AlertNotification)
        mock_alert.id = alert_id

        # Mock channel
        channel = Mock(spec=NotificationChannel)
        channel.name = "Email"

        mock_channels = Mock()
        mock_channels.filter.return_value = mock_channels
        mock_channels.exists.return_value = True
        mock_channels.__iter__ = Mock(return_value=iter([channel]))

        mock_alert.alert_rule = Mock()
        mock_alert.alert_rule.notification_channels = mock_channels

        mock_get_alert.return_value = mock_alert

        # Mock failed notification
        mock_notification_log = Mock(spec=Notification)
        mock_notification_log.status = "failed"
        mock_send.return_value = mock_notification_log

        result = send_alert_notifications(str(alert_id))

        assert result["sent"] == 0
        assert result["failed"] == 1

    @patch("apps.alerts.tasks.AlertNotification.objects.get")
    def test_handles_no_active_channels(self, mock_get_alert):
        """Test task handles no active notification channels"""
        alert_id = uuid.uuid4()
        mock_alert = Mock(spec=AlertNotification)
        mock_alert.id = alert_id

        # Mock empty channels
        mock_channels = Mock()
        mock_channels.filter.return_value = mock_channels
        mock_channels.exists.return_value = False

        mock_alert.alert_rule = Mock()
        mock_alert.alert_rule.notification_channels = mock_channels

        mock_get_alert.return_value = mock_alert

        result = send_alert_notifications(str(alert_id))

        assert result["sent"] == 0
        assert result["failed"] == 0

    @patch("apps.alerts.tasks.AlertNotification.objects.get")
    def test_handles_alert_not_found(self, mock_get_alert):
        """Test task handles alert not found error"""
        alert_id = uuid.uuid4()
        mock_get_alert.side_effect = AlertNotification.DoesNotExist()

        result = send_alert_notifications(str(alert_id))

        assert "error" in result
        assert "not found" in result["error"]

    @patch("apps.alerts.tasks.send_notification")
    @patch("apps.alerts.tasks.AlertNotification.objects.get")
    def test_handles_send_errors(self, mock_get_alert, mock_send):
        """Test task handles notification send errors"""
        alert_id = uuid.uuid4()
        mock_alert = Mock(spec=AlertNotification)
        mock_alert.id = alert_id

        # Mock channel
        channel = Mock(spec=NotificationChannel)
        channel.name = "Email"

        mock_channels = Mock()
        mock_channels.filter.return_value = mock_channels
        mock_channels.exists.return_value = True
        mock_channels.__iter__ = Mock(return_value=iter([channel]))

        mock_alert.alert_rule = Mock()
        mock_alert.alert_rule.notification_channels = mock_channels

        mock_get_alert.return_value = mock_alert

        # Mock send error
        mock_send.side_effect = Exception("Send error")

        result = send_alert_notifications(str(alert_id))

        assert result["sent"] == 0
        assert result["failed"] == 1


@pytest.mark.django_db
class TestRetryFailedNotifications:
    """Tests for retry_failed_notifications task"""

    @patch("apps.alerts.tasks.send_notification")
    @patch("apps.alerts.tasks.Notification.objects.filter")
    @patch("apps.alerts.tasks.settings")
    def test_retries_failed_notifications(self, mock_settings, mock_filter, mock_send):
        """Test task retries failed notifications"""
        mock_settings.MAX_RETRY_ATTEMPTS = 3
        mock_settings.NOTIFICATION_RETRY_DELAY = 300

        # Mock failed notification with alert and channel attributes
        notification = Mock(spec=Notification)
        notification.id = uuid.uuid4()
        notification.mark_retrying = Mock()
        notification.alert = Mock(spec=AlertNotification)
        notification.channel = Mock(spec=NotificationChannel)

        mock_filter.return_value = [notification]

        # Mock successful retry
        mock_new_log = Mock(spec=Notification)
        mock_new_log.status = "sent"
        mock_send.return_value = mock_new_log

        result = retry_failed_notifications()

        assert result["retried"] == 1
        assert result["successful"] == 1
        notification.mark_retrying.assert_called_once()

    @patch("apps.alerts.tasks.send_notification")
    @patch("apps.alerts.tasks.Notification.objects.filter")
    @patch("apps.alerts.tasks.settings")
    def test_tracks_failed_retries(self, mock_settings, mock_filter, mock_send):
        """Test task tracks failed retries"""
        mock_settings.MAX_RETRY_ATTEMPTS = 3
        mock_settings.NOTIFICATION_RETRY_DELAY = 300

        # Mock failed notification with alert and channel attributes
        notification = Mock(spec=Notification)
        notification.id = uuid.uuid4()
        notification.mark_retrying = Mock()
        notification.alert = Mock(spec=AlertNotification)
        notification.channel = Mock(spec=NotificationChannel)

        mock_filter.return_value = [notification]

        # Mock failed retry
        mock_new_log = Mock(spec=Notification)
        mock_new_log.status = "failed"
        mock_send.return_value = mock_new_log

        result = retry_failed_notifications()

        assert result["retried"] == 1
        assert result["successful"] == 0

    @patch("apps.alerts.tasks.Notification.objects.filter")
    @patch("apps.alerts.tasks.settings")
    def test_handles_retry_errors(self, mock_settings, mock_filter):
        """Test task handles retry errors gracefully"""
        mock_settings.MAX_RETRY_ATTEMPTS = 3
        mock_settings.NOTIFICATION_RETRY_DELAY = 300

        # Mock failed notification
        notification = Mock(spec=Notification)
        notification.id = uuid.uuid4()
        notification.mark_retrying = Mock(side_effect=Exception("Retry error"))

        mock_filter.return_value = [notification]

        result = retry_failed_notifications()

        # Should handle error and continue
        assert result["retried"] == 0
        assert result["successful"] == 0

    @patch("apps.alerts.tasks.Notification.objects.filter")
    def test_handles_query_errors(self, mock_filter):
        """Test task handles database query errors"""
        mock_filter.side_effect = Exception("Database error")

        result = retry_failed_notifications()

        assert "error" in result
        assert "Database error" in result["error"]


@pytest.mark.django_db
class TestCleanupOldResolvedAlerts:
    """Tests for cleanup_old_resolved_alerts task"""

    @patch("apps.alerts.tasks.AlertNotification.objects.filter")
    @patch("apps.alerts.tasks.settings")
    def test_deletes_old_resolved_alerts(self, mock_settings, mock_filter):
        """Test task deletes old resolved alerts"""
        mock_settings.ALERT_RETENTION_DAYS = 30

        # Mock queryset
        mock_queryset = Mock()
        mock_queryset.delete.return_value = (5, {"alerts.AlertNotification": 5})

        mock_filter.return_value = mock_queryset

        result = cleanup_old_resolved_alerts()

        assert result["deleted"] == 5
        mock_queryset.delete.assert_called_once()

    @patch("apps.alerts.tasks.AlertNotification.objects.filter")
    @patch("apps.alerts.tasks.settings")
    def test_handles_no_alerts_to_delete(self, mock_settings, mock_filter):
        """Test task handles no alerts to delete"""
        mock_settings.ALERT_RETENTION_DAYS = 30

        # Mock empty queryset
        mock_queryset = Mock()
        mock_queryset.delete.return_value = (0, {})

        mock_filter.return_value = mock_queryset

        result = cleanup_old_resolved_alerts()

        assert result["deleted"] == 0

    @patch("apps.alerts.tasks.AlertNotification.objects.filter")
    def test_handles_cleanup_errors(self, mock_filter):
        """Test task handles cleanup errors"""
        mock_filter.side_effect = Exception("Cleanup error")

        result = cleanup_old_resolved_alerts()

        assert "error" in result
        assert "Cleanup error" in result["error"]


@pytest.mark.django_db
class TestSendTestNotification:
    """Tests for send_test_notification task"""

    @patch("apps.alerts.models.NotificationChannel.objects.get")
    def test_handles_channel_not_found(self, mock_get_channel):
        """Test task handles channel not found error"""
        from apps.alerts.models import NotificationChannel as ChannelModel

        channel_id = uuid.uuid4()
        mock_get_channel.side_effect = ChannelModel.DoesNotExist()

        result = send_test_notification(str(channel_id))

        assert result["success"] is False
        assert "not found" in result["error"]
