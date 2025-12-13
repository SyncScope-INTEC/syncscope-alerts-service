"""
Tests for Database Mixins
"""

from unittest.mock import Mock, patch

import pytest
from django.db import OperationalError
from django.http import JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from apps.alerts.db_mixins import (
    RetryableManager,
    RetryableModelMixin,
    ServerlessViewMixin,
)


class TestRetryableModelMixin:
    """Tests for RetryableModelMixin"""

    def test_has_save_method(self):
        """Test save method exists on mixin"""
        assert hasattr(RetryableModelMixin, "save")

    def test_has_delete_method(self):
        """Test delete method exists on mixin"""
        assert hasattr(RetryableModelMixin, "delete")

    def test_has_refresh_from_db_method(self):
        """Test refresh_from_db method exists on mixin"""
        assert hasattr(RetryableModelMixin, "refresh_from_db")

    def test_has_objects_get_method(self):
        """Test objects_get classmethod exists"""
        assert hasattr(RetryableModelMixin, "objects_get")

    def test_has_objects_filter_method(self):
        """Test objects_filter classmethod exists"""
        assert hasattr(RetryableModelMixin, "objects_filter")

    def test_has_objects_create_method(self):
        """Test objects_create classmethod exists"""
        assert hasattr(RetryableModelMixin, "objects_create")

    def test_has_objects_get_or_create_method(self):
        """Test objects_get_or_create classmethod exists"""
        assert hasattr(RetryableModelMixin, "objects_get_or_create")


class TestRetryableManager:
    """Tests for RetryableManager"""

    def test_manager_get_with_retry(self):
        """Test get method has retry decorator"""
        manager = RetryableManager()
        assert hasattr(manager, "get")
        assert hasattr(manager.get, "__wrapped__")

    def test_manager_filter_with_retry(self):
        """Test filter method has retry decorator"""
        manager = RetryableManager()
        assert hasattr(manager, "filter")
        assert hasattr(manager.filter, "__wrapped__")

    def test_manager_create_with_retry(self):
        """Test create method has retry decorator"""
        manager = RetryableManager()
        assert hasattr(manager, "create")
        assert hasattr(manager.create, "__wrapped__")

    def test_manager_get_or_create_with_retry(self):
        """Test get_or_create method has retry decorator"""
        manager = RetryableManager()
        assert hasattr(manager, "get_or_create")
        assert hasattr(manager.get_or_create, "__wrapped__")

    def test_manager_update_or_create_with_retry(self):
        """Test update_or_create method has retry decorator"""
        manager = RetryableManager()
        assert hasattr(manager, "update_or_create")
        assert hasattr(manager.update_or_create, "__wrapped__")

    def test_manager_bulk_create_with_retry(self):
        """Test bulk_create method has retry decorator"""
        manager = RetryableManager()
        assert hasattr(manager, "bulk_create")
        assert hasattr(manager.bulk_create, "__wrapped__")

    def test_manager_exists_with_retry(self):
        """Test exists method has retry decorator"""
        manager = RetryableManager()
        assert hasattr(manager, "exists")
        assert hasattr(manager.exists, "__wrapped__")

    def test_manager_count_with_retry(self):
        """Test count method has retry decorator"""
        manager = RetryableManager()
        assert hasattr(manager, "count")
        assert hasattr(manager.count, "__wrapped__")


class TestRetryableQuerySet:
    """Tests for RetryableQuerySet"""

    def test_queryset_exists(self):
        """Test RetryableQuerySet can be imported"""
        from config.database_retry import RetryableQuerySet

        assert RetryableQuerySet is not None


class TestServerlessViewMixin:
    """Tests for ServerlessViewMixin"""

    def test_has_dispatch_method(self):
        """Test dispatch method exists on mixin"""
        assert hasattr(ServerlessViewMixin, "dispatch")

    def test_has_handle_exception_method(self):
        """Test handle_exception method exists on mixin"""
        assert hasattr(ServerlessViewMixin, "handle_exception")

    def test_dispatch_method_signature(self):
        """Test dispatch method has correct signature"""
        import inspect

        sig = inspect.signature(ServerlessViewMixin.dispatch)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "request" in params
        assert "args" in params or "kwargs" in params

    def test_handle_exception_method_signature(self):
        """Test handle_exception method has correct signature"""
        import inspect

        sig = inspect.signature(ServerlessViewMixin.handle_exception)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "exc" in params

    @patch("config.database_retry.DatabaseHealthCheck.is_healthy")
    def test_dispatch_healthy_database(self, mock_is_healthy):
        """Test dispatch when database is healthy"""
        mock_is_healthy.return_value = True

        # Create a base class with dispatch method
        class BaseView:
            def dispatch(self, request, *args, **kwargs):
                return "success"

        # Create test view with mixin
        class TestView(ServerlessViewMixin, BaseView):
            pass

        view = TestView()
        request = Mock()
        result = view.dispatch(request)

        assert result == "success"
        mock_is_healthy.assert_called_once()

    @patch("config.database_retry.close_old_connections")
    @patch("config.database_retry.DatabaseHealthCheck.is_healthy")
    def test_dispatch_unhealthy_database_recovers(self, mock_is_healthy, mock_close):
        """Test dispatch when database is unhealthy but recovers"""
        # First call unhealthy, second call (after closing connections) healthy
        mock_is_healthy.side_effect = [False, True]

        # Create a base class with dispatch method
        class BaseView:
            def dispatch(self, request, *args, **kwargs):
                return "success"

        # Create test view with mixin
        class TestView(ServerlessViewMixin, BaseView):
            pass

        view = TestView()
        request = Mock()
        result = view.dispatch(request)

        assert result == "success"
        mock_close.assert_called_once()
        assert mock_is_healthy.call_count == 2

    @patch("config.database_retry.close_old_connections")
    @patch("config.database_retry.DatabaseHealthCheck.is_healthy")
    def test_dispatch_unhealthy_database_fails(self, mock_is_healthy, mock_close):
        """Test dispatch when database stays unhealthy"""
        # Both calls return unhealthy
        mock_is_healthy.return_value = False

        # Create a base class with dispatch method
        class BaseView:
            def dispatch(self, request, *args, **kwargs):
                return "success"

        # Create test view with mixin
        class TestView(ServerlessViewMixin, BaseView):
            pass

        view = TestView()
        request = Mock()
        result = view.dispatch(request)

        assert isinstance(result, JsonResponse)
        assert result.status_code == 503
        import json
        content = json.loads(result.content)
        assert "error" in content
        mock_close.assert_called_once()

    @patch("config.database_retry.is_retryable_error")
    @patch("config.database_retry.DatabaseHealthCheck.mark_unhealthy")
    def test_handle_exception_retryable(self, mock_mark_unhealthy, mock_is_retryable):
        """Test handle_exception with retryable error"""
        mock_is_retryable.return_value = True

        # Create a base class with handle_exception method
        class BaseView:
            def handle_exception(self, exc):
                return "handled"

        # Create test view with mixin
        class TestView(ServerlessViewMixin, BaseView):
            pass

        view = TestView()
        exc = OperationalError("Database error")
        result = view.handle_exception(exc)

        assert result == "handled"
        mock_is_retryable.assert_called_once_with(exc)
        mock_mark_unhealthy.assert_called_once()

    @patch("config.database_retry.is_retryable_error")
    @patch("config.database_retry.DatabaseHealthCheck.mark_unhealthy")
    def test_handle_exception_not_retryable(self, mock_mark_unhealthy, mock_is_retryable):
        """Test handle_exception with non-retryable error"""
        mock_is_retryable.return_value = False

        # Create a base class with handle_exception method
        class BaseView:
            def handle_exception(self, exc):
                return "handled"

        # Create test view with mixin
        class TestView(ServerlessViewMixin, BaseView):
            pass

        view = TestView()
        exc = ValueError("Non-database error")
        result = view.handle_exception(exc)

        assert result == "handled"
        mock_is_retryable.assert_called_once_with(exc)
        mock_mark_unhealthy.assert_not_called()
