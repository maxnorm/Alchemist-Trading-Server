"""
Enum for socket connection code from MetaTrader5
"""
from enum import IntEnum


class SocketAuthCode(IntEnum):
    """
    Enum for all code use to
    authentification of socket from mt5
    """
    STREAMER = 1
    TERMINAL = 2
