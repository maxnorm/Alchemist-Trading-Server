"""
Terminal connection manager
Manages MT5 terminal connections
"""
import json
import socket
from typing import Dict, List, Optional, Callable

from codes.socket_code import Socket
from models.account import Account
from mt5_connection.terminal import MT5Terminal


class TerminalManager:
    """Manages MT5 terminal connections"""
    
    def __init__(self):
        """Initialize terminal manager"""
        self.accounts: List[Account] = []
    
    def authenticate_terminal(
        self,
        client: socket.socket,
        infos: Dict
    ) -> Optional[Account]:
        """
        Authenticate and set up a terminal connection
        :param client: Client socket
        :param infos: Authentication info dictionary
        :return: Account instance or None if failed
        """
        if len(infos) != 2:
            return None
        
        terminal = MT5Terminal(client)
        
        # Send successful auth response
        data = {
            'auth_status': Socket.SUCCESSFUL_AUTH.value,
            'terminal_id': terminal.id
        }
        client.send(bytes(json.dumps(data) + '\n', 'utf-8'))
        
        # Find existing account or create new one
        login = infos['login']
        account = self._find_account(login)
        
        if account:
            account.set_terminal(terminal)
        else:
            from models.account import Account
            account = Account(login, terminal)
            self.accounts.append(account)
        
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
