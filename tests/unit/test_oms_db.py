"""
Unit tests for OMS database persistence
"""

import pytest
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock
from datetime import datetime

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/mt5-python_server/src'))

from risk.oms import OrderManagementSystem, Order, OrderState


class TestOMSDatabase:
    """Tests for OMS database persistence"""
    
    @pytest.fixture
    def mock_database(self):
        """Create mock database connection"""
        db = Mock()
        conn = Mock()
        cursor = Mock()
        
        conn.cursor.return_value = cursor
        cursor.execute.return_value = None
        cursor.fetchall.return_value = []
        
        db._Database__get_connection.return_value = conn
        
        return db
    
    @pytest.fixture
    def oms(self, mock_database, tmp_path):
        """Create OMS with database"""
        return OrderManagementSystem(
            database=mock_database,
            persistence_path=str(tmp_path / "oms.json")
        )
    
    def test_persists_order_to_database(self, oms, mock_database):
        """Test that orders are persisted to database"""
        order = Order(
            client_order_id="test-order",
            symbol="EURUSD",
            side="BUY",
            quantity=0.1
        )
        
        oms.submit_order(order)
        
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
        assert "INSERT INTO orders" in query
        assert "id" in query
        assert "symbol" in query
        assert "side" in query
        assert "quantity" in query
    
    def test_updates_order_state_in_database(self, oms, mock_database):
        """Test that order state updates are persisted"""
        order = Order(
            client_order_id="test-order",
            symbol="EURUSD",
            side="BUY",
            quantity=0.1
        )
        
        order_id = oms.submit_order(order)
        oms.update_order_state(order_id, OrderState.NEW)
        
        # Verify multiple database calls (insert + update)
        conn = mock_database._Database__get_connection.return_value
        cursor = conn.cursor.return_value
        
        # Should have at least 2 calls (submit + update)
        assert cursor.execute.call_count >= 2
    
    def test_loads_orders_from_database(self, oms, mock_database):
        """Test that orders are loaded from database on initialization"""
        # Mock database to return an order
        conn = mock_database._Database__get_connection.return_value
        cursor = conn.cursor.return_value
        
        # Mock fetchall to return an order
        cursor.fetchall.return_value = [(
            "order-123",  # id
            "client-123",  # client_order_id
            None,  # experiment_id
            12345,  # account_login
            "EURUSD",  # symbol
            "BUY",  # side
            "MARKET",  # order_type
            0.1,  # quantity
            None,  # price
            None,  # stop_loss
            None,  # take_profit
            "NEW",  # state
            0.0,  # filled_quantity
            0.0,  # average_fill_price
            None,  # broker_order_id
            None,  # reject_reason
            None,  # metadata
            datetime.now(),  # created_at
            datetime.now()  # updated_at
        )]
        
        # Create new OMS instance - should load from database
        new_oms = OrderManagementSystem(
            database=mock_database,
            persistence_path=str(Path(oms.persistence_path) if oms.persistence_path else None)
        )
        
        # Verify database was queried
        assert cursor.execute.called
        
        # Check query contains SELECT
        calls = [call[0][0] for call in cursor.execute.call_args_list]
        select_calls = [c for c in calls if "SELECT" in c.upper()]
        assert len(select_calls) > 0
    
    def test_handles_database_failure_gracefully(self, oms, tmp_path):
        """Test that OMS handles database failures gracefully"""
        # Create database that raises exception
        failing_db = Mock()
        failing_db._Database__get_connection.side_effect = Exception("DB connection failed")
        
        oms.db = failing_db
        
        # Should not raise exception
        order = Order(
            client_order_id="test-order",
            symbol="EURUSD",
            side="BUY",
            quantity=0.1
        )
        
        # Should still work (fallback to file persistence)
        order_id = oms.submit_order(order)
        assert order_id is not None
    
    def test_alert_on_position_mismatch(self, oms):
        """Test that OMS triggers alerts on position mismatches"""
        alert_called = []
        
        def alert_handler(alert_type, alert_data):
            alert_called.append((alert_type, alert_data))
        
        oms.on_alert = alert_handler
        oms.alert_threshold_pct = 0.10  # 10% threshold
        
        # Create local position
        order = Order(symbol="EURUSD", side="BUY", quantity=0.1)
        oms.submit_order(order)
        oms.handle_fill({'order_id': order.order_id, 'quantity': 0.1, 'price': 1.0850})
        
        # Broker has different position (20% difference)
        broker_positions = {'EURUSD': 0.12}  # 20% more than local
        
        discrepancies = oms.reconcile(broker_positions)
        
        # Should have triggered alert
        assert len(alert_called) > 0
        assert alert_called[0][0] == 'position_mismatch'
        assert alert_called[0][1]['symbol'] == 'EURUSD'
    
    def test_no_alert_below_threshold(self, oms):
        """Test that OMS doesn't alert for small discrepancies"""
        alert_called = []
        
        def alert_handler(alert_type, alert_data):
            alert_called.append((alert_type, alert_data))
        
        oms.on_alert = alert_handler
        oms.alert_threshold_pct = 0.10  # 10% threshold
        
        # Create local position
        order = Order(symbol="EURUSD", side="BUY", quantity=0.1)
        oms.submit_order(order)
        oms.handle_fill({'order_id': order.order_id, 'quantity': 0.1, 'price': 1.0850})
        
        # Broker has slightly different position (5% difference - below threshold)
        broker_positions = {'EURUSD': 0.105}  # 5% more than local
        
        discrepancies = oms.reconcile(broker_positions)
        
        # Should not have triggered alert (below threshold)
        assert len(alert_called) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
