from django.apps import AppConfig


class AlertsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.alerts"
    verbose_name = "Alerts Service"

    def ready(self):
        """Import signal handlers when app is ready"""
        # Import signals here if needed
        pass
