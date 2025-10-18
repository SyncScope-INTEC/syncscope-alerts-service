#!/bin/bash

# Exit on error
set -e

echo "Starting Celery worker..."

# Start Celery worker
exec celery -A config worker \
    --loglevel=info \
    --concurrency=2 \
    --max-tasks-per-child=100 \
    --time-limit=300 \
    --soft-time-limit=240
