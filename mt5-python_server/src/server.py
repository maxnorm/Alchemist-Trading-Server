"""
Classe du serveur de connexion a MetaTrader5
"""
import socket

from database import Database


class Server:
    """
    Classe de server
    """
    def __init__(self, ip, port):
        self.conn = None
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ip = ip
        self.port = port
        self.socket.bind((self.ip, self.port))
        self.start()

    def start(self):
        """
        Start du serveur
        """
        self.socket.listen(1)
        self.conn, address = self.socket.accept()
        print('connected to', address)

    def receive_msg(self):
        """
        Recevoir un message
        :return: Retourne le message recu
        """
        cummdata = ''

        while True:
            data = self.conn.recv(10000)
            cummdata += data.decode("utf-8")
            if not data:
                break
            print(cummdata)
            return cummdata

    def __del__(self):
        self.socket.close()
"""
    def store_tick(self):
        
        Store ticks in database
        :return:
        
        while True:
            tick = self.receive_msg()
            print(tick)
            if not self.database.insert_tick(tick):
                break
"""