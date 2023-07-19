"""
Class for currency pairs
"""


class CurrencyPair:
    """
    Currency pair
    """

    def __init__(self, symbol):
        self.symbol = symbol
        self.bid = None
        self.ask = None

    def update(self, new_bid, new_ask):
        """
        Update the pair bid if it changed
        """
        if self.bid != new_bid:
            self.bid = new_bid

        if self.ask != new_ask:
            self.ask = new_ask
