from models.currency_pair import CurrencyPair
from data_providers.base_provider import DataProvider

class PriceDataProvider(DataProvider):
    def __init__(self, currency_pair: CurrencyPair):
        self.currency_pair = currency_pair
        self.subscribers = []
        
        # Subscribe to currency pair updates
        self.currency_pair.subscribe(self._on_price_update)
        
    def get_current_data(self):
        return {
            'bid': self.currency_pair.bid,
            'ask': self.currency_pair.ask,
            'mid': self.currency_pair.mid_price
        }
        
    def _on_price_update(self, pair):
        data = self.get_current_data()
        for callback in self.subscribers:
            callback(data)
            
    def subscribe(self, callback):
        self.subscribers.append(callback)
