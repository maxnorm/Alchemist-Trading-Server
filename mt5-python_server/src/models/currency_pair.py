"""
Class for currency pairs
"""


class CurrencyPair:
    """
    Currency pair
    """

    def __init__(self, symbol, digits):
        self.symbol = symbol
        self.digits = digits
        self.bid = None
        self.ask = None

    @property
    def mid_price(self):
        """
        Return the price of the pair
        """
        return round((self.bid + self.ask) / 2, self.digits)

    def update(self, new_bid, new_ask):
        """
        Update the pair bid if it changed
        """
        if self.bid != new_bid:
            self.bid = new_bid

        if self.ask != new_ask:
            self.ask = new_ask
