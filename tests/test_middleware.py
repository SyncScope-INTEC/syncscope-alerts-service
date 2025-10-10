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
    RateLimitMiddleware,
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


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware"""

    def setup_method(self):
        """Setup for each test"""
        self.factory = RequestFactory()
        self.get_response = Mock(return_value=HttpResponse())
        self.middleware = RateLimitMiddleware(self.get_response)
        cache.clear()

    @override_settings(RATELIMIT_ENABLE=False)
    def test_disabled_rate_limiting(self):
        """Test rate limiting can be disabled via settings"""
        request = self.factory.get("/alerts/rules/")

        result = self.middleware.process_request(request)

        assert result is None

    def test_skips_admin_paths(self):
        """Test rate limiting skips admin paths"""
        request = self.factory.get("/admin/")

        result = self.middleware.process_request(request)

        assert result is None

    def test_skips_static_paths(self):
        """Test rate limiting skips static paths"""
        request = self.factory.get("/static/css/style.css")

        result = self.middleware.process_request(request)

        assert result is None

    def test_rate_limit_rules_endpoint(self):
        """Test rate limit for rules endpoint is 100 per hour"""
        request = self.factory.get("/alerts/rules/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        # First request should succeed
        result = self.middleware.process_request(request)
        assert result is None

        # Check rate limit info
        assert hasattr(request, "_rate_limit_info")
        assert request._rate_limit_info["limit"] == 100
        assert request._rate_limit_info["remaining"] == 99

    def test_rate_limit_notifications_send_endpoint(self):
        """Test rate limit for notifications/send endpoint is 50 per hour"""
        request = self.factory.get("/alerts/notifications/send")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        result = self.middleware.process_request(request)

        assert result is None
        assert request._rate_limit_info["limit"] == 50

    def test_rate_limit_other_alerts_endpoints(self):
        """Test rate limit for other alerts endpoints is 200 per hour"""
        request = self.factory.get("/alerts/some-other-endpoint/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        result = self.middleware.process_request(request)

        assert result is None
        assert request._rate_limit_info["limit"] == 200

    def test_rate_limit_exceeded(self):
        """Test rate limit returns 429 when exceeded"""
        request = self.factory.get("/alerts/rules/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        # Set cache to simulate limit exceeded
        cache_key = "ratelimit_alerts:192.168.1.1:/alerts/rules/"
        cache.set(cache_key, 100, 3600)

        result = self.middleware.process_request(request)

        assert isinstance(result, JsonResponse)
        assert result.status_code == 429
        data = result.json()
        assert "Rate limit exceeded" in data["error"]

    @patch("apps.alerts.middleware.cache.get")
    def test_cache_get_error_handling(self, mock_get):
        """Test cache get error is handled gracefully"""
        mock_get.side_effect = Exception("Cache error")
        request = self.factory.get("/alerts/rules/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        result = self.middleware.process_request(request)

        # Should not raise error, should return None
        assert result is None

    @patch("apps.alerts.middleware.cache.set")
    def test_cache_set_error_handling(self, mock_set):
        """Test cache set error is handled gracefully"""
        mock_set.side_effect = Exception("Cache error")
        request = self.factory.get("/alerts/rules/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        result = self.middleware.process_request(request)

        # Should not raise error, should return None
        assert result is None

    def test_process_response_adds_headers(self):
        """Test process_response adds rate limit headers"""
        request = self.factory.get("/alerts/rules/")
        request._rate_limit_info = {"limit": 100, "remaining": 99, "reset": 3600}
        response = HttpResponse()

        response = self.middleware.process_response(request, response)

        assert response["X-RateLimit-Limit"] == "100"
        assert response["X-RateLimit-Remaining"] == "99"
        assert response["X-RateLimit-Reset"] == "3600"

    def test_process_response_no_rate_limit_info(self):
        """Test process_response when no rate limit info"""
        request = self.factory.get("/admin/")
        response = HttpResponse()

        response = self.middleware.process_response(request, response)

        assert "X-RateLimit-Limit" not in response

    def test_get_client_ip_from_remote_addr(self):
        """Test get_client_ip from REMOTE_ADDR"""
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "10.0.0.1"

        ip = self.middleware.get_client_ip(request)

        assert ip == "10.0.0.1"

    def test_get_client_ip_from_x_forwarded_for(self):
        """Test get_client_ip from X-Forwarded-For"""
        request = self.factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.1, 198.51.100.1"
        request.META["REMOTE_ADDR"] = "10.0.0.1"

        ip = self.middleware.get_client_ip(request)

        assert ip == "203.0.113.1"

    def test_get_client_ip_default(self):
        """Test get_client_ip returns default when no IP available"""
        request = self.factory.get("/")

        ip = self.middleware.get_client_ip(request)

        assert ip == "127.0.0.1"


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

    @patch("apps.alerts.middleware.time.time")
    def test_stores_metrics_in_cache(self, mock_time):
        """Test middleware stores performance metrics in cache"""
        # Simulate request taking 0.5 seconds
        mock_time.side_effect = [0, 0.5]

        request = self.factory.get("/alerts/rules/")

        self.middleware(request)

        # Check metrics are stored in cache
        cache_key = "alerts_perf:alerts_rules"
        metrics = cache.get(cache_key)

        assert metrics is not None
        assert metrics["total_requests"] == 1
        assert metrics["total_time"] == 0.5
        assert metrics["avg_time"] == 0.5

    @patch("apps.alerts.middleware.time.time")
    def test_updates_existing_metrics(self, mock_time):
        """Test middleware updates existing performance metrics"""
        # First request
        mock_time.side_effect = [0, 0.5]
        request = self.factory.get("/alerts/rules/")
        self.middleware(request)

        # Second request
        mock_time.side_effect = [0, 1.0]
        self.middleware(request)

        # Check metrics are updated
        cache_key = "alerts_perf:alerts_rules"
        metrics = cache.get(cache_key)

        assert metrics["total_requests"] == 2
        assert metrics["total_time"] == 1.5
        assert metrics["avg_time"] == 0.75

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

        assert endpoint == "unknown"


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
