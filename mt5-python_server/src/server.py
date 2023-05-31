"""
Class Server for connection to MetaTrader5
"""

import socket
import threading

import mariadb
from dotenv import dotenv_values

from database import Database


class Server:
    """
    Class for the server
    """
    def __init__(self, verbose=False):
        self.verbose = verbose
        config = dotenv_values("../../.env")

        try:
            self.db = Database()
        except mariadb.Error:
            return

        self.db_lock = threading.Lock()
        self.console_lock = threading.Lock()

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((config['SERVER_IP'], int(config['SERVER_PORT'])))

        if self.verbose:
            print(f"Server socket bind to {config['SERVER_IP']}:{config['SERVER_PORT']}:")

        self.start()

    def start(self):
        """
        Start of server
        """
        self.socket.listen(5)

        if self.verbose:
            with self.console_lock:
                print("Server now listening for MT5 EA")

        while True:
            client_conn, client_address = self.socket.accept()
            threading.Thread(target=self.receive_tick, args=(client_conn,)).start()

            with self.console_lock:
                print('Connected to', client_address)

    def receive_tick(self, client):
        """
        Receive tick from mt5 client
        """
        while True:
            data = client.recv(10000)
            data = data.decode("utf-8")

            if not data:
                break

            if self.verbose:
                with self.console_lock:
                    print(data)

            with self.db_lock:
                self.db.insert_forex_tick(data)

    def __del__(self):
        self.socket.close()
