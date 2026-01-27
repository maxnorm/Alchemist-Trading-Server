import asyncio
import os
import threading
from typing import Dict, Optional, TYPE_CHECKING

import zmq

from mt5_connection.zeromq_conn import ZeroMQConnection

if TYPE_CHECKING:
    from mt5_connection.zeromq_terminal import ZeroMQTerminal  # noqa: F401
    from mt5_connection.zeromq_tick_streamer import ZeroMQTickStreamer  # noqa: F401


class ZeroMQConnectionManager:
    """
    Manages ZeroMQ connections to MT5 EAs.
    EA binds REP/PUB sockets, Python connects via REQ for terminals.
    Streamers are queue-based and receive ticks from discovery service.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        order_port: int = 5556,
        tick_port: int = 5555,
        timeout: float = 30.0,
    ):
        self.host = host
        self.order_port = order_port
        self.tick_port = tick_port
        self.timeout = timeout
        self.context = zmq.Context()

        self._terminals: Dict[int, "ZeroMQTerminal"] = {}
        self._streamers_by_symbol: Dict[str, "ZeroMQTickStreamer"] = (
            {}
        )  # symbol -> streamer
        self._terminal_locks: Dict[int, threading.RLock] = {}
        self._lock = threading.RLock()

    def connect_terminal(
        self,
        account_login: int,
        auth_token: str,
        port_offset: int = 0,
    ):
        """
        Connect to MT5 EA terminal (REQ to EA REP).
        """
        with self._lock:
            if account_login in self._terminals:
                return self._terminals[account_login]

            port = self.order_port + port_offset
            req_socket = self.context.socket(zmq.REQ)
            req_socket.connect(f"tcp://{self.host}:{port}")

            zmq_conn = ZeroMQConnection(req_socket, "REQ", timeout=self.timeout)

            if not self._authenticate_terminal(zmq_conn, account_login, auth_token):
                req_socket.close()
                raise ConnectionError(
                    f"Authentication failed for account {account_login}"
                )

            from mt5_connection.zeromq_terminal import ZeroMQTerminal

            terminal = ZeroMQTerminal(zmq_conn)
            self._terminals[account_login] = terminal
            self._terminal_locks[account_login] = threading.RLock()

            return terminal

    def connect_streamer_by_symbol(
        self,
        symbol: str,
        digits: int = 5,
        port_offset: int = 0,
        token: Optional[str] = None,
        db=None,
    ):
        """
        Create a queue-based tick streamer for a symbol (for auto-discovery).

        Streamers no longer use SUB sockets - they receive ticks via queues
        from the discovery service which forwards all messages.

        :param symbol: Symbol name
        :param digits: Decimal precision
        :param port_offset: Port offset from base tick_port (unused, kept for compatibility)
        :param token: Streamer authentication token (validated)
        :param db: Optional database instance for tick storage
        :return: ZeroMQTickStreamer instance (queue-based, no SUB socket)
        :raises ConnectionError: If token validation fails
        """
        with self._lock:
            # Check if already connected by symbol
            if symbol in self._streamers_by_symbol:
                return self._streamers_by_symbol[symbol]

            # Validate token if provided
            if token is not None:
                if not self._validate_streamer_token(token):
                    raise ConnectionError(f"Invalid streamer token for {symbol}")

            # Create queue-based streamer (no SUB socket needed)
            # Discovery service forwards all ticks via put_tick()
            from mt5_connection.zeromq_tick_streamer import ZeroMQTickStreamer
            from models.currency_pair import CurrencyPair

            pair = CurrencyPair(symbol, digits)
            # Pass None for zmq_conn - streamer uses queue instead
            streamer = ZeroMQTickStreamer(None, pair, db=db)
            self._streamers_by_symbol[symbol] = streamer

            import logging

            logger = logging.getLogger("zeromq_connection_manager")
            logger.info(
                f"Created queue-based streamer for '{symbol}' "
                f"(digits: {digits}, discovery will forward ticks)"
            )

            return streamer

    def _validate_streamer_token(self, received_token: str) -> bool:
        """
        Validate streamer token against environment variable.

        :param received_token: Token received from streamer EA
        :return: True if token is valid
        """
        expected_token = os.getenv("STREAMER_AUTH_TOKEN")
        if not expected_token:
            return False  # Reject all if token not configured
        return received_token == expected_token

    def disconnect_streamer_by_symbol(self, symbol: str):
        """Disconnect streamer by symbol."""
        with self._lock:
            if symbol in self._streamers_by_symbol:
                del self._streamers_by_symbol[symbol]

    def get_terminal_lock(self, account_login: int) -> Optional[threading.RLock]:
        """Get request serialization lock for terminal."""
        return self._terminal_locks.get(account_login)

    def _authenticate_terminal(
        self,
        zmq_conn: ZeroMQConnection,
        account_login: int,
        auth_token: str,
    ) -> bool:
        """
        Authenticate with MT5 EA terminal using existing schema.
        """
        auth_request = {
            "auth_code": 2,
            "login": account_login,
            "auth_token": auth_token,
        }

        zmq_conn.send_msg(auth_request)
        response = asyncio.run(zmq_conn.get_response(timeout=10.0))
        return response.get("auth_status") == 0

    def disconnect_terminal(self, account_login: int):
        with self._lock:
            if account_login in self._terminals:
                del self._terminals[account_login]
                self._terminal_locks.pop(account_login, None)

    def shutdown(self):
        with self._lock:
            self._terminals.clear()
            self._streamers_by_symbol.clear()
            self._terminal_locks.clear()
            self.context.term()
