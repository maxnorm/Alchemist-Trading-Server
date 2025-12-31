"""
Price history manager
Manages price history per currency pair
"""
from typing import Dict, List, Optional
import logging
import time

from data_providers.price_provider import PriceDataProvider


class PriceHistoryManager:
    """Manages price history per currency pair"""
    
    def __init__(self, window_size: int, data_providers: List[PriceDataProvider]):
        """
        Initialize price history manager
        :param window_size: Window size for price history
        :param data_providers: List of data providers
        """
        self.window_size = window_size
        self.price_history_by_pair: Dict[str, List[float]] = {}
        self.last_update_time: Dict[str, float] = {}  # symbol -> timestamp
        
        # Initialize for each provider
        for provider in data_providers:
            symbol = provider.currency_pair.symbol
            self.price_history_by_pair[symbol] = []
            self.last_update_time[symbol] = 0.0
    
    def add_price(self, symbol: str, price: float):
        """
        Add price to history
        :param symbol: Currency pair symbol
        :param price: Price value
        """
        if symbol not in self.price_history_by_pair:
            self.price_history_by_pair[symbol] = []
        
        self.price_history_by_pair[symbol].append(price)
        self.last_update_time[symbol] = time.time()
        
        # Prune if too long (keep more for indicators calculation)
        if len(self.price_history_by_pair[symbol]) > self.window_size * 2:
            self.price_history_by_pair[symbol].pop(0)
        
        # Log when we reach sufficient data for first time
        if len(self.price_history_by_pair[symbol]) == self.window_size:
            logger = logging.getLogger('ai_model')
            logger.info(f"✅ Sufficient data collected for {symbol}: {len(self.price_history_by_pair[symbol])}/{self.window_size} points")
    
    def get_history(self, symbol: str) -> List[float]:
        """
        Get price history for symbol
        :param symbol: Currency pair symbol
        :return: List of prices
        """
        return self.price_history_by_pair.get(symbol, [])
    
    def has_sufficient_data(self, symbol: str) -> bool:
        """
        Check if sufficient data collected
        :param symbol: Currency pair symbol
        :return: True if sufficient data
        """
        return len(self.get_history(symbol)) >= self.window_size
    
    def get_all_histories(self) -> Dict[str, List[float]]:
        """
        Get all price histories
        :return: Dictionary of symbol -> price history
        """
        return self.price_history_by_pair.copy()
    
    def get_data_status(self) -> List[str]:
        """
        Get data status for all pairs
        :return: List of status strings
        """
        status = []
        for symbol, history in self.price_history_by_pair.items():
            status.append(f"{symbol}: {len(history)}/{self.window_size}")
        return status
    
    def load_historical_data(self, database, symbols: List[str], limit: int = 100, hours: int = 24):
        """
        Load historical price data from database
        :param database: Database instance
        :param symbols: List of currency pair symbols
        :param limit: Maximum number of ticks per symbol
        :param hours: Hours to look back
        """
        logger = logging.getLogger(__name__)
        
        for symbol in symbols:
            try:
                ticks = database.get_recent_ticks(symbol, limit=limit, hours=hours)
                
                for tick in ticks:
                    self.add_price(symbol, tick['mid_price'])
                
                loaded_count = len(self.price_history_by_pair.get(symbol, []))
                if loaded_count >= self.window_size:
                    logger.info(
                        f"✅ Loaded {loaded_count} historical points for {symbol} "
                        f"(sufficient for trading)"
                    )
                else:
                    logger.warning(
                        f"⚠️ Only loaded {loaded_count} points for {symbol} "
                        f"(need {self.window_size}, will wait for more ticks)"
                    )
            except Exception as e:
                logger.error(f"Error loading historical data for {symbol}: {e}", exc_info=True)
    
    def get_last_update_time(self, symbol: str) -> Optional[float]:
        """
        Get last update time for a symbol
        :param symbol: Currency pair symbol
        :return: Timestamp of last update, or None if never updated
        """
        return self.last_update_time.get(symbol)
    
    def get_data_staleness(self, symbol: str) -> Optional[float]:
        """
        Get data staleness in seconds
        :param symbol: Currency pair symbol
        :return: Seconds since last update, or None if never updated
        """
        if symbol not in self.last_update_time:
            return None
        last_update = self.last_update_time[symbol]
        if last_update == 0.0:
            return None
        return time.time() - last_update
