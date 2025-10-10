"""
Tests for Authentication Module
"""

import time
import uuid
from unittest.mock import Mock, patch

import jwt
import pytest
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from apps.alerts.authentication import (
    AlertPermissions,
    AlertsUser,
    JWTAuthentication,
    ServiceAuthentication,
    get_auth_headers,
)


class TestAlertsUser:
    """Tests for AlertsUser class"""

    def test_init_with_complete_data(self):
        """Test AlertsUser initialization with complete data"""
        user_data = {
            "user_id": "123e4567-e89b-12d3-a456-426614174000",
            "email": "test@example.com",
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "role": "admin",
            "company_id": "987e6543-e21b-12d3-a456-426614174000",
            "is_staff": True,
            "is_superuser": False,
        }

        user = AlertsUser(user_data)

        assert user.id == "123e4567-e89b-12d3-a456-426614174000"
        assert user.pk == "123e4567-e89b-12d3-a456-426614174000"
        assert user.user_id == "123e4567-e89b-12d3-a456-426614174000"
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.role == "admin"
        assert user.company_id == "987e6543-e21b-12d3-a456-426614174000"
        assert user.is_authenticated is True
        assert user.is_anonymous is False
        assert user.is_staff is True
        assert user.is_superuser is False

    def test_init_with_minimal_data(self):
        """Test AlertsUser initialization with minimal data"""
        user_data = {"user_id": "123", "company_id": "456"}

        user = AlertsUser(user_data)

        assert user.id == "123"
        assert user.email == ""
        assert user.username == ""
        assert user.first_name == ""
        assert user.last_name == ""
        assert user.role == "developer"
        assert user.is_staff is False
        assert user.is_superuser is False

    def test_str_with_full_name_and_email(self):
        """Test __str__ method with complete name and email"""
        user_data = {
            "user_id": "123",
            "email": "john@example.com",
            "first_name": "John",
            "last_name": "Doe",
        }

        user = AlertsUser(user_data)
        assert str(user) == "John Doe (john@example.com)"

    def test_str_with_only_user_id(self):
        """Test __str__ method with only user_id"""
        user_data = {"user_id": "123"}

        user = AlertsUser(user_data)
        assert str(user) == "AlertsUser(123)"

    def test_str_with_partial_name(self):
        """Test __str__ method with partial name (missing email or name parts)"""
        user_data = {
            "user_id": "123",
            "first_name": "John",
            # Missing last_name and email
        }

        user = AlertsUser(user_data)
        assert str(user) == "AlertsUser(123)"

    def test_full_name_property(self):
        """Test full_name property"""
        user_data = {"user_id": "123", "first_name": "Jane", "last_name": "Smith"}

        user = AlertsUser(user_data)
        assert user.full_name == "Jane Smith"

    def test_full_name_with_missing_parts(self):
        """Test full_name property with missing parts"""
        user_data = {"user_id": "123", "first_name": "Jane"}

        user = AlertsUser(user_data)
        assert user.full_name == "Jane"

    def test_is_admin_true(self):
        """Test is_admin method returns True for admin role"""
        user_data = {"user_id": "123", "role": "admin"}

        user = AlertsUser(user_data)
        assert user.is_admin() is True

    def test_is_admin_false(self):
        """Test is_admin method returns False for non-admin role"""
        user_data = {"user_id": "123", "role": "developer"}

        user = AlertsUser(user_data)
        assert user.is_admin() is False

    def test_is_supervisor_admin(self):
        """Test is_supervisor returns True for admin"""
        user_data = {"user_id": "123", "role": "admin"}

        user = AlertsUser(user_data)
        assert user.is_supervisor() is True

    def test_is_supervisor_supervisor(self):
        """Test is_supervisor returns True for supervisor"""
        user_data = {"user_id": "123", "role": "supervisor"}

        user = AlertsUser(user_data)
        assert user.is_supervisor() is True

    def test_is_supervisor_developer(self):
        """Test is_supervisor returns False for developer"""
        user_data = {"user_id": "123", "role": "developer"}

        user = AlertsUser(user_data)
        assert user.is_supervisor() is False

    def test_has_perm_staff(self):
        """Test has_perm returns True for staff user"""
        user_data = {"user_id": "123", "is_staff": True}

        user = AlertsUser(user_data)
        assert user.has_perm("any_permission") is True

    def test_has_perm_superuser(self):
        """Test has_perm returns True for superuser"""
        user_data = {"user_id": "123", "is_superuser": True}

        user = AlertsUser(user_data)
        assert user.has_perm("any_permission") is True

    def test_has_perm_regular_user(self):
        """Test has_perm returns False for regular user"""
        user_data = {"user_id": "123"}

        user = AlertsUser(user_data)
        assert user.has_perm("any_permission") is False

    def test_has_perms_all_true(self):
        """Test has_perms returns True when user has all permissions"""
        user_data = {"user_id": "123", "is_staff": True}

        user = AlertsUser(user_data)
        assert user.has_perms(["perm1", "perm2", "perm3"]) is True

    def test_has_perms_any_false(self):
        """Test has_perms returns False when user lacks permissions"""
        user_data = {"user_id": "123"}

        user = AlertsUser(user_data)
        assert user.has_perms(["perm1", "perm2"]) is False

    def test_has_module_perms_staff(self):
        """Test has_module_perms returns True for staff"""
        user_data = {"user_id": "123", "is_staff": True}

        user = AlertsUser(user_data)
        assert user.has_module_perms("alerts") is True

    def test_has_module_perms_regular(self):
        """Test has_module_perms returns False for regular user"""
        user_data = {"user_id": "123"}

        user = AlertsUser(user_data)
        assert user.has_module_perms("alerts") is False

    def test_get_user_data(self):
        """Test get_user_data returns original data"""
        user_data = {
            "user_id": "123",
            "email": "test@example.com",
            "custom_field": "custom_value",
        }

        user = AlertsUser(user_data)
        assert user.get_user_data() == user_data


class TestJWTAuthentication:
    """Tests for JWTAuthentication class"""

    def setup_method(self):
        """Setup for each test"""
        self.auth = JWTAuthentication()
        self.factory = APIRequestFactory()

    def test_authenticate_no_auth_header(self):
        """Test authentication with no Authorization header"""
        request = self.factory.get("/")

        result = self.auth.authenticate(request)

        assert result is None

    def test_authenticate_invalid_header_format(self):
        """Test authentication with invalid header format (no space)"""
        request = self.factory.get("/", HTTP_AUTHORIZATION="InvalidToken")

        result = self.auth.authenticate(request)

        assert result is None

    def test_authenticate_non_bearer_token(self):
        """Test authentication with non-Bearer token type"""
        request = self.factory.get("/", HTTP_AUTHORIZATION="Basic sometoken")

        result = self.auth.authenticate(request)

        assert result is None

    def test_authenticate_valid_bearer_token(self):
        """Test authentication with valid Bearer token"""
        # Create a valid JWT token
        payload = {
            "user_id": "123",
            "email": "test@example.com",
            "company_id": "456",
            "role": "developer",
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        request = self.factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        result = self.auth.authenticate(request)

        assert result is not None
        user, returned_token = result
        assert isinstance(user, AlertsUser)
        assert user.id == "123"
        assert user.email == "test@example.com"
        assert returned_token == token

    def test_authenticate_credentials_valid_token(self):
        """Test authenticate_credentials with valid token"""
        payload = {
            "user_id": "999",
            "email": "valid@example.com",
            "first_name": "Valid",
            "last_name": "User",
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        result = self.auth.authenticate_credentials(token)

        user, returned_token = result
        assert user.id == "999"
        assert user.email == "valid@example.com"
        assert returned_token == token

    def test_authenticate_credentials_invalid_token(self):
        """Test authenticate_credentials with invalid JWT token"""
        invalid_token = "invalid.jwt.token"

        with pytest.raises(AuthenticationFailed) as exc_info:
            self.auth.authenticate_credentials(invalid_token)

        assert "Invalid token" in str(exc_info.value)

    def test_authenticate_credentials_expired_token(self):
        """Test authenticate_credentials with expired token"""
        payload = {
            "user_id": "123",
            "exp": int(time.time()) - 3600,  # Expired 1 hour ago
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        with pytest.raises(AuthenticationFailed) as exc_info:
            self.auth.authenticate_credentials(token)

        assert "Invalid token" in str(exc_info.value)

    def test_authenticate_credentials_wrong_secret(self):
        """Test authenticate_credentials with token signed with wrong secret"""
        payload = {"user_id": "123"}
        token = jwt.encode(payload, "wrong_secret", algorithm="HS256")

        with pytest.raises(AuthenticationFailed) as exc_info:
            self.auth.authenticate_credentials(token)

        assert "Invalid token" in str(exc_info.value)

    def test_authenticate_header(self):
        """Test authenticate_header returns Bearer"""
        request = self.factory.get("/")

        result = self.auth.authenticate_header(request)

        assert result == "Bearer"


class TestServiceAuthentication:
    """Tests for ServiceAuthentication class"""

    def test_verify_service_token_valid(self):
        """Test verify_service_token with valid service token"""
        payload = {
            "token_type": "service",
            "service_name": "monitoring",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        result = ServiceAuthentication.verify_service_token(token)

        assert result is True

    def test_verify_service_token_invalid_type(self):
        """Test verify_service_token with non-service token type"""
        payload = {
            "token_type": "user",
            "service_name": "monitoring",
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        result = ServiceAuthentication.verify_service_token(token)

        assert result is False

    def test_verify_service_token_invalid_service_name(self):
        """Test verify_service_token with invalid service name"""
        payload = {
            "token_type": "service",
            "service_name": "invalid_service",
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        result = ServiceAuthentication.verify_service_token(token)

        assert result is False

    def test_verify_service_token_valid_service_names(self):
        """Test verify_service_token with all valid service names"""
        valid_services = ["monitoring", "management", "analytics", "auth"]

        for service in valid_services:
            payload = {
                "token_type": "service",
                "service_name": service,
            }
            token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

            result = ServiceAuthentication.verify_service_token(token)

            assert result is True, f"Failed for service: {service}"

    def test_verify_service_token_invalid_jwt(self):
        """Test verify_service_token with invalid JWT"""
        result = ServiceAuthentication.verify_service_token("invalid.jwt.token")

        assert result is False

    def test_create_service_token_default(self):
        """Test create_service_token with default service name"""
        token = ServiceAuthentication.create_service_token()

        # Decode and verify token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

        assert payload["token_type"] == "service"
        assert payload["service_name"] == "alerts"
        assert payload["iss"] == "syncscope-alerts"
        assert "iat" in payload
        assert "exp" in payload

    def test_create_service_token_custom_service(self):
        """Test create_service_token with custom service name"""
        token = ServiceAuthentication.create_service_token(service_name="monitoring")

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

        assert payload["service_name"] == "monitoring"

    def test_create_service_token_expiration(self):
        """Test create_service_token has 1 hour expiration"""
        token = ServiceAuthentication.create_service_token()

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

        # Check expiration is approximately 1 hour from now
        expected_exp = int(time.time()) + 3600
        assert abs(payload["exp"] - expected_exp) < 5  # Allow 5 second tolerance


class TestAlertPermissions:
    """Tests for AlertPermissions class"""

    def test_can_manage_alert_rules_admin(self):
        """Test admin can manage alert rules for any company"""
        user_data = {"user_id": "123", "role": "admin", "company_id": "company1"}
        user = AlertsUser(user_data)

        result = AlertPermissions.can_manage_alert_rules(user, "company2")

        assert result is True

    def test_can_manage_alert_rules_same_company(self):
        """Test user can manage alert rules for their own company"""
        user_data = {"user_id": "123", "role": "developer", "company_id": "company1"}
        user = AlertsUser(user_data)

        result = AlertPermissions.can_manage_alert_rules(user, "company1")

        assert result is True

    def test_can_manage_alert_rules_different_company(self):
        """Test user cannot manage alert rules for different company"""
        user_data = {"user_id": "123", "role": "developer", "company_id": "company1"}
        user = AlertsUser(user_data)

        result = AlertPermissions.can_manage_alert_rules(user, "company2")

        assert result is False

    def test_can_view_alerts_admin(self):
        """Test admin can view alerts for any company"""
        user_data = {"user_id": "123", "role": "admin", "company_id": "company1"}
        user = AlertsUser(user_data)

        result = AlertPermissions.can_view_alerts(user, "company2")

        assert result is True

    def test_can_view_alerts_same_company(self):
        """Test user can view alerts for their own company"""
        user_data = {"user_id": "123", "role": "developer", "company_id": "company1"}
        user = AlertsUser(user_data)

        result = AlertPermissions.can_view_alerts(user, "company1")

        assert result is True

    def test_can_view_alerts_different_company(self):
        """Test user cannot view alerts for different company"""
        user_data = {"user_id": "123", "role": "developer", "company_id": "company1"}
        user = AlertsUser(user_data)

        result = AlertPermissions.can_view_alerts(user, "company2")

        assert result is False

    def test_can_acknowledge_alert_admin(self):
        """Test admin can acknowledge any alert"""
        user_data = {"user_id": "123", "role": "admin", "company_id": "company1"}
        user = AlertsUser(user_data)

        alert = Mock()
        alert.company_id = "company2"

        result = AlertPermissions.can_acknowledge_alert(user, alert)

        assert result is True

    def test_can_acknowledge_alert_same_company(self):
        """Test user can acknowledge alert in their company"""
        user_data = {"user_id": "123", "role": "developer", "company_id": "company1"}
        user = AlertsUser(user_data)

        alert = Mock()
        alert.company_id = "company1"

        result = AlertPermissions.can_acknowledge_alert(user, alert)

        assert result is True

    def test_can_acknowledge_alert_different_company(self):
        """Test user cannot acknowledge alert in different company"""
        user_data = {"user_id": "123", "role": "developer", "company_id": "company1"}
        user = AlertsUser(user_data)

        alert = Mock()
        alert.company_id = "company2"

        result = AlertPermissions.can_acknowledge_alert(user, alert)

        assert result is False

    def test_can_manage_notification_channels_admin(self):
        """Test admin can manage notification channels for any company"""
        user_data = {"user_id": "123", "role": "admin", "company_id": "company1"}
        user = AlertsUser(user_data)

        result = AlertPermissions.can_manage_notification_channels(user, "company2")

        assert result is True

    def test_can_manage_notification_channels_supervisor_same_company(self):
        """Test supervisor can manage channels for their own company"""
        user_data = {"user_id": "123", "role": "supervisor", "company_id": "company1"}
        user = AlertsUser(user_data)

        result = AlertPermissions.can_manage_notification_channels(user, "company1")

        assert result is True

    def test_can_manage_notification_channels_supervisor_different_company(self):
        """Test supervisor cannot manage channels for different company"""
        user_data = {"user_id": "123", "role": "supervisor", "company_id": "company1"}
        user = AlertsUser(user_data)

        result = AlertPermissions.can_manage_notification_channels(user, "company2")

        assert result is False

    def test_can_manage_notification_channels_developer(self):
        """Test developer cannot manage notification channels"""
        user_data = {"user_id": "123", "role": "developer", "company_id": "company1"}
        user = AlertsUser(user_data)

        result = AlertPermissions.can_manage_notification_channels(user, "company1")

        assert result is False


class TestGetAuthHeaders:
    """Tests for get_auth_headers function"""

    @patch("apps.alerts.authentication.ServiceAuthentication.create_service_token")
    def test_get_auth_headers_monitoring_service(self, mock_create_token):
        """Test get_auth_headers for monitoring service uses X-Service-Token"""
        mock_create_token.return_value = "test-token-123"

        headers = get_auth_headers(service_name="monitoring")

        assert headers["X-Service-Token"] == "test-token-123"
        assert headers["Content-Type"] == "application/json"
        assert "Authorization" not in headers

    @patch("apps.alerts.authentication.ServiceAuthentication.create_service_token")
    def test_get_auth_headers_other_service(self, mock_create_token):
        """Test get_auth_headers for other services uses Authorization Bearer"""
        mock_create_token.return_value = "test-token-456"

        headers = get_auth_headers(service_name="analytics")

        assert headers["Authorization"] == "Bearer test-token-456"
        assert headers["Content-Type"] == "application/json"
        assert "X-Service-Token" not in headers

    @patch("apps.alerts.authentication.ServiceAuthentication.create_service_token")
    def test_get_auth_headers_no_service_name(self, mock_create_token):
        """Test get_auth_headers with no service name uses Authorization Bearer"""
        mock_create_token.return_value = "test-token-789"

        headers = get_auth_headers()

        assert headers["Authorization"] == "Bearer test-token-789"
        assert headers["Content-Type"] == "application/json"
        assert "X-Service-Token" not in headers
