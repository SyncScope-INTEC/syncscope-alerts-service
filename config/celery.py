"""
Celery configuration for syncscope-alerts-service.
"""

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("syncscope_alerts")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


# Celery Beat schedule for periodic alert evaluation
app.conf.beat_schedule = {
    "evaluate-alert-rules-every-minute": {
        "task": "apps.alerts.tasks.evaluate_all_active_alert_rules",
        "schedule": crontab(minute="*/1"),  # Run every minute
    },
    "cleanup-old-resolved-alerts": {
        "task": "apps.alerts.tasks.cleanup_old_resolved_alerts",
        "schedule": crontab(hour="2", minute="0"),  # Run daily at 2 AM
    },
    "retry-failed-notifications": {
        "task": "apps.alerts.tasks.retry_failed_notifications",
        "schedule": crontab(minute="*/5"),  # Run every 5 minutes
    },
}


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup"""
    print(f"Request: {self.request!r}")
