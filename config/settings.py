"""
Django settings for syncscope-alerts-service project.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# Generate a default secret key for development
import secrets

DEFAULT_SECRET_KEY = secrets.token_urlsafe(50)

SECRET_KEY = config("SECRET_KEY", default=DEFAULT_SECRET_KEY)

DEBUG = config("DEBUG", default=True, cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")

# Add Railway health check domain
if "RAILWAY_ENVIRONMENT" in os.environ:
    ALLOWED_HOSTS.extend(["healthcheck.railway.app", "*.railway.app", "*.up.railway.app"])

    # Add the specific Railway service domain if provided
    railway_public_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if railway_public_domain:
        ALLOWED_HOSTS.append(railway_public_domain)

DJANGO_APPS = [
    "daphne",  # ASGI server for WebSocket support (must be first)
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
    "django_extensions",
    "drf_spectacular",
    "channels",  # WebSocket support
    "django_celery_beat",  # Celery periodic tasks
    "django_celery_results",  # Celery result backend
]

LOCAL_APPS = [
    "apps.alerts",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "apps.alerts.middleware.SecurityHeadersMiddleware",
    "apps.alerts.middleware.RequestLoggingMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.alerts.middleware.RateLimitMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database
DATABASE_URL = config("DATABASE_URL", default=None)
USE_SQLITE = config("USE_SQLITE", default=False, cast=bool)

if USE_SQLITE:
    # Use SQLite for local development
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
elif DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME", default="syncscope_alerts"),
            "USER": config("DB_USER", default="postgres"),
            "PASSWORD": config("DB_PASSWORD", default=""),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432", cast=int),
        }
    }

# Database connection configuration for PostgreSQL only
if not USE_SQLITE:
    db_options = {
        "connect_timeout": 10,
        "application_name": "syncscope-alerts-serverless",
    }

    # Schema configuration
    # This alerts service works primarily with the alerts schema
    # But also needs access to other schemas for relationships
    use_alerts_schema = (
        "test" not in config("DB_NAME", default="").lower() and "test" not in os.environ.get("DATABASE_URL", "").lower()
    )

    if use_alerts_schema:
        # Set search path to include all schemas with alerts as priority
        db_options["options"] = (
            "-c search_path=alerts,auth,management,monitoring,analytics,audit,public -c statement_timeout=30000"
        )
    else:
        db_options["options"] = "-c statement_timeout=30000"

    DATABASES["default"].update(
        {
            "CONN_MAX_AGE": 0,  # Don't persist connections in serverless
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": db_options,
        }
    )

# Custom User model for UUID compatibility
AUTH_USER_MODEL = "alerts.User"

# Authentication backends
AUTHENTICATION_BACKENDS = [
    "apps.alerts.database_auth_backend.CachedAuthServiceAPIBackend",
]

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# WhiteNoise configuration for static files serving
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Ensure Django can find static files during collectstatic
STATICFILES_DIRS = [
    BASE_DIR / "apps" / "alerts" / "static",
]

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# REST Framework configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("apps.alerts.authentication.JWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# CORS settings
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="http://localhost:3000,http://127.0.0.1:3000").split(",")

CORS_ALLOW_CREDENTIALS = True

# CSRF settings
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="http://localhost:3000,http://127.0.0.1:3000").split(",")

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

# Proxy configuration for Railway
if "RAILWAY_ENVIRONMENT" in os.environ:
    USE_TZ = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = False  # Railway handles this

    # Suppress migration warnings on Railway since tables already exist with correct schema
    SILENCED_SYSTEM_CHECKS = ["models.W042"]

# Session security
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True

# Rate limiting
RATELIMIT_ENABLE = config("RATELIMIT_ENABLE", default=True, cast=bool)

# Logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": "django.log",
            "formatter": "verbose",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["file", "console"],
            "level": "INFO",
            "propagate": True,
        },
        "apps.alerts": {
            "handlers": ["file", "console"],
            "level": "INFO",
            "propagate": True,
        },
    },
}

# Cache configuration (Redis)
REDIS_URL = config("REDIS_URL", default=None)

if REDIS_URL:
    # Use hosted Redis instance
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
            "KEY_PREFIX": "syncscope_alerts",
            "TIMEOUT": config("CACHE_TIMEOUT", default=300, cast=int),
        }
    }
else:
    # Fallback Redis configuration for local development
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": f"redis://{config('REDIS_HOST', default='localhost')}:{config('REDIS_PORT', default='6379', cast=int)}/{config('REDIS_DB', default='2', cast=int)}",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
            "KEY_PREFIX": "syncscope_alerts",
            "TIMEOUT": config("CACHE_TIMEOUT", default=300, cast=int),
        }
    }

# Celery Configuration
CELERY_BROKER_URL = config(
    "CELERY_BROKER_URL",
    default=(
        REDIS_URL
        if REDIS_URL
        else f"redis://{config('REDIS_HOST', default='localhost')}:{config('REDIS_PORT', default='6379', cast=int)}/{config('REDIS_DB', default='2', cast=int)}"
    ),
)
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default="django-db")
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes

# Channels configuration for WebSocket support
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": (
                [REDIS_URL]
                if REDIS_URL
                else [(config("REDIS_HOST", default="localhost"), config("REDIS_PORT", default="6379", cast=int))]
            ),
        },
    },
}

# Service URLs for HTTP integration
AUTH_SERVICE_URL = config("AUTH_SERVICE_URL", default="https://syncscope-auth-service-dev.up.railway.app")
MONITORING_SERVICE_URL = config("MONITORING_SERVICE_URL", default="http://localhost:8001")
MANAGEMENT_SERVICE_URL = config("MANAGEMENT_SERVICE_URL", default="http://localhost:8002")
ANALYTICS_SERVICE_URL = config("ANALYTICS_SERVICE_URL", default="http://localhost:8000")

# Alerts Configuration
ALERT_EVALUATION_INTERVAL = config("ALERT_EVALUATION_INTERVAL", default=60, cast=int)  # seconds
MAX_RETRY_ATTEMPTS = config("MAX_RETRY_ATTEMPTS", default=3, cast=int)
NOTIFICATION_RETRY_DELAY = config("NOTIFICATION_RETRY_DELAY", default=300, cast=int)  # seconds
ALERT_RETENTION_DAYS = config("ALERT_RETENTION_DAYS", default=90, cast=int)

# Email Configuration for notifications
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@syncscope.com")

# API Documentation (Swagger/OpenAPI)
SPECTACULAR_SETTINGS = {
    "TITLE": "SyncScope Alerts Service API",
    "DESCRIPTION": "Real-time alerting and notification service for SyncScope platform",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/alerts/",
    # Security scheme configuration
    "SECURITY": [{"Bearer": []}],
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "Bearer": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Enter your Bearer token in the format: Bearer <token>",
            }
        }
    },
    "SERVERS": [
        {"url": "http://127.0.0.1:8003", "description": "Local alerts service"},
        {"url": "http://localhost:8003", "description": "Local development server"},
        {
            "url": "https://syncscope-alerts-service-dev.up.railway.app",
            "description": "Development server",
        },
    ],
    # Better component handling
    "COMPONENT_SPLIT_PATCH": True,
    "COMPONENT_SPLIT_REQUEST": True,
    # Tags configuration
    "TAGS": [
        {
            "name": "Alert Rules",
            "description": "Alert rule management endpoints",
        },
        {
            "name": "Alerts",
            "description": "Alert management and acknowledgment endpoints",
        },
        {
            "name": "Notification Channels",
            "description": "Notification channel configuration endpoints",
        },
        {
            "name": "Notifications",
            "description": "Notification log and status endpoints",
        },
        {
            "name": "Health",
            "description": "Service health check endpoints",
        },
    ],
    # Swagger UI
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": True,
        "defaultModelsExpandDepth": 2,
        "defaultModelExpandDepth": 2,
        "defaultModelRendering": "example",
        "displayRequestDuration": True,
        "docExpansion": "list",
        "filter": True,
        "operationsSorter": "alpha",
        "showExtensions": True,
        "tagsSorter": "alpha",
        "tryItOutEnabled": True,
        "supportedSubmitMethods": ["get", "post", "put", "delete", "patch"],
    },
}
