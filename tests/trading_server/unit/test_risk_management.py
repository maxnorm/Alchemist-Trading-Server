"""
Unit tests for risk management
"""
import unittest
from unittest.mock import Mock

from tests.shared.helpers.path_utils import setup_trading_server_path
setup_trading_server_path()

from utils.risk_management import RiskManager
from models.account import Account
from models.currency_pair import CurrencyPair


class TestRiskManagement(unittest.TestCase):
    """Test risk management calculations"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.risk_manager = RiskManager(
            max_position_size=0.1,
            max_daily_loss=0.05,
            max_drawdown=0.20,
            stop_loss_pct=0.02,
            take_profit_pct=0.04,
            max_open_positions=3
        )
        
        self.mock_account = Mock(spec=Account)
        self.mock_account.balance = 10000.0
        self.mock_account.leverage = 100
        self.mock_account.margin_free = 10000.0
        self.mock_account.current_trade = {}
        
        self.mock_pair = Mock(spec=CurrencyPair)
        self.mock_pair.symbol = 'EURUSD'
    
    def test_calculate_position_size(self):
        """Test position size calculation"""
        lot_size = self.risk_manager.calculate_position_size(
            self.mock_account,
            self.mock_pair,
            entry_price=1.1000
        )
        
        # Should return a valid lot size
        self.assertGreater(lot_size, 0.0)
        # Lot size is calculated based on risk, not directly limited to 0.1
        # But should be reasonable (less than account balance / entry price)
        self.assertLess(lot_size, self.mock_account.balance / 1.1000)
    
    def test_calculate_stop_loss_long(self):
        """Test stop loss calculation for long position"""
        entry_price = 1.1000
        stop_loss = self.risk_manager.calculate_stop_loss(entry_price, is_long=True)
        expected = entry_price * (1 - 0.02)  # 2% stop loss
        self.assertAlmostEqual(stop_loss, expected, places=4)
    
    def test_calculate_stop_loss_short(self):
        """Test stop loss calculation for short position"""
        entry_price = 1.1000
        stop_loss = self.risk_manager.calculate_stop_loss(entry_price, is_long=False)
        expected = entry_price * (1 + 0.02)  # 2% stop loss
        self.assertAlmostEqual(stop_loss, expected, places=4)
    
    def test_calculate_take_profit_long(self):
        """Test take profit calculation for long position"""
        entry_price = 1.1000
        take_profit = self.risk_manager.calculate_take_profit(entry_price, is_long=True)
        expected = entry_price * (1 + 0.04)  # 4% take profit
        self.assertAlmostEqual(take_profit, expected, places=4)
    
    def test_can_trade_sufficient_balance(self):
        """Test can_trade with sufficient balance"""
        can_trade, reason = self.risk_manager.can_trade(self.mock_account)
        self.assertTrue(can_trade)
        self.assertEqual(reason, "OK")
    
    def test_can_trade_insufficient_balance(self):
        """Test can_trade with insufficient balance"""
        self.mock_account.balance = 0.0
        can_trade, reason = self.risk_manager.can_trade(self.mock_account)
        self.assertFalse(can_trade)
        self.assertIn("Insufficient", reason)
    
    def test_can_trade_max_positions(self):
        """Test can_trade with max positions reached"""
        # Create mock trades
        self.mock_account.current_trade = {1: Mock(), 2: Mock(), 3: Mock()}
        can_trade, reason = self.risk_manager.can_trade(self.mock_account)
        self.assertFalse(can_trade)
        self.assertIn("Maximum open positions", reason)
    
    def test_check_correlation_risk_no_positions(self):
        """Test correlation risk check with no open positions"""
        can_trade, reason = self.risk_manager.check_correlation_risk(
            self.mock_account, self.mock_pair
        )
        self.assertTrue(can_trade)
        self.assertEqual(reason, "OK")
    
    def test_check_correlation_risk_correlated(self):
        """Test correlation risk check with correlated positions"""
        # Create mock trade with same base currency
        mock_trade1 = Mock()
        mock_trade1.pair.symbol = 'EURGBP'
        mock_trade2 = Mock()
        mock_trade2.pair.symbol = 'EURJPY'
        
        self.mock_account.current_trade = {1: mock_trade1, 2: mock_trade2}
        
        # New position with EUR (correlated)
        # Both EURGBP and EURJPY share EUR base with EURUSD
        # So correlation_count = 2, which equals max_correlated (2), so should fail
        can_trade, reason = self.risk_manager.check_correlation_risk(
            self.mock_account, self.mock_pair  # EURUSD
        )
        # Should fail because we already have 2 positions correlated with EURUSD
        self.assertFalse(can_trade)
        self.assertIn("correlated", reason.lower())
        
        # Test with only one correlated position
        self.mock_account.current_trade = {1: mock_trade1}  # Only EURGBP
        can_trade, reason = self.risk_manager.check_correlation_risk(
            self.mock_account, self.mock_pair  # EURUSD
        )
        # Should pass: 1 existing + 1 new = 2 total (within limit)
        self.assertTrue(can_trade)
        
        # Test with non-correlated positions
        mock_trade_usd = Mock()
        mock_trade_usd.pair.symbol = 'GBPJPY'  # No EUR
        self.mock_account.current_trade = {1: mock_trade_usd}
        can_trade, reason = self.risk_manager.check_correlation_risk(
            self.mock_account, self.mock_pair  # EURUSD
        )
        # Should pass: GBPJPY doesn't share base/quote with EURUSD
        self.assertTrue(can_trade)


if __name__ == '__main__':
    unittest.main()
