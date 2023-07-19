"""
Class for the trading interaction between MT5 and Python
"""
import asyncio
from code_enum.terminal_code import TerminalCode


def generate_new_id():
    """
    Generate a new id for each trading terminal
    by incrementing the last id
    """
    new_id = MT5Terminal.last_id + 1
    MT5Terminal.last_id = new_id
    return new_id


class MT5Terminal:
    """
    MT5 terminal connection for trading operation
    """
    last_id = 0

    def __init__(self, socket, stop_char='\n', separator='|'):
        self.__socket = socket
        self.__stop_char = stop_char
        self.__separator = separator

        self.id = generate_new_id()

    def __send_msg(self, msg):
        """
        Send a message to the terminal via socket by adding the stop character to end the message
        """
        self.__socket.send(bytes(msg + self.__stop_char, 'utf-8'))

    async def __get_response(self):
        """
        Get the response from MT5 terminal
        """
        cum_data = ''
        while True:
            data = self.__socket.recv(1024).decode("utf-8")

            cum_data += data
            if self.__stop_char in cum_data:
                return cum_data[:cum_data.index(self.__stop_char)].split(self.__separator)

    async def get_all_infos(self):
        """
        Get all the terminal infos
        """
        self.__send_msg(str(TerminalCode.ACCOUNT_INFO.value))
        return await self.__get_response()

    def __del__(self):
        self.__socket.close()
