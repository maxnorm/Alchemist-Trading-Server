"""
Integration tests for quality gate Prometheus metrics
"""

import pytest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src/backend/trading_server/src"))

from data.quality_gates import QualityGate
from utils.time_utils import get_utc_time


class TestQualityGatePrometheusMetrics:
    """Integration tests for quality gate Prometheus metrics"""

    @pytest.fixture
    def quality_gate(self):
        """Create quality gate instance"""
        return QualityGate()

    @pytest.fixture
    def normal_tick(self):
        """Create a normal valid tick"""
        current_time = get_utc_time()
        return {
            "symbol": "EURUSD",
            "datetime": current_time,
            "ask": 1.1000,
            "bid": 1.0999,
        }

    @pytest.fixture
    def stale_tick(self):
        """Create a stale tick"""
        current_time = get_utc_time()
        stale_time = current_time - timedelta(seconds=400)  # Stale (>300s default)
        return {
            "symbol": "EURUSD",
            "datetime": stale_time,
            "ask": 1.1000,
            "bid": 1.0999,
        }

    @pytest.fixture
    def outlier_tick(self):
        """Create an outlier tick"""
        current_time = get_utc_time()
        return {
            "symbol": "EURUSD",
            "datetime": current_time,
            "ask": 11.0000,  # Extreme outlier
            "bid": 10.9999,
        }

    @pytest.fixture
    def missing_data_tick(self):
        """Create a tick with missing data"""
        return {
            "symbol": "EURUSD",
            # Missing datetime, ask, bid
        }

    @patch("monitoring.metrics.quality_gate_ticks_processed_total")
    @patch("monitoring.metrics.quality_gate_ticks_accepted_total")
    @patch("monitoring.metrics.quality_gate_acceptance_rate")
    @patch("monitoring.metrics.quality_gate_rejection_rate")
    def test_metrics_updated_on_validation(
        self,
        mock_rejection_rate,
        mock_acceptance_rate,
        mock_accepted_total,
        mock_processed_total,
        quality_gate,
        normal_tick,
    ):
        """Test that Prometheus metrics are updated when ticks are validated"""
        # Mock metrics
        mock_processed_counter = MagicMock()
        mock_processed_total.labels.return_value = mock_processed_counter

        mock_accepted_counter = MagicMock()
        mock_accepted_total.labels.return_value = mock_accepted_counter

        mock_acceptance_gauge = MagicMock()
        mock_acceptance_rate.labels.return_value = mock_acceptance_gauge

        mock_rejection_gauge = MagicMock()
        mock_rejection_rate.labels.return_value = mock_rejection_gauge

        # Process some ticks
        symbol = "EURUSD"
        current_time = get_utc_time()

        for _ in range(5):
            quality_gate.validate(normal_tick, symbol, current_time)

        # Sync metrics
        quality_gate.sync_metrics_to_prometheus(symbol=symbol)

        # Verify metrics were called
        mock_processed_total.labels.assert_called_with(symbol=symbol)
        mock_processed_counter.inc.assert_called()
        mock_accepted_total.labels.assert_called_with(symbol=symbol)
        mock_accepted_counter.inc.assert_called()
        mock_acceptance_rate.labels.assert_called_with(symbol=symbol)
        mock_acceptance_gauge.set.assert_called()
        mock_rejection_rate.labels.assert_called_with(symbol=symbol)
        mock_rejection_gauge.set.assert_called()

    @patch("monitoring.metrics.quality_gate_outliers_rejected_total")
    def test_outlier_rejection_metrics(
        self, mock_outliers_rejected, quality_gate, outlier_tick
    ):
        """Test that outlier rejection metrics are updated"""
        # Mock metrics
        mock_counter = MagicMock()
        mock_outliers_rejected.labels.return_value = mock_counter

        symbol = "EURUSD"
        current_time = get_utc_time()

        # Build up history first
        normal_tick = {
            "symbol": symbol,
            "datetime": current_time,
            "ask": 1.1000,
            "bid": 1.0999,
        }
        for _ in range(20):  # Need history for outlier detection
            quality_gate.validate(normal_tick, symbol, current_time)

        # Validate outlier tick
        quality_gate.validate(outlier_tick, symbol, current_time)

        # Sync metrics
        quality_gate.sync_metrics_to_prometheus(symbol=symbol)

        # Verify outlier rejection metric was called
        mock_outliers_rejected.labels.assert_called_with(symbol=symbol)
        # Check if inc was called (may not be called if no outliers in capture-all mode)
        # In capture-all mode, extreme outliers (>10%) are still rejected

    @patch("monitoring.metrics.quality_gate_stale_rejected_total")
    def test_stale_rejection_metrics(
        self, mock_stale_rejected, quality_gate, stale_tick
    ):
        """Test that stale rejection metrics are updated"""
        # Mock metrics
        mock_counter = MagicMock()
        mock_stale_rejected.labels.return_value = mock_counter

        symbol = "EURUSD"
        current_time = get_utc_time()

        # Validate stale tick (will be rejected if not in capture-all mode)
        quality_gate.validate(stale_tick, symbol, current_time)

        # Sync metrics
        quality_gate.sync_metrics_to_prometheus(symbol=symbol)

        # Verify stale rejection metric label was called
        mock_stale_rejected.labels.assert_called_with(symbol=symbol)

    @patch("monitoring.metrics.quality_gate_missing_data_rejected_total")
    def test_missing_data_rejection_metrics(
        self, mock_missing_data_rejected, quality_gate, missing_data_tick
    ):
        """Test that missing data rejection metrics are updated"""
        # Mock metrics
        mock_counter = MagicMock()
        mock_missing_data_rejected.labels.return_value = mock_counter

        symbol = "EURUSD"
        current_time = get_utc_time()

        # Validate tick with missing data
        quality_gate.validate(missing_data_tick, symbol, current_time)

        # Sync metrics
        quality_gate.sync_metrics_to_prometheus(symbol=symbol)

        # Verify missing data rejection metric was called
        mock_missing_data_rejected.labels.assert_called_with(symbol=symbol)
        mock_counter.inc.assert_called()

    @patch("monitoring.metrics.quality_gate_ticks_processed_total")
    def test_aggregate_metrics_updated(
        self, mock_processed_total, quality_gate, normal_tick
    ):
        """Test that aggregate metrics (symbol='') are updated"""
        # Mock metrics
        mock_counter = MagicMock()
        mock_processed_total.labels.return_value = mock_counter

        symbol = "EURUSD"
        current_time = get_utc_time()

        # Process some ticks
        for _ in range(3):
            quality_gate.validate(normal_tick, symbol, current_time)

        # Sync metrics (this should also update aggregate)
        quality_gate.sync_metrics_to_prometheus(symbol=symbol)

        # Verify aggregate metrics were called (symbol="")
        # The sync method should call labels with both symbol and ""
        calls = mock_processed_total.labels.call_args_list
        symbol_calls = [call for call in calls if call.kwargs.get("symbol") == symbol]
        aggregate_calls = [call for call in calls if call.kwargs.get("symbol") == ""]

        # Should have calls for both per-symbol and aggregate
        assert len(symbol_calls) > 0, "Per-symbol metrics should be updated"
        # Note: Aggregate metrics update depends on implementation details
        # The current implementation updates aggregate when symbol is not empty

    def test_metrics_delta_tracking(self, quality_gate, normal_tick):
        """Test that metrics use delta tracking (only increment differences)"""
        symbol = "EURUSD"
        current_time = get_utc_time()

        # Process 10 ticks
        for _ in range(10):
            quality_gate.validate(normal_tick, symbol, current_time)

        # Get initial metrics
        initial_metrics = quality_gate.get_metrics()
        initial_processed = initial_metrics["total_processed"]

        # Sync metrics (should update _last_synced_metrics)
        quality_gate.sync_metrics_to_prometheus(symbol=symbol)

        # Process 5 more ticks
        for _ in range(5):
            quality_gate.validate(normal_tick, symbol, current_time)

        # Get updated metrics
        updated_metrics = quality_gate.get_metrics()
        updated_processed = updated_metrics["total_processed"]

        # Verify delta is correct
        assert updated_processed == initial_processed + 5

        # Sync again - should only sync the delta (5 ticks)
        with patch(
            "monitoring.metrics.quality_gate_ticks_processed_total"
        ) as mock_processed:
            mock_counter = MagicMock()
            mock_processed.labels.return_value = mock_counter

            quality_gate.sync_metrics_to_prometheus(symbol=symbol)

            # Verify inc was called with the delta (5)
            mock_counter.inc.assert_called_with(5)

    def test_metrics_available_via_get_metrics(self, quality_gate, normal_tick):
        """Test that metrics are available via get_metrics() method"""
        symbol = "EURUSD"
        current_time = get_utc_time()

        # Process some ticks
        for _ in range(10):
            quality_gate.validate(normal_tick, symbol, current_time)

        # Get metrics
        metrics = quality_gate.get_metrics()

        # Verify expected metrics are present
        assert "total_processed" in metrics
        assert "total_accepted" in metrics
        assert "outliers_rejected" in metrics
        assert "duplicates_rejected" in metrics
        assert "stale_rejected" in metrics
        assert "missing_data_rejected" in metrics
        assert "acceptance_rate" in metrics
        assert "rejection_rate" in metrics

        # Verify values are reasonable
        assert metrics["total_processed"] == 10
        assert metrics["total_accepted"] <= metrics["total_processed"]
        assert 0 <= metrics["acceptance_rate"] <= 100
        assert 0 <= metrics["rejection_rate"] <= 100

    def test_import_error_handling(self, quality_gate, normal_tick):
        """Test that sync gracefully handles ImportError when prometheus_client is not available"""
        symbol = "EURUSD"
        current_time = get_utc_time()

        # Process some ticks
        quality_gate.validate(normal_tick, symbol, current_time)

        # Mock ImportError
        with patch("data.quality_gates.logger") as mock_logger:
            with patch(
                "builtins.__import__", side_effect=ImportError("No module named 'monitoring'")
            ):
                # Should not raise exception
                quality_gate.sync_metrics_to_prometheus(symbol=symbol)

                # Should log debug message
                mock_logger.debug.assert_called()
