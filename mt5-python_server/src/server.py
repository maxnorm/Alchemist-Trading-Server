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


class Server:
    """
    Class for the server

    The server and data are base in the GMT+3 timezone
    """

    def __init__(self, verbose=False):
        config = dotenv_values("../../.env")

        self.__verbose = verbose

        self.__all_client = []
        self.__stop_char_tick = '\n'
        self.__ea_streamer = config['MT5_TICK_STREAMER']

        self.__db = Database()
        self.__myfxbook = WebCrawlerMyfxbook(
            email=config['MYFXBOOK_EMAIL'],
            password=config['MYFXBOOK_PASSWORD'],
            url=config['URL_MYFXBOOK']
        )

        self.__db_lock = threading.Lock()
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
            threading.Thread(target=self.__receive_tick, args=(client_conn,)).start()

            self.__all_client.append(client_conn)

            with self.__console_lock:
                print_with_datetime(f'Connected to {client_address}')

    def __receive_tick(self, client):
        """
        Receive tick from mt5 client
        and store them in the database
        """
        cum_data = ''
        while True:
            data = client.recv(1024).decode("utf-8")

            cum_data += data

            if self.__stop_char_tick in cum_data:

                final_data = cum_data[:cum_data.index(self.__stop_char_tick)]

                if self.__verbose:
                    with self.__console_lock:
                        print_with_datetime(final_data)

                self.__db.insert_forex_tick(final_data)
                cum_data = ''

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

    def __del__(self):
        self.__socket.close()
