# Generated migration for unmanaged models in alerts app

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        # All models are unmanaged (managed=False), so no actual database operations
        # This migration just registers the models with Django's migration system
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('password', models.CharField(db_column='password_hash', max_length=128)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('first_name', models.CharField(blank=True, max_length=150)),
                ('last_name', models.CharField(blank=True, max_length=150)),
                ('is_staff', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('is_superuser', models.BooleanField(default=False)),
                ('last_login', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'users',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='AlertRule',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('company_id', models.UUIDField()),
                ('metric_type', models.CharField(max_length=100)),
                ('condition', models.CharField(max_length=50)),
                ('threshold_value', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('check_interval_minutes', models.IntegerField(default=60)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'alert_rules',
                'ordering': ['-created_at'],
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='AlertNotification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('triggered_for_user_id', models.UUIDField(blank=True, null=True)),
                ('triggered_for_team_id', models.UUIDField(blank=True, null=True)),
                ('severity', models.CharField(max_length=20)),
                ('title', models.CharField(max_length=255)),
                ('message', models.TextField()),
                ('is_read', models.BooleanField(default=False)),
                ('acknowledged_by', models.UUIDField(blank=True, null=True)),
                ('acknowledged_at', models.DateTimeField(blank=True, null=True)),
                ('triggered_at', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(default='pending', max_length=20)),
                ('context_data', models.JSONField(blank=True, default=dict)),
                ('rule', models.ForeignKey(db_column='rule_id', on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='alerts.alertrule')),
            ],
            options={
                'db_table': 'alert_notifications',
                'ordering': ['-triggered_at'],
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='NotificationChannel',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('company_id', models.UUIDField()),
                ('type', models.CharField(max_length=50)),
                ('name', models.CharField(max_length=255)),
                ('config', models.JSONField(default=dict)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'notification_channels',
                'ordering': ['-created_at'],
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('user_id', models.UUIDField()),
                ('notification_type', models.CharField(max_length=20)),
                ('subject', models.CharField(blank=True, max_length=200, null=True)),
                ('message', models.TextField()),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(default='pending', max_length=20)),
                ('delivery_metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('alert', models.ForeignKey(db_column='alert_id', on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='alerts.alertnotification')),
            ],
            options={
                'db_table': 'notifications',
                'ordering': ['-created_at'],
                'managed': False,
            },
        ),
    ]
