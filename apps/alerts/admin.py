"""
Django Admin configuration for Alerts Service
"""

from django.contrib import admin

from .models import Alert, AlertRule, NotificationChannel, NotificationLog


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    """Admin interface for AlertRule"""

    list_display = [
        "name",
        "rule_type",
        "severity",
        "target_type",
        "is_active",
        "created_at",
    ]
    list_filter = ["rule_type", "severity", "target_type", "is_active", "created_at"]
    search_fields = ["name", "description", "metric_type"]
    readonly_fields = ["id", "created_at", "updated_at"]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                    "rule_type",
                    "metric_type",
                )
            },
        ),
        (
            "Condition",
            {
                "fields": (
                    "condition",
                    "threshold_value",
                    "severity",
                )
            },
        ),
        (
            "Target",
            {
                "fields": (
                    "target_type",
                    "target_id",
                )
            },
        ),
        (
            "Settings",
            {
                "fields": (
                    "is_active",
                    "cooldown_minutes",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "company_id",
                    "created_by",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    """Admin interface for Alert"""

    list_display = [
        "title",
        "alert_rule",
        "state",
        "severity",
        "triggered_at",
        "company_id",
    ]
    list_filter = ["state", "severity", "triggered_at"]
    search_fields = ["title", "message"]
    readonly_fields = [
        "id",
        "triggered_at",
        "acknowledged_at",
        "resolved_at",
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        (
            "Alert Information",
            {
                "fields": (
                    "id",
                    "alert_rule",
                    "title",
                    "message",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "state",
                    "severity",
                )
            },
        ),
        (
            "Target",
            {
                "fields": (
                    "target_type",
                    "target_id",
                )
            },
        ),
        (
            "Timeline",
            {
                "fields": (
                    "triggered_at",
                    "acknowledged_at",
                    "acknowledged_by",
                    "resolved_at",
                    "resolved_by",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "metadata",
                    "company_id",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


@admin.register(NotificationChannel)
class NotificationChannelAdmin(admin.ModelAdmin):
    """Admin interface for NotificationChannel"""

    list_display = ["name", "channel_type", "is_active", "company_id", "created_at"]
    list_filter = ["channel_type", "is_active", "created_at"]
    search_fields = ["name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    fieldsets = (
        (
            "Channel Information",
            {
                "fields": (
                    "id",
                    "name",
                    "channel_type",
                    "config",
                )
            },
        ),
        (
            "Settings",
            {
                "fields": ("is_active",)
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "company_id",
                    "created_by",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    """Admin interface for NotificationLog"""

    list_display = [
        "alert",
        "channel",
        "status",
        "sent_at",
        "retry_count",
        "created_at",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["alert__title", "channel__name", "error_message"]
    readonly_fields = ["id", "sent_at", "created_at", "updated_at"]
    fieldsets = (
        (
            "Notification Information",
            {
                "fields": (
                    "id",
                    "alert",
                    "channel",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "status",
                    "sent_at",
                    "error_message",
                    "retry_count",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "metadata",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
