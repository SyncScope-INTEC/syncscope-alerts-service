"""
Pytest configuration and fixtures for alerts service tests
"""

import pytest
from django.core.management import call_command


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """
    Override django_db_setup to create tables for unmanaged models.

    Since our models have managed=False (they map to existing tables),
    we need to temporarily make them managed and create the schema for testing.
    """
    from apps.alerts import models

    # Temporarily set managed=True for all models
    unmanaged_models = [
        models.AlertRule,
        models.AlertNotification,
        models.NotificationChannel,
        models.Notification,
    ]

    # Store original managed state
    original_managed = {}
    for model in unmanaged_models:
        original_managed[model] = model._meta.managed
        model._meta.managed = True

    with django_db_blocker.unblock():
        # Create tables
        call_command("migrate", "--run-syncdb", verbosity=0)

    # Restore original managed state
    for model in unmanaged_models:
        model._meta.managed = original_managed[model]


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection to exclude non-test functions from apps module
    """
    # Remove items from apps.alerts.tasks module (Celery tasks are not pytest tests)
    filtered_items = []
    for item in items:
        # Skip if it's from apps.alerts.tasks module
        if hasattr(item, "module") and item.module.__name__ == "apps.alerts.tasks":
            continue
        filtered_items.append(item)

    items[:] = filtered_items
