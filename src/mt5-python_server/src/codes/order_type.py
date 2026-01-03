"""
Enum for the type of order
"""
from enum import IntEnum


class OrderType(IntEnum):
    """
    Enum for the type of order send to the terminal
    """
    BUY = 0
    SELL = 1
    BUY_LIMIT = 2
    SELL_LIMIT = 3
    BUY_STOP = 4
    SELL_STOP = 5
    BUY_STOP_LIMIT = 6
    SELL_STOP_LIMIT = 7



