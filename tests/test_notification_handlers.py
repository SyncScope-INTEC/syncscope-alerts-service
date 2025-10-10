"""
Tests for Notification Handlers
"""

import uuid
from unittest.mock import Mock, patch

import pytest
from django.conf import settings

from apps.alerts.models import AlertNotification, AlertRule, Notification, NotificationChannel
from apps.alerts.notification_handlers import (
    EmailNotificationHandler,
    InAppNotificationHandler,
    PushNotificationHandler,
    SlackNotificationHandler,
    SMSNotificationHandler,
    WebhookNotificationHandler,
    send_notification,
)


@pytest.mark.django_db
class TestEmailNotificationHandler:
    """Tests for EmailNotificationHandler"""

    def setup_method(self):
        """Setup for each test"""
        self.handler = EmailNotificationHandler()

    def create_mock_alert(self):
        """Create a mock alert for testing"""
        rule = Mock(spec=AlertRule)
        rule.name = "Test Rule"
        rule.rule_type = "productivity"

        alert = Mock(spec=AlertNotification)
        alert.id = uuid.uuid4()
        alert.title = "Test Alert"
        alert.message = "Test message"
        alert.severity = "high"
        alert.state = "active"
        alert.triggered_at = Mock()
        alert.triggered_at.strftime = Mock(return_value="2024-01-01 00:00:00 UTC")
        alert.alert_rule = rule

        return alert

    @patch("apps.alerts.notification_handlers.send_mail")
    def test_send_email_success(self, mock_send_mail):
        """Test successful email sending"""
        alert = self.create_mock_alert()

        channel = Mock(spec=NotificationChannel)
        channel.name = "Email Channel"
        channel.config = {"recipients": ["test@example.com"]}

        notification_log = Mock(spec=Notification)

        result = self.handler.send(alert, channel, notification_log)

        assert result is True
        mock_send_mail.assert_called_once()

    def test_send_email_no_recipients(self):
        """Test email sending with no recipients"""
        alert = self.create_mock_alert()

        channel = Mock(spec=NotificationChannel)
        channel.name = "Email Channel"
        channel.config = {}

        notification_log = Mock(spec=Notification)

        result = self.handler.send(alert, channel, notification_log)

        assert result is False

    @patch("apps.alerts.notification_handlers.send_mail")
    def test_send_email_exception(self, mock_send_mail):
        """Test email sending with exception"""
        mock_send_mail.side_effect = Exception("SMTP error")

        alert = self.create_mock_alert()

        channel = Mock(spec=NotificationChannel)
        channel.name = "Email Channel"
        channel.config = {"recipients": ["test@example.com"]}

        notification_log = Mock(spec=Notification)

        result = self.handler.send(alert, channel, notification_log)

        assert result is False
        assert notification_log.error_message == "SMTP error"

    def test_format_email_message(self):
        """Test email message formatting"""
        alert = self.create_mock_alert()

        message = self.handler._format_email_message(alert)

        assert "Test Alert" in message
        assert "Test message" in message
        assert alert.severity.upper() in message


@pytest.mark.django_db
class TestSlackNotificationHandler:
    """Tests for SlackNotificationHandler"""

    def setup_method(self):
        """Setup for each test"""
        self.handler = SlackNotificationHandler()

    def create_mock_alert(self):
        """Create a mock alert for testing"""
        rule = Mock(spec=AlertRule)
        rule.name = "Test Rule"
        rule.rule_type = "productivity"

        alert = Mock(spec=AlertNotification)
        alert.id = uuid.uuid4()
        alert.title = "Test Alert"
        alert.message = "Test message"
        alert.severity = "high"
        alert.state = "active"
        alert.triggered_at = Mock()
        alert.triggered_at.timestamp = Mock(return_value=1234567890)
        alert.alert_rule = rule

        return alert

    @patch("apps.alerts.notification_handlers.requests.post")
    def test_send_slack_success(self, mock_post):
        """Test successful Slack notification"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        alert = self.create_mock_alert()

        channel = Mock(spec=NotificationChannel)
        channel.name = "Slack Channel"
        channel.config = {"webhook_url": "https://hooks.slack.com/test"}

        notification_log = Mock(spec=Notification)

        result = self.handler.send(alert, channel, notification_log)

        assert result is True
        mock_post.assert_called_once()

    def test_send_slack_no_webhook(self):
        """Test Slack notification with no webhook URL"""
        alert = self.create_mock_alert()

        channel = Mock(spec=NotificationChannel)
        channel.name = "Slack Channel"
        channel.config = {}

        notification_log = Mock(spec=Notification)

        result = self.handler.send(alert, channel, notification_log)

        assert result is False

    @patch("apps.alerts.notification_handlers.requests.post")
    def test_send_slack_api_error(self, mock_post):
        """Test Slack notification with API error"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        alert = self.create_mock_alert()

        channel = Mock(spec=NotificationChannel)
        channel.name = "Slack Channel"
        channel.config = {"webhook_url": "https://hooks.slack.com/test"}

        notification_log = Mock(spec=Notification)

        result = self.handler.send(alert, channel, notification_log)

        assert result is False
        assert "500" in notification_log.error_message

    def test_format_slack_message_critical_severity(self):
        """Test Slack message formatting for critical severity"""
        alert = self.create_mock_alert()
        alert.severity = "critical"

        message = self.handler._format_slack_message(alert)

        assert "attachments" in message
        assert message["attachments"][0]["color"] == "#FF0000"
        assert message["attachments"][0]["title"] == "Test Alert"

    def test_format_slack_message_low_severity(self):
        """Test Slack message formatting for low severity"""
        alert = self.create_mock_alert()
        alert.severity = "low"

        message = self.handler._format_slack_message(alert)

        assert message["attachments"][0]["color"] == "#36A64F"

    @patch("apps.alerts.notification_handlers.requests.post")
    def test_send_slack_request_exception(self, mock_post):
        """Test Slack notification with request exception"""
        mock_post.side_effect = Exception("Network error")

        alert = self.create_mock_alert()

        channel = Mock(spec=NotificationChannel)
        channel.name = "Slack Channel"
        channel.config = {"webhook_url": "https://hooks.slack.com/test"}

        notification_log = Mock(spec=Notification)

        result = self.handler.send(alert, channel, notification_log)

        assert result is False
        assert "Network error" in notification_log.error_message


@pytest.mark.django_db
class TestWebhookNotificationHandler:
    """Tests for WebhookNotificationHandler"""

    def setup_method(self):
        """Setup for each test"""
        self.handler = WebhookNotificationHandler()

    def create_mock_alert(self):
        """Create a mock alert for testing"""
        rule = Mock(spec=AlertRule)
        rule.name = "Test Rule"
        rule.rule_type = "productivity"

        alert = Mock(spec=AlertNotification)
        alert.id = uuid.uuid4()
        alert.title = "Test Alert"
        alert.message = "Test message"
        alert.severity = "high"
        alert.state = "active"
        alert.triggered_at = Mock()
        alert.triggered_at.isoformat = Mock(return_value="2024-01-01T00:00:00Z")
        alert.metadata = {}
        alert.alert_rule = rule

        return alert

    @patch("apps.alerts.notification_handlers.requests.post")
    def test_send_webhook_post_success(self, mock_post):
        """Test successful webhook POST"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        alert = self.create_mock_alert()

        channel = Mock(spec=NotificationChannel)
        channel.name = "Webhook Channel"
        channel.config = {"url": "https://example.com/webhook"}

        notification_log = Mock(spec=Notification)

        result = self.handler.send(alert, channel, notification_log)

        assert result is True
        mock_post.assert_called_once()

    @patch("apps.alerts.notification_handlers.requests.put")
    def test_send_webhook_put_success(self, mock_put):
        """Test successful webhook PUT"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_put.return_value = mock_response

        alert = self.create_mock_alert()

        channel = Mock(spec=NotificationChannel)
        channel.name = "Webhook Channel"
        channel.config = {"url": "https://example.com/webhook", "method": "PUT"}

        notification_log = Mock(spec=Notification)

        result = self.handler.send(alert, channel, notification_log)

        assert result is True
        mock_put.assert_called_once()

    def test_send_webhook_no_url(self):
        """Test webhook with no URL"""
        alert = self.create_mock_alert()

        channel = Mock(spec=NotificationChannel)
        channel.name = "Webhook Channel"
        channel.config = {}

        notification_log = Mock(spec=Notification)

        result = self.handler.send(alert, channel, notification_log)

        assert result is False

    @patch("apps.alerts.notification_handlers.requests.post")
    def test_send_webhook_with_custom_headers(self, mock_post):
        """Test webhook with custom headers"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        alert = self.create_mock_alert()

        channel = Mock(spec=NotificationChannel)
        channel.name = "Webhook Channel"
        channel.config = {
            "url": "https://example.com/webhook",
            "headers": {"X-Custom-Header": "test"},
            "payload": {"custom_field": "value"},
        }

        notification_log = Mock(spec=Notification)

        result = self.handler.send(alert, channel, notification_log)

        assert result is True

    def test_send_webhook_unsupported_method(self):
        """Test webhook with unsupported HTTP method"""
        alert = self.create_mock_alert()

        channel = Mock(spec=NotificationChannel)
        channel.name = "Webhook Channel"
        channel.config = {"url": "https://example.com/webhook", "method": "DELETE"}

        notification_log = Mock(spec=Notification)

        result = self.handler.send(alert, channel, notification_log)

        assert result is False

    @patch("apps.alerts.notification_handlers.requests.post")
    def test_send_webhook_http_error(self, mock_post):
        """Test webhook with HTTP error response"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        alert = self.create_mock_alert()

        channel = Mock(spec=NotificationChannel)
        channel.name = "Webhook Channel"
        channel.config = {"url": "https://example.com/webhook"}

        notification_log = Mock(spec=Notification)

        result = self.handler.send(alert, channel, notification_log)

        assert result is False
        assert "400" in notification_log.error_message

    @patch("apps.alerts.notification_handlers.requests.post")
    def test_send_webhook_connection_error(self, mock_post):
        """Test webhook with connection error"""
        mock_post.side_effect = Exception("Connection timeout")

        alert = self.create_mock_alert()

        channel = Mock(spec=NotificationChannel)
        channel.name = "Webhook Channel"
        channel.config = {"url": "https://example.com/webhook"}

        notification_log = Mock(spec=Notification)

        result = self.handler.send(alert, channel, notification_log)

        assert result is False
        assert "Connection timeout" in notification_log.error_message

    @patch("apps.alerts.notification_handlers.requests.post")
    def test_send_webhook_202_accepted(self, mock_post):
        """Test webhook with 202 Accepted response"""
        mock_response = Mock()
        mock_response.status_code = 202
        mock_post.return_value = mock_response

        alert = self.create_mock_alert()

        channel = Mock(spec=NotificationChannel)
        channel.name = "Webhook Channel"
        channel.config = {"url": "https://example.com/webhook"}

        notification_log = Mock(spec=Notification)

        result = self.handler.send(alert, channel, notification_log)

        assert result is True


@pytest.mark.django_db
class TestInAppNotificationHandler:
    """Tests for InAppNotificationHandler"""

    def setup_method(self):
        """Setup for each test"""
        self.handler = InAppNotificationHandler()

    def create_mock_alert(self):
        """Create a mock alert for testing"""
        rule = Mock(spec=AlertRule)
        rule.name = "Test Rule"
        rule.rule_type = "productivity"

        alert = Mock(spec=AlertNotification)
        alert.id = uuid.uuid4()
        alert.title = "Test Alert"
        alert.message = "Test message"
        alert.severity = "high"
        alert.state = "active"
        alert.triggered_at = Mock()
        alert.triggered_at.isoformat = Mock(return_value="2024-01-01T00:00:00Z")
        alert.metadata = {}
        alert.alert_rule = rule

        return alert

    def test_send_in_app_no_users(self):
        """Test in-app notification with no user IDs"""
        alert = self.create_mock_alert()

        channel = Mock(spec=NotificationChannel)
        channel.name = "In-App Channel"
        channel.config = {}

        notification_log = Mock(spec=Notification)

        result = self.handler.send(alert, channel, notification_log)

        assert result is False


@pytest.mark.django_db
class TestSMSNotificationHandler:
    """Tests for SMSNotificationHandler"""

    def test_send_sms_not_implemented(self):
        """Test SMS notification returns not implemented"""
        handler = SMSNotificationHandler()

        alert = Mock(spec=AlertNotification)
        channel = Mock(spec=NotificationChannel)
        notification_log = Mock(spec=Notification)

        result = handler.send(alert, channel, notification_log)

        assert result is False
        assert "not implemented" in notification_log.error_message.lower()


@pytest.mark.django_db
class TestPushNotificationHandler:
    """Tests for PushNotificationHandler"""

    def test_send_push_not_implemented(self):
        """Test push notification returns not implemented"""
        handler = PushNotificationHandler()

        alert = Mock(spec=AlertNotification)
        channel = Mock(spec=NotificationChannel)
        notification_log = Mock(spec=Notification)

        result = handler.send(alert, channel, notification_log)

        assert result is False
        assert "not implemented" in notification_log.error_message.lower()


@pytest.mark.django_db
class TestNotificationHandlerBase:
    """Tests for NotificationHandler base class methods"""

    def test_format_alert_data(self):
        """Test _format_alert_data method"""
        handler = EmailNotificationHandler()

        rule = Mock(spec=AlertRule)
        rule.name = "Test Rule"
        rule.rule_type = "productivity"

        alert = Mock(spec=AlertNotification)
        alert.id = uuid.uuid4()
        alert.title = "Test Alert"
        alert.message = "Test message"
        alert.severity = "high"
        alert.state = "active"
        alert.triggered_at = Mock()
        alert.triggered_at.isoformat = Mock(return_value="2024-01-01T00:00:00Z")
        alert.metadata = {"key": "value"}
        alert.alert_rule = rule

        data = handler._format_alert_data(alert)

        assert data["title"] == "Test Alert"
        assert data["severity"] == "high"
        assert data["state"] == "active"
        assert data["rule_name"] == "Test Rule"
        assert data["rule_type"] == "productivity"
        assert "id" in data


@pytest.mark.django_db
class TestSendNotification:
    """Tests for send_notification function"""

    def create_mock_alert(self):
        """Create a mock alert for testing"""
        rule = Mock(spec=AlertRule)
        rule.name = "Test Rule"
        rule.rule_type = "productivity"

        alert = Mock(spec=AlertNotification)
        alert.id = uuid.uuid4()
        alert.title = "Test Alert"
        alert.message = "Test message"
        alert.severity = "high"
        alert.state = "active"
        alert.triggered_at = Mock()
        alert.triggered_at.isoformat = Mock(return_value="2024-01-01T00:00:00Z")
        alert.triggered_for_user_id = uuid.uuid4()
        alert.triggered_for_team_id = None
        alert.metadata = {}
        alert.alert_rule = rule

        return alert

    @patch("apps.alerts.notification_handlers.Notification.objects.create")
    def test_send_notification_unsupported_type(self, mock_create):
        """Test send_notification with unsupported channel type"""
        alert = self.create_mock_alert()

        channel = Mock(spec=NotificationChannel)
        channel.type = "unsupported"
        channel.name = "Unsupported Channel"

        mock_notification = Mock(spec=Notification)
        mock_notification.mark_failed = Mock()
        mock_create.return_value = mock_notification

        result = send_notification(alert, channel)

        assert result == mock_notification
        mock_notification.mark_failed.assert_called_once()

    @patch("apps.alerts.notification_handlers.EmailNotificationHandler.send")
    @patch("apps.alerts.notification_handlers.Notification.objects.create")
    def test_send_notification_success(self, mock_create, mock_send):
        """Test send_notification success"""
        alert = self.create_mock_alert()

        channel = Mock(spec=NotificationChannel)
        channel.type = "email"
        channel.name = "Email Channel"

        mock_notification = Mock(spec=Notification)
        mock_notification.mark_sent = Mock()
        mock_notification.error_message = None
        mock_create.return_value = mock_notification

        mock_send.return_value = True

        result = send_notification(alert, channel)

        assert result == mock_notification
        mock_notification.mark_sent.assert_called_once()

    @patch("apps.alerts.notification_handlers.EmailNotificationHandler.send")
    @patch("apps.alerts.notification_handlers.Notification.objects.create")
    def test_send_notification_failure(self, mock_create, mock_send):
        """Test send_notification failure"""
        alert = self.create_mock_alert()

        channel = Mock(spec=NotificationChannel)
        channel.type = "email"
        channel.name = "Email Channel"

        mock_notification = Mock(spec=Notification)
        mock_notification.mark_failed = Mock()
        mock_notification.error_message = "Test error"
        mock_create.return_value = mock_notification

        mock_send.return_value = False

        result = send_notification(alert, channel)

        assert result == mock_notification
        mock_notification.mark_failed.assert_called_once()
