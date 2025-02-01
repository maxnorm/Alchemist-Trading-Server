"""
Class Server for connection to MetaTrader5
"""
import os
import datetime
import json
import socket
import threading
import time

from dotenv import dotenv_values
from database import Database
from web_scraper.web_scraper_myfxbook import WebScraperMyfxbook
from utils.time_utils import print_with_datetime
from codes.socket_code import Socket
from mt5_connection.tick_streamer import MT5TickStreamer
from mt5_connection.terminal import MT5Terminal
from models.currency_pair import CurrencyPair
from models.account import Account


class Server:
    """
    Class for the server

    The server and data are base in the GMT+3 timezone
    """

    def __init__(self, verbose=False):
        self.__verbose = verbose
        self.__socket = None

        self.__streamers = []
        self.__accounts = []
        self.__all_currency_pairs = {}

        self.__stop_char = '\n'

        self.__db = Database()
        self.__myfxbook = WebScraperMyfxbook(
            email=os.getenv('MYFXBOOK_EMAIL'),
            password=os.getenv('MYFXBOOK_PASSWORD'),
            url=os.getenv('URL_MYFXBOOK')
        )

        self.__console_lock = threading.Lock()
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        server_ip = os.getenv('SERVER_IP')
        server_port = int(os.getenv('SERVER_PORT'))

        self.__socket.bind((server_ip, server_port))

        if self.__verbose:
            print_with_datetime(
                f"Server socket bind to {server_ip}:{server_port}"
            )

        self.start()

    def start(self):
        """
        Start the server
        """
        self.__socket.listen(5)

        if self.__verbose:
            with self.__console_lock:
                print_with_datetime("Server now listening for MT5 EA")

        threading.Thread(target=self.__collect_economic_calendar, args=(17, 10)).start()

        while True:
            client_conn, client_address = self.__socket.accept()

            with self.__console_lock:
                print_with_datetime(f'Connected to {client_address}')

            self.__auth_socket(client_conn)

    def __collect_economic_calendar(self, hour, minute):
        """
        Collect economic data from the economic calendar of yesterday at a specific time
        and store them in database
        """
        while True:
            now = datetime.datetime.now()
            if now.hour == hour and now.minute == minute and now.weekday() < 5:
                try:
                    data = self.__myfxbook.download_economic_calendar()
                    self.__db.insert_economic_calendar_data(data)

                    if self.__verbose:
                        with self.__console_lock:
                            print_with_datetime("Economic Calendar was download")
                except Exception as e:
                    with self.__console_lock:
                        print_with_datetime(f"Error while downloading economic calendar: {e}")

            time.sleep(60)

    def __auth_socket(self, client):
        """
        Receive auth code from the newly connected socket
        and create a new instance of TickStreamer or MT5Terminal
        """
        cum_data = ''
        while True:
            data = client.recv(1024).decode("utf-8")

            cum_data += data

            if self.__stop_char in cum_data:

                infos = cum_data[:cum_data.index(self.__stop_char)]
                infos = json.loads(infos)

                if self.__verbose:
                    with self.__console_lock:
                        print_with_datetime(f"Received authentification infos: {infos}")

                auth_code = infos['auth_code']

                if auth_code == Socket.STREAMER.value:
                    self.__auth_streamer(client, infos)
                elif auth_code == Socket.TERMINAL.value:
                    self.__auth_terminal(client, infos)
                else:
                    self.__invalid_auth(client, f'Invalid authentification code [{auth_code}]')
                break

    def __auth_streamer(self, client, infos):
        """
        Authentification step for a tick streamer
        Send an authentification codes if succesfull or not

        Expected message format:
            {
                "auth_code": 1,
                "symbol": Currency pair symbol
            }

        Successfull authentification response:
            {
                "auth_status": 0
            }
        """
        if len(infos) == 3:
            data = {
                "auth_status": Socket.SUCCESSFUL_AUTH.value
            }

            client.send(bytes(json.dumps(data) + '\n', 'utf-8'))

            pair = CurrencyPair(infos['symbol'], infos['digits'])
            self.__all_currency_pairs[infos['symbol']] = pair

            streamer = MT5TickStreamer(client, pair, self.__stop_char, self.__verbose, self.__console_lock)

            threading.Thread(target=streamer.receive_tick).start()
            self.__streamers.append(streamer)
        else:
            self.__invalid_auth(client, 'Invalid message format.')

    def __auth_terminal(self, client, infos):
        """
        Manage the authentification of a mt5 trading terminal
        Create a new MT5Terminal and attach it to an Account.

        Expected message format:
            {
                "auth_code": 2,
                "login": Account login
            }

        Successfull authentification response:
            {
                "auth_status": 0,
                "terminal_id": Current terminal id
            }
        """
        if len(infos) == 2:
            terminal = MT5Terminal(client)

            data = {
                'auth_status': Socket.SUCCESSFUL_AUTH.value,
                'terminal_id': terminal.id
            }

            client.send(bytes(json.dumps(data) + '\n',
                              'utf-8'))

            for account in self.__accounts:
                if account.login == infos['login']:
                    account.set_terminal(terminal)
                    return

            account = Account(infos['login'], terminal)
            self.__accounts.append(account)
        else:
            self.__invalid_auth(client, 'Invalid message format. Missing account login')

    def __invalid_auth(self, client, msg):
        """
        When the socket failed the authentification

        Failed authentification response:
            {
                "auth_status": -1
                "message": Error message provided
            }
        """
        data = {
            'auth_status': Socket.FAILED_AUTH.value,
            'message': msg
        }
        client.send(bytes(json.dumps(data) + '\n', 'utf-8'))

        with self.__console_lock:
            print_with_datetime(f'Error from {client.getpeername()}: {msg} .'
                                f'Closing connection.')
        client.close()

    def __del__(self):
        if self.__socket:
            self.__socket.close()
