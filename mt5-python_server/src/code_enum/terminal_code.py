"""
Enum for interaction between the server and MT5 Terminal
"""
from enum import IntEnum


class TerminalCode(IntEnum):
    """
    Enum for all code_enum use for interation
    with the socket from mt5
    """
    ACCOUNT_INFO = 100

