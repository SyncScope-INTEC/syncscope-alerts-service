"""
Notification Handlers for different channels
Supports Email, Slack, Webhook, and In-App notifications
"""

import json
import logging
from abc import ABC, abstractmethod

import requests
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from .models import Alert, NotificationChannel, NotificationLog

logger = logging.getLogger(__name__)


class NotificationHandler(ABC):
    """Base class for notification handlers"""

    @abstractmethod
    def send(self, alert: Alert, channel: NotificationChannel, notification_log: NotificationLog):
        """
        Send notification through this channel

        Args:
            alert: Alert to notify about
            channel: NotificationChannel configuration
            notification_log: NotificationLog to track delivery

        Returns:
            bool: True if successful, False otherwise
        """
        pass

    def _format_alert_data(self, alert: Alert):
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
    """Handler for email notifications"""

    def send(self, alert: Alert, channel: NotificationChannel, notification_log: NotificationLog):
        try:
            config = channel.config
            recipients = config.get("recipients", [])

            if not recipients:
                logger.warning(f"No recipients configured for email channel {channel.name}")
                return False

            # Prepare email content
            subject = f"[{alert.severity.upper()}] {alert.title}"
            message = self._format_email_message(alert)

            # Send email
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                fail_silently=False,
            )

            logger.info(f"Sent email notification for alert {alert.id} to {len(recipients)} recipients")
            return True

        except Exception as e:
            logger.error(f"Error sending email notification: {e}", exc_info=True)
            notification_log.error_message = str(e)
            return False

    def _format_email_message(self, alert: Alert):
        """Format email message"""
        message = f"""
Alert: {alert.title}
Severity: {alert.severity.upper()}
Status: {alert.state}

{alert.message}

Alert Rule: {alert.alert_rule.name}
Rule Type: {alert.alert_rule.rule_type}

Triggered At: {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC')}

---
This is an automated alert from SyncScope.
"""
        return message


class SlackNotificationHandler(NotificationHandler):
    """Handler for Slack notifications"""

    def send(self, alert: Alert, channel: NotificationChannel, notification_log: NotificationLog):
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

    def _format_slack_message(self, alert: Alert):
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

    def send(self, alert: Alert, channel: NotificationChannel, notification_log: NotificationLog):
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

    def _format_webhook_payload(self, alert: Alert, config: dict):
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

    def send(self, alert: Alert, channel: NotificationChannel, notification_log: NotificationLog):
        try:
            config = channel.config
            user_ids = config.get("user_ids", [])

            if not user_ids:
                logger.warning(f"No user IDs configured for in-app channel {channel.name}")
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

    def send(self, alert: Alert, channel: NotificationChannel, notification_log: NotificationLog):
        logger.warning("SMS notifications not yet implemented")
        notification_log.error_message = "SMS not implemented"
        return False


class PushNotificationHandler(NotificationHandler):
    """Handler for push notifications (placeholder for future implementation)"""

    def send(self, alert: Alert, channel: NotificationChannel, notification_log: NotificationLog):
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


def send_notification(alert: Alert, channel: NotificationChannel):
    """
    Send notification for an alert through a specific channel

    Args:
        alert: Alert to notify about
        channel: NotificationChannel to use

    Returns:
        NotificationLog: Created notification log
    """
    # Create notification log
    notification_log = NotificationLog.objects.create(
        alert=alert,
        channel=channel,
        status="pending",
    )

    try:
        # Get handler for channel type
        handler = NOTIFICATION_HANDLERS.get(channel.channel_type)

        if not handler:
            logger.error(f"No handler for channel type: {channel.channel_type}")
            notification_log.mark_failed(f"Unsupported channel type: {channel.channel_type}")
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
