import threading
import time
import logging
from typing import Optional, List
from models.currency_pair import CurrencyPair
from data_providers.base_provider import DataProvider, Feature

logger = logging.getLogger(__name__)

class PriceDataProvider(DataProvider):
    def __init__(self, currency_pair: CurrencyPair):
        self.currency_pair = currency_pair
        self.subscribers = []
        self._subscriber_lock = threading.Lock()
        self.last_update_time = None
        
        # Subscribe to currency pair updates
        self.currency_pair.subscribe(self._on_price_update)
        
    def get_current_data(self):
        mid = self.currency_pair.mid_price
        return {
            'bid': self.currency_pair.bid,
            'ask': self.currency_pair.ask,
            'mid': mid
        }
        
    def _on_price_update(self, pair):
        self.last_update_time = time.time()  # Track update time
        data = self.get_current_data()
        # Include provider reference in data for tracking
        data['provider'] = self
        data['symbol'] = self.currency_pair.symbol
        
        with self._subscriber_lock:
            subscribers_copy = self.subscribers.copy()
        
        for callback in subscribers_copy:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Subscriber callback failed: {e}", exc_info=True)
            
    def subscribe(self, callback):
        with self._subscriber_lock:
            self.subscribers.append(callback)
    
    def is_stale(self, max_age_seconds: float = 60.0) -> bool:
        """
        Check if data is stale
        :param max_age_seconds: Maximum age in seconds before considered stale
        :return: True if stale, False otherwise
        """
        if self.last_update_time is None:
            return True  # Never updated
        
        age = time.time() - self.last_update_time
        return age > max_age_seconds
    
    def get_data_age(self) -> Optional[float]:
        """
        Get age of data in seconds
        :return: Age in seconds, or None if never updated
        """
        if self.last_update_time is None:
            return None
        return time.time() - self.last_update_time
    
    def get_features(self) -> List[Feature]:
        """
        Return list of price features this provider offers.
        
        :return: List of Feature objects for price data
        """
        symbol = self.currency_pair.symbol
        return [
            Feature(
                name=f"price_bid_{symbol}",
                data_type=float,
                source=f"price_{symbol}",
                description=f"Bid price for {symbol}",
                category="price"
            ),
            Feature(
                name=f"price_ask_{symbol}",
                data_type=float,
                source=f"price_{symbol}",
                description=f"Ask price for {symbol}",
                category="price"
            ),
            Feature(
                name=f"price_mid_{symbol}",
                data_type=float,
                source=f"price_{symbol}",
                description=f"Mid price (average of bid and ask) for {symbol}",
                category="price"
            ),
            Feature(
                name=f"spread_{symbol}",
                data_type=float,
                source=f"price_{symbol}",
                description=f"Spread (ask - bid) for {symbol}",
                category="price"
            ),
        ]
