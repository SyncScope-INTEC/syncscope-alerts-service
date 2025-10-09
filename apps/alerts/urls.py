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
)

router = DefaultRouter()
router.register(r"rules", AlertRuleViewSet, basename="alert-rules")
router.register(r"channels", NotificationChannelViewSet, basename="notification-channels")
router.register(r"notifications", NotificationLogViewSet, basename="notification-logs")
router.register(r"alerts", AlertViewSet, basename="alerts")

urlpatterns = [
    path("", include(router.urls)),
]
