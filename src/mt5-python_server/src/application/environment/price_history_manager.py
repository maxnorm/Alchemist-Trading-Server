"""
Price history manager
Manages price history per currency pair
"""

from typing import Dict, List, Optional
from datetime import datetime
import logging
import time
import threading

from connectors.base import IDataSourceConnector


class PriceHistoryManager:
    """Manages price history per currency pair"""

    def __init__(self, window_size: int, connectors: List[IDataSourceConnector]):
        """
        Initialize price history manager
        :param window_size: Window size for price history
        :param connectors: List of data source connectors
        """
        self.window_size = window_size
        self.price_history_by_pair: Dict[str, List[float]] = {}
        self.last_update_time: Dict[str, float] = {}  # symbol -> timestamp
        # Track bitemporal timestamps: (event_time, receive_time) tuples
        self.price_timestamps: Dict[str, List[tuple[datetime, Optional[datetime]]]] = {}
        
        # Background threads for consuming connector streams
        self._consumer_threads: List[threading.Thread] = []
        self._shutdown_flag = threading.Event()

        # Initialize for each connector
        for connector in connectors:
            symbol = connector.config.symbol
            self.price_history_by_pair[symbol] = []
            self.price_timestamps[symbol] = []
            self.last_update_time[symbol] = 0.0
            
            # Start consumer thread for this connector
            thread = threading.Thread(
                target=self._consume_connector,
                args=(connector, symbol),
                daemon=True
            )
            thread.start()
            self._consumer_threads.append(thread)
    
    def _consume_connector(self, connector: IDataSourceConnector, symbol: str):
        """
        Consume events from connector and update price history
        
        :param connector: Data source connector
        :param symbol: Trading symbol
        """
        logger = logging.getLogger(__name__)
        
        # Connect to connector if not already connected
        if not connector.is_connected():
            if not connector.connect():
                logger.error(f"Failed to connect to connector for {symbol}")
                return
        
        try:
            # Consume events from connector stream
            for event in connector.stream():
                if self._shutdown_flag.is_set():
                    break
                
                # Extract price from normalized event
                payload = event.get('payload', {})
                bid = payload.get('bid', 0.0)
                ask = payload.get('ask', 0.0)
                mid_price = (bid + ask) / 2.0
                
                # Extract event_time (timestamp) and receive_time
                event_time = event.get('timestamp')
                receive_time = event.get('receive_time')
                
                # Parse event_time
                if event_time:
                    if isinstance(event_time, str):
                        try:
                            event_time = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
                        except ValueError:
                            from utils.time_utils import get_utc_time
                            event_time = get_utc_time()
                    elif not isinstance(event_time, datetime):
                        from utils.time_utils import get_utc_time
                        event_time = get_utc_time()
                else:
                    from utils.time_utils import get_utc_time
                    event_time = get_utc_time()
                
                # Parse receive_time if present
                if receive_time:
                    if isinstance(receive_time, str):
                        try:
                            receive_time = datetime.fromisoformat(receive_time.replace("Z", "+00:00"))
                        except ValueError:
                            receive_time = None
                    elif not isinstance(receive_time, datetime):
                        receive_time = None
                else:
                    receive_time = None
                
                # Add price to history with bitemporal timestamps
                self.add_price(symbol, mid_price, event_time, receive_time)
                
        except Exception as e:
            logger.error(
                f"Error consuming connector stream for {symbol}: {e}",
                exc_info=True
            )
    
    def shutdown(self):
        """Shutdown all consumer threads"""
        self._shutdown_flag.set()
        for thread in self._consumer_threads:
            if thread.is_alive():
                thread.join(timeout=2.0)

    def add_price(
        self, 
        symbol: str, 
        price: float, 
        timestamp: Optional[datetime] = None,
        receive_time: Optional[datetime] = None
    ):
        """
        Add price to history with bitemporal timestamps
        :param symbol: Currency pair symbol
        :param price: Price value
        :param timestamp: Event time (when event occurred, defaults to current time if None)
        :param receive_time: Receive time (when we received it, optional)
        """
        if timestamp is None:
            from utils.time_utils import get_utc_time
            timestamp = get_utc_time()
        
        if symbol not in self.price_history_by_pair:
            self.price_history_by_pair[symbol] = []
            self.price_timestamps[symbol] = []

        self.price_history_by_pair[symbol].append(price)
        # Store as tuple: (event_time, receive_time)
        self.price_timestamps[symbol].append((timestamp, receive_time))
        self.last_update_time[symbol] = time.time()

        # Prune if too long (keep more for indicators calculation)
        if len(self.price_history_by_pair[symbol]) > self.window_size * 2:
            self.price_history_by_pair[symbol].pop(0)
            self.price_timestamps[symbol].pop(0)

        # Log when we reach sufficient data for first time
        if len(self.price_history_by_pair[symbol]) == self.window_size:
            logger = logging.getLogger("ai_model")
            history_len = len(self.price_history_by_pair[symbol])
            logger.info(
                f"✅ Sufficient data collected for {symbol}: "
                f"{history_len}/{self.window_size} points"
            )

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

    def load_historical_data(
        self, database, symbols: List[str], limit: int = 100, hours: int = 24
    ):
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
                    # Extract bitemporal timestamps if available
                    event_time = tick.get("event_time")
                    receive_time = tick.get("receive_time")
                    self.add_price(symbol, tick["mid_price"], event_time, receive_time)

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
                logger.error(
                    f"Error loading historical data for {symbol}: {e}", exc_info=True
                )

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

    def get_history_up_to(
        self, 
        symbol: str, 
        max_timestamp: datetime,
        query_by: str = 'receive_time'
    ) -> List[tuple[datetime, float, Optional[datetime]]]:
        """
        Get price history filtered to only include prices <= max_timestamp (point-in-time)
        :param symbol: Currency pair symbol
        :param max_timestamp: Maximum timestamp (point-in-time constraint)
        :param query_by: Filter by 'event_time' or 'receive_time' (default: 'receive_time' for point-in-time training)
        :return: List of tuples (event_time, price, receive_time) with timestamp <= max_timestamp
        """
        if symbol not in self.price_history_by_pair:
            return []
        
        prices = self.price_history_by_pair[symbol]
        timestamps = self.price_timestamps.get(symbol, [])
        
        # If no timestamps tracked, return all (backward compatibility)
        if not timestamps or len(timestamps) != len(prices):
            # Backward compatibility: return prices only
            return [(get_utc_time() if timestamp is None else timestamp, price, None) 
                    for price, timestamp in zip(prices, [None] * len(prices))]
        
        # Filter by point-in-time constraint
        filtered = []
        for price, (event_time, receive_time) in zip(prices, timestamps):
            if query_by == 'receive_time':
                # Filter by receive_time (transaction time) for point-in-time training
                filter_time = receive_time if receive_time is not None else event_time
                if filter_time <= max_timestamp:
                    filtered.append((event_time, price, receive_time))
            else:
                # Filter by event_time (valid time) for pattern learning
                if event_time <= max_timestamp:
                    filtered.append((event_time, price, receive_time))
        
        return filtered
