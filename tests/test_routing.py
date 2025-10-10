"""
Tests for WebSocket Routing
"""

import pytest


class TestWebSocketRouting:
    """Tests for WebSocket URL routing"""

    @pytest.mark.skipif(True, reason="Channels not installed in test environment")
    def test_websocket_urlpatterns_exists(self):
        """Test that websocket_urlpatterns is defined"""
        from apps.alerts.routing import websocket_urlpatterns

        assert websocket_urlpatterns is not None
        assert isinstance(websocket_urlpatterns, list)
        assert len(websocket_urlpatterns) == 2

    @pytest.mark.skipif(True, reason="Channels not installed in test environment")
    def test_alert_consumer_route(self):
        """Test AlertConsumer route is configured"""
        from apps.alerts.routing import websocket_urlpatterns

        # Check first route is for general alerts
        route = websocket_urlpatterns[0]
        assert route.pattern._route == "ws/alerts/"

    @pytest.mark.skipif(True, reason="Channels not installed in test environment")
    def test_company_alert_consumer_route(self):
        """Test CompanyAlertConsumer route is configured"""
        from apps.alerts.routing import websocket_urlpatterns

        # Check second route is for company alerts
        route = websocket_urlpatterns[1]
        assert "company_id" in str(route.pattern._route)
