"""
Environment provider protocol
Defines contract for environment providers
"""

from typing import Protocol, Optional, List

from environments.base_trading_env import BaseTradingEnv
from domain.environment_type import EnvironmentType
from models.account import Account
from connectors.base import IDataSourceConnector


class IEnvironmentProvider(Protocol):
    """Protocol for environment providers"""

    def get_environment(self, account_login: int) -> Optional[BaseTradingEnv]:
        """
        Get environment for an account
        :param account_login: Account login identifier
        :return: BaseTradingEnv instance or None if not found
        """
        ...

    def create_environment(
        self,
        environment_type: EnvironmentType = EnvironmentType.LIVE,
        account: Optional[Account] = None,
        connectors: Optional[List[IDataSourceConnector]] = None,
        window_size: Optional[int] = None,
        seed: Optional[int] = None,
        features: Optional[List[str]] = None,
    ) -> BaseTradingEnv:
        """
        Create a new trading environment
        :param environment_type: Type of environment to create (default: LIVE)
        :param account: Account instance (required for LIVE and PAPER)
        :param connectors: List of data source connectors (required for LIVE and PAPER)
        :param window_size: Window size for state
        :param seed: Random seed for reproducibility
        :param features: Optional list of feature names to filter by (if None, uses all features)
        :return: Created BaseTradingEnv instance
        """
        ...

    def has_environment(self, account_login: int) -> bool:
        """
        Check if environment exists for account
        :param account_login: Account login identifier
        :return: True if environment exists
        """
        ...
