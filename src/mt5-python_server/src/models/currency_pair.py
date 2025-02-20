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
        self.subscribers = []

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
        if new_bid != self.bid or new_ask != self.ask:
            self.bid = new_bid
            self.ask = new_ask
            self.notify_subscribers()

    def subscribe(self, callback):
        """
        Subscribe to the pair
        """
        self.subscribers.append(callback)

    def notify_subscribers(self):
        """
        Notify all subscribers
        """
        for callback in self.subscribers:
            callback(self)
