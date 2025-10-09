# SyncScope Alerts Service - Deployment Guide

## Prerequisites

- PostgreSQL database with `alerts` schema created
- Redis instance for caching and message queue
- Python 3.10+
- Access to SyncScope Auth Service

## Database Setup

1. Create the `alerts` schema in your PostgreSQL database:

```sql
CREATE SCHEMA IF NOT EXISTS alerts;
```

2. Run Django migrations:

```bash
python manage.py migrate
```

This will create the following tables in the `alerts` schema:
- `alerts.alert_rules`
- `alerts.alerts`
- `alerts.notification_channels`
- `alerts.alert_rule_notification_channels`
- `alerts.notification_logs`

## Environment Variables

Copy `.env.example` to `.env` and configure:

### Required Variables
```env
SECRET_KEY=<same-secret-key-as-auth-service>
DATABASE_URL=postgresql://user:pass@host:port/dbname
REDIS_URL=redis://host:port/db
AUTH_SERVICE_URL=https://your-auth-service.com
```

### Optional Variables
```env
ANALYTICS_SERVICE_URL=http://localhost:8000
MONITORING_SERVICE_URL=http://localhost:8001
MANAGEMENT_SERVICE_URL=http://localhost:8002
ALERT_EVALUATION_INTERVAL=60
MAX_RETRY_ATTEMPTS=3
NOTIFICATION_RETRY_DELAY=300
ALERT_RETENTION_DAYS=90
```

## Running Locally

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Database Migrations
```bash
python manage.py migrate
```

### 3. Create Superuser
```bash
python manage.py createsuperuser
```

### 4. Collect Static Files
```bash
python manage.py collectstatic --noinput
```

### 5. Start Services

**Terminal 1 - Django Server:**
```bash
python manage.py runserver 0.0.0.0:8003
```

**Terminal 2 - Celery Worker:**
```bash
celery -A config worker -l info
```

**Terminal 3 - Celery Beat (Scheduler):**
```bash
celery -A config beat -l info
```

**Terminal 4 - Daphne (WebSocket):**
```bash
daphne -b 0.0.0.0 -p 8003 config.asgi:application
```

## Production Deployment (Railway)

### 1. Environment Variables

Set the following in Railway:

```env
SECRET_KEY=<production-secret-key>
DATABASE_URL=<railway-postgres-url>
REDIS_URL=<railway-redis-url>
AUTH_SERVICE_URL=https://syncscope-auth-service-production.up.railway.app
ANALYTICS_SERVICE_URL=https://syncscope-analytics-service-production.up.railway.app
MONITORING_SERVICE_URL=https://syncscope-monitoring-service-production.up.railway.app
MANAGEMENT_SERVICE_URL=https://syncscope-management-service-production.up.railway.app
DEBUG=False
ALLOWED_HOSTS=*.railway.app,*.up.railway.app
```

### 2. Procfile

Railway will automatically detect the service type. For custom setup:

**Web Process (HTTP + WebSocket):**
```
web: daphne -b 0.0.0.0 -p $PORT config.asgi:application
```

**Worker Process (Celery):**
```
worker: celery -A config worker -l info
```

**Beat Process (Scheduler):**
```
beat: celery -A config beat -l info
```

### 3. Health Check

Railway health check endpoint: `https://your-service.up.railway.app/health/`

### 4. Post-Deployment

1. Run migrations:
```bash
railway run python manage.py migrate
```

2. Create superuser:
```bash
railway run python manage.py createsuperuser
```

3. Collect static files:
```bash
railway run python manage.py collectstatic --noinput
```

## Testing Deployment

### 1. Health Check
```bash
curl https://your-service.up.railway.app/health/
```

### 2. API Documentation
Visit: `https://your-service.up.railway.app/api/docs/`

### 3. WebSocket Connection
```javascript
const ws = new WebSocket('wss://your-service.up.railway.app/ws/alerts/');
ws.onopen = () => console.log('Connected');
ws.onmessage = (event) => console.log('Message:', event.data);
```

### 4. Create Test Alert Rule
```bash
curl -X POST https://your-service.up.railway.app/alerts/rules/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Alert",
    "description": "Test alert rule",
    "rule_type": "threshold_breach",
    "metric_type": "test_metric",
    "condition": {"operator": "gt"},
    "threshold_value": 100,
    "severity": "high",
    "target_type": "user",
    "is_active": true,
    "cooldown_minutes": 60
  }'
```

## Monitoring

### Celery Tasks Status
Access Django Admin: `https://your-service.up.railway.app/admin/`

Navigate to:
- Periodic tasks → See scheduled tasks
- Task results → See task execution history

### Logs
```bash
railway logs
```

### Performance Metrics
Check Redis cache for performance metrics:
```bash
redis-cli GET alerts_perf:*
```

## Troubleshooting

### Database Connection Issues
- Verify `DATABASE_URL` is correct
- Check database schema search path includes `alerts`
- Ensure PostgreSQL accepts connections from Railway IPs

### Redis Connection Issues
- Verify `REDIS_URL` is correct
- Test Redis connection: `redis-cli -u $REDIS_URL ping`

### Celery Not Running Tasks
- Check Celery worker is running
- Check Celery beat is running
- Verify Redis connection
- Check task results in Django Admin

### WebSocket Connection Failed
- Ensure using `wss://` protocol (not `ws://`)
- Check CORS settings
- Verify Daphne is running

### Email Notifications Not Sending
- Verify `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD`
- Check email provider allows SMTP
- Review notification logs in admin

## Security Checklist

- [ ] `SECRET_KEY` is unique and secure
- [ ] `DEBUG=False` in production
- [ ] Database credentials are secure
- [ ] Redis requires authentication
- [ ] HTTPS is enabled
- [ ] CORS origins are restricted
- [ ] Rate limiting is enabled
- [ ] Sensitive data is not logged

## Scaling

### Horizontal Scaling
- Run multiple Celery workers
- Use Redis cluster for high availability
- Load balance HTTP requests

### Vertical Scaling
- Increase worker concurrency: `celery -A config worker -l info --concurrency=10`
- Optimize database queries
- Adjust connection pool sizes

## Backup

### Database Backup
```bash
pg_dump -h host -U user -d dbname -n alerts > alerts_backup.sql
```

### Restore
```bash
psql -h host -U user -d dbname < alerts_backup.sql
```

## Support

For issues or questions:
- Check logs: `railway logs`
- Review API documentation: `/api/docs/`
- Contact: support@syncscope.com
