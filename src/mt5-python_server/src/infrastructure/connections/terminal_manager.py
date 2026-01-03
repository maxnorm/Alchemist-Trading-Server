"""
Terminal connection manager
Manages MT5 terminal connections
"""
import json
import socket
import threading
import time
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
        # #region agent log
        try:
            import json as json_log, os
            log_path = os.path.join(os.getenv('LOG_DIR', '/app/logs'), 'debug.log')
            with open(log_path, 'a') as f:
                f.write(json_log.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"I","location":"terminal_manager.py:22","message":"authenticate_terminal entry","data":{"infos_keys":list(infos.keys())},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        if len(infos) != 2:
            return None
        
        terminal = MT5Terminal(client)
        
        # #region agent log
        try:
            import json as json_log, os
            sock_state = {'closed':False}
            try:
                client.getpeername()
            except Exception as e:
                sock_state['closed'] = True
                sock_state['error'] = str(e)
            log_path = os.path.join(os.getenv('LOG_DIR', '/app/logs'), 'debug.log')
            with open(log_path, 'a') as f:
                f.write(json_log.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"I","location":"terminal_manager.py:22","message":"authenticate_terminal socket state before send","data":sock_state,"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        
        # Send successful auth response
        data = {
            'auth_status': Socket.SUCCESSFUL_AUTH.value,
            'terminal_id': terminal.id
        }
        client.send(bytes(json.dumps(data) + '\n', 'utf-8'))
        
        # #region agent log
        try:
            import json as json_log, os
            sock_state = {'closed':False}
            try:
                client.getpeername()
            except Exception as e:
                sock_state['closed'] = True
                sock_state['error'] = str(e)
            log_path = os.path.join(os.getenv('LOG_DIR', '/app/logs'), 'debug.log')
            with open(log_path, 'a') as f:
                f.write(json_log.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"I","location":"terminal_manager.py:22","message":"authenticate_terminal socket state after send","data":sock_state,"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        
        # Find existing account or create new one
        login = infos['login']
        account = self._find_account(login)
        
        if account:
            account.set_terminal(terminal)
        else:
            account = Account(login, terminal)
            self.accounts.append(account)
        
        # Start heartbeat to keep connection alive
        self._start_heartbeat(terminal)
        
        # #region agent log
        try:
            import json as json_log, os
            log_path = os.path.join(os.getenv('LOG_DIR', '/app/logs'), 'debug.log')
            with open(log_path, 'a') as f:
                f.write(json_log.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"I","location":"terminal_manager.py:22","message":"authenticate_terminal complete","data":{"login":login,"terminal_id":terminal.id},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        
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
    
    def _start_heartbeat(self, terminal: MT5Terminal, interval: int = 30):
        """Background heartbeat to keep MT5 terminal connection alive"""
        def _loop():
            while True:
                time.sleep(interval)
                try:
                    terminal.ping_sync()
                except Exception:
                    break
        threading.Thread(target=_loop, daemon=True).start()