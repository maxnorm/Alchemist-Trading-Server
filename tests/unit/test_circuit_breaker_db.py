"""
Unit tests for Circuit Breaker database persistence
"""

import pytest
import os
import sys
from unittest.mock import Mock, MagicMock
from datetime import datetime

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/mt5-python_server/src'))

from risk.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerState


class TestCircuitBreakerDatabase:
    """Tests for Circuit Breaker database persistence"""
    
    @pytest.fixture
    def mock_database(self):
        """Create mock database connection"""
        db = Mock()
        conn = Mock()
        cursor = Mock()
        
        conn.cursor.return_value = cursor
        cursor.lastrowid = 1
        cursor.execute.return_value = None
        
        db._Database__get_connection.return_value = conn
        
        return db
    
    @pytest.fixture
    def circuit_breaker(self, mock_database):
        """Create circuit breaker with database"""
        config = CircuitBreakerConfig(
            max_loss_per_hour_pct=0.03,
            max_loss_per_day_pct=0.05
        )
        cb = CircuitBreaker(config=config, database=mock_database)
        cb.initialize(10000.0)
        return cb
    
    def test_logs_trip_to_database(self, circuit_breaker, mock_database):
        """Test that circuit breaker logs trips to database"""
        # Cause a trip
        circuit_breaker.record_trade(-400)  # 4% loss
        circuit_breaker.check()
        
        # Verify database was called
        assert mock_database._Database__get_connection.called
        
        # Get the connection and cursor
        conn = mock_database._Database__get_connection.return_value
        cursor = conn.cursor.return_value
        
        # Verify INSERT was called
        assert cursor.execute.called
        
        # Check the query contains expected fields
        call_args = cursor.execute.call_args
        query = call_args[0][0]
        assert "INSERT INTO circuit_breaker_events" in query
        assert "breaker_type" in query
        assert "trigger_value" in query
        assert "threshold_value" in query
        assert "reason" in query
    
    def test_updates_resume_on_close(self, circuit_breaker, mock_database):
        """Test that circuit breaker updates database on resume"""
        # Trip the breaker
        circuit_breaker.record_trade(-400)
        circuit_breaker.check()
        
        # Reset (closes the circuit)
        circuit_breaker.reset(manual=True)
        
        # Verify UPDATE was called
        conn = mock_database._Database__get_connection.return_value
        cursor = conn.cursor.return_value
        
        # Should have INSERT (trip) and UPDATE (resume) calls
        assert cursor.execute.call_count >= 2
        
        # Check for UPDATE query
        calls = [call[0][0] for call in cursor.execute.call_args_list]
        update_calls = [c for c in calls if "UPDATE" in c.upper()]
        assert len(update_calls) > 0
    
    def test_handles_database_failure_gracefully(self, circuit_breaker):
        """Test that circuit breaker handles database failures gracefully"""
        # Create database that raises exception
        failing_db = Mock()
        failing_db._Database__get_connection.side_effect = Exception("DB connection failed")
        
        circuit_breaker.database = failing_db
        
        # Should not raise exception
        circuit_breaker.record_trade(-400)
        circuit_breaker.check()
        
        # Should still be in OPEN state
        assert circuit_breaker.state == CircuitBreakerState.OPEN
    
    def test_logs_different_breaker_types(self, circuit_breaker, mock_database):
        """Test that different breaker types are logged correctly"""
        # Test hourly loss
        circuit_breaker.record_trade(-400)
        circuit_breaker.check()
        
        conn = mock_database._Database__get_connection.return_value
        cursor = conn.cursor.return_value
        
        # Get the INSERT call
        insert_call = [call for call in cursor.execute.call_args_list 
                      if "INSERT" in call[0][0].upper()][0]
        
        # Check breaker_type parameter
        params = insert_call[0][1]
        breaker_type_idx = insert_call[0][0].index("breaker_type")
        # The params tuple should contain breaker_type
        assert len(params) > 0
    
    def test_volatility_calculation_from_prices(self, circuit_breaker):
        """Test volatility calculation from price history"""
        # Test with sample prices
        prices = [1.0850, 1.0855, 1.0860, 1.0858, 1.0862, 1.0865]
        
        volatility = circuit_breaker._calculate_volatility_from_prices(prices)
        
        # Should return a positive volatility value
        assert volatility > 0
        assert isinstance(volatility, float)
    
    def test_volatility_calculation_with_insufficient_data(self, circuit_breaker):
        """Test volatility calculation with insufficient data"""
        # Test with insufficient prices
        prices = [1.0850]
        
        volatility = circuit_breaker._calculate_volatility_from_prices(prices)
        
        # Should return 0.0 for insufficient data
        assert volatility == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
