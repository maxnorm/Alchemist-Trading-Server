"""
Database integration tests for safety components

Tests database persistence for KillSwitch, CircuitBreaker, and OMS.
"""

import pytest
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/backend/trading_server/src'))

from risk.kill_switch import KillSwitch, KillSwitchState
from risk.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerState
from risk.oms import OrderManagementSystem, Order, OrderState


class MockDatabase:
    """Mock database for testing"""
    
    def __init__(self):
        self.connection_pool = Mock()
        self.connections = []
        self.executed_queries = []
        self.last_insert_id = 0
    
    def _Database__get_connection(self):
        """Mock connection getter"""
        conn = Mock()
        cursor = Mock()
        
        def execute(query, params=None):
            self.executed_queries.append((query, params))
            if 'INSERT' in query.upper():
                self.last_insert_id += 1
                cursor.lastrowid = self.last_insert_id
        
        cursor.execute = execute
        cursor.fetchall = Mock(return_value=[])
        cursor.fetchone = Mock(return_value=None)
        conn.cursor = Mock(return_value=cursor)
        conn.commit = Mock()
        conn.close = Mock()
        
        self.connections.append(conn)
        return conn


class TestOMSDatabaseIntegration:
    """Test OMS database persistence"""
    
    @pytest.fixture
    def mock_db(self):
        return MockDatabase()
    
    @pytest.fixture
    def oms(self, mock_db, tmp_path):
        return OrderManagementSystem(
            database=mock_db,
            persistence_path=str(tmp_path / "oms.json")
        )
    
    def test_order_persisted_to_database(self, oms, mock_db):
        """Test that order is persisted to database on submission"""
        order = Order(
            client_order_id="test-order-1",
            symbol="EURUSD",
            side="BUY",
            quantity=0.1,
            account_id="12345"
        )
        order.metadata = {'account_login': 12345}
        
        order_id = oms.submit_order(order)
        
        # Verify database insert was called
        assert len(mock_db.executed_queries) > 0
        
        # Find INSERT query
        insert_queries = [q for q in mock_db.executed_queries 
                         if 'INSERT' in q[0].upper() and 'orders' in q[0]]
        assert len(insert_queries) > 0
        
        # Verify order data in query
        query, params = insert_queries[0]
        assert order_id in params or order.order_id in params
        assert "EURUSD" in str(params)
        assert "BUY" in str(params)
    
    def test_order_state_update_persisted(self, oms, mock_db):
        """Test that order state updates are persisted to database"""
        order = Order(symbol="EURUSD", side="BUY", quantity=0.1)
        order_id = oms.submit_order(order)
        
        # Clear previous queries
        mock_db.executed_queries.clear()
        
        # Update state
        oms.update_order_state(order_id, OrderState.NEW, broker_order_id="BROKER-123")
        
        # Verify update query was executed
        update_queries = [q for q in mock_db.executed_queries 
                         if 'INSERT' in q[0].upper() and 'ON DUPLICATE KEY UPDATE' in q[0]]
        assert len(update_queries) > 0
    
    def test_fill_persisted_to_database(self, oms, mock_db):
        """Test that fills are persisted to database"""
        order = Order(symbol="EURUSD", side="BUY", quantity=0.1)
        order_id = oms.submit_order(order)
        
        # Clear previous queries
        mock_db.executed_queries.clear()
        
        # Handle fill
        oms.handle_fill({
            'order_id': order_id,
            'quantity': 0.1,
            'price': 1.0850
        })
        
        # Verify update query was executed (for filled_quantity and average_fill_price)
        update_queries = [q for q in mock_db.executed_queries 
                         if 'INSERT' in q[0].upper() and 'ON DUPLICATE KEY UPDATE' in q[0]]
        assert len(update_queries) > 0


class TestKillSwitchDatabaseIntegration:
    """Test Kill Switch database logging"""
    
    @pytest.fixture
    def mock_db(self):
        return MockDatabase()
    
    @pytest.fixture
    def kill_switch(self, mock_db, tmp_path):
        return KillSwitch(
            audit_log_path=str(tmp_path / "audit.json"),
            database=mock_db
        )
    
    def test_trigger_logged_to_database(self, kill_switch, mock_db):
        """Test that kill switch trigger is logged to database"""
        kill_switch.arm()
        kill_switch.trigger("Test trigger", "Manual")
        
        # Verify database insert was called
        insert_queries = [q for q in mock_db.executed_queries 
                         if 'INSERT' in q[0].upper() and 'kill_switch_events' in q[0]]
        assert len(insert_queries) > 0
        
        # Verify event data
        query, params = insert_queries[0]
        assert "Manual" in str(params) or "Test trigger" in str(params)
    
    def test_reset_updates_database(self, kill_switch, mock_db):
        """Test that kill switch reset updates database"""
        kill_switch.arm()
        kill_switch.trigger("Test trigger", "Manual")
        
        # Clear previous queries
        mock_db.executed_queries.clear()
        
        # Reset
        kill_switch.reset("admin")
        
        # Verify update query was executed
        update_queries = [q for q in mock_db.executed_queries 
                         if 'UPDATE' in q[0].upper() and 'kill_switch_events' in q[0]]
        assert len(update_queries) > 0


class TestCircuitBreakerDatabaseIntegration:
    """Test Circuit Breaker database logging"""
    
    @pytest.fixture
    def mock_db(self):
        return MockDatabase()
    
    @pytest.fixture
    def circuit_breaker(self, mock_db):
        cb = CircuitBreaker(
            CircuitBreakerConfig(
                max_loss_per_hour_pct=0.03,
                max_loss_per_day_pct=0.05
            ),
            database=mock_db
        )
        cb.initialize(10000.0)
        return cb
    
    def test_trip_logged_to_database(self, circuit_breaker, mock_db):
        """Test that circuit breaker trip is logged to database"""
        # Trigger trip
        circuit_breaker.record_trade(-400)  # 4% loss
        circuit_breaker.check()
        
        # Verify database insert was called
        insert_queries = [q for q in mock_db.executed_queries 
                         if 'INSERT' in q[0].upper() and 'circuit_breaker_events' in q[0]]
        assert len(insert_queries) > 0
        
        # Verify event data
        query, params = insert_queries[0]
        assert any('loss' in str(p).lower() for p in params if p)
    
    def test_resume_updates_database(self, circuit_breaker, mock_db):
        """Test that circuit breaker resume updates database"""
        # Trip the breaker
        circuit_breaker.record_trade(-400)
        circuit_breaker.check()
        
        # Clear previous queries
        mock_db.executed_queries.clear()
        
        # Reset (which should trigger resume update)
        circuit_breaker.reset(manual=True)
        
        # Verify update query was executed
        update_queries = [q for q in mock_db.executed_queries 
                         if 'UPDATE' in q[0].upper() and 'circuit_breaker_events' in q[0]]
        assert len(update_queries) > 0


class TestDatabaseFallback:
    """Test that components degrade gracefully when database fails"""
    
    @pytest.fixture
    def failing_db(self):
        """Database that raises exceptions"""
        db = Mock()
        db._Database__get_connection = Mock(side_effect=Exception("Database connection failed"))
        return db
    
    def test_oms_fallback_on_db_failure(self, failing_db, tmp_path):
        """Test that OMS falls back to file persistence on database failure"""
        oms = OrderManagementSystem(
            database=failing_db,
            persistence_path=str(tmp_path / "oms.json")
        )
        
        # Should not raise exception
        order = Order(symbol="EURUSD", side="BUY", quantity=0.1)
        order_id = oms.submit_order(order)
        
        # Order should still be stored in memory
        assert order_id in oms.orders
    
    def test_kill_switch_continues_on_db_failure(self, failing_db, tmp_path):
        """Test that kill switch continues operation on database failure"""
        kill_switch = KillSwitch(
            audit_log_path=str(tmp_path / "audit.json"),
            database=failing_db
        )
        
        # Should not raise exception
        kill_switch.arm()
        kill_switch.trigger("Test", "Manual")
        
        # Kill switch should still be active
        assert kill_switch.is_active()
    
    def test_circuit_breaker_continues_on_db_failure(self, failing_db):
        """Test that circuit breaker continues operation on database failure"""
        circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(),
            database=failing_db
        )
        circuit_breaker.initialize(10000.0)
        
        # Should not raise exception
        circuit_breaker.record_trade(-400)
        can_trade, reason = circuit_breaker.check()
        
        # Circuit breaker should still function
        assert can_trade is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
