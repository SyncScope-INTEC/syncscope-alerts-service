"""
API Views for Alerts Service
"""

import logging

from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.template import loader
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import AlertPermissions
from .db_mixins import ServerlessViewMixin
from .models import AlertNotification, AlertRule, Notification, NotificationChannel
from .serializers import (
    AlertAcknowledgeSerializer,
    AlertDetailSerializer,
    AlertResolveSerializer,
    AlertRuleDetailSerializer,
    AlertRuleSerializer,
    AlertRuleTestSerializer,
    AlertSerializer,
    AlertStatisticsSerializer,
    NotificationChannelSerializer,
    NotificationSerializer,
)
from .tasks import evaluate_single_alert_rule, send_test_notification

logger = logging.getLogger(__name__)


@extend_schema(exclude=True)  # Exclude from API docs as it returns HTML
@api_view(["GET"])
@permission_classes([])
def api_home(request):
    """
    API Home page showing main navigation routes and service links.
    """
    # Define the main navigation routes
    main_routes = [
        {
            "title": "API Documentation",
            "description": "Interactive API documentation with live testing",
            "url": request.build_absolute_uri("/api/docs/"),
            "icon": "📖",
            "category": "documentation",
        },
        {
            "title": "ReDoc Documentation",
            "description": "Clean, three-panel OpenAPI documentation",
            "url": request.build_absolute_uri("/api/redoc/"),
            "icon": "📚",
            "category": "documentation",
        },
        {
            "title": "OpenAPI Schema",
            "description": "Raw OpenAPI specification in JSON format",
            "url": request.build_absolute_uri("/api/schema/"),
            "icon": "⚙️",
            "category": "documentation",
        },
        {
            "title": "Admin Interface",
            "description": "Django admin panel for system management",
            "url": request.build_absolute_uri("/admin/"),
            "icon": "🔧",
            "category": "admin",
        },
        {
            "title": "Health Check",
            "description": "Service health status and monitoring",
            "url": request.build_absolute_uri("/health/"),
            "icon": "❤️",
            "category": "monitoring",
        },
    ]

    # Service information and features
    service_info = {
        "features": [
            "Alert Rules Management",
            "Multi-Channel Notifications",
            "Real-time Monitoring",
            "WebSocket Support",
            "Metric-Based Triggers",
            "Custom Alert Conditions",
        ],
        "status": "Operational",
    }

    context = {
        "main_routes": main_routes,
        "service_info": service_info,
        "api_title": "SyncScope Alerts Service",
        "api_version": "1.0.0",
        "api_description": "Alert management and notification service for SyncScope platform",
        "base_url": request.build_absolute_uri("/"),
    }

    # Check if JSON format is explicitly requested
    if request.GET.get("format") == "json":
        return Response(context, status=status.HTTP_200_OK)

    # Try to render HTML template first, fallback to JSON
    try:
        # Check if this is a test case that explicitly uses a mock template
        import sys

        is_testing = "pytest" in sys.modules or "test" in sys.argv
        template = loader.get_template("alerts/api_home.html")
        return HttpResponse(template.render(context, request))
    except:
        # Fallback to JSON response if template doesn't exist
        return Response(context, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(tags=["Alert Rules"], summary="List alert rules"),
    create=extend_schema(tags=["Alert Rules"], summary="Create alert rule"),
    retrieve=extend_schema(tags=["Alert Rules"], summary="Get alert rule details"),
    update=extend_schema(tags=["Alert Rules"], summary="Update alert rule"),
    partial_update=extend_schema(tags=["Alert Rules"], summary="Partially update alert rule"),
    destroy=extend_schema(tags=["Alert Rules"], summary="Delete alert rule"),
)
class AlertRuleViewSet(ServerlessViewMixin, viewsets.ModelViewSet):
    """ViewSet for managing alert rules"""

    serializer_class = AlertRuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter alert rules by company"""
        user = self.request.user
        company_id = user.company_id

        queryset = AlertRule.objects.filter(company_id=company_id)

        # Filter by parameters
        metric_type = self.request.query_params.get("metric_type")
        if metric_type:
            queryset = queryset.filter(metric_type=metric_type)

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset.order_by("-created_at")

    def get_serializer_class(self):
        """Use detailed serializer for retrieve action"""
        if self.action == "retrieve":
            return AlertRuleDetailSerializer
        return AlertRuleSerializer

    def create(self, request, *args, **kwargs):
        """Create a new alert rule"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Set company_id from authenticated user (company_id is read-only in serializer)
        serializer.save(company_id=request.user.company_id)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Alert Rules"],
        summary="Test alert rule evaluation",
        request=AlertRuleTestSerializer,
        responses={202: {"type": "object", "properties": {"message": {"type": "string"}, "task_id": {"type": "string"}}}},
    )
    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        """Test an alert rule with optional test data"""
        rule = self.get_object()

        serializer = AlertRuleTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        test_data = serializer.validated_data.get("test_data")

        # Trigger evaluation asynchronously
        task = evaluate_single_alert_rule.delay(str(rule.id))

        return Response(
            {
                "message": "Alert rule evaluation triggered",
                "task_id": task.id,
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @extend_schema(
        tags=["Alert Rules"],
        summary="Activate alert rule",
        responses={200: {"type": "object", "properties": {"message": {"type": "string"}, "is_active": {"type": "boolean"}}}},
    )
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        """Activate an alert rule"""
        rule = self.get_object()
        rule.is_active = True
        rule.save()

        return Response(
            {"message": "Alert rule activated", "is_active": True},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Alert Rules"],
        summary="Deactivate alert rule",
        responses={200: {"type": "object", "properties": {"message": {"type": "string"}, "is_active": {"type": "boolean"}}}},
    )
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        """Deactivate an alert rule"""
        rule = self.get_object()
        rule.is_active = False
        rule.save()

        return Response(
            {"message": "Alert rule deactivated", "is_active": False},
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    list=extend_schema(tags=["Alerts"], summary="List alerts"),
    create=extend_schema(tags=["Alerts"], summary="Create alert"),
    retrieve=extend_schema(tags=["Alerts"], summary="Get alert details"),
    update=extend_schema(tags=["Alerts"], summary="Update alert"),
    partial_update=extend_schema(tags=["Alerts"], summary="Partially update alert"),
    destroy=extend_schema(tags=["Alerts"], summary="Delete alert"),
)
class AlertViewSet(ServerlessViewMixin, viewsets.ModelViewSet):
    """ViewSet for managing alerts"""

    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter alerts by company and parameters"""
        user = self.request.user
        company_id = user.company_id

        # Filter by company through the related alert rule
        queryset = AlertNotification.objects.filter(rule__company_id=company_id)

        # Filter by status
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by severity
        severity = self.request.query_params.get("severity")
        if severity:
            queryset = queryset.filter(severity=severity)

        # Filter by alert rule
        rule_id = self.request.query_params.get("rule_id")
        if rule_id:
            queryset = queryset.filter(rule_id=rule_id)

        return queryset.order_by("-triggered_at")

    def get_serializer_class(self):
        """Use detailed serializer for retrieve action"""
        if self.action == "retrieve":
            return AlertDetailSerializer
        return AlertSerializer

    @extend_schema(
        tags=["Alerts"],
        summary="Acknowledge one or more alerts",
        request=AlertAcknowledgeSerializer,
        responses={
            200: {"type": "object", "properties": {"message": {"type": "string"}, "acknowledged_count": {"type": "integer"}}}
        },
    )
    @action(detail=False, methods=["post"])
    def acknowledge(self, request):
        """Acknowledge one or more alerts"""
        serializer = AlertAcknowledgeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        alert_ids = serializer.validated_data["alert_ids"]
        user_id = request.user.id

        # Acknowledge alerts
        acknowledged_count = 0
        for alert_id in alert_ids:
            try:
                alert = AlertNotification.objects.get(id=alert_id, rule__company_id=request.user.company_id)

                # Check permission
                if AlertPermissions.can_acknowledge_alert(request.user, alert):
                    alert.acknowledge(user_id)
                    acknowledged_count += 1

            except AlertNotification.DoesNotExist:
                continue

        return Response(
            {
                "message": f"Acknowledged {acknowledged_count} alerts",
                "acknowledged_count": acknowledged_count,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Alerts"],
        summary="Resolve one or more alerts",
        request=AlertResolveSerializer,
        responses={
            200: {"type": "object", "properties": {"message": {"type": "string"}, "resolved_count": {"type": "integer"}}}
        },
    )
    @action(detail=False, methods=["post"])
    def resolve(self, request):
        """Resolve one or more alerts"""
        serializer = AlertResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        alert_ids = serializer.validated_data["alert_ids"]
        user_id = request.user.id

        # Resolve alerts
        resolved_count = 0
        for alert_id in alert_ids:
            try:
                alert = AlertNotification.objects.get(id=alert_id, rule__company_id=request.user.company_id)

                # Check permission
                if AlertPermissions.can_acknowledge_alert(request.user, alert):
                    alert.resolve(user_id)
                    resolved_count += 1

            except AlertNotification.DoesNotExist:
                continue

        return Response(
            {
                "message": f"Resolved {resolved_count} alerts",
                "resolved_count": resolved_count,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Alerts"],
        summary="Mute a specific alert",
        responses={
            200: {"type": "object", "properties": {"message": {"type": "string"}, "status": {"type": "string"}}},
            403: {"type": "object", "properties": {"error": {"type": "string"}}},
        },
    )
    @action(detail=True, methods=["post"])
    def mute(self, request, pk=None):
        """Mute a specific alert"""
        alert = self.get_object()

        # Check permission
        if not AlertPermissions.can_acknowledge_alert(request.user, alert):
            return Response(
                {"error": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN,
            )

        alert.mute()

        return Response(
            {"message": "Alert muted", "status": alert.status},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Alerts"],
        summary="Get alert statistics",
        responses={200: AlertStatisticsSerializer},
    )
    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Get alert statistics for the company"""
        company_id = request.user.company_id

        # Get counts by filtering through rule
        alerts = AlertNotification.objects.filter(rule__company_id=company_id)

        total_alerts = alerts.count()
        active_alerts = alerts.filter(status="pending").count()
        acknowledged_alerts = alerts.filter(status="acknowledged").count()
        resolved_alerts = alerts.filter(status="resolved").count()
        # Muted alerts are tracked via is_read status, not a separate status value
        muted_alerts = 0  # Deprecated: muted is no longer a valid status

        # Get counts by severity
        critical_alerts = alerts.filter(severity="critical").count()
        high_alerts = alerts.filter(severity="high").count()
        medium_alerts = alerts.filter(severity="medium").count()
        low_alerts = alerts.filter(severity="low").count()

        # Get counts by metric type from rule
        alerts_by_type = dict(
            alerts.values("rule__metric_type").annotate(count=Count("id")).values_list("rule__metric_type", "count")
        )

        # Get counts by triggered user vs team
        user_alerts = alerts.filter(triggered_for_user_id__isnull=False).count()
        team_alerts = alerts.filter(triggered_for_team_id__isnull=False).count()
        alerts_by_target = {"user": user_alerts, "team": team_alerts}

        stats = {
            "total_alerts": total_alerts,
            "active_alerts": active_alerts,
            "acknowledged_alerts": acknowledged_alerts,
            "resolved_alerts": resolved_alerts,
            "muted_alerts": muted_alerts,
            "critical_alerts": critical_alerts,
            "high_alerts": high_alerts,
            "medium_alerts": medium_alerts,
            "low_alerts": low_alerts,
            "alerts_by_type": alerts_by_type,
            "alerts_by_target": alerts_by_target,
        }

        serializer = AlertStatisticsSerializer(stats)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(tags=["Notification Channels"], summary="List notification channels"),
    create=extend_schema(tags=["Notification Channels"], summary="Create notification channel"),
    retrieve=extend_schema(tags=["Notification Channels"], summary="Get notification channel details"),
    update=extend_schema(tags=["Notification Channels"], summary="Update notification channel"),
    partial_update=extend_schema(tags=["Notification Channels"], summary="Partially update notification channel"),
    destroy=extend_schema(tags=["Notification Channels"], summary="Delete notification channel"),
)
class NotificationChannelViewSet(ServerlessViewMixin, viewsets.ModelViewSet):
    """ViewSet for managing notification channels"""

    serializer_class = NotificationChannelSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter notification channels by company"""
        user = self.request.user
        company_id = user.company_id

        # Check permission
        if not AlertPermissions.can_manage_notification_channels(user, company_id):
            return NotificationChannel.objects.none()

        queryset = NotificationChannel.objects.filter(company_id=company_id)

        # Filter by channel type
        channel_type = self.request.query_params.get("type")
        if channel_type:
            queryset = queryset.filter(type=channel_type)

        # Filter by active status
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset.order_by("-created_at")

    def create(self, request, *args, **kwargs):
        """Create a new notification channel"""
        # Check permission
        if not AlertPermissions.can_manage_notification_channels(request.user, request.user.company_id):
            return Response(
                {"error": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Set company_id from authenticated user (company_id is read-only in serializer)
        serializer.save(company_id=request.user.company_id)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Notification Channels"],
        summary="Test notification channel",
        responses={202: {"type": "object", "properties": {"message": {"type": "string"}, "task_id": {"type": "string"}}}},
    )
    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        """Test a notification channel"""
        channel = self.get_object()

        # Get user ID from request
        user_id = str(request.user.id) if request.user and hasattr(request.user, "id") else None

        # Trigger test notification asynchronously with user_id
        task = send_test_notification.delay(str(channel.id), user_id=user_id)

        return Response(
            {
                "message": "Test notification triggered",
                "task_id": task.id,
            },
            status=status.HTTP_202_ACCEPTED,
        )


@extend_schema_view(
    list=extend_schema(tags=["Notifications"], summary="List notification logs"),
    retrieve=extend_schema(tags=["Notifications"], summary="Get notification log details"),
)
class NotificationLogViewSet(ServerlessViewMixin, viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing notification logs"""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter notification logs by company"""
        user = self.request.user
        company_id = user.company_id

        queryset = Notification.objects.filter(alert__rule__company_id=company_id)

        # Filter by status
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by channel
        channel_id = self.request.query_params.get("channel_id")
        if channel_id:
            queryset = queryset.filter(channel_id=channel_id)

        # Filter by alert
        alert_id = self.request.query_params.get("alert_id")
        if alert_id:
            queryset = queryset.filter(alert_id=alert_id)

        return queryset.order_by("-created_at")


@extend_schema(
    tags=["Password Reset"],
    summary="Send password reset email",
    description="Internal endpoint for auth-service to send password reset emails. No authentication required as this is for internal service communication.",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "user_email": {"type": "string", "format": "email"},
                "user_name": {"type": "string"},
                "reset_code": {"type": "string", "minLength": 6, "maxLength": 6},
                "frontend_url": {"type": "string", "format": "uri"},
            },
            "required": ["user_email", "user_name", "reset_code", "frontend_url"],
        }
    },
    responses={
        200: {"description": "Email sent successfully"},
        400: {"description": "Invalid request"},
        500: {"description": "Failed to send email"},
    },
)
@api_view(["POST"])
@permission_classes([])  # No authentication for internal service calls
def send_password_reset_email(request):
    """
    Send password reset email with 6-digit code
    Called by auth-service when user requests password reset
    """
    from django.conf import settings
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    # Validate required fields
    user_email = request.data.get("user_email")
    user_name = request.data.get("user_name")
    reset_code = request.data.get("reset_code")
    frontend_url = request.data.get("frontend_url")

    if not all([user_email, user_name, reset_code, frontend_url]):
        return Response(
            {"error": "Missing required fields: user_email, user_name, reset_code, frontend_url"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate reset code is 6 digits
    if not reset_code.isdigit() or len(reset_code) != 6:
        return Response({"error": "Reset code must be exactly 6 digits"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Get SendGrid API key
        sendgrid_api_key = getattr(settings, "SENDGRID_API_KEY", None)
        if not sendgrid_api_key:
            logger.error("SENDGRID_API_KEY not configured")
            return Response(
                {"error": "Email service not configured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Get sender email
        from_email = getattr(settings, "SENDGRID_FROM_EMAIL", settings.DEFAULT_FROM_EMAIL)

        # Prepare email content using template
        template = loader.get_template("alerts/password_reset_email.html")
        html_content = template.render(
            {
                "user_name": user_name,
                "reset_code": reset_code,
                "frontend_url": frontend_url,
                "user_email": user_email,
                "expiration_hours": 1,
            }
        )

        # Plain text version
        plain_content = f"""
Hello {user_name},

You requested to reset your password for your SyncScope account.

Your password reset code is: {reset_code}

To reset your password, visit: {frontend_url}/auth/verify-reset-code?email={user_email}

This code will expire in 1 hour.

If you didn't request this password reset, please ignore this email.

Best regards,
The SyncScope Team
        """.strip()

        # Send email
        message = Mail(
            from_email=from_email,
            to_emails=user_email,
            subject="Reset Your SyncScope Password",
            plain_text_content=plain_content,
            html_content=html_content,
        )

        sg = SendGridAPIClient(sendgrid_api_key)
        response = sg.send(message)

        if response.status_code in [200, 201, 202]:
            logger.info(f"Password reset email sent to {user_email}")
            return Response({"message": "Password reset email sent successfully"}, status=status.HTTP_200_OK)
        else:
            logger.error(f"SendGrid returned status {response.status_code}")
            return Response(
                {"error": "Failed to send email"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    except Exception as e:
        logger.error(f"Error sending password reset email: {str(e)}")
        return Response({"error": "Failed to send email"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
