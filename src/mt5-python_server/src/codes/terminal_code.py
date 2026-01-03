"""
Enum for interaction between the server and MT5 Terminal
"""
from enum import IntEnum


class Terminal(IntEnum):
    """
    Enum for all codes use for interation
    with the socket from mt5
    """
    ACCOUNT_INFO = 100
    OPEN_ORDER = 101
    CLOSE_ORDER = 102
    MODIFY_ORDER = 103

