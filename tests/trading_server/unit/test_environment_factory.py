"""
Unit tests for EnvironmentFactory

Tests for creating all environment types (LIVE, PAPER, HISTORICAL) and backward compatibility.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from tests.shared.helpers.path_utils import setup_trading_server_path
setup_trading_server_path()

from infrastructure.factories.environment_factory import EnvironmentFactory
from domain.environment_type import EnvironmentType
from environments.base_trading_env import BaseTradingEnv
from environments.live_env import LiveTradingEnv
from environments.paper_env import PaperTradingEnv
from environments.historical_env import HistoricalTradingEnv
from models.account import Account
from connectors.base import IDataSourceConnector


class TestEnvironmentFactory:
    """Tests for EnvironmentFactory"""

    @pytest.fixture
    def factory(self):
        """Create factory instance"""
        return EnvironmentFactory()

    @pytest.fixture
    def mock_account(self):
        """Create mock account"""
        account = Mock(spec=Account)
        account.login = 12345
        account.balance = 10000.0
        return account

    @pytest.fixture
    def mock_connectors(self):
        """Create mock connectors"""
        connector = Mock(spec=IDataSourceConnector)
        connector.connect = Mock()
        return [connector]

    @pytest.fixture
    def sample_historical_data(self):
        """Create sample historical data"""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='1min')
        data = pd.DataFrame({
            'timestamp': dates,
            'bid': np.random.uniform(1.08, 1.09, len(dates)),
            'ask': np.random.uniform(1.08, 1.09, len(dates)) + 0.0002,
            'volume': np.random.randint(100, 1000, len(dates))
        })
        return data

    def test_create_live_environment(self, factory, mock_account, mock_connectors):
        """Test creating live trading environment"""
        env = factory.create_environment(
            environment_type=EnvironmentType.LIVE,
            account=mock_account,
            connectors=mock_connectors,
            window_size=50,
            seed=42
        )

        assert isinstance(env, LiveTradingEnv)
        assert isinstance(env, BaseTradingEnv)
        assert factory.has_environment(mock_account.login)
        assert factory.get_environment(mock_account.login) == env

    def test_create_paper_environment(self, factory, mock_account, mock_connectors):
        """Test creating paper trading environment"""
        env = factory.create_environment(
            environment_type=EnvironmentType.PAPER,
            account=mock_account,
            connectors=mock_connectors,
            window_size=50,
            seed=42
        )

        assert isinstance(env, PaperTradingEnv)
        assert isinstance(env, BaseTradingEnv)
        assert factory.has_environment(mock_account.login)
        assert factory.get_environment(mock_account.login) == env

    def test_create_historical_environment(self, factory, sample_historical_data):
        """Test creating historical trading environment"""
        env = factory.create_environment(
            environment_type=EnvironmentType.HISTORICAL,
            data=sample_historical_data,
            window_size=50,
            seed=42,
            initial_balance=10000.0,
            transaction_cost=0.0001
        )

        assert isinstance(env, HistoricalTradingEnv)
        assert isinstance(env, BaseTradingEnv)

    def test_default_environment_type_is_live(self, factory, mock_account, mock_connectors):
        """Test that default environment type is LIVE (backward compatibility)"""
        env = factory.create_environment(
            account=mock_account,
            connectors=mock_connectors,
            window_size=50,
            seed=42
        )

        assert isinstance(env, LiveTradingEnv)
        assert isinstance(env, BaseTradingEnv)

    def test_backward_compatibility_old_signature(self, factory, mock_account, mock_connectors):
        """Test that old signature still works (backward compatibility)"""
        # Old signature: create_environment(account, connectors, window_size, seed)
        env = factory.create_environment(
            account=mock_account,
            connectors=mock_connectors,
            window_size=50,
            seed=42
        )

        assert isinstance(env, LiveTradingEnv)
        assert factory.has_environment(mock_account.login)

    def test_live_environment_requires_account(self, factory, mock_connectors):
        """Test that live environment requires account"""
        with pytest.raises(ValueError, match="Account is required"):
            factory.create_environment(
                environment_type=EnvironmentType.LIVE,
                connectors=mock_connectors,
                window_size=50
            )

    def test_live_environment_requires_connectors(self, factory, mock_account):
        """Test that live environment requires connectors"""
        with pytest.raises(ValueError, match="Connectors are required"):
            factory.create_environment(
                environment_type=EnvironmentType.LIVE,
                account=mock_account,
                window_size=50
            )

    def test_paper_environment_requires_account(self, factory, mock_connectors):
        """Test that paper environment requires account"""
        with pytest.raises(ValueError, match="Account is required"):
            factory.create_environment(
                environment_type=EnvironmentType.PAPER,
                connectors=mock_connectors,
                window_size=50
            )

    def test_paper_environment_requires_connectors(self, factory, mock_account):
        """Test that paper environment requires connectors"""
        with pytest.raises(ValueError, match="Connectors are required"):
            factory.create_environment(
                environment_type=EnvironmentType.PAPER,
                account=mock_account,
                window_size=50
            )

    def test_historical_environment_requires_data(self, factory):
        """Test that historical environment requires data"""
        with pytest.raises(ValueError, match="Data is required"):
            factory.create_environment(
                environment_type=EnvironmentType.HISTORICAL,
                window_size=50
            )

    def test_historical_environment_defaults(self, factory, sample_historical_data):
        """Test historical environment uses default values"""
        env = factory.create_environment(
            environment_type=EnvironmentType.HISTORICAL,
            data=sample_historical_data,
            window_size=50
        )

        assert isinstance(env, HistoricalTradingEnv)
        assert env.initial_balance == 10000.0  # Default
        assert env.transaction_cost == 0.0001  # Default

    def test_historical_environment_custom_params(self, factory, sample_historical_data):
        """Test historical environment accepts custom parameters"""
        from environments.slippage_models import FixedSlippage

        env = factory.create_environment(
            environment_type=EnvironmentType.HISTORICAL,
            data=sample_historical_data,
            window_size=50,
            initial_balance=50000.0,
            transaction_cost=0.0005,
            slippage_model=FixedSlippage(0.0002)
        )

        assert isinstance(env, HistoricalTradingEnv)
        assert env.initial_balance == 50000.0
        assert env.transaction_cost == 0.0005

    def test_invalid_environment_type(self, factory):
        """Test that invalid environment type raises error"""
        with pytest.raises(ValueError, match="Unknown environment type"):
            # Create a mock enum value that doesn't exist
            class InvalidType:
                pass
            factory.create_environment(environment_type=InvalidType())

    def test_remove_environment(self, factory, mock_account, mock_connectors):
        """Test removing environment from factory"""
        env = factory.create_environment(
            account=mock_account,
            connectors=mock_connectors,
            window_size=50
        )

        assert factory.has_environment(mock_account.login)
        factory.remove_environment(mock_account.login)
        assert not factory.has_environment(mock_account.login)
        assert factory.get_environment(mock_account.login) is None

    def test_get_environment_nonexistent(self, factory):
        """Test getting non-existent environment returns None"""
        assert factory.get_environment(99999) is None
        assert not factory.has_environment(99999)

    def test_window_size_default(self, factory, mock_account, mock_connectors):
        """Test that window_size uses factory default if not provided"""
        factory_with_default = EnvironmentFactory(default_window_size=100)
        env = factory_with_default.create_environment(
            account=mock_account,
            connectors=mock_connectors
        )

        assert env.window_size == 100

    def test_window_size_override(self, factory, mock_account, mock_connectors):
        """Test that window_size can be overridden"""
        factory_with_default = EnvironmentFactory(default_window_size=100)
        env = factory_with_default.create_environment(
            account=mock_account,
            connectors=mock_connectors,
            window_size=75
        )

        assert env.window_size == 75

    def test_seed_propagation(self, factory, mock_account, mock_connectors, sample_historical_data):
        """Test that seed is properly propagated to environments"""
        seed = 12345

        # Test live environment
        live_env = factory.create_environment(
            account=mock_account,
            connectors=mock_connectors,
            seed=seed
        )
        assert live_env.get_seed() == seed

        # Test paper environment
        paper_env = factory.create_environment(
            environment_type=EnvironmentType.PAPER,
            account=mock_account,
            connectors=mock_connectors,
            seed=seed
        )
        assert paper_env.get_seed() == seed

        # Test historical environment
        hist_env = factory.create_environment(
            environment_type=EnvironmentType.HISTORICAL,
            data=sample_historical_data,
            seed=seed
        )
        assert hist_env.get_seed() == seed

    def test_multiple_environments_same_factory(self, factory, mock_connectors):
        """Test creating multiple environments with same factory"""
        account1 = Mock(spec=Account)
        account1.login = 11111
        account2 = Mock(spec=Account)
        account2.login = 22222

        env1 = factory.create_environment(
            account=account1,
            connectors=mock_connectors
        )
        env2 = factory.create_environment(
            account=account2,
            connectors=mock_connectors
        )

        assert env1 != env2
        assert factory.get_environment(account1.login) == env1
        assert factory.get_environment(account2.login) == env2
        assert factory.has_environment(account1.login)
        assert factory.has_environment(account2.login)

    def test_feature_filtering_live_environment(self, factory, mock_account):
        """Test that feature filtering works for live environment"""
        # Create connectors with different symbols
        connector1 = Mock(spec=IDataSourceConnector)
        connector1.config = Mock()
        connector1.config.symbol = "EURUSD"
        connector1.get_schema = Mock(return_value={
            "source": "mt5",
            "data_type": "tick",
            "fields": {
                "price_bid": "float",
                "price_ask": "float",
                "volume": "int"
            }
        })

        connector2 = Mock(spec=IDataSourceConnector)
        connector2.config = Mock()
        connector2.config.symbol = "GBPUSD"
        connector2.get_schema = Mock(return_value={
            "source": "mt5",
            "data_type": "tick",
            "fields": {
                "price_bid": "float",
                "price_ask": "float"
            }
        })

        connectors = [connector1, connector2]

        # Filter by features for EURUSD only
        features = ["price_bid_EURUSD", "rsi_14_EURUSD"]
        env = factory.create_environment(
            environment_type=EnvironmentType.LIVE,
            account=mock_account,
            connectors=connectors,
            window_size=50,
            features=features
        )

        assert isinstance(env, LiveTradingEnv)
        # Should have filtered connectors (at least EURUSD connector should be included)
        assert len(env.connectors) > 0
        # Check that selected_features is set
        assert env.selected_features == features

    def test_feature_filtering_paper_environment(self, factory, mock_account):
        """Test that feature filtering works for paper environment"""
        connector = Mock(spec=IDataSourceConnector)
        connector.config = Mock()
        connector.config.symbol = "EURUSD"
        connector.get_schema = Mock(return_value={
            "source": "mt5",
            "data_type": "tick",
            "fields": {
                "price_bid": "float",
                "volume": "int"
            }
        })

        features = ["price_bid_EURUSD"]
        env = factory.create_environment(
            environment_type=EnvironmentType.PAPER,
            account=mock_account,
            connectors=[connector],
            window_size=50,
            features=features
        )

        assert isinstance(env, PaperTradingEnv)
        assert env.selected_features == features

    def test_feature_filtering_no_matching_connectors(self, factory, mock_account):
        """Test that feature filtering raises error when no connectors match"""
        connector = Mock(spec=IDataSourceConnector)
        connector.config = Mock()
        connector.config.symbol = "EURUSD"
        connector.get_schema = Mock(return_value={
            "source": "mt5",
            "data_type": "tick",
            "fields": {
                "price_bid": "float"
            }
        })

        # Features for a different symbol that connector doesn't provide
        features = ["price_bid_JPYUSD", "rsi_14_JPYUSD"]

        with pytest.raises(ValueError, match="No connectors provide the selected features"):
            factory.create_environment(
                environment_type=EnvironmentType.LIVE,
                account=mock_account,
                connectors=[connector],
                window_size=50,
                features=features
            )

    def test_feature_filtering_backward_compatibility(self, factory, mock_account, mock_connectors):
        """Test that feature filtering is optional (backward compatibility)"""
        # Create environment without features parameter
        env = factory.create_environment(
            account=mock_account,
            connectors=mock_connectors,
            window_size=50
        )

        assert isinstance(env, LiveTradingEnv)
        # selected_features should be None when not specified
        assert env.selected_features is None

    def test_feature_filtering_none_value(self, factory, mock_account, mock_connectors):
        """Test that features=None uses all features (backward compatibility)"""
        env = factory.create_environment(
            account=mock_account,
            connectors=mock_connectors,
            window_size=50,
            features=None
        )

        assert isinstance(env, LiveTradingEnv)
        assert env.selected_features is None


class TestEnvironmentTypeEnum:
    """Tests for EnvironmentType enum"""

    def test_enum_values(self):
        """Test enum has correct values"""
        assert EnvironmentType.LIVE.value == "live"
        assert EnvironmentType.PAPER.value == "paper"
        assert EnvironmentType.HISTORICAL.value == "historical"

    def test_enum_string_conversion(self):
        """Test enum string conversion"""
        assert str(EnvironmentType.LIVE) == "live"
        assert str(EnvironmentType.PAPER) == "paper"
        assert str(EnvironmentType.HISTORICAL) == "historical"

    def test_from_string_valid(self):
        """Test from_string with valid values"""
        assert EnvironmentType.from_string("live") == EnvironmentType.LIVE
        assert EnvironmentType.from_string("paper") == EnvironmentType.PAPER
        assert EnvironmentType.from_string("historical") == EnvironmentType.HISTORICAL
        assert EnvironmentType.from_string("LIVE") == EnvironmentType.LIVE  # Case insensitive

    def test_from_string_invalid(self):
        """Test from_string with invalid values"""
        with pytest.raises(ValueError, match="Invalid environment type"):
            EnvironmentType.from_string("invalid")

    def test_enum_comparison(self):
        """Test enum comparison"""
        assert EnvironmentType.LIVE == EnvironmentType.LIVE
        assert EnvironmentType.LIVE != EnvironmentType.PAPER


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
