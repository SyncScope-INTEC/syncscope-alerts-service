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
if [ "$DJANGO_SETTINGS_MODULE" != "config.test_settings" ]; then
    echo "✓ Running database migrations..."

    # Function to run migrations with retry logic
    run_migrations() {
        local max_attempts=5
        local attempt=1
        local wait_time=2

        while [ $attempt -le $max_attempts ]; do
            echo "Migration attempt $attempt of $max_attempts..."

            # Try to fake-apply alerts initial migration
            if python manage.py migrate alerts 0001_initial --fake 2>/dev/null; then
                echo "✓ Alerts migration recorded"
            else
                echo "⊘ Alerts migration already applied or skipped"
            fi

            # Try to run all migrations
            if python manage.py migrate --noinput 2>&1; then
                echo "✓ Migrations completed successfully"
                return 0
            fi

            if [ $attempt -lt $max_attempts ]; then
                echo "⚠ Migration failed, retrying in ${wait_time}s..."
                sleep $wait_time
                wait_time=$((wait_time * 2))  # Exponential backoff
            fi

            attempt=$((attempt + 1))
        done

        echo "⚠ Migrations failed after $max_attempts attempts - continuing anyway"
        echo "⚠ You may need to run migrations manually: python manage.py migrate"
        return 1
    }

    # Run migrations but don't fail startup if they fail
    run_migrations || true
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
