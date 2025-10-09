"""
JWT Authentication for Alerts Service
Validates JWT tokens issued by the Auth Service
"""

import logging

from django.conf import settings
from django.contrib.auth.models import AnonymousUser

import jwt
import requests
from rest_framework import authentication, exceptions

logger = logging.getLogger(__name__)


class AlertsUser:
    """
    Simple user class for alerts service
    Contains user information extracted from JWT token
    """

    def __init__(self, user_data):
        self.id = user_data.get("user_id")
        self.pk = user_data.get("user_id")  # Add pk for django compatibility
        self.user_id = user_data.get("user_id")
        self.email = user_data.get("email", "")
        self.username = user_data.get("username", "")
        self.first_name = user_data.get("first_name", "")
        self.last_name = user_data.get("last_name", "")
        self.role = user_data.get("role", "developer")
        self.company_id = user_data.get("company_id")
        self.is_authenticated = True
        self.is_anonymous = False
        self.is_staff = user_data.get("is_staff", False)
        self.is_superuser = user_data.get("is_superuser", False)
        self._user_data = user_data

    def __str__(self):
        if self.first_name and self.last_name and self.email:
            return f"{self.first_name} {self.last_name} ({self.email})"
        return f"AlertsUser({self.user_id})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def is_admin(self):
        return self.role == "admin"

    def is_supervisor(self):
        return self.role in ["admin", "supervisor"]

    def has_perm(self, perm, obj=None):
        """Check if user has permission."""
        return self.is_staff or self.is_superuser

    def has_perms(self, perm_list, obj=None):
        """Check if user has multiple permissions."""
        return all(self.has_perm(perm, obj) for perm in perm_list)

    def has_module_perms(self, package_name):
        """Check if user has permissions for a module."""
        return self.is_staff or self.is_superuser

    def get_user_data(self):
        """Get original user data from token."""
        return self._user_data


class JWTAuthentication(authentication.BaseAuthentication):
    """
    JWT Authentication class for Alerts Service
    """

    def authenticate(self, request):
        """
        Authenticate the request and return a two-tuple of (user, token).
        """
        auth_header = request.META.get("HTTP_AUTHORIZATION")

        if not auth_header:
            return None

        try:
            # Extract token from "Bearer <token>" format
            token_type, token = auth_header.split(" ", 1)
            if token_type.lower() != "bearer":
                return None

        except ValueError:
            return None

        return self.authenticate_credentials(token)

    def authenticate_credentials(self, token):
        """
        Authenticate the JWT token and return user information.
        """
        try:
            # Decode JWT token - use same SECRET_KEY as auth service
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

            # Create user object from token payload
            user = AlertsUser(payload)

            return (user, token)

        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            raise exceptions.AuthenticationFailed("Invalid token")
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise exceptions.AuthenticationFailed("Authentication failed")

    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the `WWW-Authenticate`
        header in a `401 Unauthenticated` response.
        """
        return "Bearer"


class ServiceAuthentication:
    """
    Authentication helper for inter-service communication
    """

    @staticmethod
    def verify_service_token(token):
        """
        Verify a service-to-service authentication token
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

            # Check if it's a service token
            if payload.get("token_type") != "service":
                return False

            # Verify service name
            service_name = payload.get("service_name")
            if service_name not in ["monitoring", "management", "analytics", "auth"]:
                return False

            return True

        except jwt.InvalidTokenError:
            return False

    @staticmethod
    def create_service_token(service_name="alerts"):
        """
        Create a service authentication token for outgoing requests
        """
        import time

        payload = {
            "token_type": "service",
            "service_name": service_name,
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,  # 1 hour expiration
            "iss": "syncscope-alerts",
        }

        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


class AlertPermissions:
    """
    Helper class to check user permissions for alert operations
    """

    @staticmethod
    def can_manage_alert_rules(user, company_id):
        """
        Check if user can manage alert rules for a company
        """
        if user.is_admin():
            return True

        # User can manage rules for their own company
        return str(user.company_id) == str(company_id)

    @staticmethod
    def can_view_alerts(user, company_id):
        """
        Check if user can view alerts for a company
        """
        if user.is_admin():
            return True

        # User can view alerts for their own company
        return str(user.company_id) == str(company_id)

    @staticmethod
    def can_acknowledge_alert(user, alert):
        """
        Check if user can acknowledge an alert
        """
        if user.is_admin():
            return True

        # User can acknowledge alerts in their company
        return str(user.company_id) == str(alert.company_id)

    @staticmethod
    def can_manage_notification_channels(user, company_id):
        """
        Check if user can manage notification channels for a company
        """
        if user.is_admin():
            return True

        if user.is_supervisor():
            return str(user.company_id) == str(company_id)

        return False


def get_auth_headers(service_name=None):
    """
    Get authentication headers for outgoing requests to other services
    """
    service_token = ServiceAuthentication.create_service_token()

    # Different services may use different authentication methods
    if service_name == "monitoring":
        return {
            "X-Service-Token": service_token,
            "Content-Type": "application/json",
        }

    # Other services use standard Authorization header
    return {
        "Authorization": f"Bearer {service_token}",
        "Content-Type": "application/json",
    }
