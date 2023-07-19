"""
Enum for socket connection code_enum from MetaTrader5
"""
from enum import IntEnum


class SocketCode(IntEnum):
    """
    Enum for all code_enum use to
    authentification of socket from mt5
    """
    DECONNECTION = -2
    FAILED_AUTH = -1
    SUCCESSFUL_AUTH = 0
    STREAMER = 1
    TERMINAL = 2
