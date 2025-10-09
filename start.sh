#!/bin/bash

# Exit on error
set -e

# Collect static files (only if not in test mode)
if [ "$DJANGO_SETTINGS_MODULE" != "config.test_settings" ]; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
fi

# Start Gunicorn with Daphne for WebSocket support
# Use Daphne as ASGI server for WebSocket
echo "Starting Daphne ASGI server..."
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
