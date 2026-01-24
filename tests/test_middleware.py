"""
Tests for Middleware
"""

import time
from unittest.mock import Mock, patch

import pytest
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory, override_settings


from apps.alerts.middleware import (
    AlertsPerformanceMiddleware,
    CacheControlMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
)


class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware"""

    def setup_method(self):
        """Setup for each test"""
        self.factory = RequestFactory()
        self.get_response = Mock(return_value=HttpResponse())
        self.middleware = SecurityHeadersMiddleware(self.get_response)

    def test_adds_security_headers(self):
        """Test middleware adds security headers to response"""
        request = self.factory.get("/alerts/rules/")

        response = self.middleware(request)

        assert response["X-Content-Type-Options"] == "nosniff"
        assert response["X-Frame-Options"] == "DENY"
        assert response["X-XSS-Protection"] == "1; mode=block"
        assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert response["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"

    def test_adds_hsts_for_https(self):
        """Test middleware adds HSTS header for secure requests"""
        request = self.factory.get("/alerts/rules/", secure=True)

        response = self.middleware(request)

        assert response["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"

    def test_no_hsts_for_http(self):
        """Test middleware does not add HSTS header for insecure requests"""
        request = self.factory.get("/alerts/rules/")

        response = self.middleware(request)

        assert "Strict-Transport-Security" not in response

    def test_adds_csp_for_alerts_endpoints(self):
        """Test middleware adds CSP header for alerts endpoints"""
        request = self.factory.get("/alerts/rules/")

        response = self.middleware(request)

        assert response["Content-Security-Policy"] == "default-src 'none'; script-src 'none'; object-src 'none'"

    def test_no_csp_for_non_alerts_endpoints(self):
        """Test middleware does not add CSP header for non-alerts endpoints"""
        request = self.factory.get("/admin/")

        response = self.middleware(request)

        assert "Content-Security-Policy" not in response


class TestRequestLoggingMiddleware:
    """Tests for RequestLoggingMiddleware"""

    def setup_method(self):
        """Setup for each test"""
        self.factory = RequestFactory()
        self.get_response = Mock(return_value=HttpResponse())
        self.middleware = RequestLoggingMiddleware(self.get_response)

    @patch("apps.alerts.middleware.logger")
    def test_logs_request(self, mock_logger):
        """Test middleware logs incoming requests"""
        request = self.factory.get("/alerts/rules/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        self.middleware(request)

        # Check request was logged
        mock_logger.info.assert_any_call("Alerts Request: GET /alerts/rules/ from 192.168.1.1")

    @patch("apps.alerts.middleware.logger")
    def test_logs_response(self, mock_logger):
        """Test middleware logs response with duration"""
        request = self.factory.get("/alerts/rules/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        self.middleware(request)

        # Check response was logged with duration
        calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("Alerts Response: 200" in call for call in calls)

    @patch("apps.alerts.middleware.logger")
    @patch("apps.alerts.middleware.time.time")
    def test_logs_slow_requests(self, mock_time, mock_logger):
        """Test middleware logs slow requests as warnings"""
        # Simulate slow request (6 seconds)
        mock_time.side_effect = [0, 6.0]

        request = self.factory.get("/alerts/rules/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        self.middleware(request)

        # Check slow request was logged as warning
        mock_logger.warning.assert_called_once()
        assert "Slow alerts request" in str(mock_logger.warning.call_args)
        assert "6.000s" in str(mock_logger.warning.call_args)

    @patch("apps.alerts.middleware.logger")
    @patch("apps.alerts.middleware.time.time")
    def test_does_not_log_fast_requests_as_slow(self, mock_time, mock_logger):
        """Test middleware does not log fast requests as slow"""
        # Simulate fast request (1 second)
        mock_time.side_effect = [0, 1.0]

        request = self.factory.get("/alerts/rules/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        self.middleware(request)

        # Check slow request warning was not logged
        mock_logger.warning.assert_not_called()

    def test_get_client_ip_from_x_forwarded_for(self):
        """Test get_client_ip from X-Forwarded-For"""
        request = self.factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.1, 198.51.100.1"

        ip = self.middleware.get_client_ip(request)

        assert ip == "203.0.113.1"

    def test_get_client_ip_default(self):
        """Test get_client_ip returns default when no IP available"""
        request = self.factory.get("/")

        ip = self.middleware.get_client_ip(request)

        assert ip == "127.0.0.1"


class TestAlertsPerformanceMiddleware:
    """Tests for AlertsPerformanceMiddleware"""

    def setup_method(self):
        """Setup for each test"""
        self.factory = RequestFactory()
        self.get_response = Mock(return_value=HttpResponse())
        self.middleware = AlertsPerformanceMiddleware(self.get_response)
        cache.clear()

    def test_tracks_performance_for_alerts_endpoints(self):
        """Test middleware tracks performance metrics for alerts endpoints"""
        request = self.factory.get("/alerts/rules/")

        response = self.middleware(request)

        # Check performance header is added
        assert "X-Response-Time" in response

    def test_does_not_track_non_alerts_endpoints(self):
        """Test middleware does not track non-alerts endpoints"""
        request = self.factory.get("/admin/")

        response = self.middleware(request)

        # Check performance header is not added
        assert "X-Response-Time" not in response

    def test_stores_metrics_in_cache(self):
        """Test middleware stores performance metrics in cache"""
        import time

        request = self.factory.get("/alerts/rules/")

        # Call middleware (will take some small amount of time)
        self.middleware(request)

        # Check metrics are stored in cache
        cache_key = "alerts_perf:alerts_rules"
        metrics = cache.get(cache_key)

        assert metrics is not None
        assert metrics["total_requests"] == 1
        assert metrics["total_time"] > 0  # Should have some time
        assert metrics["avg_time"] == metrics["total_time"]

    def test_updates_existing_metrics(self):
        """Test middleware updates existing performance metrics"""
        request = self.factory.get("/alerts/rules/")

        # First request
        self.middleware(request)

        # Get first metrics
        cache_key = "alerts_perf:alerts_rules"
        metrics1 = cache.get(cache_key)

        # Second request
        self.middleware(request)

        # Check metrics are updated
        metrics2 = cache.get(cache_key)

        assert metrics2["total_requests"] == 2
        assert metrics2["total_time"] > metrics1["total_time"]
        assert metrics2["avg_time"] == metrics2["total_time"] / 2

    @patch("apps.alerts.middleware.cache.get")
    @patch("apps.alerts.middleware.logger")
    def test_cache_error_handling(self, mock_logger, mock_get):
        """Test middleware handles cache errors gracefully"""
        mock_get.side_effect = Exception("Cache error")

        request = self.factory.get("/alerts/rules/")

        # Should not raise error
        response = self.middleware(request)

        # Should still add response time header
        assert "X-Response-Time" in response
        # Should log warning
        mock_logger.warning.assert_called_once()

    def test_get_endpoint_name_two_parts(self):
        """Test _get_endpoint_name with two path parts"""
        endpoint = self.middleware._get_endpoint_name("/alerts/rules/")

        assert endpoint == "alerts_rules"

    def test_get_endpoint_name_three_parts(self):
        """Test _get_endpoint_name with three or more path parts"""
        endpoint = self.middleware._get_endpoint_name("/alerts/rules/123/")

        assert endpoint == "alerts_rules"

    def test_get_endpoint_name_one_part(self):
        """Test _get_endpoint_name with one path part"""
        endpoint = self.middleware._get_endpoint_name("/alerts/")

        assert endpoint == "alerts"

    def test_get_endpoint_name_empty(self):
        """Test _get_endpoint_name with empty path"""
        endpoint = self.middleware._get_endpoint_name("/")

        # Empty path after stripping slashes returns empty string, not "unknown"
        assert endpoint == ""


class TestCacheControlMiddleware:
    """Tests for CacheControlMiddleware"""

    def setup_method(self):
        """Setup for each test"""
        self.factory = RequestFactory()
        self.get_response = Mock(return_value=HttpResponse())
        self.middleware = CacheControlMiddleware(self.get_response)

    def test_cache_get_rules_endpoint(self):
        """Test cache headers for GET request to rules endpoint"""
        request = self.factory.get("/alerts/rules/")

        response = self.middleware(request)

        assert response["Cache-Control"] == "max-age=60, private"

    def test_cache_get_notifications_endpoint(self):
        """Test cache headers for GET request to notifications endpoint"""
        request = self.factory.get("/alerts/notifications/")

        response = self.middleware(request)

        assert response["Cache-Control"] == "max-age=60, private"

    def test_cache_get_other_alerts_endpoint(self):
        """Test cache headers for GET request to other alerts endpoints"""
        request = self.factory.get("/alerts/other/")

        response = self.middleware(request)

        assert response["Cache-Control"] == "max-age=30, private"

    def test_no_cache_post_request(self):
        """Test no-cache headers for POST request"""
        request = self.factory.post("/alerts/rules/")

        response = self.middleware(request)

        assert response["Cache-Control"] == "no-cache, no-store, must-revalidate"
        assert response["Pragma"] == "no-cache"
        assert response["Expires"] == "0"

    def test_no_cache_put_request(self):
        """Test no-cache headers for PUT request"""
        request = self.factory.put("/alerts/rules/123/")

        response = self.middleware(request)

        assert response["Cache-Control"] == "no-cache, no-store, must-revalidate"
        assert response["Pragma"] == "no-cache"
        assert response["Expires"] == "0"

    def test_no_cache_delete_request(self):
        """Test no-cache headers for DELETE request"""
        request = self.factory.delete("/alerts/rules/123/")

        response = self.middleware(request)

        assert response["Cache-Control"] == "no-cache, no-store, must-revalidate"

    def test_no_headers_for_non_alerts_endpoints(self):
        """Test no cache headers added for non-alerts endpoints"""
        request = self.factory.get("/admin/")

        response = self.middleware(request)

        assert "Cache-Control" not in response
        assert "Pragma" not in response
        assert "Expires" not in response
