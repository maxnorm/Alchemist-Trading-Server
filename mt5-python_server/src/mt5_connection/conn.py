import json


class Connection:
    """
    Class to connect to MT5 terminal via socket
    """
    def __init__(self, socket, stop_char='\n', verbose=False, console_lock=None):
        self.__socket = socket
        self.__stop_char = stop_char
        self.__verbose = verbose
        self.__console_lock = console_lock

    def send_msg(self, msg):
        """
        Send a message to the terminal via socket by adding the stop character to end the message
        :param msg: message to send
        """
        self.__socket.send(bytes(msg + self.__stop_char, 'utf-8'))

    async def get_response(self):
        """
        Get the response in json fromat from MT5 terminal
        """
        cum_data = ''
        while True:
            data = self.__socket.recv(1024).decode("utf-8")

            cum_data += data
            if self.__stop_char in cum_data:
                return json.loads(cum_data[:cum_data.index(self.__stop_char)])

    def __del__(self):
        self.__socket.close()