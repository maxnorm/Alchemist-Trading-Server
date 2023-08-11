"""
Trade Model
"""
from codes.order_type import OrderType


class Trade:
    """
    Class to represent a trade
    """

    def __init__(self, ticket, ordertype, pair, lotsize, open_price, sl, tp):
        self.ticket = ticket
        self.ordertype = ordertype
        self.pair = pair
        self.lotsize = lotsize
        self.open_price = open_price
        self.close_price = None
        self.sl = sl
        self.tp = tp

    def close(self, price):
        """
        Close the trade
        :param price: Price to close the trade
        """
        self.close_price = price

    def update_lotsize(self, lotsize):
        """
        Update the lotsize of the trade
        :param lotsize: New lotsize
        """
        self.lotsize = lotsize
