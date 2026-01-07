"""
Authentication handler for socket connections
"""

import json
import socket
from typing import Dict, Any, Callable, Optional

from codes.socket_code import Socket
from utils.time_utils import print_with_datetime


class AuthenticationHandler:
    """Handles authentication for socket connections"""

    def __init__(self, stop_char: str = "\n", verbose: bool = False, console_lock=None):
        """
        Initialize authentication handler
        :param stop_char: Character that marks end of message
        :param verbose: Enable verbose logging
        :param console_lock: Thread lock for console output
        """
        self.stop_char = stop_char
        self.verbose = verbose
        self.console_lock = console_lock
        self.streamer_handler: Optional[Callable] = None
        self.terminal_handler: Optional[Callable] = None

    def set_streamer_handler(self, handler: Callable):
        """Set handler for streamer authentication"""
        self.streamer_handler = handler

    def set_terminal_handler(self, handler: Callable):
        """Set handler for terminal authentication"""
        self.terminal_handler = handler

    def authenticate(self, client: socket.socket) -> Optional[Dict[str, Any]]:
        """
        Authenticate a client connection
        :param client: Client socket
        :return: Authentication info dictionary or None if failed
        """
        cum_data = ""
        while True:
            try:
                data = client.recv(1024).decode("utf-8")
                if not data:
                    return None

                cum_data += data

                if self.stop_char in cum_data:
                    infos_str = cum_data[: cum_data.index(self.stop_char)]
                    infos = json.loads(infos_str)

                    if self.verbose and self.console_lock:
                        with self.console_lock:
                            print_with_datetime(
                                f"Received authentification infos: {infos}"
                            )

                    auth_code = infos.get("auth_code")

                    if auth_code == Socket.STREAMER.value:
                        if self.streamer_handler:
                            self.streamer_handler(client, infos)
                        else:
                            self._reject_auth(client, "Streamer handler not set")
                    elif auth_code == Socket.TERMINAL.value:
                        if self.terminal_handler:
                            self.terminal_handler(client, infos)
                        else:
                            self._reject_auth(client, "Terminal handler not set")
                    else:
                        self._reject_auth(
                            client, f"Invalid authentification code [{auth_code}]"
                        )

                    return infos
            except json.JSONDecodeError as e:
                if self.verbose:
                    print_with_datetime(f"JSON decode error: {e}")
                return None
            except Exception as e:
                if self.verbose:
                    print_with_datetime(f"Error during authentication: {e}")
                return None

    def _reject_auth(self, client: socket.socket, reason: str):
        """
        Reject authentication
        :param client: Client socket
        :param reason: Reason for rejection
        """
        data = {"auth_status": Socket.FAILED_AUTH.value}
        try:
            client.send(bytes(json.dumps(data) + "\n", "utf-8"))
            if self.verbose:
                print_with_datetime(f"Authentication rejected: {reason}")
        except Exception as e:
            if self.verbose:
                print_with_datetime(f"Error sending rejection: {e}")
