"""
Test settings for syncscope-alerts-service
Inherits from base settings and overrides for testing environment
"""

from .settings import *

# Remove apps that aren't installed or not needed for tests
INSTALLED_APPS = [
    app
    for app in INSTALLED_APPS
    if app
    not in [
        "daphne",
        "channels",
        "django_celery_beat",
        "django_celery_results",
    ]
]

# Override secret key for tests
SECRET_KEY = "test-secret-key-for-ci-cd-pipeline"

# Debug should be True for tests to get detailed error messages
DEBUG = True

# Use in-memory SQLite for faster tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}


# Disable migrations for faster tests
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

# Use faster password hasher for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Disable Redis requirement for tests - use in-memory cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-test-cache",
    }
}

# Disable Celery for tests - execute tasks synchronously
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

# Disable ASGI for tests
ASGI_APPLICATION = None

# Disable CSRF for tests
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# Use console email backend for tests
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Disable rate limiting in tests
RATELIMIT_ENABLE = False

# Test-specific logging - less verbose
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps.alerts": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Service URLs for tests (mock endpoints)
AUTH_SERVICE_URL = "http://localhost:8001"
ANALYTICS_SERVICE_URL = "http://localhost:8004"
MONITORING_SERVICE_URL = "http://localhost:8002"
MANAGEMENT_SERVICE_URL = "http://localhost:8005"

# Alerts configuration for tests
ALERT_EVALUATION_INTERVAL = 5  # Faster evaluation in tests
MAX_RETRY_ATTEMPTS = 2  # Fewer retries in tests
NOTIFICATION_RETRY_DELAY = 1  # Faster retry in tests
ALERT_RETENTION_DAYS = 7  # Shorter retention in tests

# Disable security features that might interfere with tests
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Allow all hosts in tests
ALLOWED_HOSTS = ["*"]

# CORS - allow all origins in tests
CORS_ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
CORS_ALLOW_ALL_ORIGINS = True

# Suppress system checks that aren't relevant for tests
SILENCED_SYSTEM_CHECKS = [
    "models.W042",  # Auto-created primary key warning
]
