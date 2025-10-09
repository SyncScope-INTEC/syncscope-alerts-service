"""
Serializers for Alerts Service
"""

from rest_framework import serializers

from .models import AlertNotification, AlertRule, Notification, NotificationChannel


class AlertRuleSerializer(serializers.ModelSerializer):
    """Serializer for AlertRule model"""

    notification_channels = serializers.PrimaryKeyRelatedField(
        many=True, queryset=NotificationChannel.objects.all(), required=False
    )

    class Meta:
        model = AlertNotificationRule
        fields = [
            "id",
            "name",
            "description",
            "rule_type",
            "metric_type",
            "condition",
            "threshold_value",
            "severity",
            "target_type",
            "target_id",
            "is_active",
            "cooldown_minutes",
            "notification_channels",
            "company_id",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_condition(self, value):
        """Validate condition JSON structure"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Condition must be a JSON object")

        # Check for required fields
        if "operator" not in value:
            raise serializers.ValidationError("Condition must have an 'operator' field")

        # Validate operator
        valid_operators = ["gt", "lt", "eq", "gte", "lte", "between", "trend_up", "trend_down", "custom"]
        if value["operator"] not in valid_operators:
            raise serializers.ValidationError(f"Invalid operator. Must be one of: {', '.join(valid_operators)}")

        return value

    def create(self, validated_data):
        """Create alert rule with notification channels"""
        notification_channels = validated_data.pop("notification_channels", [])
        alert_rule = AlertRule.objects.create(**validated_data)

        # Add notification channels
        if notification_channels:
            alert_rule.notification_channels.set(notification_channels)

        return alert_rule

    def update(self, instance, validated_data):
        """Update alert rule with notification channels"""
        notification_channels = validated_data.pop("notification_channels", None)

        # Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update notification channels if provided
        if notification_channels is not None:
            instance.notification_channels.set(notification_channels)

        return instance


class AlertRuleDetailSerializer(AlertRuleSerializer):
    """Detailed serializer for AlertRule with nested notification channels"""

    notification_channels = serializers.SerializerMethodField()

    def get_notification_channels(self, obj):
        """Get notification channels with details"""
        channels = obj.notification_channels.all()
        return NotificationChannelSerializer(channels, many=True).data


class AlertSerializer(serializers.ModelSerializer):
    """Serializer for Alert model"""

    alert_rule_name = serializers.CharField(source="alert_rule.name", read_only=True)

    class Meta:
        model = AlertNotification
        fields = [
            "id",
            "alert_rule",
            "alert_rule_name",
            "state",
            "severity",
            "title",
            "message",
            "triggered_at",
            "acknowledged_at",
            "acknowledged_by",
            "resolved_at",
            "resolved_by",
            "metadata",
            "target_type",
            "target_id",
            "company_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "alert_rule_name",
            "triggered_at",
            "created_at",
            "updated_at",
        ]


class AlertDetailSerializer(AlertSerializer):
    """Detailed serializer for Alert with full alert rule info"""

    alert_rule = AlertRuleSerializer(read_only=True)


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

    class Meta:
        model = NotificationChannel
        fields = [
            "id",
            "name",
            "channel_type",
            "config",
            "is_active",
            "company_id",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_config(self, value):
        """Validate config JSON structure based on channel type"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Config must be a JSON object")

        # Validate based on channel type
        channel_type = self.initial_data.get("channel_type")

        if channel_type == "email":
            if "recipients" not in value:
                raise serializers.ValidationError("Email config must have 'recipients' field")
            if not isinstance(value["recipients"], list):
                raise serializers.ValidationError("Email recipients must be a list")

        elif channel_type == "slack":
            if "webhook_url" not in value:
                raise serializers.ValidationError("Slack config must have 'webhook_url' field")

        elif channel_type == "webhook":
            if "url" not in value:
                raise serializers.ValidationError("Webhook config must have 'url' field")

        return value


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model"""

    alert_title = serializers.CharField(source="alert.title", read_only=True)
    channel_name = serializers.CharField(source="channel.name", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "alert",
            "alert_title",
            "channel",
            "channel_name",
            "status",
            "sent_at",
            "error_message",
            "retry_count",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "alert_title",
            "channel_name",
            "sent_at",
            "created_at",
            "updated_at",
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

    rule_id = serializers.UUIDField(required=True)
    test_data = serializers.JSONField(required=False, help_text="Optional test data to simulate metric values")
