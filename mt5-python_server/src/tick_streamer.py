"""
Class for the tick streaming operation from MT5
"""
import json

from database import Database
from utils.time_utils import print_with_datetime


class TickStreamer:
    """
    MT5 terminal connection for tick streaming
    """

    def __init__(self, socket, asset, stop_char='\n',
                 verbose=False, console_lock=None, ):
        self.__socket = socket
        self.__asset = asset
        self.__stop_char = stop_char
        self.__verbose = verbose
        self.__console_lock = console_lock
        self.__db = Database()

    def receive_tick(self):
        """
        Receive tick from mt5 client
        and store them in the database
        """
        cum_data = ''
        while True:
            data = self.__socket.recv(1024).decode("utf-8")

            cum_data += data

            if self.__stop_char in cum_data:
                final_data = cum_data[:cum_data.index(self.__stop_char)]

                if self.__verbose:
                    with self.__console_lock:
                        print_with_datetime(final_data)

                tick_info = json.loads(final_data)
                if len(tick_info) == 4:
                    symbol = tick_info['symbol']
                    date_time = tick_info['date_time']
                    ask = tick_info['ask']
                    bid = tick_info['bid']

                    self.__db.insert_forex_tick(symbol, date_time, ask, bid)
                    self.__asset.update(bid, ask)
                else:
                    print_with_datetime(f"Error wrong format of tick. Tick received: {tick_info}")
                cum_data = ''

    def __del__(self):
        self.__socket.close()
