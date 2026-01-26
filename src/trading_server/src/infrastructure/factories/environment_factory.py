"""
Environment factory
Creates trading environments
"""

from typing import Dict, List, Optional
import pandas as pd

from environments.base_trading_env import BaseTradingEnv
from environments.live_env import LiveTradingEnv
from environments.paper_env import PaperTradingEnv
from environments.historical_env import HistoricalTradingEnv
from environments.slippage_models import SlippageModel
from models.account import Account
from connectors.base import IDataSourceConnector
from domain.constants import TradingConstants
from domain.environment_type import EnvironmentType


class EnvironmentFactory:
    """Factory for creating trading environments"""

    def __init__(self, default_window_size: Optional[int] = None):
        """
        Initialize environment factory
        :param default_window_size: Default window size for environments
        """
        self.default_window_size = (
            default_window_size or TradingConstants.DEFAULT_WINDOW_SIZE
        )
        self.environments: Dict[int, BaseTradingEnv] = (
            {}
        )  # account_login -> environment

    def create_environment(
        self,
        environment_type: EnvironmentType = EnvironmentType.LIVE,
        account: Optional[Account] = None,
        connectors: Optional[List[IDataSourceConnector]] = None,
        window_size: Optional[int] = None,
        seed: Optional[int] = None,
        features: Optional[List[str]] = None,
        # Historical-specific parameters
        data: Optional[pd.DataFrame] = None,
        initial_balance: Optional[float] = None,
        transaction_cost: Optional[float] = None,
        slippage_model: Optional[SlippageModel] = None,
    ) -> BaseTradingEnv:
        """
        Create a trading environment

        :param environment_type: Type of environment to create (default: LIVE for backward compatibility)
        :param account: Account instance (required for LIVE and PAPER)
        :param connectors: List of data source connectors (required for LIVE and PAPER)
        :param window_size: Window size (uses default if not provided)
        :param seed: Random seed for reproducibility
        :param features: Optional list of feature names to filter by (if None, uses all features)
        :param data: Historical data DataFrame (required for HISTORICAL)
        :param initial_balance: Initial balance for historical environment
        :param transaction_cost: Transaction cost for historical environment
        :param slippage_model: Slippage model for historical environment
        :return: Created environment instance (BaseTradingEnv)
        """
        window_size = window_size or self.default_window_size

        if environment_type == EnvironmentType.LIVE:
            return self._create_live_env(
                account=account,
                connectors=connectors,
                window_size=window_size,
                seed=seed,
                features=features,
            )
        elif environment_type == EnvironmentType.PAPER:
            return self._create_paper_env(
                account=account,
                connectors=connectors,
                window_size=window_size,
                seed=seed,
                features=features,
            )
        elif environment_type == EnvironmentType.HISTORICAL:
            return self._create_historical_env(
                data=data,
                window_size=window_size,
                seed=seed,
                initial_balance=initial_balance,
                transaction_cost=transaction_cost,
                slippage_model=slippage_model,
            )
        else:
            raise ValueError(f"Unknown environment type: {environment_type}")

    def _create_live_env(
        self,
        account: Optional[Account],
        connectors: Optional[List[IDataSourceConnector]],
        window_size: int,
        seed: Optional[int],
        features: Optional[List[str]] = None,
    ) -> LiveTradingEnv:
        """
        Create a live trading environment
        :param account: Account instance
        :param connectors: List of data source connectors
        :param window_size: Window size
        :param seed: Random seed
        :param features: Optional list of feature names to filter by
        :return: LiveTradingEnv instance
        """
        if account is None:
            raise ValueError("Account is required for live trading environment")
        if connectors is None:
            raise ValueError("Connectors are required for live trading environment")

        # Filter connectors by features if specified
        if features:
            filtered_connectors = self._filter_connectors_by_features(connectors, features)
            if not filtered_connectors:
                raise ValueError(
                    f"No connectors provide the selected features: {features}"
                )
            connectors = filtered_connectors

        env = LiveTradingEnv(
            account=account,
            connectors=connectors,
            window_size=window_size,
            seed=seed,
            selected_features=features,
        )

        self.environments[account.login] = env
        return env

    def _create_paper_env(
        self,
        account: Optional[Account],
        connectors: Optional[List[IDataSourceConnector]],
        window_size: int,
        seed: Optional[int],
        features: Optional[List[str]] = None,
    ) -> PaperTradingEnv:
        """
        Create a paper trading environment
        :param account: Account instance (demo account)
        :param connectors: List of data source connectors
        :param window_size: Window size
        :param seed: Random seed
        :param features: Optional list of feature names to filter by
        :return: PaperTradingEnv instance
        """
        if account is None:
            raise ValueError("Account is required for paper trading environment")
        if connectors is None:
            raise ValueError("Connectors are required for paper trading environment")

        # Filter connectors by features if specified
        if features:
            filtered_connectors = self._filter_connectors_by_features(connectors, features)
            if not filtered_connectors:
                raise ValueError(
                    f"No connectors provide the selected features: {features}"
                )
            connectors = filtered_connectors

        env = PaperTradingEnv(
            account=account,
            connectors=connectors,
            window_size=window_size,
            seed=seed,
            selected_features=features,
        )

        self.environments[account.login] = env
        return env

    def _create_historical_env(
        self,
        data: Optional[pd.DataFrame],
        window_size: int,
        seed: Optional[int],
        initial_balance: Optional[float],
        transaction_cost: Optional[float],
        slippage_model: Optional[SlippageModel],
    ) -> HistoricalTradingEnv:
        """
        Create a historical backtesting environment
        :param data: Historical data DataFrame
        :param window_size: Window size
        :param seed: Random seed
        :param initial_balance: Initial balance
        :param transaction_cost: Transaction cost
        :param slippage_model: Slippage model
        :return: HistoricalTradingEnv instance
        """
        if data is None:
            raise ValueError("Data is required for historical trading environment")

        env = HistoricalTradingEnv(
            data=data,
            window_size=window_size,
            initial_balance=initial_balance or 10000.0,
            transaction_cost=transaction_cost or 0.0001,
            slippage_model=slippage_model,
            seed=seed,
        )

        # Historical environments don't use account_login, use a synthetic key
        # Use hash of data shape and window_size as identifier
        env_key = hash((id(data), window_size, seed))
        self.environments[env_key] = env
        return env

    def get_environment(self, account_login: int) -> Optional[BaseTradingEnv]:
        """
        Get environment for an account
        :param account_login: Account login identifier
        :return: BaseTradingEnv instance or None if not found
        """
        return self.environments.get(account_login)

    def has_environment(self, account_login: int) -> bool:
        """
        Check if environment exists for account
        :param account_login: Account login identifier
        :return: True if environment exists
        """
        return account_login in self.environments

    def remove_environment(self, account_login: int):
        """
        Remove environment for an account
        :param account_login: Account login identifier
        """
        if account_login in self.environments:
            del self.environments[account_login]

    def _filter_connectors_by_features(
        self,
        connectors: List[IDataSourceConnector],
        features: List[str],
    ) -> List[IDataSourceConnector]:
        """
        Filter connectors to only those that provide at least one of the selected features.

        Features can be:
        - Connector features: e.g., "price_bid_EURUSD" (from connector schema)
        - Technical indicator features: e.g., "rsi_14_EURUSD" (computed by FeatureEngine)

        For connector features, we check if the connector's schema provides the feature.
        For technical indicator features, we keep connectors for pairs mentioned in the feature name.

        :param connectors: List of all available connectors
        :param features: List of feature names to filter by
        :return: Filtered list of connectors
        """
        if not features:
            return connectors

        filtered = []
        feature_set = set(features)

        # Extract symbols from feature names (e.g., "price_bid_EURUSD" -> "EURUSD")
        # Features are named as {field_name}_{symbol} or {indicator}_{symbol}
        symbols_from_features = set()
        for feature_name in features:
            # Try to extract symbol from end of feature name
            # Most features end with _{SYMBOL} where SYMBOL is 6 characters (e.g., EURUSD)
            parts = feature_name.rsplit("_", 1)
            if len(parts) == 2:
                potential_symbol = parts[1]
                # Check if it looks like a currency pair (6 uppercase letters)
                if len(potential_symbol) == 6 and potential_symbol.isupper():
                    symbols_from_features.add(potential_symbol)

        for connector in connectors:
            # Get connector symbol
            config = getattr(connector, "config", None)
            connector_symbol = (
                getattr(config, "symbol", None) if config else None
            )

            # Check if connector provides any selected features
            provides_feature = False

            # Method 1: Check if connector symbol matches any symbol from features
            if connector_symbol and connector_symbol in symbols_from_features:
                provides_feature = True
            else:
                # Method 2: Check connector schema for matching features
                try:
                    schema = connector.get_schema()
                    if isinstance(schema, dict):
                        fields = schema.get("fields", {})
                        if isinstance(fields, dict):
                            # Check if any field from this connector matches a selected feature
                            for field_name in fields.keys():
                                if field_name in ["timestamp", "symbol", "datetime"]:
                                    continue
                                # Feature name format: {field_name}_{symbol}
                                if connector_symbol:
                                    connector_feature_name = f"{field_name}_{connector_symbol}"
                                    if connector_feature_name in feature_set:
                                        provides_feature = True
                                        break
                except Exception:
                    # If schema retrieval fails, skip this connector
                    # (better to be conservative and include it if we're not sure)
                    pass

            if provides_feature:
                filtered.append(connector)

        return filtered
