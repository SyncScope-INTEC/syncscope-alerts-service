#!/bin/bash

# Exit on error
set -e

echo "========================================="
echo "Starting SyncScope Alerts Service"
echo "========================================="

# Use Railway's PORT environment variable, fallback to 8080
export PORT=${PORT:-8080}
echo "✓ Using port: $PORT"

# Collect static files (only if not in test mode)
if [ "$DJANGO_SETTINGS_MODULE" != "config.test_settings" ]; then
    echo "✓ Collecting static files..."
    python manage.py collectstatic --noinput
else
    echo "⊘ Skipping static files (test mode)"
fi

# Run database migrations (only if not in test mode)
# Note: All models are managed=False (tables already exist), so migrations are optional
if [ "$DJANGO_SETTINGS_MODULE" != "config.test_settings" ]; then
    echo "✓ Checking database migrations..."

    # Skip migrations for now - all models are unmanaged (managed=False)
    # Tables already exist in the database, so no schema changes are needed
    echo "⊘ Skipping Django migrations (all models are unmanaged - tables already exist)"
    echo "  If you need to run migrations manually, use: python manage.py migrate --fake-initial"
else
    echo "⊘ Skipping migrations (test mode)"
fi

echo "========================================="
echo "Starting multi-process supervisor:"
echo "  - Daphne (web server) on port $PORT"
echo "  - Celery Worker (background tasks)"
echo "  - Celery Beat (scheduled tasks)"
echo "========================================="

# Start supervisord to manage all processes (Daphne, Celery Worker, Celery Beat)
exec supervisord -c /etc/supervisor/conf.d/supervisord.conf