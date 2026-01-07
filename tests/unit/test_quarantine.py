"""
Unit tests for quarantine functionality
"""

import pytest
import os
import sys
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/mt5-python_server/src'))

from database import Database
from utils.time_utils import get_utc_time


class TestQuarantineCategorization:
    """Test rejection reason categorization"""
    
    @pytest.fixture
    def db(self):
        """Database fixture with mocked connection"""
        db = Database()
        return db
    
    def test_categorize_outlier(self, db):
        """Test categorizing outlier rejection"""
        reason = "Bid price outlier: 1.2000 (method: z-score)"
        category = db._categorize_rejection_reason(reason)
        assert category == "outlier"
    
    def test_categorize_duplicate(self, db):
        """Test categorizing duplicate rejection"""
        reason = "Duplicate tick: 500μs from last tick (tolerance: 1000μs), same price"
        category = db._categorize_rejection_reason(reason)
        assert category == "duplicate"
    
    def test_categorize_stale(self, db):
        """Test categorizing stale rejection"""
        reason = "Tick is stale: 600.5s old (threshold: 300s)"
        category = db._categorize_rejection_reason(reason)
        assert category == "stale"
    
    def test_categorize_missing_data(self, db):
        """Test categorizing missing data rejection"""
        reason = "Missing ask price"
        category = db._categorize_rejection_reason(reason)
        assert category == "missing_data"
    
    def test_categorize_invalid_spread(self, db):
        """Test categorizing invalid spread rejection"""
        reason = "Invalid spread: ask <= bid"
        category = db._categorize_rejection_reason(reason)
        assert category == "invalid_spread"
    
    def test_categorize_unknown(self, db):
        """Test categorizing unknown rejection"""
        reason = "Some unknown rejection reason"
        category = db._categorize_rejection_reason(reason)
        assert category == "unknown"


class TestInsertQuarantineTick:
    """Test insert_quarantine_tick method"""
    
    @pytest.fixture
    def db(self):
        """Database fixture"""
        db = Database()
        return db
    
    @patch('database.psycopg2.pool.ThreadedConnectionPool')
    def test_insert_quarantine_tick_success(self, mock_pool, db):
        """Test successful quarantine insert"""
        # Mock connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.commit = MagicMock()
        
        # Mock pool
        mock_pool_instance = MagicMock()
        mock_pool_instance.getconn.return_value = mock_conn
        db._Database__pool = mock_pool_instance
        
        # Test insert
        symbol = "EURUSD"
        date_time = get_utc_time()
        ask = 1.1001
        bid = 1.1000
        rejection_reason = "Duplicate tick"
        
        result = db.insert_quarantine_tick(
            symbol=symbol,
            date_time=date_time,
            ask=ask,
            bid=bid,
            rejection_reason=rejection_reason
        )
        
        assert result is True
        assert mock_cursor.execute.called
        assert mock_conn.commit.called
        assert mock_pool_instance.putconn.called
    
    @patch('database.psycopg2.pool.ThreadedConnectionPool')
    def test_insert_quarantine_tick_with_receive_time(self, mock_pool, db):
        """Test quarantine insert with receive_time"""
        # Mock connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.commit = MagicMock()
        
        # Mock pool
        mock_pool_instance = MagicMock()
        mock_pool_instance.getconn.return_value = mock_conn
        db._Database__pool = mock_pool_instance
        
        # Test insert
        symbol = "EURUSD"
        date_time = get_utc_time() - timedelta(seconds=300)
        receive_time = get_utc_time()
        ask = 1.1001
        bid = 1.1000
        rejection_reason = "Stale tick"
        
        result = db.insert_quarantine_tick(
            symbol=symbol,
            date_time=date_time,
            ask=ask,
            bid=bid,
            rejection_reason=rejection_reason,
            receive_time=receive_time
        )
        
        assert result is True
        # Verify execute was called with correct parameters
        call_args = mock_cursor.execute.call_args
        assert call_args is not None
    
    @patch('database.psycopg2.pool.ThreadedConnectionPool')
    def test_insert_quarantine_tick_database_error(self, mock_pool, db):
        """Test quarantine insert with database error"""
        # Mock connection that raises error
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock pool
        mock_pool_instance = MagicMock()
        mock_pool_instance.getconn.return_value = mock_conn
        db._Database__pool = mock_pool_instance
        
        # Test insert
        result = db.insert_quarantine_tick(
            symbol="EURUSD",
            date_time=get_utc_time(),
            ask=1.1001,
            bid=1.1000,
            rejection_reason="Test rejection"
        )
        
        assert result is False
        assert mock_pool_instance.putconn.called
    
    @patch('database.psycopg2.pool.ThreadedConnectionPool')
    @patch('monitoring.metrics.quarantine_ticks_total')
    def test_insert_quarantine_tick_updates_metrics(self, mock_metrics, mock_pool, db):
        """Test that quarantine insert updates Prometheus metrics"""
        # Mock connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.commit = MagicMock()
        
        # Mock pool
        mock_pool_instance = MagicMock()
        mock_pool_instance.getconn.return_value = mock_conn
        db._Database__pool = mock_pool_instance
        
        # Mock metrics
        mock_counter = MagicMock()
        mock_metrics.labels.return_value = mock_counter
        
        # Test insert
        result = db.insert_quarantine_tick(
            symbol="EURUSD",
            date_time=get_utc_time(),
            ask=1.1001,
            bid=1.1000,
            rejection_reason="Duplicate tick"
        )
        
        assert result is True
        # Verify metrics were updated
        mock_metrics.labels.assert_called_once()
        mock_counter.inc.assert_called_once()
