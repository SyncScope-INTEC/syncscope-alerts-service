# SyncScope Alerts Service

Real-time alerting and notification service for the SyncScope platform.

## Features

- **Alert Rule Management**: Create and manage complex alert rules with multiple condition operators
- **Real-time Notifications**: Multi-channel notifications (Email, Slack, Webhook, In-App)
- **WebSocket Support**: Real-time push notifications via WebSocket
- **Smart Alerting**: Cooldown periods, severity levels, and spam prevention
- **Flexible Conditions**: Support for gt, lt, eq, gte, lte, between, trend analysis, and custom formulas
- **Background Processing**: Celery-based periodic alert evaluation
- **Notification Retry**: Automatic retry for failed notifications
- **Alert Lifecycle**: Active, Acknowledged, Resolved, Muted states

## Architecture

- **Framework**: Django 4.2+ with Django REST Framework
- **Database**: PostgreSQL with schema `alerts`
- **Cache/Queue**: Redis
- **Task Queue**: Celery with Beat scheduler
- **WebSocket**: Django Channels with Redis channel layer
- **Authentication**: JWT tokens from Auth Service

## Models

### AlertRule
- Complex condition evaluation (productivity drop, code quality, deadline risk, anomaly detection)
- Multi-target support (user, team, project, company)
- Configurable severity and cooldown periods
- Many-to-many relationship with notification channels

### Alert
- Lifecycle management (active, acknowledged, resolved, muted)
- Rich metadata for context
- Linked to alert rules and notification logs

### NotificationChannel
- Multiple channel types (email, slack, webhook, in_app, sms, push)
- JSON configuration for channel-specific settings
- Active/inactive status management

### NotificationLog
- Delivery tracking with retry count
- Status monitoring (pending, sent, failed, retrying)
- Error message logging

## API Endpoints

### Alert Rules
- `GET /alerts/rules/` - List alert rules
- `POST /alerts/rules/` - Create alert rule
- `GET /alerts/rules/{id}/` - Get alert rule details
- `PUT /alerts/rules/{id}/` - Update alert rule
- `DELETE /alerts/rules/{id}/` - Delete alert rule
- `POST /alerts/rules/{id}/test/` - Test alert rule
- `POST /alerts/rules/{id}/activate/` - Activate alert rule
- `POST /alerts/rules/{id}/deactivate/` - Deactivate alert rule

### Alerts
- `GET /alerts/` - List alerts
- `GET /alerts/{id}/` - Get alert details
- `POST /alerts/acknowledge/` - Acknowledge alerts
- `POST /alerts/resolve/` - Resolve alerts
- `POST /alerts/{id}/mute/` - Mute alert
- `GET /alerts/statistics/` - Get alert statistics

### Notification Channels
- `GET /alerts/channels/` - List notification channels
- `POST /alerts/channels/` - Create notification channel
- `GET /alerts/channels/{id}/` - Get channel details
- `PUT /alerts/channels/{id}/` - Update channel
- `DELETE /alerts/channels/{id}/` - Delete channel
- `POST /alerts/channels/{id}/test/` - Test channel

### Notification Logs
- `GET /alerts/notifications/` - List notification logs
- `GET /alerts/notifications/{id}/` - Get notification log details

## WebSocket Endpoints

- `ws://localhost:8003/ws/alerts/` - User alert notifications
- `ws://localhost:8003/ws/alerts/company/{company_id}/` - Company-wide alerts (admin only)

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Run migrations:
```bash
python manage.py migrate
```

4. Create superuser:
```bash
python manage.py createsuperuser
```

5. Start development server:
```bash
python manage.py runserver 0.0.0.0:8003
```

6. Start Celery worker (in separate terminal):
```bash
celery -A config worker -l info
```

7. Start Celery beat (in separate terminal):
```bash
celery -A config beat -l info
```

8. Start Daphne for WebSocket support (production):
```bash
daphne -b 0.0.0.0 -p 8003 config.asgi:application
```

## Celery Tasks

### Periodic Tasks
- `evaluate_all_active_alert_rules` - Runs every minute
- `cleanup_old_resolved_alerts` - Runs daily at 2 AM
- `retry_failed_notifications` - Runs every 5 minutes

### On-Demand Tasks
- `evaluate_single_alert_rule` - Evaluate specific rule
- `send_alert_notifications` - Send notifications for alert
- `test_notification_channel` - Test notification channel

## Alert Condition Examples

### Simple Threshold
```json
{
  "operator": "gt",
  "threshold": 100
}
```

### Range Check
```json
{
  "operator": "between",
  "min_value": 50,
  "max_value": 100
}
```

### Trend Analysis
```json
{
  "operator": "trend_down",
  "trend_threshold": 20
}
```

### Custom Formula
```json
{
  "operator": "custom",
  "formula": "current_value < threshold * 0.8"
}
```

## Notification Channel Configuration

### Email
```json
{
  "recipients": ["user1@example.com", "user2@example.com"]
}
```

### Slack
```json
{
  "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
}
```

### Webhook
```json
{
  "url": "https://api.example.com/alerts",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer token"
  }
}
```

### In-App
```json
{
  "user_ids": ["uuid1", "uuid2"]
}
```

## Testing

Run tests:
```bash
python -m pytest tests/ --cov=apps.alerts
```

## Deployment

The service is designed for serverless deployment on Railway with:
- Automatic schema search path configuration
- Connection pooling for PostgreSQL
- Redis for caching and message queue
- Health check endpoints
- Graceful error handling