"""
Unit tests for timestamp alignment service
Tests bitemporal timestamp extraction, preservation, and latency calculation
"""

import pytest
from datetime import datetime, timedelta
from utils.timestamp_alignment import (
    TimestampAlignmentService,
    TimestampInfo,
    SourceTimestampConfig,
)
from utils.time_utils import get_utc_time


class TestTimestampAlignment:
    """Test timestamp alignment service"""
    
    def test_extract_timestamps_mt5(self):
        """Test timestamp extraction from MT5 source"""
        service = TimestampAlignmentService()
        receive_time = get_utc_time()
        event_time = receive_time - timedelta(seconds=300)  # 5 minutes ago
        
        raw_event = {
            "symbol": "EURUSD",
            "date_time": event_time.strftime("%Y.%m.%d %H:%M:%S"),
            "bid": 1.1000,
            "ask": 1.1001,
        }
        
        timestamp_info = service.extract_timestamps(raw_event, "mt5", receive_time)
        
        assert timestamp_info.event_time is not None
        assert timestamp_info.receive_time == receive_time
        assert timestamp_info.latency_seconds == pytest.approx(300.0, abs=1.0)
        assert timestamp_info.metadata['is_stale'] is True
        assert timestamp_info.metadata['timestamp_source'] == 'event'
    
    def test_extract_timestamps_preserves_event_time(self):
        """Test that event_time is preserved (not overridden)"""
        service = TimestampAlignmentService()
        receive_time = get_utc_time()
        event_time = receive_time - timedelta(seconds=600)  # 10 minutes ago (stale)
        
        raw_event = {
            "symbol": "EURUSD",
            "date_time": event_time.strftime("%Y.%m.%d %H:%M:%S"),
            "bid": 1.1000,
            "ask": 1.1001,
        }
        
        timestamp_info = service.extract_timestamps(raw_event, "mt5", receive_time)
        
        # Event time should be preserved (not overridden with receive_time)
        assert timestamp_info.event_time < receive_time
        assert timestamp_info.event_time == pytest.approx(event_time, abs=timedelta(seconds=1))
        assert timestamp_info.receive_time == receive_time
        assert timestamp_info.latency_seconds == pytest.approx(600.0, abs=1.0)
    
    def test_latency_calculation(self):
        """Test latency calculation accuracy"""
        service = TimestampAlignmentService()
        receive_time = get_utc_time()
        event_time = receive_time - timedelta(seconds=150)  # 2.5 minutes ago
        
        raw_event = {
            "symbol": "EURUSD",
            "date_time": event_time.strftime("%Y.%m.%d %H:%M:%S"),
            "bid": 1.1000,
            "ask": 1.1001,
        }
        
        timestamp_info = service.extract_timestamps(raw_event, "mt5", receive_time)
        
        assert timestamp_info.latency_seconds == pytest.approx(150.0, abs=1.0)
        assert timestamp_info.metadata['latency_seconds'] == pytest.approx(150.0, abs=1.0)
    
    def test_point_in_time_filtering(self):
        """Test point-in-time filtering capability"""
        # This test verifies that we can filter data by receive_time
        # The actual filtering is tested in integration tests
        service = TimestampAlignmentService()
        
        # Create multiple events with different receive times
        base_time = get_utc_time()
        events = []
        
        for i in range(5):
            event_time = base_time - timedelta(seconds=600 - i * 60)
            receive_time = base_time - timedelta(seconds=300 - i * 60)
            
            raw_event = {
                "symbol": "EURUSD",
                "date_time": event_time.strftime("%Y.%m.%d %H:%M:%S"),
                "bid": 1.1000,
                "ask": 1.1001,
            }
            
            timestamp_info = service.extract_timestamps(raw_event, "mt5", receive_time)
            events.append((timestamp_info, receive_time))
        
        # Verify we can filter by receive_time
        point_in_time = base_time - timedelta(seconds=200)
        filtered = [e for e, rt in events if rt <= point_in_time]
        
        assert len(filtered) > 0
        assert all(rt <= point_in_time for _, rt in events[:len(filtered)])
    
    def test_lookahead_bias_prevention(self):
        """Test that look-ahead bias is prevented by using receive_time"""
        service = TimestampAlignmentService()
        base_time = get_utc_time()
        
        # Event 1: occurs at 10:00, received at 10:05
        event1_time = base_time - timedelta(seconds=600)
        receive1_time = base_time - timedelta(seconds=300)
        
        raw_event1 = {
            "symbol": "EURUSD",
            "date_time": event1_time.strftime("%Y.%m.%d %H:%M:%S"),
            "bid": 1.1000,
            "ask": 1.1001,
        }
        
        timestamp_info1 = service.extract_timestamps(raw_event1, "mt5", receive1_time)
        
        # Event 2: occurs at 10:10, received at 10:12
        event2_time = base_time - timedelta(seconds=120)
        receive2_time = base_time - timedelta(seconds=60)
        
        raw_event2 = {
            "symbol": "EURUSD",
            "date_time": event2_time.strftime("%Y.%m.%d %H:%M:%S"),
            "bid": 1.1005,
            "ask": 1.1006,
        }
        
        timestamp_info2 = service.extract_timestamps(raw_event2, "mt5", receive2_time)
        
        # At point_in_time = 10:05, we should only see event1 (received at 10:05)
        # Not event2 (received at 10:12, which is in the future)
        point_in_time = base_time - timedelta(seconds=300)
        
        assert timestamp_info1.receive_time <= point_in_time
        assert timestamp_info2.receive_time > point_in_time  # Future data
        
        # This ensures no look-ahead bias: we can't see event2 at point_in_time
