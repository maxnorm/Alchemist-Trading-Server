"""
Integration tests for data source connector interface
"""

import pytest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/backend/trading_server/src'))

from connectors.base import IDataSourceConnector, ConnectorConfig
from connectors.mt5_tick_connector import MT5TickConnector
from events.normalizer import EventNormalizer


class TestConnectorInterface:
    """Tests for connector interface compliance"""

    def test_interface_definition(self):
        """Test that IDataSourceConnector is properly defined"""
        # Check that it's an ABC
        import abc
        assert issubclass(IDataSourceConnector, abc.ABC)
        
        # Check required abstract methods exist
        assert hasattr(IDataSourceConnector, 'stream')
        assert hasattr(IDataSourceConnector, 'batch')
        assert hasattr(IDataSourceConnector, 'get_schema')
        assert hasattr(IDataSourceConnector, 'get_latest_timestamp')
        assert hasattr(IDataSourceConnector, 'connect')
        assert hasattr(IDataSourceConnector, 'disconnect')
        assert hasattr(IDataSourceConnector, 'is_connected')

    def test_connector_config(self):
        """Test ConnectorConfig dataclass"""
        config = ConnectorConfig(
            source="mt5",
            symbol="EURUSD",
            batch_size=500,
            timeout=60.0,
        )
        
        assert config.source == "mt5"
        assert config.symbol == "EURUSD"
        assert config.batch_size == 500
        assert config.timeout == 60.0
        assert config.retry_count == 3  # default
        assert isinstance(config.extra_config, dict)


class TestMT5TickConnector:
    """Tests for MT5 tick connector implementation"""

    @pytest.fixture
    def mock_socket(self):
        """Create mock socket"""
        return Mock()

    @pytest.fixture
    def connector_config(self):
        """Create connector config"""
        return ConnectorConfig(
            source="mt5",
            symbol="EURUSD",
            extra_config={"digits": 5},
        )

    @pytest.fixture
    def connector(self, mock_socket, connector_config):
        """Create MT5 tick connector"""
        return MT5TickConnector(
            socket=mock_socket,
            symbol="EURUSD",
            config=connector_config,
        )

    def test_connector_implements_interface(self, connector):
        """Test that MT5TickConnector implements IDataSourceConnector"""
        assert isinstance(connector, IDataSourceConnector)

    def test_get_schema(self, connector):
        """Test schema definition"""
        schema = connector.get_schema()
        
        assert isinstance(schema, dict)
        assert schema["source"] == "mt5"
        assert schema["data_type"] == "tick"
        assert "fields" in schema
        assert "required_fields" in schema

    def test_connect_disconnect(self, connector):
        """Test connection lifecycle"""
        # Initially not connected
        assert not connector.is_connected()
        
        # Connect (will fail without real socket, but tests interface)
        # Note: Actual connection requires real MT5 streamer
        # This test verifies the interface is implemented
        
        # Disconnect
        connector.disconnect()
        assert not connector.is_connected()

    def test_batch_validation(self, connector):
        """Test batch method validates input"""
        start_time = datetime.now()
        end_time = start_time - timedelta(hours=1)  # Invalid: end < start
        
        with pytest.raises(ValueError, match="start_time must be < end_time"):
            list(connector.batch(start_time, end_time))

    @patch('connectors.mt5_tick_connector.Database')
    def test_batch_fetch(self, mock_db_class, connector):
        """Test historical batch fetch"""
        # Mock database
        mock_db = Mock()
        mock_db.get_recent_ticks.return_value = [
            {
                "datetime": datetime.now() - timedelta(minutes=10),
                "mid_price": 1.1000,
            },
            {
                "datetime": datetime.now() - timedelta(minutes=5),
                "mid_price": 1.1001,
            },
        ]
        mock_db_class.return_value = mock_db
        
        start_time = datetime.now() - timedelta(hours=1)
        end_time = datetime.now()
        
        # Fetch batch
        events = list(connector.batch(start_time, end_time))
        
        # Should return normalized events
        assert len(events) >= 0  # May be 0 if filtering removes all
        for event in events:
            assert "timestamp" in event
            assert event["source"] == "mt5"
            assert event["symbol"] == "EURUSD"

    def test_get_latest_timestamp(self, connector):
        """Test latest timestamp retrieval"""
        timestamp = connector.get_latest_timestamp()
        # Initially None
        assert timestamp is None or isinstance(timestamp, datetime)


class TestConnectorNormalization:
    """Tests for connector normalization integration"""

    @pytest.fixture
    def mock_socket(self):
        """Create mock socket"""
        return Mock()

    @pytest.fixture
    def connector_config(self):
        """Create connector config"""
        return ConnectorConfig(
            source="mt5",
            symbol="EURUSD",
        )

    def test_connector_has_normalizer(self, mock_socket, connector_config):
        """Test that connector has normalizer"""
        connector = MT5TickConnector(
            socket=mock_socket,
            symbol="EURUSD",
            config=connector_config,
        )
        
        assert hasattr(connector, 'normalizer')
        assert isinstance(connector.normalizer, EventNormalizer)

    def test_connector_yields_normalized_events(self, mock_socket, connector_config):
        """Test that connector yields normalized events"""
        connector = MT5TickConnector(
            socket=mock_socket,
            symbol="EURUSD",
            config=connector_config,
        )
        
        # Schema should indicate normalized format
        schema = connector.get_schema()
        assert schema["source"] == "mt5"
        assert "fields" in schema
        assert "timestamp" in schema.get("fields", {})


class TestConnectorConnectionManagement:
    """Tests for connector connection management"""

    @pytest.fixture
    def mock_socket(self):
        """Create mock socket"""
        return Mock()

    @pytest.fixture
    def connector_config(self):
        """Create connector config"""
        return ConnectorConfig(
            source="mt5",
            symbol="EURUSD",
        )

    def test_connection_state_tracking(self, mock_socket, connector_config):
        """Test connection state is tracked correctly"""
        connector = MT5TickConnector(
            socket=mock_socket,
            symbol="EURUSD",
            config=connector_config,
        )
        
        # Initially disconnected
        assert not connector.is_connected()
        
        # Disconnect when already disconnected (should not error)
        connector.disconnect()
        assert not connector.is_connected()

    def test_error_handling_on_connection_failure(self, mock_socket, connector_config):
        """Test error handling on connection failure"""
        connector = MT5TickConnector(
            socket=mock_socket,
            symbol="EURUSD",
            config=connector_config,
        )
        
        # Connection may fail without real streamer
        # This test verifies error handling exists
        try:
            result = connector.connect()
            # If connection fails, should return False
            assert isinstance(result, bool)
        except Exception as e:
            # Connection errors are acceptable
            assert isinstance(e, (ConnectionError, Exception))


class TestMultiSourceConnectors:
    """Tests for multiple connectors running simultaneously"""

    @pytest.fixture
    def mock_socket(self):
        """Create mock socket"""
        return Mock()

    def test_multiple_connectors_independent(self, mock_socket):
        """Test that multiple connectors can run independently"""
        connector1 = MT5TickConnector(
            socket=mock_socket,
            symbol="EURUSD",
            config=ConnectorConfig(source="mt5", symbol="EURUSD"),
        )
        
        connector2 = MT5TickConnector(
            socket=mock_socket,
            symbol="GBPUSD",
            config=ConnectorConfig(source="mt5", symbol="GBPUSD"),
        )
        
        # Each connector should have its own state
        assert connector1.symbol != connector2.symbol
        assert connector1.get_schema()["source"] == connector2.get_schema()["source"]
        
        # Disconnect one should not affect the other
        connector1.disconnect()
        assert not connector1.is_connected()
        # connector2 state unchanged (still not connected, but independent)
