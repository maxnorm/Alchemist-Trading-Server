"""
Unit tests for Broker Adapter system

Tests IBrokerAdapter interface and implementations.
"""

import pytest
import unittest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime

from tests.shared.helpers.path_utils import setup_trading_server_path
setup_trading_server_path()

from trading.brokers.base import IBrokerAdapter, OrderStatus
from trading.brokers.mt5_adapter import MT5BrokerAdapter
from trading.brokers.factory import BrokerFactory
from risk.oms import Order, OrderState, Position, Discrepancy
from domain.entities.account_info import AccountInfo
from mt5_connection.zeromq_terminal import ZeroMQTerminal
from models.trade import Trade
from codes.order_type import OrderType as MT5OrderType


class TestOrderStatus(unittest.TestCase):
    """Test OrderStatus model"""
    
    def test_order_status_creation(self):
        """Test creating order status"""
        status = OrderStatus(
            order_id="test-123",
            state=OrderState.FILLED,
            filled_quantity=0.01,
            average_fill_price=1.1000,
            broker_order_id="MT5-456",
        )
        
        self.assertEqual(status.order_id, "test-123")
        self.assertEqual(status.state, OrderState.FILLED)
        self.assertEqual(status.filled_quantity, 0.01)
        self.assertEqual(status.average_fill_price, 1.1000)
        self.assertEqual(status.broker_order_id, "MT5-456")
    
    def test_order_status_to_dict(self):
        """Test converting order status to dictionary"""
        status = OrderStatus(
            order_id="test-123",
            state=OrderState.FILLED,
            filled_quantity=0.01,
            average_fill_price=1.1000,
        )
        
        status_dict = status.to_dict()
        self.assertIsInstance(status_dict, dict)
        self.assertEqual(status_dict["order_id"], "test-123")
        self.assertEqual(status_dict["state"], "filled")


class TestIBrokerAdapter(unittest.TestCase):
    """Test IBrokerAdapter interface"""
    
    def test_interface_definition(self):
        """Test that IBrokerAdapter is properly defined"""
        import abc
        assert issubclass(IBrokerAdapter, abc.ABC)
        
        # Check required abstract methods exist
        assert hasattr(IBrokerAdapter, 'submit_order')
        assert hasattr(IBrokerAdapter, 'get_positions')
        assert hasattr(IBrokerAdapter, 'reconcile')
        assert hasattr(IBrokerAdapter, 'get_order_status')
        assert hasattr(IBrokerAdapter, 'cancel_order')
        assert hasattr(IBrokerAdapter, 'get_account_info')


class TestMT5BrokerAdapter(unittest.TestCase):
    """Test MT5BrokerAdapter implementation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_terminal = Mock(spec=ZeroMQTerminal)
        self.adapter = MT5BrokerAdapter(terminal=self.mock_terminal)
    
    def test_adapter_implements_interface(self):
        """Test that MT5BrokerAdapter implements IBrokerAdapter"""
        self.assertIsInstance(self.adapter, IBrokerAdapter)
    
    def test_submit_order(self):
        """Test order submission"""
        # Mock terminal response
        mock_trade = Mock(spec=Trade)
        mock_trade.ticket = 12345
        mock_trade.open_price = 1.1000
        
        async def mock_send_order(*args, **kwargs):
            return mock_trade
        
        self.mock_terminal.send_order = AsyncMock(return_value=mock_trade)
        
        # Create order
        order = Order(
            order_id="test-123",
            client_order_id="client-123",
            symbol="EURUSD",
            side="BUY",
            quantity=0.01,
            order_type="MARKET",
        )
        
        # Submit order
        status = self.adapter.submit_order(order, idempotency_key="test-key")
        
        # Verify
        self.assertIsInstance(status, OrderStatus)
        self.assertEqual(status.order_id, "test-123")
        self.assertIn(status.state, [OrderState.FILLED, OrderState.NEW])
    
    def test_submit_order_idempotency(self):
        """Test order submission idempotency"""
        # Mock terminal
        mock_trade = Mock(spec=Trade)
        mock_trade.ticket = 12345
        mock_trade.open_price = 1.1000
        self.mock_terminal.send_order = AsyncMock(return_value=mock_trade)
        
        order = Order(
            order_id="test-123",
            client_order_id="client-123",
            symbol="EURUSD",
            side="BUY",
            quantity=0.01,
        )
        
        # Submit same order twice with same idempotency key
        status1 = self.adapter.submit_order(order, idempotency_key="same-key")
        status2 = self.adapter.submit_order(order, idempotency_key="same-key")
        
        # Should return same order status
        self.assertEqual(status1.order_id, status2.order_id)
        # Terminal should only be called once
        self.assertEqual(self.mock_terminal.send_order.call_count, 1)
    
    def test_get_account_info(self):
        """Test getting account information"""
        # Mock terminal response
        mock_infos = {
            "login": 12345,
            "currency": "USD",
            "leverage": 100,
            "balance": 10000.0,
            "equity": 10050.0,
            "profit": 50.0,
            "margin": 100.0,
            "margin_free": 9950.0,
        }
        
        async def mock_get_all_infos():
            return mock_infos
        
        self.mock_terminal.get_all_infos = AsyncMock(return_value=mock_infos)
        
        # Get account info
        account_info = self.adapter.get_account_info()
        
        # Verify
        self.assertIsInstance(account_info, AccountInfo)
        self.assertEqual(account_info.login, 12345)
        self.assertEqual(account_info.balance, 10000.0)
        self.assertEqual(account_info.equity, 10050.0)
    
    def test_get_positions(self):
        """Test getting positions"""
        positions = self.adapter.get_positions()
        
        # Should return list (may be empty)
        self.assertIsInstance(positions, list)
        for pos in positions:
            self.assertIsInstance(pos, Position)
    
    def test_reconcile(self):
        """Test position reconciliation"""
        expected = {"EURUSD": 0.01, "GBPUSD": -0.01}
        
        discrepancies = self.adapter.reconcile(expected)
        
        # Should return list of discrepancies
        self.assertIsInstance(discrepancies, list)
        for disc in discrepancies:
            self.assertIsInstance(disc, Discrepancy)
    
    def test_get_order_status(self):
        """Test getting order status"""
        # First submit an order
        mock_trade = Mock(spec=Trade)
        mock_trade.ticket = 12345
        mock_trade.open_price = 1.1000
        self.mock_terminal.send_order = AsyncMock(return_value=mock_trade)
        
        order = Order(
            order_id="test-123",
            client_order_id="client-123",
            symbol="EURUSD",
            side="BUY",
            quantity=0.01,
        )
        
        self.adapter.submit_order(order, idempotency_key="test-key")
        
        # Get status
        status = self.adapter.get_order_status("test-123")
        
        self.assertIsInstance(status, OrderStatus)
        self.assertEqual(status.order_id, "test-123")
    
    def test_get_order_status_not_found(self):
        """Test getting status for non-existent order"""
        with self.assertRaises(ValueError):
            self.adapter.get_order_status("non-existent")
    
    def test_cancel_order(self):
        """Test canceling order"""
        # Cancel not fully implemented for MT5
        # Should return False or raise
        result = self.adapter.cancel_order("test-123")
        # May return False if not implemented
        self.assertIsInstance(result, bool)
    
    def test_from_terminal(self):
        """Test factory method"""
        adapter = MT5BrokerAdapter.from_terminal(self.mock_terminal)
        
        self.assertIsInstance(adapter, MT5BrokerAdapter)
        self.assertEqual(adapter.terminal, self.mock_terminal)


class TestBrokerFactory(unittest.TestCase):
    """Test BrokerFactory"""
    
    def test_create_mt5_adapter(self):
        """Test creating MT5 adapter"""
        mock_terminal = Mock(spec=ZeroMQTerminal)
        
        adapter = BrokerFactory.create_mt5_adapter(mock_terminal)
        
        self.assertIsInstance(adapter, MT5BrokerAdapter)
        self.assertEqual(adapter.terminal, mock_terminal)
    
    def test_create_from_config_mt5(self):
        """Test creating adapter from config"""
        mock_terminal = Mock(spec=ZeroMQTerminal)
        config = {"broker_type": "mt5"}
        
        adapter = BrokerFactory.create_from_config(config, terminal=mock_terminal)
        
        self.assertIsInstance(adapter, MT5BrokerAdapter)
    
    def test_create_from_config_invalid(self):
        """Test creating adapter with invalid config"""
        config = {"broker_type": "invalid"}
        
        with self.assertRaises(ValueError):
            BrokerFactory.create_from_config(config)
    
    def test_create_from_config_missing_terminal(self):
        """Test creating MT5 adapter without terminal"""
        config = {"broker_type": "mt5"}
        
        with self.assertRaises(ValueError):
            BrokerFactory.create_from_config(config)


if __name__ == '__main__':
    unittest.main()
