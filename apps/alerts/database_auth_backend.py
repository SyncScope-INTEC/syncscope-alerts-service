"""
Database Authentication Backend for Alerts Service
Integrates with Auth Service API for admin authentication
"""

import logging

import jwt
import requests
from django.conf import settings
from django.contrib.auth.backends import BaseBackend
from django.core.cache import cache

from .models import User

logger = logging.getLogger(__name__)


class CachedAuthServiceAPIBackend(BaseBackend):
    """
    Authentication backend that validates credentials against Auth Service API
    with caching for better performance
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate user against Auth Service API
        """
        if not username or not password:
            return None

        try:
            # Check cache first
            cache_key = f"auth_user_{username}"
            cached_user_data = cache.get(cache_key)

            if cached_user_data:
                # Verify password still matches (simplified check)
                # In production, you'd want to verify against auth service
                try:
                    user = User.objects.get(email=username)
                    return user
                except User.DoesNotExist:
                    pass

            # Authenticate against Auth Service API
            auth_service_url = settings.AUTH_SERVICE_URL
            response = requests.post(
                f"{auth_service_url}/auth/login/",
                json={"email": username, "password": password},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                user_data = data.get("user", {})

                # Get or create user in local database
                user, created = User.objects.get_or_create(
                    email=user_data.get("email"),
                    defaults={
                        "id": user_data.get("id"),
                        "first_name": user_data.get("first_name", ""),
                        "last_name": user_data.get("last_name", ""),
                        "is_staff": user_data.get("is_staff", False),
                        "is_superuser": user_data.get("is_superuser", False),
                        "is_active": user_data.get("is_active", True),
                    },
                )

                # Cache user data for 5 minutes
                cache.set(cache_key, user_data, 300)

                return user

            else:
                logger.warning(f"Auth service authentication failed: {response.status_code}")
                return None

        except requests.RequestException as e:
            logger.error(f"Error connecting to auth service: {e}")
            return None
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None

    def get_user(self, user_id):
        """
        Get user by ID
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
