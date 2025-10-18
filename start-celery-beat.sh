#!/bin/bash

# Exit on error
set -e

echo "Starting Celery beat scheduler..."

# Start Celery beat
exec celery -A config beat \
    --loglevel=info \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler
