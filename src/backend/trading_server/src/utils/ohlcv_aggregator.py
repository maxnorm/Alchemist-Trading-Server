"""
OHLCV Aggregator Utility
Converts tick data to OHLCV bars for multiple timeframes
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class TickToOHLCVAggregator:
    """
    Aggregates tick data to OHLCV bars for multiple timeframes.

    Uses mid-price (average of bid/ask) for OHLC calculations.
    Supports point-in-time aggregation (no future data).
    """

    # Timeframe to timedelta mapping
    TIMEFRAME_MAP = {
        "M1": timedelta(minutes=1),
        "M5": timedelta(minutes=5),
        "M15": timedelta(minutes=15),
        "M30": timedelta(minutes=30),
        "H1": timedelta(hours=1),
        "H4": timedelta(hours=4),
        "D1": timedelta(days=1),
    }

    def __init__(self):
        """Initialize OHLCV aggregator"""
        pass

    def _calculate_mid_price(self, bid: float, ask: float) -> float:
        """
        Calculate mid-price from bid and ask

        :param bid: Bid price
        :param ask: Ask price
        :return: Mid price
        """
        if bid <= 0 or ask <= 0:
            return 0.0
        return (bid + ask) / 2.0

    def _align_to_timeframe(self, dt: datetime, timeframe: str) -> datetime:
        """
        Align datetime to timeframe boundary

        :param dt: Datetime to align
        :param timeframe: Timeframe string (M1, M5, etc.)
        :return: Aligned datetime
        """
        if timeframe == "M1":
            return dt.replace(second=0, microsecond=0)
        elif timeframe == "M5":
            return dt.replace(minute=(dt.minute // 5) * 5, second=0, microsecond=0)
        elif timeframe == "M15":
            return dt.replace(minute=(dt.minute // 15) * 15, second=0, microsecond=0)
        elif timeframe == "M30":
            return dt.replace(minute=(dt.minute // 30) * 30, second=0, microsecond=0)
        elif timeframe == "H1":
            return dt.replace(minute=0, second=0, microsecond=0)
        elif timeframe == "H4":
            return dt.replace(
                hour=(dt.hour // 4) * 4, minute=0, second=0, microsecond=0
            )
        elif timeframe == "D1":
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

    def aggregate_ticks(
        self, ticks: List[Dict[str, Any]], timeframe: str
    ) -> List[Dict[str, Any]]:
        """
        Aggregate tick data to OHLCV bars for a single timeframe

        :param ticks: List of tick dictionaries with keys:
                     - timestamp (datetime)
                     - bid (float)
                     - ask (float)
                     - volume (float, optional)
        :param timeframe: Timeframe string (M1, M5, M15, M30, H1, H4, D1)
        :return: List of bar dictionaries with keys:
                 - datetime (datetime)
                 - open (float)
                 - high (float)
                 - low (float)
                 - close (float)
                 - volume (float, optional)
        """
        if timeframe not in self.TIMEFRAME_MAP:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        if not ticks:
            return []

        # Sort ticks by timestamp
        # Handle None values by using a sentinel datetime.min
        from datetime import datetime as dt

        sorted_ticks = sorted(
            ticks,
            key=lambda t: t.get("timestamp") or t.get("datetime") or dt.min,
        )

        bars = []
        current_bar = None
        bar_start_time = None

        for tick in sorted_ticks:
            # Extract tick data
            tick_time = tick.get("timestamp") or tick.get("datetime")
            if not tick_time:
                continue

            if not isinstance(tick_time, datetime):
                # Try to parse if it's a string
                try:
                    if isinstance(tick_time, str):
                        tick_time = datetime.fromisoformat(
                            tick_time.replace("Z", "+00:00")
                        )
                    else:
                        continue
                except Exception:
                    continue

            bid = tick.get("bid", 0.0)
            ask = tick.get("ask", 0.0)
            volume = tick.get("volume")

            # Calculate mid-price
            mid_price = self._calculate_mid_price(bid, ask)
            if mid_price <= 0:
                continue

            # Align to timeframe boundary
            aligned_time = self._align_to_timeframe(tick_time, timeframe)

            # Check if we need a new bar
            if current_bar is None or bar_start_time != aligned_time:
                # Save previous bar if exists
                if current_bar is not None:
                    bars.append(current_bar)

                # Start new bar
                bar_start_time = aligned_time
                current_bar = {
                    "datetime": aligned_time,
                    "open": mid_price,
                    "high": mid_price,
                    "low": mid_price,
                    "close": mid_price,
                    "volume": volume if volume is not None else 0.0,
                }
            else:
                # Update current bar
                current_bar["high"] = max(current_bar["high"], mid_price)
                current_bar["low"] = min(current_bar["low"], mid_price)
                current_bar["close"] = mid_price
                if volume is not None:
                    current_bar["volume"] = current_bar.get("volume", 0.0) + volume

        # Add final bar
        if current_bar is not None:
            bars.append(current_bar)

        return bars

    def aggregate_timeframe(
        self,
        ticks: List[Dict[str, Any]],
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Aggregate ticks for a specific timeframe within a time range

        :param ticks: List of tick dictionaries
        :param timeframe: Timeframe string
        :param start_time: Optional start time filter
        :param end_time: Optional end time filter
        :return: List of bar dictionaries
        """
        # Filter ticks by time range if provided
        filtered_ticks = ticks
        if start_time or end_time:
            filtered_ticks = []
            for tick in ticks:
                tick_time = tick.get("timestamp") or tick.get("datetime")
                if not tick_time:
                    continue
                if not isinstance(tick_time, datetime):
                    try:
                        if isinstance(tick_time, str):
                            tick_time = datetime.fromisoformat(
                                tick_time.replace("Z", "+00:00")
                            )
                        else:
                            continue
                    except Exception:
                        continue

                if start_time and tick_time < start_time:
                    continue
                if end_time and tick_time > end_time:
                    continue
                filtered_ticks.append(tick)

        return self.aggregate_ticks(filtered_ticks, timeframe)

    def aggregate_all_timeframes(
        self, ticks: List[Dict[str, Any]], timeframes: Optional[List[str]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Aggregate ticks to OHLCV bars for all specified timeframes

        :param ticks: List of tick dictionaries
        :param timeframes: List of timeframe strings (defaults to all supported)
        :return: Dictionary mapping timeframe to list of bars
        """
        if timeframes is None:
            timeframes = list(self.TIMEFRAME_MAP.keys())

        result = {}
        for timeframe in timeframes:
            try:
                bars = self.aggregate_ticks(ticks, timeframe)
                result[timeframe] = bars
            except Exception as e:
                logger.warning(f"Error aggregating {timeframe}: {e}")
                result[timeframe] = []

        return result
