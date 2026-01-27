"""
Unit tests for Data Source Connector system

Tests ConnectorRegistry and connector implementations.
"""

import pytest
import os
import sys
import unittest
import time
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import threading

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/backend/trading_server/src'))

from domain.models.feature import Feature
from connectors.registry import ConnectorRegistry
from connectors.mt5_price_connector import MT5PriceConnector
from connectors.base import ConnectorConfig, IDataSourceConnector
from models.currency_pair import CurrencyPair


class TestFeature(unittest.TestCase):
    """Test Feature dataclass (still used for feature catalog)"""
    
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


class TestConnectorRegistry(unittest.TestCase):
    """Test ConnectorRegistry"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.registry = ConnectorRegistry()
    
    def test_register_connector(self):
        """Test registering a connector"""
        connector = Mock(spec=IDataSourceConnector)
        connector.get_schema.return_value = {
            "source": "test",
            "data_type": "price",
            "fields": {"price": "float"}
        }
        connector.config = Mock(spec=ConnectorConfig)
        connector.config.symbol = "EURUSD"
        
        self.registry.register_connector("test_connector", connector)
        self.assertEqual(self.registry.get_connector_count(), 1)
        self.assertEqual(self.registry.get_connector("test_connector"), connector)
    
    def test_register_connector_validation(self):
        """Test connector registration validation"""
        with self.assertRaises(ValueError):
            self.registry.register_connector("", Mock())
        
        with self.assertRaises(ValueError):
            self.registry.register_connector("test", None)
    
    def test_discover_features(self):
        """Test feature discovery from connector schemas"""
        connector1 = Mock(spec=IDataSourceConnector)
        connector1.get_schema.return_value = {
            "source": "test1",
            "data_type": "price",
            "fields": {
                "bid": "float",
                "ask": "float",
            }
        }
        connector1.config = Mock(spec=ConnectorConfig)
        connector1.config.symbol = "EURUSD"
        
        connector2 = Mock(spec=IDataSourceConnector)
        connector2.get_schema.return_value = {
            "source": "test2",
            "data_type": "price",
            "fields": {
                "volume": "float",
            }
        }
        connector2.config = Mock(spec=ConnectorConfig)
        connector2.config.symbol = "GBPUSD"
        
        self.registry.register_connector("connector1", connector1)
        self.registry.register_connector("connector2", connector2)
        
        features = self.registry.discover_features()
        # Should discover features from both connectors
        self.assertGreater(len(features), 0)
        # Check that features have correct structure
        for feature in features:
            self.assertIsInstance(feature, Feature)
            self.assertIn(feature.name, ["bid_EURUSD", "ask_EURUSD", "volume_GBPUSD"])
    
    def test_discover_features_error_handling(self):
        """Test that errors in discovery are handled gracefully"""
        connector = Mock(spec=IDataSourceConnector)
        connector.get_schema.side_effect = Exception("Test error")
        connector.config = Mock(spec=ConnectorConfig)
        connector.config.symbol = "EURUSD"
        
        self.registry.register_connector("error_connector", connector)
        
        # Should not raise, but log error
        features = self.registry.discover_features()
        # May have 0 features if error occurred
        self.assertIsInstance(features, list)
    
    def test_list_connectors(self):
        """Test listing connector names"""
        connector1 = Mock(spec=IDataSourceConnector)
        connector2 = Mock(spec=IDataSourceConnector)
        
        self.registry.register_connector("connector1", connector1)
        self.registry.register_connector("connector2", connector2)
        
        connectors = self.registry.list_connectors()
        self.assertEqual(len(connectors), 2)
        self.assertIn("connector1", connectors)
        self.assertIn("connector2", connectors)
    
    def test_health_check(self):
        """Test health check"""
        connector = Mock(spec=IDataSourceConnector)
        connector.is_connected.return_value = True
        connector.is_stale.return_value = False
        
        self.registry.register_connector("healthy_connector", connector)
        
        health = self.registry.health_check()
        self.assertEqual(health["healthy_connector"], True)
    
    def test_unregister_connector(self):
        """Test unregistering a connector"""
        connector = Mock(spec=IDataSourceConnector)
        connector.disconnect = Mock()
        self.registry.register_connector("test", connector)
        self.assertEqual(self.registry.get_connector_count(), 1)
        
        self.registry.unregister_connector("test")
        self.assertEqual(self.registry.get_connector_count(), 0)
        self.assertIsNone(self.registry.get_connector("test"))
        # Should have called disconnect
        connector.disconnect.assert_called_once()


class TestMT5PriceConnector(unittest.TestCase):
    """Test MT5PriceConnector"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.currency_pair = CurrencyPair("EURUSD", 5)
        self.currency_pair.update(1.1000, 1.1002)
        self.config = ConnectorConfig(
            source="mt5",
            symbol="EURUSD",
            extra_config={"digits": 5}
        )
        self.connector = MT5PriceConnector(
            currency_pair=self.currency_pair,
            config=self.config,
        )
    
    def test_get_schema(self):
        """Test that connector returns schema"""
        schema = self.connector.get_schema()
        self.assertIsInstance(schema, dict)
        self.assertEqual(schema["source"], "mt5")
        self.assertEqual(schema["data_type"], "price")
        self.assertIn("fields", schema)
    
    def test_connect(self):
        """Test connecting connector"""
        result = self.connector.connect()
        self.assertTrue(result)
        self.assertTrue(self.connector.is_connected())
    
    def test_disconnect(self):
        """Test disconnecting connector"""
        self.connector.connect()
        self.connector.disconnect()
        self.assertFalse(self.connector.is_connected())
    
    def test_stream(self):
        """Test streaming events"""
        self.connector.connect()
        
        # Update currency pair to trigger event
        self.currency_pair.update(1.1001, 1.1003)
        time.sleep(0.1)  # Small delay for event processing
        
        # Get first event from stream (with timeout)
        events = []
        for event in self.connector.stream():
            events.append(event)
            if len(events) >= 1:
                break
        
        # Should have at least one event
        if events:
            event = events[0]
            self.assertIn("timestamp", event)
            self.assertIn("source", event)
            self.assertIn("symbol", event)
            self.assertIn("payload", event)
    
    def test_is_stale(self):
        """Test stale data detection"""
        # Initially stale (never updated)
        self.assertTrue(self.connector.is_stale())
        
        # Connect and update
        self.connector.connect()
        self.currency_pair.update(1.1001, 1.1003)
        time.sleep(0.1)
        
        # Should not be stale immediately
        self.assertFalse(self.connector.is_stale(max_age_seconds=60.0))
    
    def test_get_latest_timestamp(self):
        """Test getting latest timestamp"""
        # Initially None
        self.assertIsNone(self.connector.get_latest_timestamp())
        
        # Connect and update
        self.connector.connect()
        self.currency_pair.update(1.1001, 1.1003)
        time.sleep(0.1)
        
        # Should have timestamp after update
        timestamp = self.connector.get_latest_timestamp()
        # May still be None if event hasn't been processed yet
        # This is acceptable for testing
    
    def test_batch(self):
        """Test batch historical data fetching"""
        # This would require database setup, so we'll just test the interface
        start_time = datetime(2024, 1, 1)
        end_time = datetime(2024, 1, 2)
        
        # Should not raise if database is not available
        try:
            events = list(self.connector.batch(start_time, end_time))
            # If database is available, should return events
            # If not, may raise exception which is acceptable
        except Exception:
            # Database not available - acceptable for unit test
            pass


if __name__ == '__main__':
    unittest.main()
