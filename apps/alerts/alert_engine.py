"""
Alert Rule Evaluation Engine
Evaluates alert rules against current metrics
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal

import requests
from django.conf import settings
from django.utils import timezone

from .authentication import get_auth_headers
from .models import AlertNotification, AlertRule

logger = logging.getLogger(__name__)


class AlertEngine:
    """Engine for evaluating alert rules and triggering alerts"""

    def __init__(self):
        self.analytics_service_url = settings.ANALYTICS_SERVICE_URL
        self.monitoring_service_url = settings.MONITORING_SERVICE_URL

    def evaluate_rule(self, rule: AlertRule, test_data=None):
        """
        Evaluate a single alert rule

        Args:
            rule: AlertRule instance to evaluate
            test_data: Optional test data for simulation

        Returns:
            tuple: (should_trigger: bool, context: dict)
        """
        try:
            # Check if rule is active
            if not rule.is_active:
                logger.debug(f"Rule {rule.name} is not active, skipping")
                return False, {}

            # Get current metric value
            if test_data:
                current_value = test_data.get("current_value")
                metadata = test_data
            else:
                current_value, metadata = self._fetch_metric_value(rule)

            if current_value is None:
                logger.warning(f"Could not fetch metric value for rule {rule.name}")
                return False, {}

            # Evaluate condition
            condition = rule.condition
            operator = condition.get("operator")

            should_trigger = self._evaluate_condition(operator, current_value, rule, condition, metadata)

            context = {
                "current_value": current_value,
                "threshold": str(rule.threshold_value) if rule.threshold_value else None,
                "operator": operator,
                "metric_type": rule.metric_type,
                "evaluation_time": timezone.now().isoformat(),
                **metadata,
            }

            return should_trigger, context

        except Exception as e:
            logger.error(f"Error evaluating rule {rule.name}: {e}", exc_info=True)
            return False, {}

    def _evaluate_condition(self, operator, current_value, rule, condition, metadata):
        """Evaluate condition based on operator"""

        try:
            current_value = Decimal(str(current_value))

            if operator == "gt":
                threshold = Decimal(str(rule.threshold_value))
                return current_value > threshold

            elif operator == "gte":
                threshold = Decimal(str(rule.threshold_value))
                return current_value >= threshold

            elif operator == "lt":
                threshold = Decimal(str(rule.threshold_value))
                return current_value < threshold

            elif operator == "lte":
                threshold = Decimal(str(rule.threshold_value))
                return current_value <= threshold

            elif operator == "eq":
                threshold = Decimal(str(rule.threshold_value))
                return current_value == threshold

            elif operator == "between":
                min_val = Decimal(str(condition.get("min_value", 0)))
                max_val = Decimal(str(condition.get("max_value", 0)))
                return min_val <= current_value <= max_val

            elif operator == "trend_up":
                # Check if value is trending upward
                return self._evaluate_trend(rule, current_value, direction="up", metadata=metadata)

            elif operator == "trend_down":
                # Check if value is trending downward
                return self._evaluate_trend(rule, current_value, direction="down", metadata=metadata)

            elif operator == "custom":
                # Custom evaluation logic
                return self._evaluate_custom_condition(rule, current_value, condition, metadata)

            else:
                logger.warning(f"Unknown operator: {operator}")
                return False

        except (ValueError, TypeError) as e:
            logger.error(f"Error evaluating condition: {e}")
            return False

    def _evaluate_trend(self, rule, current_value, direction, metadata):
        """Evaluate trend-based conditions"""
        try:
            # Get historical values
            historical_values = metadata.get("historical_values", [])

            if len(historical_values) < 2:
                logger.debug(f"Not enough historical data for trend analysis")
                return False

            # Calculate trend
            trend_threshold = rule.condition.get("trend_threshold", 10)  # percentage

            # Compare with previous value
            previous_value = Decimal(str(historical_values[-1]))
            change_percent = ((current_value - previous_value) / previous_value) * 100

            if direction == "up":
                return change_percent > Decimal(str(trend_threshold))
            else:  # down
                return change_percent < -Decimal(str(trend_threshold))

        except Exception as e:
            logger.error(f"Error evaluating trend: {e}")
            return False

    def _evaluate_custom_condition(self, rule, current_value, condition, metadata):
        """Evaluate custom condition logic"""
        try:
            # Custom formula evaluation
            formula = condition.get("formula", "")

            # Create safe evaluation context
            context = {
                "current_value": current_value,
                "threshold": rule.threshold_value,
                "metadata": metadata,
            }

            # Add safe math operations
            import math

            safe_context = {
                "abs": abs,
                "min": min,
                "max": max,
                "round": round,
                "math": math,
                **context,
            }

            # Evaluate formula
            result = eval(formula, {"__builtins__": {}}, safe_context)
            return bool(result)

        except Exception as e:
            logger.error(f"Error evaluating custom condition: {e}")
            return False

    def _fetch_metric_value(self, rule: AlertRule):
        """Fetch current metric value from appropriate service"""
        try:
            metric_type = rule.metric_type
            target_type = rule.target_type
            target_id = rule.target_id

            # Determine which service to query based on metric type
            if metric_type.startswith("productivity_") or metric_type.startswith("code_"):
                # Query analytics service
                return self._fetch_from_analytics(metric_type, target_type, target_id)
            elif metric_type.startswith("activity_") or metric_type.startswith("session_"):
                # Query monitoring service
                return self._fetch_from_monitoring(metric_type, target_type, target_id)
            else:
                # Default to analytics service
                return self._fetch_from_analytics(metric_type, target_type, target_id)

        except Exception as e:
            logger.error(f"Error fetching metric value: {e}")
            return None, {}

    def _fetch_from_analytics(self, metric_type, target_type, target_id):
        """Fetch metric from analytics service"""
        try:
            url = f"{self.analytics_service_url}/analytics/metrics/calculate/"

            headers = get_auth_headers("analytics")

            payload = {
                "metric_type": metric_type,
                "target_type": target_type,
                "target_id": str(target_id) if target_id else None,
                "time_range": "24h",  # Default to last 24 hours
            }

            response = requests.post(url, json=payload, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return data.get("value"), data
            else:
                logger.warning(f"Analytics service returned {response.status_code}")
                return None, {}

        except Exception as e:
            logger.error(f"Error fetching from analytics service: {e}")
            return None, {}

    def _fetch_from_monitoring(self, metric_type, target_type, target_id):
        """Fetch metric from monitoring service"""
        try:
            url = f"{self.monitoring_service_url}/monitoring/metrics/"

            headers = get_auth_headers("monitoring")

            params = {
                "metric_type": metric_type,
                "target_type": target_type,
                "target_id": str(target_id) if target_id else None,
            }

            response = requests.get(url, params=params, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                # Extract value from monitoring data structure
                results = data.get("results", [])
                if results:
                    value = results[0].get("value")
                    return value, data
                return None, {}
            else:
                logger.warning(f"Monitoring service returned {response.status_code}")
                return None, {}

        except Exception as e:
            logger.error(f"Error fetching from monitoring service: {e}")
            return None, {}

    def trigger_alert(self, rule: AlertRule, context: dict):
        """
        Create a new alert for the given rule

        Args:
            rule: AlertRule that was triggered
            context: Context data from evaluation
        """
        try:
            # Check cooldown period
            target_id = context.get("target_id") or rule.target_id
            if rule.is_in_cooldown(target_id):
                logger.info(f"Rule {rule.name} is in cooldown period, skipping alert creation")
                return None

            # Create alert title and message
            title = self._generate_alert_title(rule, context)
            message = self._generate_alert_message(rule, context)

            # Create alert
            alert = AlertNotification.objects.create(
                alert_rule=rule,
                state="active",
                severity=rule.severity,
                title=title,
                message=message,
                metadata=context,
                target_type=rule.target_type,
                target_id=target_id or rule.target_id,
                company_id=rule.company_id,
            )

            logger.info(f"Created alert {alert.id} for rule {rule.name}")

            # Trigger notifications (async)
            from .tasks import send_alert_notifications

            send_alert_notifications.delay(str(alert.id))

            return alert

        except Exception as e:
            logger.error(f"Error triggering alert: {e}", exc_info=True)
            return None

    def _generate_alert_title(self, rule: AlertRule, context: dict):
        """Generate alert title from rule and context"""
        current_value = context.get("current_value")
        threshold = context.get("threshold")

        if threshold:
            return f"{rule.name}: {current_value} (threshold: {threshold})"
        else:
            return f"{rule.name}: {current_value}"

    def _generate_alert_message(self, rule: AlertRule, context: dict):
        """Generate alert message from rule and context"""
        operator = context.get("operator")
        current_value = context.get("current_value")
        threshold = context.get("threshold")
        metric_type = context.get("metric_type")

        message = f"{rule.description}\n\n"
        message += f"Metric: {metric_type}\n"
        message += f"Current Value: {current_value}\n"

        if threshold:
            message += f"Threshold: {threshold}\n"
            message += f"Condition: {operator}\n"

        message += f"\nTarget: {rule.target_type}"
        if rule.target_id:
            message += f" (ID: {rule.target_id})"

        message += f"\nSeverity: {rule.severity.upper()}"
        message += f"\nTriggered at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"

        return message


# Singleton instance
alert_engine = AlertEngine()
