"""
Socket server for handling socket connections
"""

import socket
from typing import Tuple, Optional


class SocketServer:
    """Handles socket server operations"""

    def __init__(self, host: str, port: int, verbose: bool = False):
        """
        Initialize socket server
        :param host: Server host address
        :param port: Server port
        :param verbose: Enable verbose logging
        """
        self.host = host
        self.port = port
        self.verbose = verbose
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.is_running = False

    def bind(self):
        """Bind socket to host and port"""
        self.socket.bind((self.host, self.port))
        if self.verbose:
            print(f"Server socket bound to {self.host}:{self.port}")

    def listen(self, backlog: int = 5):
        """
        Start listening for connections
        :param backlog: Maximum number of queued connections
        """
        self.socket.listen(backlog)
        self.is_running = True
        if self.verbose:
            print("Server now listening for MT5 EA")

    def accept(self) -> Optional[Tuple[socket.socket, Tuple[str, int]]]:
        """
        Accept a new connection
        :return: Tuple of (client_socket, client_address) or None if not running
        """
        if not self.is_running:
            return None

        try:
            client_conn, client_address = self.socket.accept()
            return client_conn, client_address
        except Exception as e:
            if self.verbose:
                print(f"Error accepting connection: {e}")
            return None

    def close(self):
        """Close the socket"""
        self.is_running = False
        try:
            self.socket.close()
        except Exception as e:
            if self.verbose:
                print(f"Error closing socket: {e}")
