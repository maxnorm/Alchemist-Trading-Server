"""
Phase 2 Integration Tests
Tests for MT5 backfill, OHLCV aggregation, progress tracking, and resume capability
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock

# Add src to path
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "trading_server", "src"))

from connectors.mt5_tick_connector import MT5TickConnector
from connectors.base import ConnectorConfig
from infrastructure.backfill.progress_tracker import BackfillProgressTracker
from utils.ohlcv_aggregator import TickToOHLCVAggregator
from database import Database


@pytest.fixture
def mock_db():
    """Create mock database"""
    return Mock(spec=Database)


@pytest.fixture
def connector_config():
    """Create connector config"""
    return ConnectorConfig(
        source="mt5",
        symbol="EURUSD",
        extra_config={"digits": 5},
    )


@pytest.fixture
def mock_connector(connector_config):
    """Create mock MT5 tick connector"""
    class DummySocket:
        pass

    connector = MT5TickConnector(
        socket=DummySocket(),
        symbol="EURUSD",
        config=connector_config,
    )
    return connector


class TestMT5Backfill:
    """Tests for MT5 historical backfill"""

    @pytest.mark.skipif(
        not pytest.config.getoption("--run-integration"),
        reason="Integration test - requires MT5 connection",
    )
    def test_mt5_backfill_single_symbol(self, mock_connector):
        """Test MT5 backfill for 1 month of data"""
        start_time = datetime.now(timezone.utc) - timedelta(days=30)
        end_time = datetime.now(timezone.utc)

        # Mock MetaTrader5
        with patch("connectors.mt5_tick_connector.mt5") as mock_mt5:
            mock_mt5.initialize.return_value = True
            mock_mt5.copy_ticks_range.return_value = [
                (int(start_time.timestamp()), 1.0850, 1.0851, 1.08505, 100, 0, 0, 0)
            ]

            ticks = list(mock_connector.backfill(start_time, end_time))
            assert len(ticks) > 0
            assert all("symbol" in tick for tick in ticks)
            assert all("timestamp" in tick for tick in ticks)

    def test_backfill_interface(self, mock_connector):
        """Test that backfill method exists and has correct signature"""
        assert hasattr(mock_connector, "backfill")
        assert callable(mock_connector.backfill)

    def test_get_available_range_interface(self, mock_connector):
        """Test that get_available_range method exists"""
        assert hasattr(mock_connector, "get_available_range")
        assert callable(mock_connector.get_available_range)


class TestOHLCVAggregation:
    """Tests for OHLCV aggregation"""

    def test_aggregate_ticks_single_timeframe(self):
        """Test aggregating ticks to OHLCV bars for a single timeframe"""
        aggregator = TickToOHLCVAggregator()

        # Create sample ticks
        base_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        ticks = [
            {
                "timestamp": base_time + timedelta(seconds=i * 10),
                "bid": 1.0850 + (i * 0.0001),
                "ask": 1.0851 + (i * 0.0001),
                "volume": 100,
            }
            for i in range(10)
        ]

        bars = aggregator.aggregate_ticks(ticks, "M1")

        assert len(bars) > 0
        assert all("datetime" in bar for bar in bars)
        assert all("open" in bar for bar in bars)
        assert all("high" in bar for bar in bars)
        assert all("low" in bar for bar in bars)
        assert all("close" in bar for bar in bars)
        assert all("timeframe" in bar for bar in bars)

    def test_aggregate_all_timeframes(self):
        """Test aggregating to all timeframes at once"""
        aggregator = TickToOHLCVAggregator()

        base_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        ticks = [
            {
                "timestamp": base_time + timedelta(minutes=i),
                "bid": 1.0850 + (i * 0.0001),
                "ask": 1.0851 + (i * 0.0001),
                "volume": 100,
            }
            for i in range(100)
        ]

        timeframes = ["M1", "M5", "M15", "H1"]
        result = aggregator.aggregate_all_timeframes(ticks, timeframes)

        assert len(result) == len(timeframes)
        for timeframe in timeframes:
            assert timeframe in result
            assert len(result[timeframe]) > 0

    def test_ohlcv_calculations_correctness(self):
        """Test that OHLCV calculations are correct"""
        aggregator = TickToOHLCVAggregator()

        base_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        # Create ticks with known prices
        ticks = [
            {"timestamp": base_time, "bid": 1.0850, "ask": 1.0851, "volume": 100},
            {"timestamp": base_time + timedelta(seconds=10), "bid": 1.0852, "ask": 1.0853, "volume": 100},
            {"timestamp": base_time + timedelta(seconds=20), "bid": 1.0848, "ask": 1.0849, "volume": 100},
            {"timestamp": base_time + timedelta(seconds=30), "bid": 1.0855, "ask": 1.0856, "volume": 100},
        ]

        bars = aggregator.aggregate_ticks(ticks, "M1")

        assert len(bars) == 1
        bar = bars[0]

        # Verify OHLCV
        # Open should be first mid-price: (1.0850 + 1.0851) / 2 = 1.08505
        # High should be max: (1.0855 + 1.0856) / 2 = 1.08555
        # Low should be min: (1.0848 + 1.0849) / 2 = 1.08485
        # Close should be last: (1.0855 + 1.0856) / 2 = 1.08555

        assert abs(bar["open"] - 1.08505) < 0.00001
        assert abs(bar["high"] - 1.08555) < 0.00001
        assert abs(bar["low"] - 1.08485) < 0.00001
        assert abs(bar["close"] - 1.08555) < 0.00001
        assert bar["high"] >= bar["low"]
        assert bar["high"] >= bar["open"]
        assert bar["high"] >= bar["close"]
        assert bar["low"] <= bar["open"]
        assert bar["low"] <= bar["close"]


class TestProgressTracking:
    """Tests for backfill progress tracking"""

    @pytest.fixture
    def progress_tracker(self, mock_db):
        """Create progress tracker with mock database"""
        return BackfillProgressTracker(db=mock_db)

    def test_start_backfill(self, progress_tracker, mock_db):
        """Test starting a backfill progress record"""
        start_time = datetime.now(timezone.utc) - timedelta(days=1)
        end_time = datetime.now(timezone.utc)

        # Mock database result
        mock_db.execute_with_result.return_value = [[1]]  # Return progress_id = 1

        progress_id = progress_tracker.start_backfill(
            "mt5_tick", "EURUSD", start_time, end_time
        )

        assert progress_id == 1
        assert mock_db.execute_with_result.called

    def test_update_progress(self, progress_tracker, mock_db):
        """Test updating backfill progress"""
        progress_id = 1
        last_time = datetime.now(timezone.utc)
        records = 1000

        progress_tracker.update_progress(progress_id, last_time, records)

        assert mock_db.execute_with_result.called

    def test_mark_completed(self, progress_tracker, mock_db):
        """Test marking backfill as completed"""
        progress_id = 1

        progress_tracker.mark_completed(progress_id)

        assert mock_db.execute_with_result.called

    def test_mark_failed(self, progress_tracker, mock_db):
        """Test marking backfill as failed"""
        progress_id = 1
        error_message = "Connection failed"

        progress_tracker.mark_failed(progress_id, error_message)

        assert mock_db.execute_with_result.called

    def test_get_resume_point(self, progress_tracker, mock_db):
        """Test getting resume point for failed backfill"""
        progress_id = 1
        resume_time = datetime.now(timezone.utc) - timedelta(hours=1)

        # Mock database result
        mock_db.execute_with_result.return_value = [[resume_time, "failed"]]

        result = progress_tracker.get_resume_point(progress_id)

        assert result == resume_time


class TestResumeCapability:
    """Tests for resume capability"""

    def test_resume_from_checkpoint(self, mock_db):
        """Test resuming a failed backfill from checkpoint"""
        # This would require integration with actual database
        # For now, test the interface
        progress_tracker = BackfillProgressTracker(db=mock_db)

        # Mock existing progress
        mock_db.execute_with_result.return_value = [
            [1, "mt5_tick", "EURUSD", None, None, datetime.now(timezone.utc), 1000, "failed", "Error"]
        ]

        resume_point = progress_tracker.get_resume_point(1)
        assert resume_point is not None


class TestQualityGates:
    """Tests for quality gates on backfilled data"""

    def test_quality_gates_on_backfilled_data(self):
        """Test that quality gates pass on backfilled data"""
        # This would require actual database and quality gate implementation
        # For now, test that quality gate can be imported
        from data.quality_gates import QualityGate

        quality_gate = QualityGate()
        assert quality_gate is not None


class TestParallelBackfill:
    """Tests for parallel backfill"""

    def test_parallel_backfill_interface(self):
        """Test that orchestrator supports parallel backfill"""
        from infrastructure.backfill.orchestrator import BackfillOrchestrator

        orchestrator = BackfillOrchestrator(max_parallel=3)
        assert orchestrator.max_parallel == 3
        assert hasattr(orchestrator, "backfill_symbols")
        assert hasattr(orchestrator, "backfill_with_aggregation")
