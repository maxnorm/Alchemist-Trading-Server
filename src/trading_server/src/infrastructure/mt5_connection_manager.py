"""
MT5 Connection Manager
Manages MT5 connections with thread-safe account switching for multiple accounts

This solves the scalability issue where MT5 Python API only supports:
- One mt5.initialize() call per process
- One active account at a time (via mt5.login())

For 1000+ accounts, this manager handles account switching efficiently.
"""

import MetaTrader5 as mt5
import threading
from typing import Dict, Optional
from utils.logging_config import get_logger


class MT5ConnectionManager:
    """
    Manages MT5 connections with account switching for multiple accounts.
    
    Thread-safe singleton that handles:
    - Single MT5 initialization per process
    - Account switching when needed
    - Connection state management
    """

    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self):
        """Initialize connection manager (private - use get_instance())"""
        self.logger = get_logger("mt5_connection_manager", "mt5_connection_manager.log")
        self._initialized = False
        self._current_login: Optional[int] = None
        self._current_server: Optional[str] = None
        self._lock = threading.RLock()  # Reentrant lock for nested calls
        self._account_cache: Dict[int, dict] = {}  # Cache account info to reduce switches

    @classmethod
    def get_instance(cls) -> "MT5ConnectionManager":
        """
        Get singleton instance (thread-safe)
        
        :return: MT5ConnectionManager instance
        """
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def initialize(self):
        """
        Initialize MT5 (only once per process, thread-safe)
        
        :raises ConnectionError: If initialization fails
        """
        with self._lock:
            if not self._initialized:
                if not mt5.initialize():
                    error = mt5.last_error()
                    self.logger.error(f"Failed to initialize MT5: {error}")
                    raise ConnectionError(f"Failed to initialize MT5: {error}")
                self._initialized = True
                self.logger.info("MT5 initialized successfully")

    def switch_account(self, login: int, password: str, server: str):
        """
        Switch to a different account (thread-safe)
        
        If already logged into this account, no switch is performed.
        
        :param login: MT5 account login
        :param password: MT5 account password
        :param server: MT5 broker server name
        :raises ConnectionError: If login fails
        """
        with self._lock:
            # If already logged into this account, no need to switch
            if self._current_login == login and self._current_server == server:
                return

            # Initialize if needed
            if not self._initialized:
                self.initialize()

            # Login to the account
            if not mt5.login(login, password=password, server=server):
                error = mt5.last_error()
                self.logger.error(f"Failed to login to account {login} on {server}: {error}")
                raise ConnectionError(f"Failed to login to account {login}: {error}")

            self._current_login = login
            self._current_server = server
            self.logger.debug(f"Switched to account {login} on server {server}")

    def get_account_info(self, login: int, password: str, server: str):
        """
        Get account info (switches account if needed)
        
        :param login: MT5 account login
        :param password: MT5 account password
        :param server: MT5 broker server name
        :return: MT5 account info object
        :raises ConnectionError: If login fails
        """
        self.switch_account(login, password, server)
        account_info = mt5.account_info()
        if account_info is None:
            error = mt5.last_error()
            raise ConnectionError(f"Failed to get account info: {error}")
        return account_info

    def get_positions(self, login: int, password: str, server: str):
        """
        Get positions for account (switches account if needed)
        
        :param login: MT5 account login
        :param password: MT5 account password
        :param server: MT5 broker server name
        :return: List of position objects
        """
        self.switch_account(login, password, server)
        positions = mt5.positions_get()
        if positions is None:
            # Not an error - just no positions
            return []
        return positions

    def order_send(self, login: int, password: str, server: str, request: dict):
        """
        Send order for account (switches account if needed)
        
        :param login: MT5 account login
        :param password: MT5 account password
        :param server: MT5 broker server name
        :param request: Order request dictionary
        :return: MT5 order result
        """
        self.switch_account(login, password, server)
        result = mt5.order_send(request)
        return result

    def get_current_account(self) -> Optional[int]:
        """
        Get currently active account login
        
        :return: Account login or None if not logged in
        """
        with self._lock:
            return self._current_login

    def shutdown(self):
        """
        Shutdown MT5 connection (thread-safe)
        
        Should be called on application shutdown.
        """
        with self._lock:
            if self._initialized:
                try:
                    mt5.logout()
                    mt5.shutdown()
                    self.logger.info("MT5 shutdown successfully")
                except Exception as e:
                    self.logger.error(f"Error during MT5 shutdown: {e}")
                finally:
                    self._initialized = False
                    self._current_login = None
                    self._current_server = None

    def __del__(self):
        """Cleanup on destruction"""
        try:
            self.shutdown()
        except Exception:
            pass  # Ignore errors during cleanup
