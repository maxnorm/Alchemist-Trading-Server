"""
Integration tests for feature discovery flow

Tests the complete flow: registry → discovery → catalog → database
"""
import pytest
import unittest
from unittest.mock import Mock, patch

from tests.shared.helpers.path_utils import setup_trading_server_path
setup_trading_server_path()

from data_providers.registry import DataProviderRegistry
from domain.models.feature import Feature
from data_providers.price_provider import PriceDataProvider
from data_providers.indicator_provider import IndicatorProvider
from models.currency_pair import CurrencyPair


class TestFeatureDiscoveryFlow(unittest.TestCase):
    """Test complete feature discovery flow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.registry = DataProviderRegistry()
    
    def test_provider_registration_and_discovery(self):
        """Test registering providers and discovering features"""
        # Create currency pair and providers
        pair = CurrencyPair("EURUSD", 5)
        pair.update(1.1000, 1.1002)
        
        price_provider = PriceDataProvider(pair)
        indicator_provider = IndicatorProvider(pair, window_size=50)
        
        # Register providers
        self.registry.register_provider("price_EURUSD", price_provider)
        self.registry.register_provider("indicator_EURUSD", indicator_provider)
        
        # Discover features
        features = self.registry.discover_features()
        
        # Verify features were discovered
        self.assertGreater(len(features), 0)
        
        # Check price features
        price_features = [f for f in features if f.source == "price_EURUSD"]
        self.assertGreater(len(price_features), 0)
        self.assertTrue(any("price_bid" in f.name for f in price_features))
        self.assertTrue(any("price_ask" in f.name for f in price_features))
        
        # Check indicator features
        indicator_features = [f for f in features if f.source == "indicator_EURUSD"]
        self.assertGreater(len(indicator_features), 0)
        self.assertTrue(any("rsi" in f.name for f in indicator_features))
        self.assertTrue(any("macd" in f.name for f in indicator_features))
    
    def test_feature_catalog_sync(self):
        """Test syncing catalog with registry"""
        # This test requires a real database connection
        # For now, we'll mock it
        
        from features.catalog import FeatureCatalog
        mock_db = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_db.get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # New features
        
        catalog = FeatureCatalog(mock_db)
        
        # Create and register providers
        pair = CurrencyPair("EURUSD", 5)
        pair.update(1.1000, 1.1002)
        
        price_provider = PriceDataProvider(pair)
        self.registry.register_provider("price_EURUSD", price_provider)
        
        # Sync catalog
        catalog.sync_with_registry(self.registry)
        
        # Verify database operations were called
        self.assertTrue(mock_cursor.execute.called)
        mock_conn.commit.assert_called()
    
    def test_provider_health_check(self):
        """Test provider health checking"""
        pair = CurrencyPair("EURUSD", 5)
        pair.update(1.1000, 1.1002)
        
        price_provider = PriceDataProvider(pair)
        self.registry.register_provider("price_EURUSD", price_provider)
        
        # Check health
        health = self.registry.check_health()
        
        self.assertIn("price_EURUSD", health)
        # Initially stale (never updated via streamer)
        # But after update, should be healthy
        self.assertIsInstance(health["price_EURUSD"], bool)
    
    def test_multiple_providers_same_pair(self):
        """Test multiple providers for the same currency pair"""
        pair = CurrencyPair("EURUSD", 5)
        pair.update(1.1000, 1.1002)
        
        price_provider = PriceDataProvider(pair)
        indicator_provider = IndicatorProvider(pair, window_size=50)
        
        self.registry.register_provider("price_EURUSD", price_provider)
        self.registry.register_provider("indicator_EURUSD", indicator_provider)
        
        # Both should be registered
        self.assertEqual(self.registry.get_provider_count(), 2)
        
        # Both should provide features
        features = self.registry.discover_features()
        price_features = [f for f in features if "price" in f.name]
        indicator_features = [f for f in features if "rsi" in f.name or "macd" in f.name]
        
        self.assertGreater(len(price_features), 0)
        self.assertGreater(len(indicator_features), 0)
    
    def test_feature_uniqueness(self):
        """Test that feature names are unique per provider"""
        pair1 = CurrencyPair("EURUSD", 5)
        pair2 = CurrencyPair("GBPUSD", 5)
        
        pair1.update(1.1000, 1.1002)
        pair2.update(1.2500, 1.2502)
        
        provider1 = PriceDataProvider(pair1)
        provider2 = PriceDataProvider(pair2)
        
        self.registry.register_provider("price_EURUSD", provider1)
        self.registry.register_provider("price_GBPUSD", provider2)
        
        features = self.registry.discover_features()
        feature_names = [f.name for f in features]
        
        # Each feature should be unique
        self.assertEqual(len(feature_names), len(set(feature_names)))
        
        # Features from different pairs should have different names
        eurusd_features = [f for f in features if "EURUSD" in f.name]
        gbpusd_features = [f for f in features if "GBPUSD" in f.name]
        
        self.assertGreater(len(eurusd_features), 0)
        self.assertGreater(len(gbpusd_features), 0)
        
        # No overlap in names
        eurusd_names = {f.name for f in eurusd_features}
        gbpusd_names = {f.name for f in gbpusd_features}
        self.assertEqual(len(eurusd_names & gbpusd_names), 0)


class TestProviderErrorHandling(unittest.TestCase):
    """Test error handling in provider system"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.registry = DataProviderRegistry()
    
    def test_provider_with_exception_in_get_features(self):
        """Test that provider errors don't break discovery"""
        # Create a provider that raises an exception
        bad_provider = Mock()
        bad_provider.get_features.side_effect = Exception("Test error")
        
        # Register bad provider
        self.registry.register_provider("bad_provider", bad_provider)
        
        # Discovery should continue despite error
        features = self.registry.discover_features()
        
        # Should return empty list (or features from other providers)
        self.assertIsInstance(features, list)
    
    def test_provider_with_invalid_features(self):
        """Test handling of invalid feature objects"""
        # Create a provider that returns invalid features
        bad_provider = Mock()
        bad_provider.get_features.return_value = [
            "not a feature",  # Invalid
            None,  # Invalid
        ]
        
        self.registry.register_provider("bad_provider", bad_provider)
        
        # Discovery should skip invalid features
        features = self.registry.discover_features()
        
        # Should only contain valid features
        for feature in features:
            self.assertIsInstance(feature, Feature)


if __name__ == '__main__':
    unittest.main()
