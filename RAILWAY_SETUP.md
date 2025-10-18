# Railway Deployment Setup

This service requires **two separate Railway services** to function properly:

## 1. Web Service (Alerts API)
- **Dockerfile**: `Dockerfile`
- **Start Command**: `/app/start.sh`
- Runs the Django/Daphne server on port 8080

## 2. Celery Worker Service
- **Dockerfile**: `Dockerfile.worker`
- **Start Command**: `/app/start-celery-worker.sh`
- Processes background tasks (notifications, alert evaluation, etc.)

## Railway Configuration

### Setting up the Celery Worker:

1. **In your Railway project**, click "New Service" → "GitHub Repo"
2. Select the same repository: `syncscope-alerts-service`
3. In the service settings:
   - **Name**: `syncscope-alerts-service-worker`
   - **Root Directory**: Leave empty (same as web service)
   - **Dockerfile Path**: `Dockerfile.worker`
   - **Start Command**: (leave empty, uses CMD from Dockerfile)

4. **Environment Variables** (same as web service):
   - Copy ALL environment variables from the web service
   - Both services need the same DATABASE_URL, REDIS_URL, SENDGRID_API_KEY, etc.

5. **Important**:
   - The worker service does NOT need a public domain
   - It only needs to connect to Redis and PostgreSQL

### Environment Variables Required:
```
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
CELERY_BROKER_URL=${REDIS_URL}/0
CELERY_RESULT_BACKEND=${REDIS_URL}/0
SENDGRID_API_KEY=SG.xxx
SENDGRID_FROM_EMAIL=your@email.com
# ... (all other variables from web service)
```

## Optional: Celery Beat (for periodic tasks)

If you need periodic tasks (alert evaluation every minute), create a third service:
- **Dockerfile**: Create `Dockerfile.beat` (similar to worker)
- **Start Command**: `/app/start-celery-beat.sh`

## Verification

After deploying the worker, check logs for:
```
[INFO/MainProcess] Connected to redis://...
[INFO/MainProcess] celery@hostname ready.
```

Test notifications should now work!
