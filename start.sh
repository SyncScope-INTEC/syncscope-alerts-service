#!/bin/bash

# Exit on error
set -e

# Use Railway's PORT environment variable, fallback to 8080
export PORT=${PORT:-8080}
echo "Using port: $PORT"

# Collect static files (only if not in test mode)
if [ "$DJANGO_SETTINGS_MODULE" != "config.test_settings" ]; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
fi

# Run database migrations (only if not in test mode)
if [ "$DJANGO_SETTINGS_MODULE" != "config.test_settings" ]; then
    echo "Running database migrations..."
    python manage.py migrate --noinput
fi

# Start supervisord to manage all processes (Daphne, Celery Worker, Celery Beat)
echo "Starting supervisord to manage web server and background workers..."
exec supervisord -c /etc/supervisor/conf.d/supervisord.conf
