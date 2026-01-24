"""
URL configuration for Alerts app
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AlertRuleViewSet,
    AlertViewSet,
    NotificationChannelViewSet,
    NotificationLogViewSet,
    send_company_invitation_email,
    send_password_reset_email,
    send_project_invitation_email,
    send_welcome_email,
)

router = DefaultRouter()
router.register(r"rules", AlertRuleViewSet, basename="alert-rules")
router.register(r"channels", NotificationChannelViewSet, basename="notification-channels")
router.register(r"notifications", NotificationLogViewSet, basename="notification-logs")
# Use empty string to avoid double prefix (/alerts/alerts/)
# This creates /alerts/ endpoints for the AlertViewSet
router.register(r"", AlertViewSet, basename="alerts")

urlpatterns = [
    # Internal service email endpoints (no authentication required) - MUST be before router
    path("send-password-reset-email/", send_password_reset_email, name="send_password_reset_email"),
    path("send-welcome-email/", send_welcome_email, name="send_welcome_email"),
    path("send-company-invitation-email/", send_company_invitation_email, name="send_company_invitation_email"),
    path("send-project-invitation-email/", send_project_invitation_email, name="send_project_invitation_email"),
    # Router URLs (with authentication)
    path("", include(router.urls)),
]
