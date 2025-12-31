"""
Environment provider protocol
Defines contract for environment providers
"""
from typing import Protocol, Optional

from environments.live_env import LiveTradingEnv


class IEnvironmentProvider(Protocol):
    """Protocol for environment providers"""
    
    def get_environment(self, account_login: str) -> Optional[LiveTradingEnv]:
        """
        Get environment for an account
        :param account_login: Account login identifier
        :return: LiveTradingEnv instance or None if not found
        """
        ...
    
    def create_environment(
        self,
        account,
        data_providers,
        window_size: int = 50
    ) -> LiveTradingEnv:
        """
        Create a new trading environment
        :param account: Account instance
        :param data_providers: List of data providers
        :param window_size: Window size for state
        :return: Created LiveTradingEnv instance
        """
        ...
    
    def has_environment(self, account_login: str) -> bool:
        """
        Check if environment exists for account
        :param account_login: Account login identifier
        :return: True if environment exists
        """
        ...
