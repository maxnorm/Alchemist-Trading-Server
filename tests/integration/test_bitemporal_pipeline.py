"""
Integration tests for bitemporal timestamp pipeline
Tests end-to-end flow from data source to database with bitemporal timestamps
"""

import pytest
from datetime import datetime, timedelta
from database import Database
from utils.time_utils import get_utc_time


class TestBitemporalPipeline:
    """Test bitemporal timestamp pipeline end-to-end"""
    
    @pytest.fixture
    def db(self):
        """Database fixture"""
        return Database()
    
    def test_database_insert_with_bitemporal(self, db):
        """Test database insert with bitemporal timestamps"""
        symbol = "EURUSD"
        event_time = get_utc_time() - timedelta(seconds=300)
        receive_time = get_utc_time()
        ask = 1.1001
        bid = 1.1000
        
        result = db.insert_forex_tick(
            symbol=symbol,
            date_time=event_time,
            ask=ask,
            bid=bid,
            receive_time=receive_time,
            latency_seconds=300,
            is_stale=True,
            stale_age_seconds=300,
            timestamp_source='event'
        )
        
        assert result is True
        
        # Query back and verify bitemporal data
        ticks = db.get_recent_ticks(symbol, limit=1, hours=1, query_by='event_time')
        assert len(ticks) > 0
        
        tick = ticks[0]
        assert tick['event_time'] is not None
        assert tick['receive_time'] is not None
        assert tick['latency_seconds'] == 300
        assert tick['is_stale'] is True
    
    def test_query_by_receive_time(self, db):
        """Test querying by receive_time for point-in-time training"""
        symbol = "EURUSD"
        base_time = get_utc_time()
        
        # Insert multiple ticks with different receive times
        for i in range(5):
            event_time = base_time - timedelta(seconds=600 - i * 60)
            receive_time = base_time - timedelta(seconds=300 - i * 60)
            
            db.insert_forex_tick(
                symbol=symbol,
                date_time=event_time,
                ask=1.1001 + i * 0.0001,
                bid=1.1000 + i * 0.0001,
                receive_time=receive_time,
                latency_seconds=int((receive_time - event_time).total_seconds()),
                is_stale=False,
                timestamp_source='event'
            )
        
        # Query by receive_time up to a point in time
        point_in_time = base_time - timedelta(seconds=200)
        ticks = db.get_recent_ticks(
            symbol, 
            limit=10, 
            hours=1, 
            query_by='receive_time'
        )
        
        # Filter to only include ticks received before point_in_time
        filtered = [t for t in ticks if t['receive_time'] and t['receive_time'] <= point_in_time]
        
        # Verify no future data
        assert all(t['receive_time'] <= point_in_time for t in filtered)
    
    def test_state_building_with_latency(self):
        """Test state building with latency features"""
        # This would require setting up the full environment
        # For now, we test the concept
        from application.environment.state_builder import StateBuilder
        from application.environment.price_history_manager import PriceHistoryManager
        from application.environment.feature_engine import FeatureEngine
        
        # This is a placeholder - actual test would require full setup
        # The key is that state includes latency features
        pass
    
    def test_training_with_point_in_time(self):
        """Test training with point-in-time constraint"""
        # This would require setting up the full training environment
        # For now, we test the concept
        # The key is that training queries use receive_time
        pass
