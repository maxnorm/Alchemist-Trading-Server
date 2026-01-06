"""
Integration tests for quarantine flow
Tests end-to-end quarantine functionality including quality gate rejection,
database storage, API queries, and metrics
"""

import pytest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/mt5-python_server/src'))

from database import Database
from data.quality_gates import QualityGate
from utils.time_utils import get_utc_time


class TestQuarantineFlow:
    """Test end-to-end quarantine flow"""
    
    @pytest.fixture
    def db(self):
        """Database fixture"""
        return Database()
    
    @pytest.fixture
    def quality_gate(self):
        """Quality gate fixture"""
        return QualityGate()
    
    def test_quality_gate_rejection_quarantines_tick(self, db, quality_gate):
        """Test that rejected ticks are quarantined"""
        symbol = "EURUSD"
        current_time = get_utc_time()
        
        # Create an invalid tick (bid > ask)
        invalid_tick = {
            "symbol": symbol,
            "datetime": current_time - timedelta(seconds=10),
            "ask": 1.0999,  # ask < bid (invalid)
            "bid": 1.1000,
        }
        
        # Validate tick (should be rejected)
        is_valid, rejection_reason, _ = quality_gate.validate(
            invalid_tick, symbol, current_time
        )
        
        assert is_valid is False
        assert rejection_reason is not None
        
        # Insert into quarantine
        result = db.insert_quarantine_tick(
            symbol=symbol,
            date_time=invalid_tick["datetime"],
            ask=invalid_tick["ask"],
            bid=invalid_tick["bid"],
            rejection_reason=rejection_reason,
            receive_time=current_time
        )
        
        assert result is True
    
    def test_quarantine_categorization(self, db):
        """Test that rejection reasons are properly categorized"""
        test_cases = [
            ("Bid price outlier: 1.2000", "outlier"),
            ("Duplicate tick: 500μs from last", "duplicate"),
            ("Tick is stale: 600s old", "stale"),
            ("Missing ask price", "missing_data"),
            ("Invalid spread: ask <= bid", "invalid_spread"),
        ]
        
        for reason, expected_category in test_cases:
            category = db._categorize_rejection_reason(reason)
            assert category == expected_category, f"Failed for reason: {reason}"
    
    def test_multiple_rejections_quarantined(self, db, quality_gate):
        """Test that multiple rejected ticks are all quarantined"""
        symbol = "EURUSD"
        current_time = get_utc_time()
        
        # Create multiple invalid ticks
        invalid_ticks = [
            {"datetime": current_time - timedelta(seconds=30), "ask": 1.0999, "bid": 1.1000},  # Invalid spread
            {"datetime": current_time - timedelta(seconds=20), "ask": 1.1001, "bid": 1.1000},  # Duplicate (same price)
            {"datetime": current_time - timedelta(seconds=10), "ask": None, "bid": 1.1000},  # Missing data
        ]
        
        quarantined_count = 0
        
        for tick_data in invalid_ticks:
            tick = {
                "symbol": symbol,
                "datetime": tick_data["datetime"],
                "ask": tick_data.get("ask"),
                "bid": tick_data.get("bid"),
            }
            
            is_valid, rejection_reason, _ = quality_gate.validate(
                tick, symbol, current_time
            )
            
            if not is_valid:
                result = db.insert_quarantine_tick(
                    symbol=symbol,
                    date_time=tick_data["datetime"],
                    ask=tick_data.get("ask") or 0.0,
                    bid=tick_data.get("bid") or 0.0,
                    rejection_reason=rejection_reason,
                    receive_time=current_time
                )
                if result:
                    quarantined_count += 1
        
        assert quarantined_count > 0
    
    @patch('monitoring.metrics.quarantine_ticks_total')
    def test_quarantine_metrics_updated(self, mock_metrics, db):
        """Test that Prometheus metrics are updated on quarantine"""
        # Mock metrics
        mock_counter = MagicMock()
        mock_metrics.labels.return_value = mock_counter
        
        # Insert quarantined tick
        result = db.insert_quarantine_tick(
            symbol="EURUSD",
            date_time=get_utc_time(),
            ask=1.1001,
            bid=1.1000,
            rejection_reason="Test rejection"
        )
        
        assert result is True
        # Verify metrics were called
        mock_metrics.labels.assert_called()
        mock_counter.inc.assert_called()


class TestQuarantineAPI:
    """Test quarantine API endpoint (requires API server)"""
    
    @pytest.mark.skip(reason="Requires running API server and database")
    def test_get_quarantine_ticks_endpoint(self):
        """Test GET /api/v1/data/quarantine endpoint"""
        import httpx
        
        # This test would require a running API server
        # For now, we'll skip it in unit tests
        # It should be run as part of E2E tests
        pass
    
    @pytest.mark.skip(reason="Requires running API server and database")
    def test_quarantine_filtering(self):
        """Test quarantine endpoint filtering"""
        # Test symbol filter
        # Test rejection_category filter
        # Test date range filter
        # Test pagination
        pass
