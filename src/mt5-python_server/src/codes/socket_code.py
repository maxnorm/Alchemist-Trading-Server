"""
Enum for socket connection codes from MetaTrader5
"""
from enum import IntEnum


class Socket(IntEnum):
    """
    Enum for all codes use to
    authentification of socket from mt5
    """
    DECONNECTION = -2
    FAILED_AUTH = -1
    SUCCESSFUL_AUTH = 0
    STREAMER = 1
    TERMINAL = 2
