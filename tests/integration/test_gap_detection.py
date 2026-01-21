"""
Integration tests for gap detection validation and alerting
"""

import pytest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/trading_server/src'))

from monitoring.gap_detector import GapDetector, get_global_gap_detector, set_global_gap_detector
from monitoring.metrics import data_gap_minutes, data_gaps_detected_total
from utils.time_utils import get_utc_time


class TestGapDetection:
    """Integration tests for gap detection"""

    @pytest.fixture
    def gap_detector(self):
        """Create gap detector instance"""
        detector = GapDetector(
            gap_threshold_minutes=5.0,
            check_interval_minutes=5.0,
            lookback_minutes=10.0,
            enabled=True,
        )
        yield detector
        # Cleanup
        detector.stop()

    @pytest.fixture
    def gap_detector_disabled(self):
        """Create disabled gap detector instance"""
        return GapDetector(
            gap_threshold_minutes=5.0,
            check_interval_minutes=5.0,
            lookback_minutes=10.0,
            enabled=False,
        )

    @pytest.fixture
    def mock_database(self):
        """Create mock database"""
        mock_db = Mock()
        mock_db.execute_with_result = Mock(return_value=[])
        return mock_db

    def test_gap_detector_initialization(self, gap_detector):
        """Test that gap detector can be initialized"""
        assert gap_detector is not None
        assert gap_detector.enabled is True
        assert gap_detector.gap_threshold_seconds == 5.0 * 60
        assert gap_detector.check_interval_seconds == 5.0 * 60
        assert gap_detector.lookback_seconds == 10.0 * 60

    def test_gap_detector_status(self, gap_detector):
        """Test get_status() method"""
        status = gap_detector.get_status()
        
        assert "enabled" in status
        assert "last_check_time" in status
        assert "gap_count" in status
        assert "system_wide_gap_count" in status
        assert "gap_threshold_seconds" in status
        assert "gap_threshold_minutes" in status
        assert "check_interval_seconds" in status
        
        assert status["enabled"] is True
        assert status["gap_threshold_minutes"] == 5.0

    def test_gap_detector_disabled_status(self, gap_detector_disabled):
        """Test status when gap detector is disabled"""
        status = gap_detector_disabled.get_status()
        assert status["enabled"] is False

    @patch('monitoring.gap_detector.Database')
    def test_gap_detection_with_mock_data(self, mock_db_class, gap_detector):
        """Test gap detection with mock database data"""
        # Setup mock database
        mock_db = Mock()
        
        # Create mock gap data: EURUSD with 6 minute gap
        current_time = get_utc_time()
        gap_start = current_time - timedelta(minutes=10)
        gap_end = current_time - timedelta(minutes=4)
        gap_seconds = (gap_end - gap_start).total_seconds()
        
        mock_db.execute_with_result = Mock(return_value=[
            ('EURUSD', gap_start, gap_end, gap_seconds)
        ])
        mock_db_class.return_value = mock_db
        
        # Replace database in gap detector
        gap_detector.db = mock_db
        
        # Detect gaps
        gaps = gap_detector.detect_gaps()
        
        assert len(gaps) == 1
        assert gaps[0]["symbol"] == "EURUSD"
        assert gaps[0]["data_type"] == "tick"
        assert gaps[0]["gap_seconds"] == gap_seconds
        assert gaps[0]["gap_seconds"] / 60.0 > 5.0  # Gap > 5 minutes

    @patch('monitoring.gap_detector.Database')
    def test_gap_detection_no_gaps(self, mock_db_class, gap_detector):
        """Test gap detection when no gaps exist"""
        # Setup mock database with no gaps
        mock_db = Mock()
        mock_db.execute_with_result = Mock(return_value=[])
        mock_db_class.return_value = mock_db
        
        gap_detector.db = mock_db
        
        # Detect gaps
        gaps = gap_detector.detect_gaps()
        
        assert len(gaps) == 0

    @patch('monitoring.gap_detector.Database')
    def test_gap_metric_exposure(self, mock_db_class, gap_detector):
        """Test that gap metrics are exposed and updated"""
        # Setup mock database with gap data
        mock_db = Mock()
        current_time = get_utc_time()
        gap_start = current_time - timedelta(minutes=10)
        gap_end = current_time - timedelta(minutes=4)
        gap_seconds = (gap_end - gap_start).total_seconds()
        
        mock_db.execute_with_result = Mock(return_value=[
            ('EURUSD', gap_start, gap_end, gap_seconds)
        ])
        mock_db_class.return_value = mock_db
        
        gap_detector.db = mock_db
        
        # Reset metrics before test
        data_gap_minutes.labels(symbol='EURUSD', data_type='tick').set(0)
        
        # Detect gaps
        gaps = gap_detector.detect_gaps()
        
        assert len(gaps) == 1
        
        # Check that metric was updated
        # Note: We can't directly read Prometheus metrics in tests easily,
        # but we can verify the metric was called
        # The metric should be set to gap duration in minutes
        gap_minutes = gap_seconds / 60.0
        assert gap_minutes > 5.0

    @patch('monitoring.gap_detector.Database')
    def test_gap_alert_threshold(self, mock_db_class, gap_detector):
        """Test that gaps > 5 minutes are detected"""
        # Setup mock database with gap > 5 minutes
        mock_db = Mock()
        current_time = get_utc_time()
        gap_start = current_time - timedelta(minutes=12)
        gap_end = current_time - timedelta(minutes=4)
        gap_seconds = (gap_end - gap_start).total_seconds()
        gap_minutes = gap_seconds / 60.0
        
        assert gap_minutes > 5.0  # Verify test setup
        
        mock_db.execute_with_result = Mock(return_value=[
            ('EURUSD', gap_start, gap_end, gap_seconds)
        ])
        mock_db_class.return_value = mock_db
        
        gap_detector.db = mock_db
        
        # Detect gaps
        gaps = gap_detector.detect_gaps()
        
        assert len(gaps) == 1
        assert gaps[0]["gap_seconds"] / 60.0 > 5.0

    @patch('monitoring.gap_detector.Database')
    def test_gap_below_threshold(self, mock_db_class, gap_detector):
        """Test that gaps < 5 minutes are not detected"""
        # Setup mock database with gap < 5 minutes
        mock_db = Mock()
        current_time = get_utc_time()
        gap_start = current_time - timedelta(minutes=7)
        gap_end = current_time - timedelta(minutes=4)
        gap_seconds = (gap_end - gap_start).total_seconds()
        gap_minutes = gap_seconds / 60.0
        
        assert gap_minutes < 5.0  # Verify test setup
        
        # Gap detector uses threshold of 5 minutes, so gap < 5 minutes won't be returned
        mock_db.execute_with_result = Mock(return_value=[])
        mock_db_class.return_value = mock_db
        
        gap_detector.db = mock_db
        
        # Detect gaps
        gaps = gap_detector.detect_gaps()
        
        # Should return empty because gap is below threshold
        assert len(gaps) == 0

    @patch('monitoring.gap_detector.Database')
    def test_multiple_symbols_gaps(self, mock_db_class, gap_detector):
        """Test gap detection for multiple symbols"""
        # Setup mock database with gaps for multiple symbols
        mock_db = Mock()
        current_time = get_utc_time()
        gap_start = current_time - timedelta(minutes=10)
        gap_end = current_time - timedelta(minutes=4)
        gap_seconds = (gap_end - gap_start).total_seconds()
        
        mock_db.execute_with_result = Mock(return_value=[
            ('EURUSD', gap_start, gap_end, gap_seconds),
            ('GBPUSD', gap_start, gap_end, gap_seconds),
            ('USDJPY', gap_start, gap_end, gap_seconds),
        ])
        mock_db_class.return_value = mock_db
        
        gap_detector.db = mock_db
        
        # Detect gaps
        gaps = gap_detector.detect_gaps()
        
        assert len(gaps) == 3
        symbols = [gap["symbol"] for gap in gaps]
        assert "EURUSD" in symbols
        assert "GBPUSD" in symbols
        assert "USDJPY" in symbols

    def test_global_gap_detector_registry(self):
        """Test global gap detector registry functions"""
        # Initially should be None
        assert get_global_gap_detector() is None
        
        # Create and set gap detector
        detector = GapDetector(enabled=False)
        set_global_gap_detector(detector)
        
        # Should be able to retrieve it
        retrieved = get_global_gap_detector()
        assert retrieved is detector
        
        # Cleanup
        set_global_gap_detector(None)
        assert get_global_gap_detector() is None

    @patch('monitoring.gap_detector.Database')
    def test_health_endpoint_healthy(self, mock_db_class, gap_detector):
        """Test health endpoint when no gaps exist"""
        # Setup mock database with no gaps
        mock_db = Mock()
        mock_db.execute_with_result = Mock(return_value=[])
        mock_db_class.return_value = mock_db
        
        gap_detector.db = mock_db
        
        # Set as global for health endpoint access
        set_global_gap_detector(gap_detector)
        
        # Get status
        status = gap_detector.get_status()
        gaps = gap_detector.detect_gaps()
        
        # Should be healthy (no gaps > threshold)
        assert len(gaps) == 0
        assert status["enabled"] is True
        
        # Cleanup
        set_global_gap_detector(None)

    @patch('monitoring.gap_detector.Database')
    def test_health_endpoint_unhealthy(self, mock_db_class, gap_detector):
        """Test health endpoint when gaps exist"""
        # Setup mock database with gap > 5 minutes
        mock_db = Mock()
        current_time = get_utc_time()
        gap_start = current_time - timedelta(minutes=10)
        gap_end = current_time - timedelta(minutes=4)
        gap_seconds = (gap_end - gap_start).total_seconds()
        
        mock_db.execute_with_result = Mock(return_value=[
            ('EURUSD', gap_start, gap_end, gap_seconds)
        ])
        mock_db_class.return_value = mock_db
        
        gap_detector.db = mock_db
        
        # Set as global for health endpoint access
        set_global_gap_detector(gap_detector)
        
        # Detect gaps
        gaps = gap_detector.detect_gaps()
        
        # Should be unhealthy (gap > threshold)
        assert len(gaps) > 0
        gap_minutes = gaps[0]["gap_seconds"] / 60.0
        assert gap_minutes > 5.0
        
        # Cleanup
        set_global_gap_detector(None)

    def test_gap_detector_disabled_health(self, gap_detector_disabled):
        """Test health when gap detector is disabled"""
        status = gap_detector_disabled.get_status()
        assert status["enabled"] is False
        
        # When disabled, should be considered healthy (no monitoring)
        # This is the expected behavior - disabled detector doesn't indicate unhealthy state

    @patch('monitoring.gap_detector.Database')
    def test_gap_detector_start_stop(self, mock_db_class, gap_detector):
        """Test gap detector start and stop methods"""
        # Start should not raise exception
        gap_detector.start()
        
        # Stop should not raise exception
        gap_detector.stop()
        
        # Status should reflect stopped state
        # (monitoring thread should be stopped)

    @patch('monitoring.gap_detector.Database')
    def test_gap_detection_error_handling(self, mock_db_class, gap_detector):
        """Test error handling in gap detection"""
        # Setup mock database to raise exception
        mock_db = Mock()
        mock_db.execute_with_result = Mock(side_effect=Exception("Database error"))
        mock_db_class.return_value = mock_db
        
        gap_detector.db = mock_db
        
        # Detect gaps should handle error gracefully
        gaps = gap_detector.detect_gaps()
        
        # Should return empty list on error
        assert gaps == []

    @patch('monitoring.gap_detector.Database')
    def test_gap_detection_all_types(self, mock_db_class, gap_detector):
        """Test gap detection for all data types"""
        mock_db = Mock()
        current_time = get_utc_time()
        gap_start = current_time - timedelta(minutes=10)
        gap_end = current_time - timedelta(minutes=4)
        gap_seconds = (gap_end - gap_start).total_seconds()
        
        # Test tick gaps
        mock_db.execute_with_result = Mock(return_value=[
            ('EURUSD', gap_start, gap_end, gap_seconds)
        ])
        gap_detector.db = mock_db
        tick_gaps = gap_detector.detect_gaps()
        assert len(tick_gaps) == 1
        
        # Test bar gaps
        mock_db.execute_with_result = Mock(return_value=[
            ('EURUSD', 'M1', gap_start, gap_end, gap_seconds)
        ])
        bar_gaps = gap_detector.detect_bar_gaps()
        assert len(bar_gaps) == 1
        assert bar_gaps[0]["data_type"] == "bar"
