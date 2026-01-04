"""
Indicator Data Provider

Wraps TechnicalIndicators to expose technical indicators as data provider features.
Calculates indicators from price history buffer.
"""

import threading
import time
import logging
import numpy as np
from typing import List, Optional, Dict, Any
from models.currency_pair import CurrencyPair
from data_providers.base_provider import DataProvider, Feature
from utils.technical_indicators import TechnicalIndicators

logger = logging.getLogger(__name__)


class IndicatorProvider(DataProvider):
    """
    Data provider that wraps technical indicators.

    Maintains a price history buffer and calculates technical indicators
    on-demand. Subscribes to price updates to maintain the buffer.
    """

    def __init__(self, currency_pair: CurrencyPair, window_size: int = 100):
        """
        Initialize indicator provider.

        :param currency_pair: CurrencyPair instance to track
        :param window_size: Size of price history buffer
        """
        self.currency_pair = currency_pair
        self.symbol = currency_pair.symbol
        self.window_size = window_size
        self.price_history: List[float] = []
        self._price_lock = threading.Lock()
        self.subscribers: List[Any] = []
        self._subscriber_lock = threading.Lock()
        self.last_update_time: Optional[float] = None

        # Subscribe to currency pair updates
        self.currency_pair.subscribe(self._on_price_update)

    def _on_price_update(self, pair: CurrencyPair):
        """Callback when currency pair price updates."""
        mid_price = pair.mid_price
        if mid_price is not None:
            with self._price_lock:
                self.price_history.append(mid_price)
                # Keep only recent prices (window_size * 2 to have enough for indicators)
                if len(self.price_history) > self.window_size * 2:
                    self.price_history.pop(0)
                self.last_update_time = time.time()

            # Notify subscribers with current indicator data
            data = self.get_current_data()
            data["symbol"] = self.symbol
            data["provider"] = self

            with self._subscriber_lock:
                subscribers_copy = self.subscribers.copy()

            for callback in subscribers_copy:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Subscriber callback failed: {e}", exc_info=True)

    def get_current_data(self) -> Dict[str, Any]:
        """
        Calculate and return current indicator values.

        :return: Dictionary of indicator values
        """
        with self._price_lock:
            if len(self.price_history) < 2:
                # Not enough data - return default/NaN values
                return self._get_default_indicators()

            prices = np.array(self.price_history)

        # Calculate all indicators
        indicators = TechnicalIndicators.calculate_all_indicators(prices)

        # Return latest values (last element of each array)
        result = {}
        for key, values in indicators.items():
            if isinstance(values, np.ndarray) and len(values) > 0:
                # Get last non-NaN value, or last value if all NaN
                last_valid_idx = len(values) - 1
                for i in range(len(values) - 1, -1, -1):
                    if not np.isnan(values[i]):
                        last_valid_idx = i
                        break
                result[key] = (
                    float(values[last_valid_idx])
                    if not np.isnan(values[last_valid_idx])
                    else 0.0
                )
            else:
                result[key] = 0.0

        return result

    def _get_default_indicators(self) -> Dict[str, float]:
        """Return default indicator values when insufficient data."""
        return {
            "sma_20": 0.0,
            "sma_50": 0.0,
            "ema_12": 0.0,
            "ema_26": 0.0,
            "rsi": 50.0,  # Neutral RSI
            "macd": 0.0,
            "macd_signal": 0.0,
            "macd_histogram": 0.0,
            "bb_upper": 0.0,
            "bb_middle": 0.0,
            "bb_lower": 0.0,
            "bb_width": 0.0,
            "price_change": 0.0,
            "price_change_pct": 0.0,
        }

    def subscribe(self, callback):
        """Subscribe to indicator updates."""
        with self._subscriber_lock:
            self.subscribers.append(callback)

    def get_features(self) -> List[Feature]:
        """
        Return list of technical indicator features.

        :return: List of Feature objects for technical indicators
        """
        symbol = self.symbol
        return [
            Feature(
                name=f"rsi_14_{symbol}",
                data_type=float,
                source=f"indicator_{symbol}",
                description=f"Relative Strength Index (14-period) for {symbol}",
                category="technical",
            ),
            Feature(
                name=f"macd_line_{symbol}",
                data_type=float,
                source=f"indicator_{symbol}",
                description=f"MACD line (12-26-9) for {symbol}",
                category="technical",
            ),
            Feature(
                name=f"macd_signal_{symbol}",
                data_type=float,
                source=f"indicator_{symbol}",
                description=f"MACD signal line for {symbol}",
                category="technical",
            ),
            Feature(
                name=f"macd_histogram_{symbol}",
                data_type=float,
                source=f"indicator_{symbol}",
                description=f"MACD histogram for {symbol}",
                category="technical",
            ),
            Feature(
                name=f"bollinger_upper_{symbol}",
                data_type=float,
                source=f"indicator_{symbol}",
                description=f"Bollinger Bands upper band (20-period, 2 std) for {symbol}",
                category="technical",
            ),
            Feature(
                name=f"bollinger_middle_{symbol}",
                data_type=float,
                source=f"indicator_{symbol}",
                description=f"Bollinger Bands middle band (SMA 20) for {symbol}",
                category="technical",
            ),
            Feature(
                name=f"bollinger_lower_{symbol}",
                data_type=float,
                source=f"indicator_{symbol}",
                description=f"Bollinger Bands lower band (20-period, 2 std) for {symbol}",
                category="technical",
            ),
            Feature(
                name=f"bollinger_width_{symbol}",
                data_type=float,
                source=f"indicator_{symbol}",
                description=f"Bollinger Bands width (normalized) for {symbol}",
                category="technical",
            ),
            Feature(
                name=f"sma_20_{symbol}",
                data_type=float,
                source=f"indicator_{symbol}",
                description=f"Simple Moving Average (20-period) for {symbol}",
                category="technical",
            ),
            Feature(
                name=f"sma_50_{symbol}",
                data_type=float,
                source=f"indicator_{symbol}",
                description=f"Simple Moving Average (50-period) for {symbol}",
                category="technical",
            ),
            Feature(
                name=f"ema_12_{symbol}",
                data_type=float,
                source=f"indicator_{symbol}",
                description=f"Exponential Moving Average (12-period) for {symbol}",
                category="technical",
            ),
            Feature(
                name=f"ema_26_{symbol}",
                data_type=float,
                source=f"indicator_{symbol}",
                description=f"Exponential Moving Average (26-period) for {symbol}",
                category="technical",
            ),
            Feature(
                name=f"price_change_{symbol}",
                data_type=float,
                source=f"indicator_{symbol}",
                description=f"Price change (absolute) for {symbol}",
                category="technical",
            ),
            Feature(
                name=f"price_change_pct_{symbol}",
                data_type=float,
                source=f"indicator_{symbol}",
                description=f"Price change (percentage) for {symbol}",
                category="technical",
            ),
        ]

    def is_stale(self, max_age_seconds: float = 60.0) -> bool:
        """
        Check if indicator data is stale.

        :param max_age_seconds: Maximum age in seconds before considered stale
        :return: True if stale, False otherwise
        """
        if self.last_update_time is None:
            return True  # Never updated

        age = time.time() - self.last_update_time
        return age > max_age_seconds

    def get_data_age(self) -> Optional[float]:
        """
        Get age of data in seconds.

        :return: Age in seconds, or None if never updated
        """
        if self.last_update_time is None:
            return None
        return time.time() - self.last_update_time
