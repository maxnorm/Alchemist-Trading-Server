"""
Integration tests for data quality gates
"""

import pytest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/mt5-python_server/src'))

from data.quality_gates import QualityGate
from utils.time_utils import get_utc_time


class TestDataQualityGates:
    """Integration tests for data quality gates"""

    @pytest.fixture
    def quality_gate(self):
        """Create quality gate instance"""
        return QualityGate()

    @pytest.fixture
    def quality_gate_custom(self):
        """Create quality gate with custom config"""
        return QualityGate(config={
            'outlier_z_threshold': 2.0,
            'staleness_threshold_seconds': 60,
            'duplicate_tolerance_seconds': 0.5,
        })

    @pytest.fixture
    def normal_tick(self):
        """Create a normal valid tick"""
        current_time = get_utc_time()
        return {
            'symbol': 'EURUSD',
            'datetime': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'ask': 1.1000,
            'bid': 1.0999,
        }

    def test_outlier_detection_price_too_high(self, quality_gate):
        """Test outlier detection with price 10x normal"""
        # Build up history with normal prices
        current_time = get_utc_time()
        symbol = 'EURUSD'
        normal_price = 1.1000
        
        # Add 20 normal ticks to build history
        for i in range(20):
            tick = {
                'symbol': symbol,
                'datetime': (current_time - timedelta(seconds=20-i)).strftime('%Y-%m-%d %H:%M:%S'),
                'ask': normal_price + 0.0001 * i,
                'bid': normal_price + 0.0001 * i - 0.0001,
            }
            is_valid, reason = quality_gate.validate(tick, symbol, current_time)
            assert is_valid, f"Normal tick should be accepted: {reason}"
        
        # Now test with outlier (10x normal price)
        outlier_tick = {
            'symbol': symbol,
            'datetime': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'ask': normal_price * 10,  # 10x normal
            'bid': normal_price * 10 - 0.0001,
        }
        is_valid, reason = quality_gate.validate(outlier_tick, symbol, current_time)
        assert not is_valid, "Outlier tick should be rejected"
        assert 'outlier' in reason.lower() or 'bid' in reason.lower() or 'ask' in reason.lower()

    def test_outlier_detection_normal_price(self, quality_gate):
        """Test that normal price is accepted"""
        current_time = get_utc_time()
        symbol = 'EURUSD'
        
        # Build history
        for i in range(20):
            tick = {
                'symbol': symbol,
                'datetime': (current_time - timedelta(seconds=20-i)).strftime('%Y-%m-%d %H:%M:%S'),
                'ask': 1.1000 + 0.0001 * i,
                'bid': 1.1000 + 0.0001 * i - 0.0001,
            }
            quality_gate.validate(tick, symbol, current_time)
        
        # Normal tick should be accepted
        normal_tick = {
            'symbol': symbol,
            'datetime': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'ask': 1.1000,
            'bid': 1.0999,
        }
        is_valid, reason = quality_gate.validate(normal_tick, symbol, current_time)
        assert is_valid, f"Normal tick should be accepted: {reason}"

    def test_outlier_detection_spread_too_wide(self, quality_gate):
        """Test that spread > 10 pips is rejected"""
        current_time = get_utc_time()
        symbol = 'EURUSD'
        
        # Build history
        for i in range(20):
            tick = {
                'symbol': symbol,
                'datetime': (current_time - timedelta(seconds=20-i)).strftime('%Y-%m-%d %H:%M:%S'),
                'ask': 1.1000 + 0.0001 * i,
                'bid': 1.1000 + 0.0001 * i - 0.0001,
            }
            quality_gate.validate(tick, symbol, current_time)
        
        # Tick with unrealistic spread (> 0.001 / 10 pips)
        wide_spread_tick = {
            'symbol': symbol,
            'datetime': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'ask': 1.1000,
            'bid': 1.0990,  # 10 pips spread = 0.0010
        }
        is_valid, reason = quality_gate.validate(wide_spread_tick, symbol, current_time)
        # Should reject due to unrealistic spread
        assert not is_valid, "Wide spread tick should be rejected"
        assert 'spread' in reason.lower()

    def test_duplicate_detection_identical_timestamp(self, quality_gate):
        """Test duplicate detection with identical timestamp"""
        current_time = get_utc_time()
        symbol = 'EURUSD'
        
        # First tick
        tick1 = {
            'symbol': symbol,
            'datetime': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'ask': 1.1000,
            'bid': 1.0999,
        }
        is_valid, reason = quality_gate.validate(tick1, symbol, current_time)
        assert is_valid, f"First tick should be accepted: {reason}"
        
        # Duplicate tick with same timestamp
        tick2 = {
            'symbol': symbol,
            'datetime': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'ask': 1.1001,
            'bid': 1.1000,
        }
        is_valid, reason = quality_gate.validate(tick2, symbol, current_time)
        assert not is_valid, "Duplicate tick should be rejected"
        assert 'duplicate' in reason.lower()

    def test_duplicate_detection_different_timestamps(self, quality_gate):
        """Test that different timestamps are accepted"""
        current_time = get_utc_time()
        symbol = 'EURUSD'
        
        # First tick
        tick1 = {
            'symbol': symbol,
            'datetime': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'ask': 1.1000,
            'bid': 1.0999,
        }
        is_valid, reason = quality_gate.validate(tick1, symbol, current_time)
        assert is_valid, f"First tick should be accepted: {reason}"
        
        # Second tick with different timestamp (2 seconds later)
        tick2 = {
            'symbol': symbol,
            'datetime': (current_time + timedelta(seconds=2)).strftime('%Y-%m-%d %H:%M:%S'),
            'ask': 1.1001,
            'bid': 1.1000,
        }
        is_valid, reason = quality_gate.validate(tick2, symbol, current_time + timedelta(seconds=2))
        assert is_valid, f"Different timestamp tick should be accepted: {reason}"

    def test_duplicate_detection_within_tolerance(self, quality_gate_custom):
        """Test duplicate detection within tolerance window"""
        current_time = get_utc_time()
        symbol = 'EURUSD'
        # Custom config has duplicate_tolerance_seconds = 0.5
        
        # First tick
        tick1 = {
            'symbol': symbol,
            'datetime': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'ask': 1.1000,
            'bid': 1.0999,
        }
        is_valid, reason = quality_gate_custom.validate(tick1, symbol, current_time)
        assert is_valid, f"First tick should be accepted: {reason}"
        
        # Second tick within tolerance (0.3 seconds later)
        tick2 = {
            'symbol': symbol,
            'datetime': (current_time + timedelta(seconds=0.3)).strftime('%Y-%m-%d %H:%M:%S'),
            'ask': 1.1001,
            'bid': 1.1000,
        }
        is_valid, reason = quality_gate_custom.validate(tick2, symbol, current_time + timedelta(seconds=0.3))
        assert not is_valid, "Tick within tolerance should be rejected as duplicate"
        assert 'duplicate' in reason.lower()

    def test_staleness_detection_old_tick(self, quality_gate):
        """Test staleness detection with old tick"""
        current_time = get_utc_time()
        symbol = 'EURUSD'
        
        # Tick older than threshold (300 seconds)
        old_tick = {
            'symbol': symbol,
            'datetime': (current_time - timedelta(seconds=400)).strftime('%Y-%m-%d %H:%M:%S'),
            'ask': 1.1000,
            'bid': 1.0999,
        }
        is_valid, reason = quality_gate.validate(old_tick, symbol, current_time)
        assert not is_valid, "Old tick should be rejected"
        assert 'stale' in reason.lower()

    def test_staleness_detection_recent_tick(self, quality_gate):
        """Test that recent tick is accepted"""
        current_time = get_utc_time()
        symbol = 'EURUSD'
        
        # Recent tick (10 seconds ago)
        recent_tick = {
            'symbol': symbol,
            'datetime': (current_time - timedelta(seconds=10)).strftime('%Y-%m-%d %H:%M:%S'),
            'ask': 1.1000,
            'bid': 1.0999,
        }
        is_valid, reason = quality_gate.validate(recent_tick, symbol, current_time)
        assert is_valid, f"Recent tick should be accepted: {reason}"

    def test_staleness_detection_at_threshold_boundary(self, quality_gate):
        """Test staleness at threshold boundary"""
        current_time = get_utc_time()
        symbol = 'EURUSD'
        
        # Tick exactly at threshold (300 seconds)
        boundary_tick = {
            'symbol': symbol,
            'datetime': (current_time - timedelta(seconds=300)).strftime('%Y-%m-%d %H:%M:%S'),
            'ask': 1.1000,
            'bid': 1.0999,
        }
        is_valid, reason = quality_gate.validate(boundary_tick, symbol, current_time)
        # At threshold should be accepted (not > threshold)
        assert is_valid, f"Tick at threshold should be accepted: {reason}"

    def test_missing_data_missing_symbol(self, quality_gate):
        """Test missing symbol rejection"""
        current_time = get_utc_time()
        
        tick = {
            'datetime': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'ask': 1.1000,
            'bid': 1.0999,
        }
        is_valid, reason = quality_gate.validate(tick, '', current_time)
        assert not is_valid, "Tick without symbol should be rejected"
        assert 'symbol' in reason.lower()

    def test_missing_data_missing_ask(self, quality_gate):
        """Test missing ask price rejection"""
        current_time = get_utc_time()
        symbol = 'EURUSD'
        
        tick = {
            'symbol': symbol,
            'datetime': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'bid': 1.0999,
        }
        is_valid, reason = quality_gate.validate(tick, symbol, current_time)
        assert not is_valid, "Tick without ask should be rejected"
        assert 'ask' in reason.lower()

    def test_missing_data_missing_bid(self, quality_gate):
        """Test missing bid price rejection"""
        current_time = get_utc_time()
        symbol = 'EURUSD'
        
        tick = {
            'symbol': symbol,
            'datetime': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'ask': 1.1000,
        }
        is_valid, reason = quality_gate.validate(tick, symbol, current_time)
        assert not is_valid, "Tick without bid should be rejected"
        assert 'bid' in reason.lower()

    def test_missing_data_none_values(self, quality_gate):
        """Test None values rejection"""
        current_time = get_utc_time()
        symbol = 'EURUSD'
        
        tick = {
            'symbol': symbol,
            'datetime': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'ask': None,
            'bid': 1.0999,
        }
        is_valid, reason = quality_gate.validate(tick, symbol, current_time)
        assert not is_valid, "Tick with None ask should be rejected"
        assert 'ask' in reason.lower()

    def test_metrics_tracking(self, quality_gate):
        """Test that metrics are tracked correctly"""
        current_time = get_utc_time()
        symbol = 'EURUSD'
        
        # Process some valid ticks
        for i in range(5):
            tick = {
                'symbol': symbol,
                'datetime': (current_time - timedelta(seconds=5-i)).strftime('%Y-%m-%d %H:%M:%S'),
                'ask': 1.1000 + 0.0001 * i,
                'bid': 1.1000 + 0.0001 * i - 0.0001,
            }
            quality_gate.validate(tick, symbol, current_time)
        
        # Process a rejected tick (stale)
        stale_tick = {
            'symbol': symbol,
            'datetime': (current_time - timedelta(seconds=400)).strftime('%Y-%m-%d %H:%M:%S'),
            'ask': 1.1000,
            'bid': 1.0999,
        }
        quality_gate.validate(stale_tick, symbol, current_time)
        
        metrics = quality_gate.get_metrics()
        assert metrics['total_processed'] == 6
        assert metrics['total_accepted'] == 5
        assert metrics['stale_rejected'] == 1
        assert metrics['acceptance_rate'] > 0

    def test_integration_with_tick_streamer_flow(self, quality_gate):
        """Test QualityGate with actual tick streamer-like flow"""
        current_time = get_utc_time()
        symbol = 'EURUSD'
        
        # Simulate tick streamer flow
        ticks = [
            {
                'symbol': symbol,
                'datetime': (current_time - timedelta(seconds=10-i)).strftime('%Y-%m-%d %H:%M:%S'),
                'ask': 1.1000 + 0.0001 * i,
                'bid': 1.1000 + 0.0001 * i - 0.0001,
            }
            for i in range(10)
        ]
        
        accepted_count = 0
        rejected_count = 0
        
        for tick in ticks:
            is_valid, reason = quality_gate.validate(tick, symbol, current_time)
            if is_valid:
                accepted_count += 1
            else:
                rejected_count += 1
        
        assert accepted_count > 0, "Some ticks should be accepted"
        metrics = quality_gate.get_metrics()
        assert metrics['total_processed'] == 10
        assert metrics['total_accepted'] == accepted_count

    def test_mt5_timestamp_format(self, quality_gate):
        """Test that MT5 timestamp format is supported"""
        current_time = get_utc_time()
        symbol = 'EURUSD'
        
        # MT5 format: "YYYY.MM.DD HH:MM:SS"
        mt5_tick = {
            'symbol': symbol,
            'datetime': current_time.strftime('%Y.%m.%d %H:%M:%S'),  # MT5 format
            'ask': 1.1000,
            'bid': 1.0999,
        }
        is_valid, reason = quality_gate.validate(mt5_tick, symbol, current_time)
        assert is_valid, f"MT5 format tick should be accepted: {reason}"

    def test_mt5_timestamp_format_with_milliseconds(self, quality_gate):
        """Test that MT5 timestamp format with milliseconds is supported"""
        current_time = get_utc_time()
        symbol = 'EURUSD'
        
        # MT5 format with milliseconds: "YYYY.MM.DD HH:MM:SS.mmm"
        # Format the timestamp with milliseconds
        time_str = current_time.strftime('%Y.%m.%d %H:%M:%S')
        milliseconds = current_time.microsecond // 1000  # Convert microseconds to milliseconds
        mt5_tick_with_msc = {
            'symbol': symbol,
            'datetime': f"{time_str}.{milliseconds:03d}",  # MT5 format with milliseconds
            'ask': 1.1000,
            'bid': 1.0999,
        }
        is_valid, reason = quality_gate.validate(mt5_tick_with_msc, symbol, current_time)
        assert is_valid, f"MT5 format with milliseconds tick should be accepted: {reason}"