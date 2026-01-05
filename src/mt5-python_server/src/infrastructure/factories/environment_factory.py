"""
Environment factory
Creates trading environments
"""

from typing import Dict, List, Optional

from environments.live_env import LiveTradingEnv
from models.account import Account
from connectors.base import IDataSourceConnector
from domain.constants import TradingConstants


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
        self.environments: Dict[int, LiveTradingEnv] = (
            {}
        )  # account_login -> environment

    def create_environment(
        self,
        account: Account,
        connectors: List[IDataSourceConnector],
        window_size: Optional[int] = None,
    ) -> LiveTradingEnv:
        """
        Create a trading environment for an account
        :param account: Account instance
        :param connectors: List of data source connectors
        :param window_size: Window size (uses default if not provided)
        :return: Created LiveTradingEnv instance
        """
        window_size = window_size or self.default_window_size

        env = LiveTradingEnv(
            account=account, connectors=connectors, window_size=window_size
        )

        self.environments[account.login] = env
        return env

    def get_environment(self, account_login: int) -> Optional[LiveTradingEnv]:
        """
        Get environment for an account
        :param account_login: Account login identifier
        :return: LiveTradingEnv instance or None if not found
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
