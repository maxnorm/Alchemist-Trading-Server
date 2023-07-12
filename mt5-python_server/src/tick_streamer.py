"""
Class for the tick streaming operation from MT5
"""
from database import Database
from utils import print_with_datetime


class TickStreamer:
    """
    MT5 terminal connection for tick streaming
    """

    def __init__(self, socket, stop_char='\n', verbose=False, console_lock=None):
        self.__socket = socket
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

                self.__db.insert_forex_tick(final_data)
                cum_data = ''
