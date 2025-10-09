"""
Celery tasks for Alert Service
Background tasks for alert evaluation and notification sending
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .alert_engine import alert_engine
from .models import Alert, AlertRule, NotificationLog
from .notification_handlers import send_notification

logger = logging.getLogger(__name__)


@shared_task(name="apps.alerts.tasks.evaluate_all_active_alert_rules")
def evaluate_all_active_alert_rules():
    """
    Periodic task to evaluate all active alert rules
    Runs every minute (configured in celery.py)
    """
    logger.info("Starting periodic alert rule evaluation")

    try:
        # Get all active alert rules
        active_rules = AlertRule.objects.filter(is_active=True)

        evaluated_count = 0
        triggered_count = 0

        for rule in active_rules:
            try:
                # Evaluate rule
                should_trigger, context = alert_engine.evaluate_rule(rule)

                evaluated_count += 1

                if should_trigger:
                    # Trigger alert
                    alert = alert_engine.trigger_alert(rule, context)
                    if alert:
                        triggered_count += 1

            except Exception as e:
                logger.error(f"Error evaluating rule {rule.id}: {e}", exc_info=True)
                continue

        logger.info(f"Alert evaluation complete: {evaluated_count} rules evaluated, {triggered_count} alerts triggered")

        return {
            "evaluated": evaluated_count,
            "triggered": triggered_count,
        }

    except Exception as e:
        logger.error(f"Error in periodic alert evaluation: {e}", exc_info=True)
        return {"error": str(e)}


@shared_task(name="apps.alerts.tasks.evaluate_single_alert_rule")
def evaluate_single_alert_rule(rule_id: str):
    """
    Evaluate a single alert rule

    Args:
        rule_id: UUID of the alert rule to evaluate
    """
    try:
        rule = AlertRule.objects.get(id=rule_id)

        # Evaluate rule
        should_trigger, context = alert_engine.evaluate_rule(rule)

        if should_trigger:
            # Trigger alert
            alert = alert_engine.trigger_alert(rule, context)
            return {
                "triggered": True,
                "alert_id": str(alert.id) if alert else None,
            }
        else:
            return {"triggered": False}

    except AlertRule.DoesNotExist:
        logger.error(f"Alert rule {rule_id} not found")
        return {"error": "Alert rule not found"}
    except Exception as e:
        logger.error(f"Error evaluating rule {rule_id}: {e}", exc_info=True)
        return {"error": str(e)}


@shared_task(name="apps.alerts.tasks.send_alert_notifications")
def send_alert_notifications(alert_id: str):
    """
    Send notifications for an alert through all configured channels

    Args:
        alert_id: UUID of the alert to send notifications for
    """
    try:
        alert = Alert.objects.get(id=alert_id)

        # Get notification channels from alert rule
        channels = alert.alert_rule.notification_channels.filter(is_active=True)

        if not channels.exists():
            logger.warning(f"No active notification channels for alert {alert_id}")
            return {"sent": 0, "failed": 0}

        sent_count = 0
        failed_count = 0

        for channel in channels:
            try:
                # Send notification
                notification_log = send_notification(alert, channel)

                if notification_log.status == "sent":
                    sent_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                logger.error(f"Error sending notification via {channel.name}: {e}", exc_info=True)
                failed_count += 1

        logger.info(f"Notifications sent for alert {alert_id}: {sent_count} successful, {failed_count} failed")

        return {
            "sent": sent_count,
            "failed": failed_count,
        }

    except Alert.DoesNotExist:
        logger.error(f"Alert {alert_id} not found")
        return {"error": "Alert not found"}
    except Exception as e:
        logger.error(f"Error sending notifications for alert {alert_id}: {e}", exc_info=True)
        return {"error": str(e)}


@shared_task(name="apps.alerts.tasks.retry_failed_notifications")
def retry_failed_notifications():
    """
    Periodic task to retry failed notifications
    Runs every 5 minutes (configured in celery.py)
    """
    logger.info("Starting retry of failed notifications")

    try:
        # Get failed notifications that haven't exceeded max retries
        max_retries = settings.MAX_RETRY_ATTEMPTS
        retry_delay = timedelta(seconds=settings.NOTIFICATION_RETRY_DELAY)

        failed_notifications = NotificationLog.objects.filter(
            status="failed",
            retry_count__lt=max_retries,
            updated_at__lt=timezone.now() - retry_delay,
        )

        retry_count = 0
        success_count = 0

        for notification_log in failed_notifications:
            try:
                # Mark as retrying
                notification_log.mark_retrying()

                # Retry sending
                new_log = send_notification(notification_log.alert, notification_log.channel)

                retry_count += 1

                if new_log.status == "sent":
                    success_count += 1

            except Exception as e:
                logger.error(f"Error retrying notification {notification_log.id}: {e}", exc_info=True)
                continue

        logger.info(f"Notification retry complete: {retry_count} retried, {success_count} successful")

        return {
            "retried": retry_count,
            "successful": success_count,
        }

    except Exception as e:
        logger.error(f"Error in notification retry task: {e}", exc_info=True)
        return {"error": str(e)}


@shared_task(name="apps.alerts.tasks.cleanup_old_resolved_alerts")
def cleanup_old_resolved_alerts():
    """
    Periodic task to cleanup old resolved alerts
    Runs daily at 2 AM (configured in celery.py)
    """
    logger.info("Starting cleanup of old resolved alerts")

    try:
        retention_days = settings.ALERT_RETENTION_DAYS
        cutoff_date = timezone.now() - timedelta(days=retention_days)

        # Delete old resolved alerts
        deleted_count, _ = Alert.objects.filter(
            state="resolved",
            resolved_at__lt=cutoff_date,
        ).delete()

        logger.info(f"Cleanup complete: {deleted_count} old resolved alerts deleted")

        return {"deleted": deleted_count}

    except Exception as e:
        logger.error(f"Error in cleanup task: {e}", exc_info=True)
        return {"error": str(e)}


@shared_task(name="apps.alerts.tasks.test_notification_channel")
def test_notification_channel(channel_id: str, test_alert_data: dict = None):
    """
    Test a notification channel by sending a test notification

    Args:
        channel_id: UUID of the notification channel to test
        test_alert_data: Optional test alert data
    """
    try:
        from .models import NotificationChannel

        channel = NotificationChannel.objects.get(id=channel_id)

        # Create a test alert (not saved to database)
        if test_alert_data:
            alert = Alert(**test_alert_data)
        else:
            # Use default test data
            alert = Alert(
                id="00000000-0000-0000-0000-000000000000",
                title="Test Alert",
                message="This is a test notification from SyncScope Alerts Service",
                severity="low",
                state="active",
                triggered_at=timezone.now(),
            )
            alert.alert_rule = type(
                "obj",
                (object,),
                {
                    "name": "Test Rule",
                    "rule_type": "test",
                },
            )

        # Send test notification
        from .notification_handlers import NOTIFICATION_HANDLERS

        handler = NOTIFICATION_HANDLERS.get(channel.channel_type)

        if not handler:
            return {"success": False, "error": f"Unsupported channel type: {channel.channel_type}"}

        # Create a dummy notification log for testing
        notification_log = NotificationLog(
            alert=None,
            channel=channel,
            status="pending",
        )

        success = handler.send(alert, channel, notification_log)

        return {
            "success": success,
            "error": notification_log.error_message if not success else None,
        }

    except NotificationChannel.DoesNotExist:
        return {"success": False, "error": "Notification channel not found"}
    except Exception as e:
        logger.error(f"Error testing notification channel {channel_id}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
