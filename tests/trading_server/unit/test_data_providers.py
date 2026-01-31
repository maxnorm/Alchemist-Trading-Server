"""
Unit tests for Data Provider system

Tests DataProviderRegistry, FeatureCatalog, and provider implementations.
"""
import pytest
import unittest
import time
from unittest.mock import Mock, MagicMock, patch
import numpy as np

from tests.shared.helpers.path_utils import setup_trading_server_path
setup_trading_server_path()

from domain.models.feature import Feature
from data_providers.registry import DataProviderRegistry
from data_providers.price_provider import PriceDataProvider
from data_providers.indicator_provider import IndicatorProvider
from models.currency_pair import CurrencyPair


class TestFeature(unittest.TestCase):
    """Test Feature dataclass"""
    
    def test_feature_creation(self):
        """Test creating a feature"""
        feature = Feature(
            name="test_feature",
            data_type=float,
            source="test_source",
            description="Test feature",
            category="test"
        )
        self.assertEqual(feature.name, "test_feature")
        self.assertEqual(feature.data_type, float)
        self.assertEqual(feature.source, "test_source")
        self.assertEqual(feature.category, "test")
    
    def test_feature_validation(self):
        """Test feature validation"""
        with self.assertRaises(ValueError):
            Feature(name="", data_type=float, source="test", description="")
        
        with self.assertRaises(ValueError):
            Feature(name="test", data_type=float, source="", description="")


class TestDataProviderRegistry(unittest.TestCase):
    """Test DataProviderRegistry"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.registry = DataProviderRegistry()
    
    def test_register_provider(self):
        """Test registering a provider"""
        provider = Mock(spec=DataProvider)
        provider.get_features.return_value = []
        
        self.registry.register_provider("test_provider", provider)
        self.assertEqual(self.registry.get_provider_count(), 1)
        self.assertEqual(self.registry.get_provider("test_provider"), provider)
    
    def test_register_provider_validation(self):
        """Test provider registration validation"""
        with self.assertRaises(ValueError):
            self.registry.register_provider("", Mock())
        
        with self.assertRaises(ValueError):
            self.registry.register_provider("test", None)
    
    def test_discover_features(self):
        """Test feature discovery"""
        provider1 = Mock(spec=DataProvider)
        provider1.get_features.return_value = [
            Feature(name="feature1", data_type=float, source="provider1", description=""),
            Feature(name="feature2", data_type=int, source="provider1", description=""),
        ]
        
        provider2 = Mock(spec=DataProvider)
        provider2.get_features.return_value = [
            Feature(name="feature3", data_type=str, source="provider2", description=""),
        ]
        
        self.registry.register_provider("provider1", provider1)
        self.registry.register_provider("provider2", provider2)
        
        features = self.registry.discover_features()
        self.assertEqual(len(features), 3)
        self.assertEqual(features[0].name, "feature1")
        self.assertEqual(features[2].name, "feature3")
    
    def test_discover_features_error_handling(self):
        """Test that errors in discovery are handled gracefully"""
        provider = Mock(spec=DataProvider)
        provider.get_features.side_effect = Exception("Test error")
        
        self.registry.register_provider("error_provider", provider)
        
        # Should not raise, but log error
        features = self.registry.discover_features()
        self.assertEqual(len(features), 0)
    
    def test_get_all_providers(self):
        """Test getting all providers"""
        provider1 = Mock(spec=DataProvider)
        provider2 = Mock(spec=DataProvider)
        
        self.registry.register_provider("provider1", provider1)
        self.registry.register_provider("provider2", provider2)
        
        all_providers = self.registry.get_all_providers()
        self.assertEqual(len(all_providers), 2)
        self.assertIn("provider1", all_providers)
        self.assertIn("provider2", all_providers)
    
    def test_check_health(self):
        """Test health check"""
        provider = Mock(spec=DataProvider)
        provider.is_stale.return_value = False
        
        self.registry.register_provider("healthy_provider", provider)
        
        health = self.registry.check_health()
        self.assertEqual(health["healthy_provider"], True)
    
    def test_unregister_provider(self):
        """Test unregistering a provider"""
        provider = Mock(spec=DataProvider)
        self.registry.register_provider("test", provider)
        self.assertEqual(self.registry.get_provider_count(), 1)
        
        self.registry.unregister_provider("test")
        self.assertEqual(self.registry.get_provider_count(), 0)
        self.assertIsNone(self.registry.get_provider("test"))


class TestPriceDataProvider(unittest.TestCase):
    """Test PriceDataProvider"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.currency_pair = CurrencyPair("EURUSD", 5)
        self.currency_pair.update(1.1000, 1.1002)
        self.provider = PriceDataProvider(self.currency_pair)
    
    def test_get_features(self):
        """Test that price provider declares features"""
        features = self.provider.get_features()
        self.assertIsInstance(features, list)
        self.assertGreater(len(features), 0)
        
        # Check feature structure
        for feature in features:
            self.assertIsInstance(feature, Feature)
            self.assertIn("EURUSD", feature.name)
            self.assertEqual(feature.category, "price")
            self.assertEqual(feature.data_type, float)
    
    def test_get_current_data(self):
        """Test getting current price data"""
        data = self.provider.get_current_data()
        self.assertIn("bid", data)
        self.assertIn("ask", data)
        self.assertIn("mid", data)
        self.assertEqual(data["bid"], 1.1000)
        self.assertEqual(data["ask"], 1.1002)
    
    def test_is_stale(self):
        """Test stale data detection"""
        # Initially stale (never updated)
        self.assertTrue(self.provider.is_stale())
        
        # Update price
        self.currency_pair.update(1.1001, 1.1003)
        time.sleep(0.1)  # Small delay for update
        
        # Should not be stale immediately
        self.assertFalse(self.provider.is_stale(max_age_seconds=60.0))


class TestIndicatorProvider(unittest.TestCase):
    """Test IndicatorProvider"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.currency_pair = CurrencyPair("EURUSD", 5)
        self.provider = IndicatorProvider(self.currency_pair, window_size=50)
    
    def test_get_features(self):
        """Test that indicator provider declares features"""
        features = self.provider.get_features()
        self.assertIsInstance(features, list)
        self.assertGreater(len(features), 0)
        
        # Check that technical indicators are declared
        feature_names = [f.name for f in features]
        self.assertTrue(any("rsi" in name for name in feature_names))
        self.assertTrue(any("macd" in name for name in feature_names))
        self.assertTrue(any("bollinger" in name for name in feature_names))
        
        # Check feature structure
        for feature in features:
            self.assertIsInstance(feature, Feature)
            self.assertIn("EURUSD", feature.name)
            self.assertEqual(feature.category, "technical")
            self.assertEqual(feature.data_type, float)
    
    def test_get_current_data_insufficient_data(self):
        """Test getting indicator data with insufficient price history"""
        data = self.provider.get_current_data()
        
        # Should return default values when insufficient data
        self.assertIn("rsi", data)
        self.assertIn("macd", data)
        self.assertIn("bollinger_upper", data)
    
    def test_get_current_data_with_history(self):
        """Test getting indicator data with sufficient price history"""
        # Add price history
        prices = np.linspace(1.1000, 1.1100, 100)
        for price in prices:
            self.currency_pair.update(price - 0.0001, price + 0.0001)
        
        data = self.provider.get_current_data()
        
        # Should have calculated indicators
        self.assertIn("rsi", data)
        self.assertIn("macd", data)
        self.assertIn("sma_20", data)
        self.assertIn("ema_12", data)
        
        # Values should be reasonable
        self.assertIsInstance(data["rsi"], (int, float))
        self.assertIsInstance(data["macd"], (int, float))
    
    def test_is_stale(self):
        """Test stale data detection"""
        # Initially stale (never updated)
        self.assertTrue(self.provider.is_stale())
        
        # Add some price updates
        for i in range(10):
            price = 1.1000 + i * 0.0001
            self.currency_pair.update(price - 0.0001, price + 0.0001)
        
        time.sleep(0.1)  # Small delay
        
        # Should not be stale immediately
        self.assertFalse(self.provider.is_stale(max_age_seconds=60.0))


class TestFeatureCatalog(unittest.TestCase):
    """Test FeatureCatalog"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        # Mock the get_connection method
        self.mock_conn = Mock()
        self.mock_cursor = Mock()
        self.mock_db.get_connection.return_value = self.mock_conn
        self.mock_conn.cursor.return_value = self.mock_cursor
        
        from features.catalog import FeatureCatalog
        self.catalog = FeatureCatalog(self.mock_db)
    
    def test_store_features(self):
        """Test storing features"""
        features = [
            Feature(name="test1", data_type=float, source="test", description="Test 1"),
            Feature(name="test2", data_type=int, source="test", description="Test 2"),
        ]
        
        # Mock cursor.execute and fetchone
        self.mock_cursor.fetchone.return_value = None  # New feature
        self.mock_cursor.execute.return_value = None
        
        self.catalog.store_features(features)
        
        # Verify database calls were made
        self.assertTrue(self.mock_cursor.execute.called)
        self.mock_conn.commit.assert_called_once()
    
    def test_get_all_features(self):
        """Test retrieving all features"""
        # Mock database response
        self.mock_cursor.fetchall.return_value = [
            ("test1", "float", "test", "Test 1", "test", True),
            ("test2", "int", "test", "Test 2", "test", True),
        ]
        
        features = self.catalog.get_all_features()
        
        self.assertEqual(len(features), 2)
        self.assertEqual(features[0].name, "test1")
        self.assertEqual(features[1].name, "test2")
    
    def test_get_features_by_source(self):
        """Test filtering features by source"""
        self.mock_cursor.fetchall.return_value = [
            ("test1", "float", "source1", "Test 1", "test", True),
        ]
        
        features = self.catalog.get_features_by_source("source1")
        
        self.assertEqual(len(features), 1)
        self.assertEqual(features[0].source, "source1")
    
    def test_get_features_by_category(self):
        """Test filtering features by category"""
        self.mock_cursor.fetchall.return_value = [
            ("test1", "float", "test", "Test 1", "price", True),
        ]
        
        features = self.catalog.get_features_by_category("price")
        
        self.assertEqual(len(features), 1)
        self.assertEqual(features[0].category, "price")
    
    def test_get_feature(self):
        """Test getting a single feature"""
        self.mock_cursor.fetchone.return_value = (
            "test1", "float", "test", "Test 1", "test", True
        )
        
        feature = self.catalog.get_feature("test1")
        
        self.assertIsNotNone(feature)
        self.assertEqual(feature.name, "test1")
    
    def test_update_feature_availability(self):
        """Test updating feature availability"""
        self.catalog.update_feature_availability("test1", False)
        
        # Verify update query was executed
        self.assertTrue(self.mock_cursor.execute.called)
        self.mock_conn.commit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
