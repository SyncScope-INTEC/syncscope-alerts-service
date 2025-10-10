"""
Tests for Health Check Endpoints
"""

from unittest.mock import patch

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    """Fixture for API client"""
    return APIClient()


@pytest.mark.django_db
class TestHealthEndpoints:
    """Tests for health check endpoints"""

    def test_simple_health_check(self, api_client):
        """Test simple health check endpoint"""
        response = api_client.get("/health/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_detailed_health_check_success(self, api_client):
        """Test detailed health check when all services are healthy"""
        response = api_client.get("/health/detailed/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "checks" in data
        assert "database" in data["checks"]
        assert "cache" in data["checks"]

    @patch("apps.alerts.health.connection.cursor")
    def test_health_check_database_failure(self, mock_cursor, api_client):
        """Test health check when database fails"""
        mock_cursor.side_effect = Exception("Database connection failed")

        response = api_client.get("/health/detailed/")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["checks"]["database"]["status"] == "unhealthy"

    @patch("django.core.cache.cache.set")
    def test_health_check_cache_failure(self, mock_cache_set, api_client):
        """Test health check when cache fails"""
        mock_cache_set.side_effect = Exception("Cache connection failed")

        response = api_client.get("/health/detailed/")

        # Should still return 200 but status degraded
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["checks"]["cache"]["status"] == "unhealthy"

    @patch("django.core.cache.cache.get")
    @patch("django.core.cache.cache.set")
    def test_health_check_cache_read_write_mismatch(self, mock_set, mock_get, api_client):
        """Test health check when cache write/read fails"""
        mock_set.return_value = True
        mock_get.return_value = "wrong_value"

        response = api_client.get("/health/detailed/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["checks"]["cache"]["status"] == "unhealthy"

    def test_readiness_check_success(self, api_client):
        """Test readiness check when service is ready"""
        response = api_client.get("/health/ready/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["service"] == "alerts"

    @patch("apps.alerts.health.connection.cursor")
    def test_readiness_check_failure(self, mock_cursor, api_client):
        """Test readiness check when database is not ready"""
        mock_cursor.side_effect = Exception("Database not ready")

        response = api_client.get("/health/ready/")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert "error" in data

    def test_liveness_check(self, api_client):
        """Test liveness check endpoint"""
        response = api_client.get("/health/live/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert data["service"] == "alerts"

    def test_health_check_celery_configured(self, api_client):
        """Test health check reports Celery status"""
        response = api_client.get("/health/detailed/")

        data = response.json()
        assert "celery" in data["checks"]
        # Celery check should have a status
        assert "status" in data["checks"]["celery"]
