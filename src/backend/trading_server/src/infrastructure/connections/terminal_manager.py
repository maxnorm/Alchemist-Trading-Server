"""
Terminal connection manager
Manages MT5 terminal connections
"""

import threading
import time
from typing import Dict, List, Optional

from infrastructure.zeromq.zeromq_connection_manager import ZeroMQConnectionManager
from models.account import Account
from mt5_connection.zeromq_terminal import ZeroMQTerminal


class TerminalManager:
    """Manages MT5 terminal connections"""

    def __init__(self, zmq_manager: ZeroMQConnectionManager) -> None:
        """Initialize terminal manager"""
        self.accounts: List[Account] = []
        self.zmq_manager = zmq_manager

    def authenticate_terminal(self, infos: Dict) -> Optional[Account]:
        """
        Authenticate and set up a terminal connection
        :param infos: Authentication info dictionary
        :return: Account instance or None if failed
        """
        login = infos.get("login")
        auth_token = infos.get("auth_token")
        if not login or not auth_token:
            return None

        terminal = self.zmq_manager.connect_terminal(
            account_login=login,
            auth_token=auth_token,
            port_offset=(login % 100),
        )

        # Find existing account or create new one
        login = infos["login"]
        account = self._find_account(login)

        if account:
            account.set_terminal(terminal)
        else:
            account = Account(login, terminal=terminal)
            self.accounts.append(account)

        # Start heartbeat to keep connection alive
        self._start_heartbeat(terminal, login)

        return account

    def _find_account(self, login: int) -> Optional[Account]:
        """Find account by login"""
        for account in self.accounts:
            if account.login == login:
                return account
        return None

    def get_account(self, login: int) -> Optional[Account]:
        """Get account by login"""
        return self._find_account(login)

    def get_all_accounts(self) -> List[Account]:
        """Get all accounts"""
        return self.accounts.copy()

    def _start_heartbeat(
        self, terminal: ZeroMQTerminal, login: int, interval: int = 30
    ):
        """Background heartbeat to keep MT5 terminal connection alive"""

        def _loop():
            while True:
                time.sleep(interval)
                try:
                    lock = self.zmq_manager.get_terminal_lock(login)
                    if lock:
                        with lock:
                            terminal.ping_sync()
                    else:
                        terminal.ping_sync()
                except Exception:
                    break

        threading.Thread(target=_loop, daemon=True).start()
