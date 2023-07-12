"""
Class Server for connection to MetaTrader5
"""
import datetime
import socket
import threading
import time

from dotenv import dotenv_values
from database import Database
from web_crawler_myfxbook import WebCrawlerMyfxbook
from utils import print_with_datetime
from socket_auth_code import SocketAuthCode
from tick_streamer import TickStreamer
from mt5_terminal import Terminal


class Server:
    """
    Class for the server

    The server and data are base in the GMT+3 timezone
    """

    def __init__(self, verbose=False):
        config = dotenv_values("../../.env")

        self.__verbose = verbose

        self.__streamers = []
        self.__terminals = {}
        self.__stop_char = '\n'

        self.__db = Database()
        self.__myfxbook = WebCrawlerMyfxbook(
            email=config['MYFXBOOK_EMAIL'],
            password=config['MYFXBOOK_PASSWORD'],
            url=config['URL_MYFXBOOK']
        )

        self.__console_lock = threading.Lock()
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.bind((config['SERVER_IP'], int(config['SERVER_PORT'])))

        if self.__verbose:
            print_with_datetime(
                f"Server socket bind to {config['SERVER_IP']}:{config['SERVER_PORT']}"
            )

        self.start()

    def start(self):
        """
        Start of server
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
                data = self.__myfxbook.download_economic_calendar()
                self.__db.insert_economic_calendar_data(data)
                if self.__verbose:
                    with self.__console_lock:
                        print_with_datetime("Economic Calendar download")
            time.sleep(60)

    def __auth_socket(self, client):
        """
        Receive auth code from the newly connected socket
        and create a new instance of the proper
        """
        cum_data = ''
        while True:
            data = client.recv(1024).decode("utf-8")

            cum_data += data

            if self.__stop_char in cum_data:

                final_data = cum_data[:cum_data.index(self.__stop_char)]

                if self.__verbose:
                    with self.__console_lock:
                        print_with_datetime(final_data)

                if int(final_data) == SocketAuthCode.STREAMER.value:
                    streamer = TickStreamer(client, self.__stop_char,
                                            self.__verbose, self.__console_lock)
                    threading.Thread(target=streamer.receive_tick).start()
                    self.__streamers.append(streamer)
                elif int(final_data) == SocketAuthCode.TERMINAL.value:
                    self.__terminals = Terminal(client)
                else:
                    print_with_datetime(f"Error: Invalid authentification code from {client.getpeername()}. "
                                        f"Closing connection.")
                    client.close()
                break

    def __del__(self):
        self.__socket.close()
