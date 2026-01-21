"""
Unit tests for MT5 Trading Operations

These tests use mocks to test order execution logic without requiring
a live MT5 connection. This allows fast, reliable testing that can run
in CI/CD environments.

Key Benefits:
- Fast execution (milliseconds vs seconds)
- No external dependencies
- Can test error scenarios easily
- Deterministic results
- Runs in CI/CD
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock, patch

# Add src/trading_server to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "trading_server" / "src"))

from codes.order_type import OrderType
from models.currency_pair import CurrencyPair
from models.account import Account
from models.trade import Trade
from trading.brokers.mt5_adapter import MT5BrokerAdapter
from mt5_connection.zeromq_terminal import ZeroMQTerminal
from application.trading.trade_executor import TradeExecutor
from domain.entities.account_info import AccountInfo


class TestMT5OrderExecutionUnit:
    """Unit tests for order execution with mocked terminal"""
    
    @pytest.fixture
    def mock_terminal(self):
        """Create mock MT5 terminal"""
        terminal = Mock(spec=ZeroMQTerminal)
        terminal.is_alive.return_value = True
        terminal.send_order = AsyncMock()
        terminal.close_order = AsyncMock()
        terminal.get_all_infos = AsyncMock()
        terminal.id = 1
        return terminal
    
    @pytest.fixture
    def mock_account_info(self):
        """Create mock account info"""
        return AccountInfo(
            login=12345,
            currency="USD",
            leverage=500,
            balance=10000.0,
            equity=10000.0,
            profit=0.0,
            margin=0.0,
            margin_free=10000.0
        )
    
    @pytest.fixture
    def account(self, mock_terminal, mock_account_info):
        """Create account with mocked terminal"""
        # Mock get_account_info to return account info
        async def mock_get_all_infos():
            return {
                "currency": mock_account_info.currency,
                "leverage": mock_account_info.leverage,
                "balance": mock_account_info.balance,
                "equity": mock_account_info.equity,
                "profit": mock_account_info.profit,
                "margin": mock_account_info.margin,
                "margin_free": mock_account_info.margin_free
            }
        
        mock_terminal.get_all_infos = AsyncMock(return_value=mock_get_all_infos())
        
        adapter = MT5BrokerAdapter(terminal=mock_terminal)
        account = Account(login=12345, broker_adapter=adapter)
        return account
    
    def test_send_buy_order_success(self, account, mock_terminal):
        """Test successful BUY order execution"""
        # Mock successful order response
        mock_trade = Mock(spec=Trade)
        mock_trade.ticket = 12345
        mock_trade.open_price = 1.1000
        mock_trade.lotsize = 0.01
        mock_trade.pair = CurrencyPair("EURUSD", 5)
        mock_trade.order_type = OrderType.BUY
        
        mock_terminal.send_order = AsyncMock(return_value=mock_trade)
        
        # Update account's broker adapter with new mock
        account.broker_adapter.terminal = mock_terminal
        
        # Execute order
        pair = CurrencyPair("EURUSD", 5)
        trade = account.send_order(OrderType.BUY, pair, 0.01)
        
        # Verify
        assert trade is not None
        assert trade.ticket == 12345
        assert trade.open_price == 1.1000
        assert trade.lotsize == 0.01
        assert mock_terminal.send_order.called
        
        # Verify order was tracked
        assert 12345 in account.current_trade
    
    def test_send_sell_order_success(self, account, mock_terminal):
        """Test successful SELL order execution"""
        # Mock successful order response
        mock_trade = Mock(spec=Trade)
        mock_trade.ticket = 12346
        mock_trade.open_price = 1.0990
        mock_trade.lotsize = 0.01
        mock_trade.pair = CurrencyPair("EURUSD", 5)
        mock_trade.order_type = OrderType.SELL
        
        mock_terminal.send_order = AsyncMock(return_value=mock_trade)
        account.broker_adapter.terminal = mock_terminal
        
        # Execute order
        pair = CurrencyPair("EURUSD", 5)
        trade = account.send_order(OrderType.SELL, pair, 0.01)
        
        # Verify
        assert trade is not None
        assert trade.ticket == 12346
        assert trade.order_type == OrderType.SELL
    
    def test_send_order_with_sl_tp(self, account, mock_terminal):
        """Test order with stop loss and take profit"""
        # Mock successful order with SL/TP
        mock_trade = Mock(spec=Trade)
        mock_trade.ticket = 12347
        mock_trade.open_price = 1.1000
        mock_trade.lotsize = 0.01
        mock_trade.pair = CurrencyPair("EURUSD", 5)
        
        mock_terminal.send_order = AsyncMock(return_value=mock_trade)
        account.broker_adapter.terminal = mock_terminal
        
        # Execute order with SL/TP
        pair = CurrencyPair("EURUSD", 5)
        trade = account.send_order(
            OrderType.BUY, 
            pair, 
            0.01, 
            sl=1.0950, 
            tp=1.1100
        )
        
        # Verify SL/TP were passed to terminal
        call_args = mock_terminal.send_order.call_args
        assert call_args[1]['sl'] == 1.0950
        assert call_args[1]['tp'] == 1.1100
    
    def test_send_order_connection_error(self, account, mock_terminal):
        """Test order failure due to connection error"""
        # Mock connection error
        mock_terminal.is_alive.return_value = False
        account.broker_adapter.terminal = mock_terminal
        
        pair = CurrencyPair("EURUSD", 5)
        
        # Should raise ConnectionError or return None
        with pytest.raises((ConnectionError, AttributeError)):
            trade = account.send_order(OrderType.BUY, pair, 0.01)
    
    def test_send_order_rejection(self, account, mock_terminal):
        """Test order rejection (e.g., insufficient margin)"""
        # Mock rejection response (None or error)
        mock_terminal.send_order = AsyncMock(return_value=None)
        account.broker_adapter.terminal = mock_terminal
        
        pair = CurrencyPair("EURUSD", 5)
        trade = account.send_order(OrderType.BUY, pair, 1000.0)  # Huge lot size
        
        # Should return None on rejection
        assert trade is None
        assert len(account.current_trade) == 0
    
    def test_send_order_invalid_symbol(self, account, mock_terminal):
        """Test order with invalid symbol"""
        # Mock rejection for invalid symbol
        mock_terminal.send_order = AsyncMock(return_value=None)
        account.broker_adapter.terminal = mock_terminal
        
        pair = CurrencyPair("INVALID_XYZ", 5)
        trade = account.send_order(OrderType.BUY, pair, 0.01)
        
        # Should return None
        assert trade is None
    
    def test_close_order_full(self, account, mock_terminal):
        """Test closing a position fully"""
        # First create an open trade
        mock_trade = Mock(spec=Trade)
        mock_trade.ticket = 12345
        mock_trade.lotsize = 0.01
        mock_trade.pair = CurrencyPair("EURUSD", 5)
        account.current_trade[12345] = mock_trade
        
        # Mock successful close
        mock_close_response = {
            "return_code": 10009,
            "order": {
                "lotsize": 0.01,
                "close_price": 1.1050
            },
            "account": {
                "balance": 10010.0,
                "equity": 10010.0,
                "profit": 10.0
            }
        }
        
        # Mock close_order to update trade
        def mock_close_order(ticket, lotsize=None):
            if ticket == 12345:
                mock_trade.close(1.1050)
                return mock_close_response
            return None
        
        mock_terminal.close_order = AsyncMock(side_effect=mock_close_order)
        account.broker_adapter.terminal = mock_terminal
        
        # Close order
        account.close_order(12345)
        
        # Verify trade was removed
        assert 12345 not in account.current_trade
    
    def test_close_order_partial(self, account, mock_terminal):
        """Test partial position closing"""
        # Create an open trade
        mock_trade = Mock(spec=Trade)
        mock_trade.ticket = 12345
        mock_trade.lotsize = 0.10
        mock_trade.pair = CurrencyPair("EURUSD", 5)
        account.current_trade[12345] = mock_trade
        
        # Mock partial close response
        mock_close_response = {
            "return_code": 10009,
            "order": {
                "lotsize": 0.05,  # Remaining after partial close
                "close_price": 1.1050
            }
        }
        
        def mock_close_order(ticket, lotsize=None):
            if ticket == 12345:
                # Update trade lotsize
                mock_trade.lotsize = 0.05
                return mock_close_response
            return None
        
        mock_terminal.close_order = AsyncMock(side_effect=mock_close_order)
        account.broker_adapter.terminal = mock_terminal
        
        # Partially close (0.05 lots)
        account.close_order(12345, lotsize=0.05)
        
        # Verify trade still exists but with reduced lotsize
        assert 12345 in account.current_trade
        assert account.current_trade[12345].lotsize == 0.05
    
    def test_multiple_orders_tracking(self, account, mock_terminal):
        """Test that multiple orders are tracked correctly"""
        trades = []
        ticket_counter = 10000
        
        def mock_send_order(*args, **kwargs):
            ticket = ticket_counter
            ticket_counter += 1
            
            mock_trade = Mock(spec=Trade)
            mock_trade.ticket = ticket
            mock_trade.open_price = 1.1000
            mock_trade.lotsize = kwargs.get('lotsize', 0.01)
            mock_trade.pair = kwargs.get('pair')
            trades.append(mock_trade)
            return mock_trade
        
        mock_terminal.send_order = AsyncMock(side_effect=mock_send_order)
        account.broker_adapter.terminal = mock_terminal
        
        # Send multiple orders
        pair = CurrencyPair("EURUSD", 5)
        trade1 = account.send_order(OrderType.BUY, pair, 0.01)
        trade2 = account.send_order(OrderType.BUY, pair, 0.02)
        trade3 = account.send_order(OrderType.SELL, pair, 0.01)
        
        # Verify all tracked
        assert len(account.current_trade) == 3
        assert trade1.ticket in account.current_trade
        assert trade2.ticket in account.current_trade
        assert trade3.ticket in account.current_trade


class TestMT5AccountInfoUnit:
    """Unit tests for account information retrieval"""
    
    @pytest.fixture
    def mock_terminal(self):
        """Create mock terminal with account info"""
        terminal = Mock(spec=ZeroMQTerminal)
        terminal.is_alive.return_value = True
        
        async def mock_get_all_infos():
            return {
                "currency": "USD",
                "leverage": 500,
                "balance": 10000.0,
                "equity": 10050.0,
                "profit": 50.0,
                "margin": 100.0,
                "margin_free": 9950.0
            }
        
        terminal.get_all_infos = AsyncMock(return_value=mock_get_all_infos())
        return terminal
    
    def test_get_account_info(self, mock_terminal):
        """Test retrieving account information"""
        adapter = MT5BrokerAdapter(terminal=mock_terminal)
        account = Account(login=12345, broker_adapter=adapter)
        
        # Verify account info
        assert account.info.balance == 10000.0
        assert account.info.equity == 10050.0
        assert account.info.currency == "USD"
        assert account.info.leverage == 500
        assert account.info.profit == 50.0
    
    def test_update_account_info(self, mock_terminal):
        """Test updating account information"""
        adapter = MT5BrokerAdapter(terminal=mock_terminal)
        account = Account(login=12345, broker_adapter=adapter)
        
        initial_equity = account.info.equity
        
        # Update info
        account.update_info()
        
        # Verify updated (should call get_all_infos)
        assert mock_terminal.get_all_infos.called


class TestMT5OrderTypeConversion:
    """Unit tests for order type conversion"""
    
    def test_order_type_buy(self):
        """Test BUY order type"""
        assert OrderType.BUY == 0
    
    def test_order_type_sell(self):
        """Test SELL order type"""
        assert OrderType.SELL == 1
    
    def test_order_type_buy_limit(self):
        """Test BUY_LIMIT order type"""
        assert OrderType.BUY_LIMIT == 2


if __name__ == "__main__":
    """
    Run tests directly
    Usage: python -m pytest tests/unit/test_mt5_trading_operations_unit.py -v
    """
    pytest.main([__file__, "-v"])
