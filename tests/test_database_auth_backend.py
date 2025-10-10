"""
Tests for Database Authentication Backend
"""

import uuid
from unittest.mock import Mock, patch

import pytest
from django.core.cache import cache

from apps.alerts.database_auth_backend import CachedAuthServiceAPIBackend
from apps.alerts.models import User


@pytest.mark.django_db
class TestCachedAuthServiceAPIBackend:
    """Tests for CachedAuthServiceAPIBackend"""

    def setup_method(self):
        """Setup for each test"""
        self.backend = CachedAuthServiceAPIBackend()
        cache.clear()

    @patch("apps.alerts.database_auth_backend.requests.post")
    def test_authenticate_success(self, mock_post):
        """Test successful authentication"""
        user_id = uuid.uuid4()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user": {
                "id": str(user_id),
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "is_staff": True,
                "is_superuser": False,
                "is_active": True,
            },
            "token": "test-token",
        }
        mock_post.return_value = mock_response

        user = self.backend.authenticate(None, username="test@example.com", password="password123")

        assert user is not None
        assert user.email == "test@example.com"
        assert user.first_name == "Test"
        assert user.is_staff is True
        mock_post.assert_called_once()

    @patch("apps.alerts.database_auth_backend.requests.post")
    def test_authenticate_failure(self, mock_post):
        """Test failed authentication"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        user = self.backend.authenticate(None, username="test@example.com", password="wrong")

        assert user is None
        mock_post.assert_called_once()

    def test_authenticate_no_credentials(self):
        """Test authentication without credentials"""
        user = self.backend.authenticate(None, username=None, password=None)
        assert user is None

        user = self.backend.authenticate(None, username="test@example.com", password=None)
        assert user is None

        user = self.backend.authenticate(None, username=None, password="password")
        assert user is None

    @patch("apps.alerts.database_auth_backend.requests.post")
    def test_authenticate_with_cache(self, mock_post):
        """Test authentication with cached user data"""
        # Create a user first
        user = User.objects.create(
            id=uuid.uuid4(),
            email="cached@example.com",
            first_name="Cached",
            last_name="User",
            is_staff=False,
            is_active=True,
        )

        # Set cache
        cache_key = "auth_user_cached@example.com"
        cache.set(cache_key, {"email": "cached@example.com"}, 300)

        # Authenticate should use cache
        result = self.backend.authenticate(None, username="cached@example.com", password="password")

        assert result == user
        mock_post.assert_not_called()

    @patch("apps.alerts.database_auth_backend.requests.post")
    def test_authenticate_request_exception(self, mock_post):
        """Test authentication when request fails"""
        mock_post.side_effect = Exception("Connection error")

        user = self.backend.authenticate(None, username="test@example.com", password="password")

        assert user is None

    @patch("apps.alerts.database_auth_backend.requests.post")
    def test_authenticate_creates_user(self, mock_post):
        """Test that authentication creates new user"""
        user_id = uuid.uuid4()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user": {
                "id": str(user_id),
                "email": "newuser@example.com",
                "first_name": "New",
                "last_name": "User",
                "is_staff": False,
                "is_superuser": False,
                "is_active": True,
            }
        }
        mock_post.return_value = mock_response

        # Verify user doesn't exist
        assert not User.objects.filter(email="newuser@example.com").exists()

        user = self.backend.authenticate(None, username="newuser@example.com", password="password")

        # Verify user was created
        assert user is not None
        assert User.objects.filter(email="newuser@example.com").exists()

    @patch("apps.alerts.database_auth_backend.requests.post")
    def test_authenticate_updates_cache(self, mock_post):
        """Test that authentication updates cache"""
        user_id = uuid.uuid4()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user": {
                "id": str(user_id),
                "email": "test@example.com",
                "first_name": "Test",
            }
        }
        mock_post.return_value = mock_response

        cache_key = "auth_user_test@example.com"
        assert cache.get(cache_key) is None

        self.backend.authenticate(None, username="test@example.com", password="password")

        # Verify cache was set
        assert cache.get(cache_key) is not None

    def test_get_user_success(self):
        """Test getting user by ID"""
        user_id = uuid.uuid4()
        user = User.objects.create(
            id=user_id,
            email="test@example.com",
            first_name="Test",
        )

        result = self.backend.get_user(user_id)

        assert result == user

    def test_get_user_not_found(self):
        """Test getting non-existent user"""
        result = self.backend.get_user(uuid.uuid4())

        assert result is None
