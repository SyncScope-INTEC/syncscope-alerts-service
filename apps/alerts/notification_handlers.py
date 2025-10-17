"""
Notification Handlers for different channels
Supports Email, Slack, Webhook, and In-App notifications
"""

import json
import logging
from abc import ABC, abstractmethod

import requests
from django.conf import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from .models import AlertNotification, Notification, NotificationChannel

logger = logging.getLogger(__name__)


class NotificationHandler(ABC):
    """Base class for notification handlers"""

    @abstractmethod
    def send(self, alert: AlertNotification, channel: NotificationChannel, notification_log: Notification):
        """
        Send notification through this channel

        Args:
            alert: AlertNotification to notify about
            channel: NotificationChannel configuration
            notification_log: Notification to track delivery

        Returns:
            bool: True if successful, False otherwise
        """
        pass

    def _format_alert_data(self, alert: AlertNotification):
        """Format alert data for notification"""
        return {
            "id": str(alert.id),
            "title": alert.title,
            "message": alert.message,
            "severity": alert.severity,
            "state": alert.state,
            "triggered_at": alert.triggered_at.isoformat(),
            "metadata": alert.metadata,
            "rule_name": alert.alert_rule.name,
            "rule_type": alert.alert_rule.rule_type,
        }


class EmailNotificationHandler(NotificationHandler):
    """Handler for email notifications using SendGrid API"""

    def send(self, alert: AlertNotification, channel: NotificationChannel, notification_log: Notification):
        try:
            config = channel.config
            recipients = config.get("recipients", [])

            if not recipients:
                logger.warning(f"No recipients configured for email channel {channel.name}")
                return False

            # Get SendGrid API key from settings
            sendgrid_api_key = getattr(settings, "SENDGRID_API_KEY", None)
            if not sendgrid_api_key:
                logger.error("SENDGRID_API_KEY not configured in settings")
                notification_log.error_message = "SendGrid API key not configured"
                return False

            # Prepare email content
            subject = f"[{alert.severity.upper()}] {alert.title}"
            html_content = self._format_email_html(alert)
            plain_content = self._format_email_message(alert)

            # Get sender email from settings
            from_email = getattr(settings, "SENDGRID_FROM_EMAIL", settings.DEFAULT_FROM_EMAIL)

            # Send to each recipient
            sg = SendGridAPIClient(sendgrid_api_key)
            success_count = 0
            last_error = None

            for recipient in recipients:
                try:
                    message = Mail(
                        from_email=from_email,
                        to_emails=recipient,
                        subject=subject,
                        plain_text_content=plain_content,
                        html_content=html_content,
                    )

                    response = sg.send(message)

                    if response.status_code in [200, 201, 202]:
                        success_count += 1
                        logger.info(f"Sent email to {recipient} - Status: {response.status_code}")
                    else:
                        error_msg = f"Status {response.status_code}"
                        logger.error(f"Failed to send to {recipient} - {error_msg}")
                        if not last_error:
                            last_error = error_msg

                except Exception as e:
                    logger.error(f"Error sending to {recipient}: {e}")
                    if not last_error:
                        last_error = str(e)

            if success_count > 0:
                logger.info(f"Sent email notification for alert {alert.id} to {success_count}/{len(recipients)} recipients")
                return True
            else:
                notification_log.error_message = last_error or "Failed to send to any recipients"
                return False

        except Exception as e:
            logger.error(f"Error sending email notification: {e}", exc_info=True)
            notification_log.error_message = str(e)
            return False

    def _format_email_message(self, alert: AlertNotification):
        """Format plain text email message"""
        message = f"""
Alert: {alert.title}
Severity: {alert.severity.upper()}
Status: {alert.status}

{alert.message}

Alert Rule: {alert.rule.name}
Metric Type: {alert.rule.metric_type}

Triggered At: {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC')}

---
This is an automated alert from SyncScope.
"""
        return message

    def _format_email_html(self, alert: AlertNotification):
        """Format HTML email message"""
        # Severity color mapping
        severity_colors = {
            "critical": "#DC2626",  # Red
            "high": "#EA580C",  # Orange
            "medium": "#F59E0B",  # Amber
            "low": "#10B981",  # Green
        }
        severity_color = severity_colors.get(alert.severity, "#6B7280")

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
        <h1 style="color: {severity_color}; margin-top: 0; font-size: 24px;">
            [{alert.severity.upper()}] Alert Notification
        </h1>
    </div>

    <div style="background-color: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
        <h2 style="color: #1f2937; margin-top: 0; font-size: 20px;">{alert.title}</h2>
        <p style="color: #4b5563; font-size: 16px; margin: 15px 0;">{alert.message}</p>

        <div style="border-top: 1px solid #e5e7eb; margin: 20px 0; padding-top: 20px;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 0; color: #6b7280; font-weight: 600;">Severity:</td>
                    <td style="padding: 8px 0;">
                        <span style="background-color: {severity_color}; color: white; padding: 4px 12px; border-radius: 4px; font-size: 14px; font-weight: 600;">
                            {alert.severity.upper()}
                        </span>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #6b7280; font-weight: 600;">Status:</td>
                    <td style="padding: 8px 0;">{alert.status}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #6b7280; font-weight: 600;">Alert Rule:</td>
                    <td style="padding: 8px 0;">{alert.rule.name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #6b7280; font-weight: 600;">Metric Type:</td>
                    <td style="padding: 8px 0;">{alert.rule.metric_type}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #6b7280; font-weight: 600;">Triggered At:</td>
                    <td style="padding: 8px 0;">{alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</td>
                </tr>
            </table>
        </div>
    </div>

    <div style="text-align: center; color: #6b7280; font-size: 14px; margin-top: 30px;">
        <p>This is an automated alert from <strong>SyncScope</strong></p>
        <p style="margin-top: 10px;">Alert ID: {alert.id}</p>
    </div>
</body>
</html>
"""
        return html


class SlackNotificationHandler(NotificationHandler):
    """Handler for Slack notifications"""

    def send(self, alert: AlertNotification, channel: NotificationChannel, notification_log: Notification):
        try:
            config = channel.config
            webhook_url = config.get("webhook_url")

            if not webhook_url:
                logger.warning(f"No webhook URL configured for Slack channel {channel.name}")
                return False

            # Prepare Slack message
            slack_message = self._format_slack_message(alert)

            # Send to Slack
            response = requests.post(
                webhook_url,
                json=slack_message,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            if response.status_code == 200:
                logger.info(f"Sent Slack notification for alert {alert.id}")
                return True
            else:
                logger.error(f"Slack API returned {response.status_code}: {response.text}")
                notification_log.error_message = f"Slack API error: {response.status_code}"
                return False

        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}", exc_info=True)
            notification_log.error_message = str(e)
            return False

    def _format_slack_message(self, alert: AlertNotification):
        """Format Slack message with blocks"""
        # Color based on severity
        color_map = {
            "critical": "#FF0000",
            "high": "#FF6B00",
            "medium": "#FFA500",
            "low": "#36A64F",
        }
        color = color_map.get(alert.severity, "#808080")

        return {
            "attachments": [
                {
                    "color": color,
                    "title": alert.title,
                    "text": alert.message,
                    "fields": [
                        {
                            "title": "Severity",
                            "value": alert.severity.upper(),
                            "short": True,
                        },
                        {
                            "title": "Status",
                            "value": alert.state,
                            "short": True,
                        },
                        {
                            "title": "Alert Rule",
                            "value": alert.alert_rule.name,
                            "short": True,
                        },
                        {
                            "title": "Rule Type",
                            "value": alert.alert_rule.rule_type,
                            "short": True,
                        },
                    ],
                    "footer": "SyncScope Alerts",
                    "ts": int(alert.triggered_at.timestamp()),
                }
            ]
        }


class WebhookNotificationHandler(NotificationHandler):
    """Handler for webhook notifications"""

    def send(self, alert: AlertNotification, channel: NotificationChannel, notification_log: Notification):
        try:
            config = channel.config
            webhook_url = config.get("url")

            if not webhook_url:
                logger.warning(f"No URL configured for webhook channel {channel.name}")
                return False

            # Prepare webhook payload
            payload = self._format_webhook_payload(alert, config)

            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "SyncScope-Alerts/1.0",
            }

            # Add custom headers if configured
            custom_headers = config.get("headers", {})
            headers.update(custom_headers)

            # Send webhook
            method = config.get("method", "POST").upper()

            if method == "POST":
                response = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
            elif method == "PUT":
                response = requests.put(webhook_url, json=payload, headers=headers, timeout=10)
            else:
                logger.error(f"Unsupported webhook method: {method}")
                return False

            if response.status_code in [200, 201, 202, 204]:
                logger.info(f"Sent webhook notification for alert {alert.id}")
                return True
            else:
                logger.error(f"Webhook returned {response.status_code}: {response.text}")
                notification_log.error_message = f"Webhook error: {response.status_code}"
                return False

        except Exception as e:
            logger.error(f"Error sending webhook notification: {e}", exc_info=True)
            notification_log.error_message = str(e)
            return False

    def _format_webhook_payload(self, alert: AlertNotification, config: dict):
        """Format webhook payload"""
        # Base payload
        payload = {
            "event": "alert.triggered",
            "alert": self._format_alert_data(alert),
        }

        # Add custom payload fields if configured
        custom_payload = config.get("payload", {})
        payload.update(custom_payload)

        return payload


class InAppNotificationHandler(NotificationHandler):
    """Handler for in-app notifications via WebSocket"""

    def send(self, alert: AlertNotification, channel: NotificationChannel, notification_log: Notification):
        try:
            config = channel.config
            user_ids = config.get("user_ids", [])

            if not user_ids:
                logger.warning(f"No user IDs configured for in-app channel {channel.name}")
                return False

            # Lazy import channels to avoid dependency issues in tests
            try:
                from asgiref.sync import async_to_sync
                from channels.layers import get_channel_layer
            except ImportError:
                logger.error("Channels not installed - in-app notifications unavailable")
                return False

            # Get channel layer
            channel_layer = get_channel_layer()

            if not channel_layer:
                logger.error("Channel layer not configured")
                return False

            # Prepare notification data
            notification_data = {
                "type": "alert_notification",
                "alert": self._format_alert_data(alert),
            }

            # Send to each user's WebSocket group
            success_count = 0
            for user_id in user_ids:
                try:
                    group_name = f"user_{user_id}_alerts"

                    async_to_sync(channel_layer.group_send)(
                        group_name,
                        {
                            "type": "send_alert",
                            "data": notification_data,
                        },
                    )

                    success_count += 1
                except Exception as e:
                    logger.error(f"Error sending to user {user_id}: {e}")

            if success_count > 0:
                logger.info(f"Sent in-app notification for alert {alert.id} to {success_count} users")
                return True
            else:
                notification_log.error_message = "Failed to send to any users"
                return False

        except Exception as e:
            logger.error(f"Error sending in-app notification: {e}", exc_info=True)
            notification_log.error_message = str(e)
            return False


class SMSNotificationHandler(NotificationHandler):
    """Handler for SMS notifications (placeholder for future implementation)"""

    def send(self, alert: AlertNotification, channel: NotificationChannel, notification_log: Notification):
        logger.warning("SMS notifications not yet implemented")
        notification_log.error_message = "SMS not implemented"
        return False


class PushNotificationHandler(NotificationHandler):
    """Handler for push notifications (placeholder for future implementation)"""

    def send(self, alert: AlertNotification, channel: NotificationChannel, notification_log: Notification):
        logger.warning("Push notifications not yet implemented")
        notification_log.error_message = "Push notifications not implemented"
        return False


# Handler registry
NOTIFICATION_HANDLERS = {
    "email": EmailNotificationHandler(),
    "slack": SlackNotificationHandler(),
    "webhook": WebhookNotificationHandler(),
    "in_app": InAppNotificationHandler(),
    "sms": SMSNotificationHandler(),
    "push": PushNotificationHandler(),
}


def send_notification(alert: AlertNotification, channel: NotificationChannel):
    """
    Send notification for an alert through a specific channel

    Args:
        alert: AlertNotification to notify about
        channel: NotificationChannel to use

    Returns:
        Notification: Created notification log
    """
    # Create notification log
    notification_log = Notification.objects.create(
        alert=alert,
        user_id=alert.triggered_for_user_id or alert.triggered_for_team_id or "00000000-0000-0000-0000-000000000000",
        notification_type=channel.type,
        message=alert.message,
        status="pending",
    )

    try:
        # Get handler for channel type
        handler = NOTIFICATION_HANDLERS.get(channel.type)

        if not handler:
            logger.error(f"No handler for channel type: {channel.type}")
            notification_log.mark_failed(f"Unsupported channel type: {channel.type}")
            return notification_log

        # Send notification
        success = handler.send(alert, channel, notification_log)

        if success:
            notification_log.mark_sent()
        else:
            notification_log.mark_failed(notification_log.error_message or "Unknown error")

    except Exception as e:
        logger.error(f"Error in send_notification: {e}", exc_info=True)
        notification_log.mark_failed(str(e))

    return notification_log
