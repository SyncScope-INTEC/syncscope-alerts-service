"""
WebSocket URL routing for Alerts Service
"""

from django.urls import path

from .websocket_consumers import AlertConsumer, CompanyAlertConsumer

websocket_urlpatterns = [
    path("ws/alerts/", AlertConsumer.as_asgi()),
    path("ws/alerts/company/<uuid:company_id>/", CompanyAlertConsumer.as_asgi()),
]
