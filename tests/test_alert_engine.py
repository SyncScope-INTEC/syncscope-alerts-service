"""
Tests for Alert Engine
"""

import uuid
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.alerts.alert_engine import AlertEngine, alert_engine
from apps.alerts.models import AlertRule


class TestAlertEngine:
    """Tests for AlertEngine class"""

    def setup_method(self):
        """Setup for each test"""
        self.engine = AlertEngine()

    def test_init(self):
        """Test AlertEngine initialization"""
        assert self.engine.analytics_service_url is not None
        assert self.engine.monitoring_service_url is not None

    def test_singleton_instance_exists(self):
        """Test singleton alert_engine instance"""
        assert alert_engine is not None
        assert isinstance(alert_engine, AlertEngine)


@pytest.mark.django_db
class TestEvaluateRule:
    """Tests for evaluate_rule method"""

    def setup_method(self):
        """Setup for each test"""
        self.engine = AlertEngine()
        self.company_id = uuid.uuid4()

    def test_evaluate_inactive_rule(self):
        """Test evaluation of inactive rule"""
        rule = AlertRule(
            name="Test Rule",
            company_id=self.company_id,
            metric_type="test",
            condition={"operator": "gt"},
            threshold_value=100,
            is_active=False,
        )

        should_trigger, context = self.engine.evaluate_rule(rule)

        assert should_trigger is False
        assert context == {}

    def test_evaluate_with_test_data(self):
        """Test evaluation with test data"""
        rule = AlertRule(
            name="Test Rule",
            company_id=self.company_id,
            metric_type="test",
            condition={"operator": "gt"},
            threshold_value=100,
            is_active=True,
        )

        test_data = {"current_value": 150}

        should_trigger, context = self.engine.evaluate_rule(rule, test_data)

        assert should_trigger is True
        assert context["current_value"] == 150
        assert context["metric_type"] == "test"

    @patch.object(AlertEngine, "_fetch_metric_value")
    def test_evaluate_with_fetched_data(self, mock_fetch):
        """Test evaluation with fetched metric data"""
        mock_fetch.return_value = (75, {"historical_values": [70, 72]})

        rule = AlertRule(
            name="Test Rule",
            company_id=self.company_id,
            metric_type="test",
            condition={"operator": "lt"},
            threshold_value=100,
            is_active=True,
        )

        should_trigger, context = self.engine.evaluate_rule(rule)

        assert should_trigger is True
        assert context["current_value"] == 75

    @patch.object(AlertEngine, "_fetch_metric_value")
    def test_evaluate_with_null_metric_value(self, mock_fetch):
        """Test evaluation when metric fetch returns None"""
        mock_fetch.return_value = (None, {})

        rule = AlertRule(
            name="Test Rule",
            company_id=self.company_id,
            metric_type="test",
            condition={"operator": "gt"},
            threshold_value=100,
            is_active=True,
        )

        should_trigger, context = self.engine.evaluate_rule(rule)

        assert should_trigger is False
        assert context == {}

    @patch.object(AlertEngine, "_fetch_metric_value")
    def test_evaluate_handles_exceptions(self, mock_fetch):
        """Test evaluation handles exceptions gracefully"""
        mock_fetch.side_effect = Exception("Test error")

        rule = AlertRule(
            name="Test Rule",
            company_id=self.company_id,
            metric_type="test",
            condition={"operator": "gt"},
            threshold_value=100,
            is_active=True,
        )

        should_trigger, context = self.engine.evaluate_rule(rule)

        assert should_trigger is False
        assert context == {}


class TestEvaluateCondition:
    """Tests for _evaluate_condition method"""

    def setup_method(self):
        """Setup for each test"""
        self.engine = AlertEngine()
        self.rule = Mock(spec=AlertRule)
        self.rule.threshold_value = 100

    def test_operator_gt_true(self):
        """Test greater than operator returns True"""
        result = self.engine._evaluate_condition("gt", 150, self.rule, {}, {})
        assert result is True

    def test_operator_gt_false(self):
        """Test greater than operator returns False"""
        result = self.engine._evaluate_condition("gt", 50, self.rule, {}, {})
        assert result is False

    def test_operator_gte_equal(self):
        """Test greater than or equal operator with equal values"""
        result = self.engine._evaluate_condition("gte", 100, self.rule, {}, {})
        assert result is True

    def test_operator_lt_true(self):
        """Test less than operator returns True"""
        result = self.engine._evaluate_condition("lt", 50, self.rule, {}, {})
        assert result is True

    def test_operator_lte_equal(self):
        """Test less than or equal operator with equal values"""
        result = self.engine._evaluate_condition("lte", 100, self.rule, {}, {})
        assert result is True

    def test_operator_eq_true(self):
        """Test equal operator returns True"""
        result = self.engine._evaluate_condition("eq", 100, self.rule, {}, {})
        assert result is True

    def test_operator_eq_false(self):
        """Test equal operator returns False"""
        result = self.engine._evaluate_condition("eq", 99, self.rule, {}, {})
        assert result is False

    def test_operator_between_inside(self):
        """Test between operator with value inside range"""
        condition = {"operator": "between", "min_value": 50, "max_value": 150}
        result = self.engine._evaluate_condition("between", 100, self.rule, condition, {})
        assert result is True

    def test_operator_between_outside(self):
        """Test between operator with value outside range"""
        condition = {"operator": "between", "min_value": 50, "max_value": 150}
        result = self.engine._evaluate_condition("between", 200, self.rule, condition, {})
        assert result is False

    @patch.object(AlertEngine, "_evaluate_trend")
    def test_operator_trend_up(self, mock_trend):
        """Test trend_up operator"""
        mock_trend.return_value = True
        result = self.engine._evaluate_condition("trend_up", 100, self.rule, {}, {})
        assert result is True
        mock_trend.assert_called_once()

    @patch.object(AlertEngine, "_evaluate_trend")
    def test_operator_trend_down(self, mock_trend):
        """Test trend_down operator"""
        mock_trend.return_value = True
        result = self.engine._evaluate_condition("trend_down", 100, self.rule, {}, {})
        assert result is True

    @patch.object(AlertEngine, "_evaluate_custom_condition")
    def test_operator_custom(self, mock_custom):
        """Test custom operator"""
        mock_custom.return_value = True
        result = self.engine._evaluate_condition("custom", 100, self.rule, {}, {})
        assert result is True

    def test_unknown_operator(self):
        """Test unknown operator returns False"""
        result = self.engine._evaluate_condition("unknown", 100, self.rule, {}, {})
        assert result is False

    def test_invalid_value_type(self):
        """Test invalid value type raises exception (caught by try/except in code)"""
        # The actual code would catch this in evaluate_rule's try/except
        # This test just confirms the behavior at this level
        from decimal import InvalidOperation

        with pytest.raises(InvalidOperation):
            self.engine._evaluate_condition("gt", "invalid", self.rule, {}, {})


class TestEvaluateTrend:
    """Tests for _evaluate_trend method"""

    def setup_method(self):
        """Setup for each test"""
        self.engine = AlertEngine()
        self.rule = Mock(spec=AlertRule)
        self.rule.condition = {"trend_threshold": 10}

    def test_trend_up_positive(self):
        """Test upward trend detection"""
        metadata = {"historical_values": [80, 85]}
        result = self.engine._evaluate_trend(self.rule, Decimal("95"), "up", metadata)
        assert result is True  # (95-85)/85 = 11.76% > 10%

    def test_trend_up_negative(self):
        """Test upward trend with insufficient change"""
        metadata = {"historical_values": [90, 92]}
        result = self.engine._evaluate_trend(self.rule, Decimal("95"), "up", metadata)
        assert result is False  # (95-92)/92 = 3.26% < 10%

    def test_trend_down_positive(self):
        """Test downward trend detection"""
        metadata = {"historical_values": [90, 95]}
        result = self.engine._evaluate_trend(self.rule, Decimal("80"), "down", metadata)
        assert result is True  # (80-95)/95 = -15.79% < -10%

    def test_trend_insufficient_data(self):
        """Test trend with insufficient historical data"""
        metadata = {"historical_values": [90]}
        result = self.engine._evaluate_trend(self.rule, Decimal("95"), "up", metadata)
        assert result is False

    def test_trend_no_data(self):
        """Test trend with no historical data"""
        metadata = {"historical_values": []}
        result = self.engine._evaluate_trend(self.rule, Decimal("95"), "up", metadata)
        assert result is False

    def test_trend_handles_exceptions(self):
        """Test trend evaluation handles exceptions"""
        metadata = {"historical_values": ["invalid"]}
        result = self.engine._evaluate_trend(self.rule, Decimal("95"), "up", metadata)
        assert result is False


class TestEvaluateCustomCondition:
    """Tests for _evaluate_custom_condition method"""

    def setup_method(self):
        """Setup for each test"""
        self.engine = AlertEngine()
        self.rule = Mock(spec=AlertRule)
        self.rule.threshold_value = 100

    def test_custom_formula_simple(self):
        """Test simple custom formula"""
        condition = {"formula": "current_value > threshold"}
        result = self.engine._evaluate_custom_condition(self.rule, 150, condition, {})
        assert result is True

    def test_custom_formula_with_math(self):
        """Test custom formula with math operations"""
        condition = {"formula": "abs(current_value - threshold) > 10"}
        result = self.engine._evaluate_custom_condition(self.rule, 85, condition, {})
        assert result is True

    def test_custom_formula_false(self):
        """Test custom formula returning false"""
        condition = {"formula": "current_value < 50"}
        result = self.engine._evaluate_custom_condition(self.rule, 150, condition, {})
        assert result is False

    def test_custom_formula_invalid(self):
        """Test invalid custom formula returns False"""
        condition = {"formula": "invalid_syntax ((("}
        result = self.engine._evaluate_custom_condition(self.rule, 150, condition, {})
        assert result is False


class TestFetchMetricValue:
    """Tests for _fetch_metric_value method"""

    def setup_method(self):
        """Setup for each test"""
        self.engine = AlertEngine()

    @patch.object(AlertEngine, "_fetch_from_analytics")
    def test_fetch_productivity_metric(self, mock_analytics):
        """Test fetching productivity metric from analytics"""
        mock_analytics.return_value = (75.5, {"key": "value"})

        rule = Mock(spec=AlertRule)
        rule.metric_type = "productivity_score"
        rule.target_type = "user"
        rule.target_id = uuid.uuid4()

        value, metadata = self.engine._fetch_metric_value(rule)

        assert value == 75.5
        mock_analytics.assert_called_once()

    @patch.object(AlertEngine, "_fetch_from_monitoring")
    def test_fetch_activity_metric(self, mock_monitoring):
        """Test fetching activity metric from monitoring"""
        mock_monitoring.return_value = (120, {"active": True})

        rule = Mock(spec=AlertRule)
        rule.metric_type = "activity_duration"
        rule.target_type = "user"
        rule.target_id = uuid.uuid4()

        value, metadata = self.engine._fetch_metric_value(rule)

        assert value == 120
        mock_monitoring.assert_called_once()

    @patch.object(AlertEngine, "_fetch_from_analytics")
    def test_fetch_default_to_analytics(self, mock_analytics):
        """Test default fetching uses analytics service"""
        mock_analytics.return_value = (50, {})

        rule = Mock(spec=AlertRule)
        rule.metric_type = "unknown_metric"
        rule.target_type = "team"
        rule.target_id = uuid.uuid4()

        value, metadata = self.engine._fetch_metric_value(rule)

        mock_analytics.assert_called_once()

    @patch.object(AlertEngine, "_fetch_from_analytics")
    def test_fetch_handles_exception(self, mock_analytics):
        """Test fetch handles exceptions"""
        mock_analytics.side_effect = Exception("Service error")

        rule = Mock(spec=AlertRule)
        rule.metric_type = "test_metric"
        rule.target_type = "user"
        rule.target_id = uuid.uuid4()

        value, metadata = self.engine._fetch_metric_value(rule)

        assert value is None
        assert metadata == {}


class TestFetchFromAnalytics:
    """Tests for _fetch_from_analytics method"""

    def setup_method(self):
        """Setup for each test"""
        self.engine = AlertEngine()

    @patch("apps.alerts.alert_engine.requests.post")
    @patch("apps.alerts.alert_engine.get_auth_headers")
    def test_fetch_success(self, mock_headers, mock_post):
        """Test successful fetch from analytics"""
        mock_headers.return_value = {"Authorization": "Bearer token"}
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": 85.5, "unit": "percent"}
        mock_post.return_value = mock_response

        value, data = self.engine._fetch_from_analytics("productivity_score", "user", uuid.uuid4())

        assert value == 85.5
        assert data["unit"] == "percent"
        mock_post.assert_called_once()

    @patch("apps.alerts.alert_engine.requests.post")
    @patch("apps.alerts.alert_engine.get_auth_headers")
    def test_fetch_error_response(self, mock_headers, mock_post):
        """Test fetch with error response"""
        mock_headers.return_value = {"Authorization": "Bearer token"}
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        value, data = self.engine._fetch_from_analytics("productivity_score", "user", uuid.uuid4())

        assert value is None
        assert data == {}

    @patch("apps.alerts.alert_engine.requests.post")
    @patch("apps.alerts.alert_engine.get_auth_headers")
    def test_fetch_request_exception(self, mock_headers, mock_post):
        """Test fetch handles request exceptions"""
        mock_headers.return_value = {"Authorization": "Bearer token"}
        mock_post.side_effect = Exception("Connection error")

        value, data = self.engine._fetch_from_analytics("productivity_score", "user", uuid.uuid4())

        assert value is None
        assert data == {}


class TestGenerateAlertMessages:
    """Tests for alert message generation"""

    def setup_method(self):
        """Setup for each test"""
        self.engine = AlertEngine()
        self.rule = Mock(spec=AlertRule)
        self.rule.name = "Test Alert"
        self.rule.description = "Test alert description"
        self.rule.target_type = "user"
        self.rule.target_id = uuid.uuid4()
        self.rule.severity = "high"

    def test_generate_title_with_threshold(self):
        """Test alert title generation with threshold"""
        context = {"current_value": 150, "threshold": "100"}

        title = self.engine._generate_alert_title(self.rule, context)

        assert "Test Alert" in title
        assert "150" in title
        assert "100" in title

    def test_generate_title_without_threshold(self):
        """Test alert title generation without threshold"""
        context = {"current_value": 150, "threshold": None}

        title = self.engine._generate_alert_title(self.rule, context)

        assert "Test Alert" in title
        assert "150" in title
        assert "threshold" not in title.lower()

    def test_generate_message_complete(self):
        """Test complete alert message generation"""
        context = {
            "operator": "gt",
            "current_value": 150,
            "threshold": "100",
            "metric_type": "productivity_score",
        }

        message = self.engine._generate_alert_message(self.rule, context)

        assert "Test alert description" in message
        assert "productivity_score" in message
        assert "150" in message
        assert "100" in message
        assert "gt" in message
        assert "HIGH" in message
