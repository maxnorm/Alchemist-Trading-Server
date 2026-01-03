"""
Unit tests for feature engineering
"""
import unittest
import numpy as np
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'mt5-python_server', 'src'))

from utils.feature_engineering import FeatureEngineer
from utils.technical_indicators import TechnicalIndicators


class TestFeatureEngineering(unittest.TestCase):
    """Test feature engineering"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.feature_engineer = FeatureEngineer(normalization_method='standard')
        self.prices = np.array([1.0, 1.1, 1.2, 1.15, 1.25, 1.3, 1.28, 1.35, 1.4, 1.38] * 10)
    
    def test_feature_engineer_fit(self):
        """Test feature engineer fitting"""
        features = {
            'price': self.prices,
            'sma_20': TechnicalIndicators.sma(self.prices, 20),
            'rsi': TechnicalIndicators.rsi(self.prices, 14)
        }
        
        self.feature_engineer.fit(features)
        self.assertTrue(self.feature_engineer.is_fitted)
    
    def test_feature_engineer_transform(self):
        """Test feature engineer transformation"""
        features = {
            'price': self.prices,
            'sma_20': TechnicalIndicators.sma(self.prices, 20),
            'rsi': TechnicalIndicators.rsi(self.prices, 14)
        }
        
        self.feature_engineer.fit(features)
        transformed = self.feature_engineer.transform(features)
        
        # Check shape
        self.assertEqual(len(transformed.shape), 2)
        self.assertEqual(transformed.shape[0], len(self.prices))
    
    def test_feature_engineer_handles_nan(self):
        """Test feature engineer handles NaN values"""
        prices_with_nan = self.prices.copy()
        prices_with_nan[0] = np.nan
        
        features = {
            'price': prices_with_nan,
            'sma_20': TechnicalIndicators.sma(prices_with_nan, 20),
            'rsi': TechnicalIndicators.rsi(prices_with_nan, 14)
        }
        
        # Should not raise exception
        self.feature_engineer.fit(features)
        transformed = self.feature_engineer.transform(features)
        
        # Check no NaN in output
        self.assertFalse(np.isnan(transformed).any())


class TestTechnicalIndicators(unittest.TestCase):
    """Test technical indicators"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.prices = np.array([1.0, 1.1, 1.2, 1.15, 1.25, 1.3, 1.28, 1.35, 1.4, 1.38] * 10)
    
    def test_sma(self):
        """Test Simple Moving Average"""
        sma = TechnicalIndicators.sma(self.prices, 20)
        self.assertEqual(len(sma), len(self.prices))
        # Check that SMA values are reasonable
        self.assertTrue(np.all(sma[19:] >= 0))
    
    def test_ema(self):
        """Test Exponential Moving Average"""
        ema = TechnicalIndicators.ema(self.prices, 12)
        self.assertEqual(len(ema), len(self.prices))
        # EMA should be close to prices
        self.assertTrue(np.all(ema >= 0))
    
    def test_rsi(self):
        """Test Relative Strength Index"""
        rsi = TechnicalIndicators.rsi(self.prices, 14)
        self.assertEqual(len(rsi), len(self.prices))
        # RSI should be between 0 and 100
        self.assertTrue(np.all((rsi >= 0) & (rsi <= 100)))
    
    def test_macd(self):
        """Test MACD"""
        macd_line, signal_line, histogram = TechnicalIndicators.macd(self.prices)
        self.assertEqual(len(macd_line), len(self.prices))
        self.assertEqual(len(signal_line), len(self.prices))
        self.assertEqual(len(histogram), len(self.prices))
    
    def test_bollinger_bands(self):
        """Test Bollinger Bands"""
        upper, middle, lower = TechnicalIndicators.bollinger_bands(self.prices)
        self.assertEqual(len(upper), len(self.prices))
        # Upper should be >= middle >= lower
        valid_indices = ~np.isnan(upper)
        if np.any(valid_indices):
            self.assertTrue(np.all(upper[valid_indices] >= middle[valid_indices]))
            self.assertTrue(np.all(middle[valid_indices] >= lower[valid_indices]))


if __name__ == '__main__':
    unittest.main()
