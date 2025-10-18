"""
Serializers for Alerts Service
"""

from rest_framework import serializers

from .models import AlertNotification, AlertRule, Notification, NotificationChannel

# Valid notification channel types
CHANNEL_TYPE_CHOICES = [
    ("email", "Email"),
    ("slack", "Slack"),
    ("webhook", "Webhook"),
    ("in_app", "In-App"),
    ("sms", "SMS"),
    ("push", "Push Notification"),
]


class AlertRuleSerializer(serializers.ModelSerializer):
    """Serializer for AlertRule model"""

    # company_id is read-only - automatically set from authenticated user's company
    company_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = AlertRule
        fields = [
            "id",
            "name",
            "description",
            "metric_type",
            "condition",
            "threshold_value",
            "is_active",
            "check_interval_minutes",
            "company_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "company_id", "created_at", "updated_at"]

    def validate_condition(self, value):
        """Validate condition JSON structure"""
        # Condition can be a string or dict
        if isinstance(value, str):
            return value

        if not isinstance(value, dict):
            raise serializers.ValidationError("Condition must be a string or JSON object")

        # Check for required fields if it's a dict
        if "operator" not in value:
            raise serializers.ValidationError("Condition must have an 'operator' field")

        # Validate operator
        valid_operators = ["gt", "lt", "eq", "gte", "lte", "between", "trend_up", "trend_down", "custom"]
        if value["operator"] not in valid_operators:
            raise serializers.ValidationError(f"Invalid operator. Must be one of: {', '.join(valid_operators)}")

        return value


class AlertRuleDetailSerializer(AlertRuleSerializer):
    """Detailed serializer for AlertRule"""

    pass


class AlertSerializer(serializers.ModelSerializer):
    """Serializer for Alert model"""

    rule_name = serializers.CharField(source="rule.name", read_only=True)

    class Meta:
        model = AlertNotification
        fields = [
            "id",
            "rule",
            "rule_name",
            "triggered_for_user_id",
            "triggered_for_team_id",
            "severity",
            "title",
            "message",
            "is_read",
            "acknowledged_by",
            "acknowledged_at",
            "triggered_at",
            "status",
            "context_data",
        ]
        read_only_fields = [
            "id",
            "rule_name",
            "triggered_at",
        ]


class AlertDetailSerializer(AlertSerializer):
    """Detailed serializer for Alert with full alert rule info"""

    rule = AlertRuleSerializer(read_only=True)


class AlertAcknowledgeSerializer(serializers.Serializer):
    """Serializer for acknowledging alerts"""

    alert_ids = serializers.ListField(
        child=serializers.UUIDField(), required=True, help_text="List of alert IDs to acknowledge"
    )


class AlertResolveSerializer(serializers.Serializer):
    """Serializer for resolving alerts"""

    alert_ids = serializers.ListField(child=serializers.UUIDField(), required=True, help_text="List of alert IDs to resolve")


class NotificationChannelSerializer(serializers.ModelSerializer):
    """Serializer for NotificationChannel model"""

    # company_id is read-only - automatically set from authenticated user's company
    company_id = serializers.UUIDField(read_only=True)

    # Use ChoiceField to enforce valid channel types
    type = serializers.ChoiceField(
        choices=CHANNEL_TYPE_CHOICES, help_text="Type of notification channel (email, slack, webhook, in_app, sms, push)"
    )

    class Meta:
        model = NotificationChannel
        fields = [
            "id",
            "name",
            "type",
            "config",
            "is_active",
            "company_id",
            "created_at",
        ]
        read_only_fields = ["id", "company_id", "created_at"]

    def validate_config(self, value):
        """Validate config JSON structure based on channel type"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Config must be a JSON object")

        # Validate based on channel type
        channel_type = self.initial_data.get("type")

        if channel_type == "email":
            if "recipients" not in value:
                raise serializers.ValidationError("Email config must have 'recipients' field (list of email addresses)")
            if not isinstance(value["recipients"], list):
                raise serializers.ValidationError("Email 'recipients' must be a list of email addresses")

        elif channel_type == "slack":
            if "webhook_url" not in value:
                raise serializers.ValidationError("Slack config must have 'webhook_url' field")

        elif channel_type == "webhook":
            if "url" not in value:
                raise serializers.ValidationError("Webhook config must have 'url' field")

        elif channel_type == "in_app":
            if "user_ids" not in value:
                raise serializers.ValidationError("In-app config must have 'user_ids' field (list of UUIDs)")
            if not isinstance(value["user_ids"], list):
                raise serializers.ValidationError("In-app 'user_ids' must be a list of user UUIDs")

        return value


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model"""

    alert_title = serializers.CharField(source="alert.title", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "user_id",
            "alert",
            "alert_title",
            "notification_type",
            "subject",
            "message",
            "sent_at",
            "read_at",
            "status",
            "delivery_metadata",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "alert_title",
            "sent_at",
            "read_at",
            "created_at",
        ]


class AlertStatisticsSerializer(serializers.Serializer):
    """Serializer for alert statistics"""

    total_alerts = serializers.IntegerField()
    active_alerts = serializers.IntegerField()
    acknowledged_alerts = serializers.IntegerField()
    resolved_alerts = serializers.IntegerField()
    muted_alerts = serializers.IntegerField()
    critical_alerts = serializers.IntegerField()
    high_alerts = serializers.IntegerField()
    medium_alerts = serializers.IntegerField()
    low_alerts = serializers.IntegerField()
    alerts_by_type = serializers.DictField()
    alerts_by_target = serializers.DictField()


class AlertRuleTestSerializer(serializers.Serializer):
    """Serializer for testing alert rules"""

    test_data = serializers.JSONField(required=False, help_text="Optional test data to simulate metric values")
