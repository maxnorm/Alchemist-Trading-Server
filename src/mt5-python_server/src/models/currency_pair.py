"""
Class for currency pairs
"""
import logging
import threading

logger = logging.getLogger(__name__)


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
        self._lock = threading.Lock()

    @property
    def mid_price(self):
        """
        Return the price of the pair
        """
        if self.bid is None or self.ask is None:
            return None
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
        with self._lock:
            self.subscribers.append(callback)

    def notify_subscribers(self):
        """
        Notify all subscribers
        """
        with self._lock:
            subscribers_copy = self.subscribers.copy()
        
        for callback in subscribers_copy:
            try:
                callback(self)
            except Exception as e:
                logger.error(f"Subscriber callback failed: {e}", exc_info=True)
