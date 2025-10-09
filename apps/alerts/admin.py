"""
Django Admin configuration for Alerts Service
"""

from django.contrib import admin

from .models import AlertNotification, AlertRule, Notification, NotificationChannel


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    """Admin interface for AlertRule"""

    list_display = [
        "name",
        "metric_type",
        "condition",
        "is_active",
        "created_at",
    ]
    list_filter = ["metric_type", "condition", "is_active", "created_at"]
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
                )
            },
        ),
        (
            "Settings",
            {
                "fields": (
                    "is_active",
                    "check_interval_minutes",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "company_id",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


@admin.register(AlertNotification)
class AlertNotificationAdmin(admin.ModelAdmin):
    """Admin interface for AlertNotification"""

    list_display = [
        "title",
        "rule",
        "severity",
        "status",
        "triggered_at",
        "is_read",
    ]
    list_filter = ["severity", "status", "is_read", "triggered_at"]
    search_fields = ["title", "message"]
    readonly_fields = [
        "id",
        "triggered_at",
        "acknowledged_at",
    ]
    fieldsets = (
        (
            "Alert Information",
            {
                "fields": (
                    "id",
                    "rule",
                    "title",
                    "message",
                    "severity",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "status",
                    "is_read",
                )
            },
        ),
        (
            "Target",
            {
                "fields": (
                    "triggered_for_user_id",
                    "triggered_for_team_id",
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
                )
            },
        ),
        (
            "Context",
            {"fields": ("context_data",)},
        ),
    )


@admin.register(NotificationChannel)
class NotificationChannelAdmin(admin.ModelAdmin):
    """Admin interface for NotificationChannel"""

    list_display = ["name", "type", "is_active", "company_id", "created_at"]
    list_filter = ["type", "is_active", "created_at"]
    search_fields = ["name"]
    readonly_fields = ["id", "created_at"]
    fieldsets = (
        (
            "Channel Information",
            {
                "fields": (
                    "id",
                    "name",
                    "type",
                    "config",
                )
            },
        ),
        (
            "Settings",
            {"fields": ("is_active",)},
        ),
        (
            "Metadata",
            {
                "fields": (
                    "company_id",
                    "created_at",
                )
            },
        ),
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin interface for Notification"""

    list_display = [
        "user_id",
        "alert",
        "notification_type",
        "status",
        "sent_at",
        "created_at",
    ]
    list_filter = ["notification_type", "status", "created_at"]
    search_fields = ["subject", "message", "user_id"]
    readonly_fields = ["id", "sent_at", "read_at", "created_at"]
    fieldsets = (
        (
            "Notification Information",
            {
                "fields": (
                    "id",
                    "user_id",
                    "alert",
                    "notification_type",
                )
            },
        ),
        (
            "Content",
            {
                "fields": (
                    "subject",
                    "message",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "status",
                    "sent_at",
                    "read_at",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "delivery_metadata",
                    "created_at",
                )
            },
        ),
    )
