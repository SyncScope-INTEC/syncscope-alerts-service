"""
Celery configuration for syncscope-alerts-service.
"""

import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_postrun, worker_process_init, worker_process_shutdown

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("syncscope_alerts")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


# Database connection management for serverless/Railway
@worker_process_init.connect
def close_db_connections_on_worker_init(**kwargs):
    """Close database connections when worker process initializes"""
    from django.db import connections

    for conn in connections.all():
        conn.close()


@worker_process_shutdown.connect
def close_db_connections_on_worker_shutdown(**kwargs):
    """Close database connections when worker process shuts down"""
    from django.db import connections

    for conn in connections.all():
        conn.close()


@task_postrun.connect
def close_db_connections_after_task(**kwargs):
    """Close database connections after each task completes"""
    from django.db import close_old_connections

    close_old_connections()


# Celery configuration for serverless/Railway environment
app.conf.update(
    # Recycle worker after processing N tasks to prevent connection leaks
    worker_max_tasks_per_child=100,
    # Don't prefetch tasks to reduce concurrent connections
    worker_prefetch_multiplier=1,
    # Task time limits
    task_time_limit=300,  # 5 minutes hard limit
    task_soft_time_limit=240,  # 4 minutes soft limit
    # Connection settings
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
)


# Celery Beat schedule for periodic alert evaluation
app.conf.beat_schedule = {
    "evaluate-alert-rules-every-5-minutes": {
        "task": "apps.alerts.tasks.evaluate_all_active_alert_rules",
        "schedule": crontab(minute="*/5"),  # Run every 5 minutes
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
