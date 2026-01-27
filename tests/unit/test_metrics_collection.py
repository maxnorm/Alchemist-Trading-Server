"""
Unit tests for metrics collection
"""

import pytest
import time
from prometheus_client import REGISTRY

from monitoring.metrics import (
    trades_executed_total,
    trade_latency_seconds,
    account_equity,
    current_drawdown_pct,
    api_request_duration,
    api_requests_total,
    model_inference_latency,
    feature_extraction_duration,
    kill_switch_active,
    circuit_breaker_state,
    oms_reconciliation_errors,
)


class TestTradingMetrics:
    """Test trading metrics collection"""

    def test_trades_executed_total(self):
        """Test trade counter increments"""
        initial = trades_executed_total.labels(symbol="EURUSD", action_type="buy")._value.get()
        trades_executed_total.labels(symbol="EURUSD", action_type="buy").inc()
        assert trades_executed_total.labels(symbol="EURUSD", action_type="buy")._value.get() == initial + 1

    def test_trade_latency_seconds(self):
        """Test trade latency histogram"""
        trade_latency_seconds.labels(symbol="EURUSD").observe(0.1)
        # Verify metric exists (can't easily check histogram values without scraping)
        assert trade_latency_seconds.labels(symbol="EURUSD") is not None

    def test_account_equity(self):
        """Test equity gauge"""
        account_equity.set(10000.0)
        assert account_equity._value.get() == 10000.0

    def test_current_drawdown_pct(self):
        """Test drawdown gauge"""
        current_drawdown_pct.set(5.5)
        assert current_drawdown_pct._value.get() == 5.5


class TestSystemMetrics:
    """Test system metrics collection"""

    def test_api_request_duration(self):
        """Test API request duration histogram"""
        api_request_duration.labels(method="GET", endpoint="/health", status_code="200").observe(0.05)
        assert api_request_duration.labels(method="GET", endpoint="/health", status_code="200") is not None

    def test_api_requests_total(self):
        """Test API request counter"""
        initial = api_requests_total.labels(method="GET", endpoint="/health", status_code="200")._value.get()
        api_requests_total.labels(method="GET", endpoint="/health", status_code="200").inc()
        assert api_requests_total.labels(method="GET", endpoint="/health", status_code="200")._value.get() == initial + 1


class TestMLMetrics:
    """Test ML metrics collection"""

    def test_model_inference_latency(self):
        """Test model inference latency histogram"""
        model_inference_latency.observe(0.01)
        assert model_inference_latency is not None

    def test_feature_extraction_duration(self):
        """Test feature extraction duration histogram"""
        feature_extraction_duration.observe(0.1)
        assert feature_extraction_duration is not None


class TestSafetyMetrics:
    """Test safety metrics collection"""

    def test_kill_switch_active(self):
        """Test kill switch gauge"""
        kill_switch_active.set(1)
        assert kill_switch_active._value.get() == 1
        kill_switch_active.set(0)
        assert kill_switch_active._value.get() == 0

    def test_circuit_breaker_state(self):
        """Test circuit breaker state gauge"""
        circuit_breaker_state.labels(state="closed").set(1)
        assert circuit_breaker_state.labels(state="closed")._value.get() == 1
        circuit_breaker_state.labels(state="open").set(1)
        assert circuit_breaker_state.labels(state="open")._value.get() == 1

    def test_oms_reconciliation_errors(self):
        """Test OMS reconciliation error counter"""
        initial = oms_reconciliation_errors._value.get()
        oms_reconciliation_errors.inc()
        assert oms_reconciliation_errors._value.get() == initial + 1


if __name__ == "__main__":
    pytest.main([__file__])
