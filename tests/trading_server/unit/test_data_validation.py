"""
Unit tests for data validation
"""
import unittest
from unittest.mock import Mock

from tests.shared.helpers.path_utils import setup_trading_server_path
setup_trading_server_path()

from mt5_connection.tick_processor import TickProcessor


class TestDataValidation(unittest.TestCase):
    """Test data validation in tick streamer"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_asset = Mock()
        self.mock_asset.symbol = 'EURUSD'
        self.mock_asset.bid = 1.1000
        self.mock_asset.ask = 1.1002
        self.mock_db = Mock()
        
        self.processor = TickProcessor(
            asset=self.mock_asset,
            db=self.mock_db
        )
    
    def test_validate_tick_valid(self):
        """Test validation of valid tick"""
        result = self.processor._validate_tick(
            'EURUSD', '2024.01.01 12:00:00', 1.1002, 1.1000
        )
        self.assertTrue(result)
    
    def test_validate_tick_negative_price(self):
        """Test validation rejects negative prices"""
        result = self.processor._validate_tick(
            'EURUSD', '2024.01.01 12:00:00', -1.1002, 1.1000
        )
        self.assertFalse(result)
    
    def test_validate_tick_reversed_prices(self):
        """Test validation rejects reversed prices (ask <= bid)"""
        result = self.processor._validate_tick(
            'EURUSD', '2024.01.01 12:00:00', 1.1000, 1.1002
        )
        self.assertFalse(result)
    
    def test_validate_tick_order_valid(self):
        """Test validation of tick ordering"""
        result = self.processor._validate_tick_order(
            'EURUSD', '2024.01.01 12:00:00'
        )
        self.assertTrue(result)
        
        # Second tick should also be valid if later
        result = self.processor._validate_tick_order(
            'EURUSD', '2024.01.01 12:00:01'
        )
        self.assertTrue(result)
    
    def test_validate_tick_order_out_of_order(self):
        """Test validation rejects out-of-order ticks"""
        # First tick
        self.processor._validate_tick_order(
            'EURUSD', '2024.01.01 12:00:00'
        )
        
        # Out-of-order tick should be rejected
        result = self.processor._validate_tick_order(
            'EURUSD', '2024.01.01 11:59:59'
        )
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
