"""
Alert Service Models
"""

import sys
import uuid

from django.contrib.auth.models import AbstractBaseUser
from django.db import models
from django.utils import timezone

from config.database_retry import atomic_with_retry

from .db_mixins import RetryableManager, RetryableModelMixin


class User(AbstractBaseUser):
    """
    Custom User model that references the auth.users table from auth service.
    Uses UUID primary key to match the auth service schema.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    password = models.CharField(max_length=128, db_column="password_hash")
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_superuser = models.BooleanField(default=False)
    last_login = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"  # Reference auth.users table via search path
        managed = False  # Don't let Django manage this table

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser

    def get_username(self):
        return self.username if hasattr(self, "username") else self.email


def get_table_name(base_name):
    """Get table name with or without schema prefix based on test mode."""
    if "test" in sys.argv or "pytest" in sys.modules:
        # SQLite doesn't support schemas, use simple table names for tests
        return base_name
    else:
        # PostgreSQL with alerts schema
        return f"alerts.{base_name}"


class AlertRule(RetryableModelMixin, models.Model):
    """
    Model representing alert rules for automatic monitoring and notifications.
    Maps to the existing alerts.alert_rules table.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    company_id = models.UUIDField()
    metric_type = models.CharField(max_length=100)
    condition = models.CharField(max_length=50)
    threshold_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    check_interval_minutes = models.IntegerField(default=60)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = RetryableManager()

    class Meta:
        db_table = get_table_name("alert_rules")
        managed = False  # Table already exists
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name}"

    def get_last_alert_time(self, target_id=None):
        """Get the last time an alert was triggered for this rule"""
        alerts = AlertNotification.objects.filter(rule=self)
        if target_id:
            alerts = alerts.filter(models.Q(triggered_for_user_id=target_id) | models.Q(triggered_for_team_id=target_id))

        last_alert = alerts.order_by("-triggered_at").first()
        return last_alert.triggered_at if last_alert else None

    def is_in_cooldown(self, target_id=None):
        """Check if this rule is in cooldown period"""
        last_alert_time = self.get_last_alert_time(target_id)
        if not last_alert_time:
            return False

        from datetime import timedelta

        cooldown_period = timedelta(minutes=self.check_interval_minutes)
        return timezone.now() < (last_alert_time + cooldown_period)


class AlertNotification(RetryableModelMixin, models.Model):
    """
    Model representing triggered alert notifications.
    Maps to the existing alerts.alert_notifications table.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE, related_name="notifications", db_column="rule_id")
    triggered_for_user_id = models.UUIDField(null=True, blank=True)
    triggered_for_team_id = models.UUIDField(null=True, blank=True)
    severity = models.CharField(max_length=20)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    acknowledged_by = models.UUIDField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    triggered_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default="pending")
    context_data = models.JSONField(default=dict, blank=True)

    objects = RetryableManager()

    class Meta:
        db_table = get_table_name("alert_notifications")
        managed = False  # Table already exists
        ordering = ["-triggered_at"]

    def __str__(self):
        return f"{self.title} ({self.severity})"

    def acknowledge(self, user_id):
        """Acknowledge this alert notification"""
        self.is_read = True
        self.acknowledged_at = timezone.now()
        self.acknowledged_by = user_id
        self.status = "acknowledged"
        self.save()

    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.save()

    def resolve(self, user_id):
        """Resolve this alert notification"""
        self.status = "resolved"
        self.is_read = True
        self.save()

    def mute(self):
        """Mute this alert notification"""
        self.status = "muted"
        self.save()


class NotificationChannel(RetryableModelMixin, models.Model):
    """
    Model representing notification channels.
    Maps to the existing alerts.notification_channels table.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    type = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    config = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = RetryableManager()

    class Meta:
        db_table = get_table_name("notification_channels")
        managed = False  # Table already exists
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.type})"


class Notification(RetryableModelMixin, models.Model):
    """
    Model representing individual notifications sent to users.
    Maps to the existing alerts.notifications table.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField()
    alert = models.ForeignKey(AlertNotification, on_delete=models.CASCADE, related_name="notifications", db_column="alert_id")
    notification_type = models.CharField(max_length=20)
    subject = models.CharField(max_length=200, blank=True, null=True)
    message = models.TextField()
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default="pending")
    delivery_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = RetryableManager()

    class Meta:
        db_table = get_table_name("notifications")
        managed = False  # Table already exists
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.notification_type} notification for user {self.user_id}"

    def mark_sent(self):
        """Mark notification as sent"""
        self.status = "sent"
        self.sent_at = timezone.now()
        self.save()

    def mark_read(self):
        """Mark notification as read"""
        self.read_at = timezone.now()
        self.save()

    def mark_failed(self, error_message):
        """Mark notification as failed"""
        self.status = "failed"
        self.delivery_metadata["error"] = error_message
        self.save()

    def mark_retrying(self):
        """Mark notification as retrying"""
        if not self.delivery_metadata:
            self.delivery_metadata = {}
        retry_count = self.delivery_metadata.get("retry_count", 0)
        self.delivery_metadata["retry_count"] = retry_count + 1
        self.status = "retrying"
        self.save()
