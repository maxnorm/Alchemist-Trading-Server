"""
Systematic quality pipeline for tick validation
"""

import os
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta
from collections import defaultdict
import statistics
import numpy as np
import pytz


class QualityGate:
    """
    Systematic quality pipeline for tick validation
    Implements checks for outliers, duplicates, staleness, and missing data
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize quality gate with configurable thresholds
        
        :param config: Configuration dictionary with optional keys:
            - outlier_z_threshold: Z-score threshold for outliers (default: 3.0)
            - staleness_threshold_seconds: Max age threshold in seconds (default: 300)
            - duplicate_tolerance_seconds: Tolerance window for duplicates (default: 1)
            - use_iqr_method: Use IQR method instead of z-score (default: False)
        """
        if config is None:
            config = {}
        
        self.outlier_z_threshold = config.get('outlier_z_threshold', 3.0)
        self.staleness_threshold_seconds = config.get('staleness_threshold_seconds', 300)
        # Change default duplicate tolerance to milliseconds (configurable via env var)
        default_duplicate_tolerance = float(
            os.getenv("QUALITY_GATE_DUPLICATE_TOLERANCE_SECONDS", "0.001")
        )
        self.duplicate_tolerance_seconds = config.get(
            'duplicate_tolerance_seconds', 
            default_duplicate_tolerance
        )
        self.use_iqr_method = config.get('use_iqr_method', False)
        
        # Metrics tracking
        self.metrics = {
            'total_processed': 0,
            'total_accepted': 0,
            'outliers_rejected': 0,
            'duplicates_rejected': 0,
            'stale_rejected': 0,
            'missing_data_rejected': 0,
        }
        
        # Track recent ticks for duplicate detection and outlier calculation
        # Store (symbol, timestamp, bid, ask) tuples
        self.recent_ticks: Dict[str, List[Tuple[datetime, float, float]]] = defaultdict(list)
        self.max_recent_ticks = 1000  # Keep last 1000 ticks per symbol for statistics
        
        # Track last seen timestamps and prices per symbol for duplicate detection
        self.last_seen_timestamps: Dict[str, datetime] = {}
        self.last_seen_prices: Dict[str, Tuple[float, float]] = {}  # (bid, ask)
        
        # Track price history for outlier detection (bid/ask separately)
        self.price_history_bid: Dict[str, List[float]] = defaultdict(list)
        self.price_history_ask: Dict[str, List[float]] = defaultdict(list)
        self.max_price_history = 1000  # Keep last 1000 prices per symbol

    def validate(
        self, tick: Dict[str, Any], symbol: str, current_time: datetime
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate tick quality
        
        :param tick: Tick data dictionary with keys: symbol, datetime, ask, bid
        :param symbol: Currency pair symbol
        :param current_time: Current datetime for staleness check
        :return: Tuple of (is_valid, rejection_reason)
        """
        self.metrics['total_processed'] += 1
        
        # Check 1: Missing Data
        missing_reason = self._check_missing_data(tick, symbol)
        if missing_reason:
            self.metrics['missing_data_rejected'] += 1
            return False, missing_reason
        
        # Extract tick data
        try:
            tick_datetime = self._parse_datetime(tick.get('datetime') or tick.get('date_time'))
            ask = float(tick.get('ask', 0))
            bid = float(tick.get('bid', 0))
        except (ValueError, TypeError) as e:
            self.metrics['missing_data_rejected'] += 1
            return False, f"Invalid data types: {e}"
        
        # Check 2: Staleness
        staleness_reason = self._check_staleness(tick_datetime, current_time, symbol)
        if staleness_reason:
            self.metrics['stale_rejected'] += 1
            return False, staleness_reason
        
        # Check 3: Duplicates (pass bid/ask for price comparison)
        duplicate_reason = self._check_duplicates(tick_datetime, symbol, bid, ask)
        if duplicate_reason:
            self.metrics['duplicates_rejected'] += 1
            return False, duplicate_reason
        
        # Check 4: Outliers
        outlier_reason = self._check_outliers(bid, ask, symbol)
        if outlier_reason:
            self.metrics['outliers_rejected'] += 1
            return False, outlier_reason
        
        # All checks passed - update tracking data
        self._update_tracking(symbol, tick_datetime, bid, ask)
        self.metrics['total_accepted'] += 1
        return True, None

    def _check_missing_data(self, tick: Dict[str, Any], symbol: str) -> Optional[str]:
        """
        Check for missing required fields
        
        :param tick: Tick data dictionary
        :param symbol: Currency pair symbol
        :return: Rejection reason if invalid, None otherwise
        """
        # Check symbol
        if not tick.get('symbol') and not symbol:
            return "Missing symbol"
        
        # Check datetime
        if not tick.get('datetime') and not tick.get('date_time'):
            return "Missing datetime"
        
        # Check ask
        ask = tick.get('ask')
        if ask is None:
            return "Missing ask price"
        try:
            float(ask)
        except (ValueError, TypeError):
            return "Invalid ask price type"
        
        # Check bid
        bid = tick.get('bid')
        if bid is None:
            return "Missing bid price"
        try:
            float(bid)
        except (ValueError, TypeError):
            return "Invalid bid price type"
        
        return None

    def _check_staleness(
        self, tick_datetime: datetime, current_time: datetime, symbol: str
    ) -> Optional[str]:
        """
        Check if tick is too old (stale)
        
        :param tick_datetime: Tick datetime
        :param current_time: Current datetime
        :param symbol: Currency pair symbol
        :return: Rejection reason if stale, None otherwise
        """
        # Normalize timezones for comparison - convert both to UTC
        utc_tz = pytz.UTC
        
        # Make tick_datetime timezone-aware if it's naive (assume UTC)
        if tick_datetime.tzinfo is None:
            tick_datetime = utc_tz.localize(tick_datetime)
        else:
            # Convert to UTC if not already
            tick_datetime = tick_datetime.astimezone(utc_tz)
        
        # Make current_time timezone-aware if it's naive (assume UTC)
        if current_time.tzinfo is None:
            current_time = utc_tz.localize(current_time)
        else:
            # Convert to UTC if not already
            current_time = current_time.astimezone(utc_tz)
        
        age_seconds = (current_time - tick_datetime).total_seconds()
        
        if age_seconds > self.staleness_threshold_seconds:
            return f"Tick is stale: {age_seconds:.1f}s old (threshold: {self.staleness_threshold_seconds}s)"
        
        return None

    def _check_duplicates(
        self, tick_datetime: datetime, symbol: str, bid: float = None, ask: float = None
    ) -> Optional[str]:
        """
        Check for duplicate ticks - improved to use microsecond precision
        Only reject if timestamp AND price are both identical
        
        :param tick_datetime: Tick datetime
        :param symbol: Currency pair symbol
        :param bid: Bid price (optional, for price comparison)
        :param ask: Ask price (optional, for price comparison)
        :return: Rejection reason if duplicate, None otherwise
        """
        if symbol in self.last_seen_timestamps:
            last_timestamp = self.last_seen_timestamps[symbol]
            
            # Normalize timezones
            utc_tz = pytz.UTC
            if tick_datetime.tzinfo is None:
                tick_dt = utc_tz.localize(tick_datetime)
            else:
                tick_dt = tick_datetime.astimezone(utc_tz)
            
            if last_timestamp.tzinfo is None:
                last_dt = utc_tz.localize(last_timestamp)
            else:
                last_dt = last_timestamp.astimezone(utc_tz)
            
            # Use microsecond precision for comparison
            time_diff_microseconds = abs((tick_dt - last_dt).total_seconds() * 1_000_000)
            time_diff_seconds = time_diff_microseconds / 1_000_000
            
            # Check if timestamp is within tolerance (now in milliseconds)
            if time_diff_seconds <= self.duplicate_tolerance_seconds:
                # Check if price has changed
                if bid is not None and ask is not None and symbol in self.last_seen_prices:
                    last_bid, last_ask = self.last_seen_prices[symbol]
                    
                    # Use relative price difference to account for floating point precision
                    bid_diff = abs(bid - last_bid) / max(abs(bid), abs(last_bid), 1e-10)
                    ask_diff = abs(ask - last_ask) / max(abs(ask), abs(last_ask), 1e-10)
                    
                    # If price changed significantly (> 0.0001% relative difference), not a duplicate
                    if bid_diff > 1e-6 or ask_diff > 1e-6:
                        # Price changed - not a duplicate, update tracking
                        self.last_seen_timestamps[symbol] = tick_dt
                        self.last_seen_prices[symbol] = (bid, ask)
                        return None
                
                # Timestamp within tolerance AND price is same (or no price info)
                return (
                    f"Duplicate tick: {time_diff_microseconds:.0f}μs from last tick "
                    f"(tolerance: {self.duplicate_tolerance_seconds*1_000_000:.0f}μs)"
                )
        
        # Update tracking
        utc_tz = pytz.UTC
        if tick_datetime.tzinfo is None:
            tick_datetime = utc_tz.localize(tick_datetime)
        else:
            tick_datetime = tick_datetime.astimezone(utc_tz)
        self.last_seen_timestamps[symbol] = tick_datetime
        if bid is not None and ask is not None:
            self.last_seen_prices[symbol] = (bid, ask)
        return None

    def _check_outliers(self, bid: float, ask: float, symbol: str) -> Optional[str]:
        """
        Check for outliers using z-score or IQR method
        
        :param bid: Bid price
        :param ask: Ask price
        :param symbol: Currency pair symbol
        :return: Rejection reason if outlier, None otherwise
        """
        # Check spread
        spread = ask - bid
        if spread <= 0:
            return "Invalid spread: ask <= bid"
        
        # Check for unrealistic spread (> 10 pips for major pairs, which is ~0.0010 for most pairs)
        # For EUR/USD, 1 pip = 0.0001, so 10 pips = 0.0010
        # We'll use a more conservative threshold of 0.001 (10 pips)
        if spread > 0.001:
            return f"Unrealistic spread: {spread:.6f} (> 0.001 / 10 pips)"
        
        # Need historical data for outlier detection
        bid_history = self.price_history_bid.get(symbol, [])
        ask_history = self.price_history_ask.get(symbol, [])
        
        # Need at least 10 data points for meaningful statistics
        if len(bid_history) < 10 or len(ask_history) < 10:
            return None  # Not enough data yet, accept the tick
        
        if self.use_iqr_method:
            # IQR method
            bid_outlier = self._is_outlier_iqr(bid, bid_history)
            ask_outlier = self._is_outlier_iqr(ask, ask_history)
        else:
            # Z-score method
            bid_outlier = self._is_outlier_zscore(bid, bid_history)
            ask_outlier = self._is_outlier_zscore(ask, ask_history)
        
        if bid_outlier:
            return f"Bid price outlier: {bid} (method: {'IQR' if self.use_iqr_method else 'z-score'})"
        
        if ask_outlier:
            return f"Ask price outlier: {ask} (method: {'IQR' if self.use_iqr_method else 'z-score'})"
        
        return None

    def _is_outlier_zscore(self, value: float, history: List[float]) -> bool:
        """
        Check if value is an outlier using z-score method
        
        :param value: Value to check
        :param history: Historical values
        :return: True if outlier
        """
        if len(history) < 2:
            return False
        
        mean = statistics.mean(history)
        stdev = statistics.stdev(history) if len(history) > 1 else 0.0
        
        if stdev == 0:
            return False  # No variation, can't detect outliers
        
        z_score = abs((value - mean) / stdev)
        return z_score > self.outlier_z_threshold

    def _is_outlier_iqr(self, value: float, history: List[float]) -> bool:
        """
        Check if value is an outlier using IQR (Interquartile Range) method
        
        :param value: Value to check
        :param history: Historical values
        :return: True if outlier
        """
        if len(history) < 4:
            return False
        
        sorted_history = sorted(history)
        q1_index = len(sorted_history) // 4
        q3_index = 3 * len(sorted_history) // 4
        
        q1 = sorted_history[q1_index]
        q3 = sorted_history[q3_index]
        iqr = q3 - q1
        
        if iqr == 0:
            return False  # No variation
        
        # Outlier if value is outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR]
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        return value < lower_bound or value > upper_bound

    def _parse_datetime(self, dt_value: Any) -> datetime:
        """
        Parse datetime from various formats
        
        :param dt_value: Datetime value (string or datetime object)
        :return: Parsed datetime
        """
        if isinstance(dt_value, datetime):
            return dt_value
        
        if isinstance(dt_value, str):
            # Try MT5 format with milliseconds: "YYYY.MM.DD HH:MM:SS.mmm" (23 chars)
            if "." in dt_value and len(dt_value) == 23 and dt_value[19] == '.':
                return datetime.strptime(dt_value, "%Y.%m.%d %H:%M:%S.%f")
            # Try MT5 format without milliseconds: "YYYY.MM.DD HH:MM:SS" (19 chars)
            elif "." in dt_value and len(dt_value) == 19:
                return datetime.strptime(dt_value, "%Y.%m.%d %H:%M:%S")
            # Try standard format: "YYYY-MM-DD HH:MM:SS" (19 chars)
            elif "-" in dt_value and len(dt_value) == 19:
                return datetime.strptime(dt_value, "%Y-%m-%d %H:%M:%S")
            else:
                raise ValueError(f"Unsupported datetime format: {dt_value}")
        
        raise ValueError(f"Invalid datetime type: {type(dt_value)}")

    def _update_tracking(
        self, symbol: str, tick_datetime: datetime, bid: float, ask: float
    ):
        """
        Update tracking data structures
        
        :param symbol: Currency pair symbol
        :param tick_datetime: Tick datetime
        :param bid: Bid price
        :param ask: Ask price
        """
        # Update recent ticks
        self.recent_ticks[symbol].append((tick_datetime, bid, ask))
        if len(self.recent_ticks[symbol]) > self.max_recent_ticks:
            self.recent_ticks[symbol].pop(0)
        
        # Update price history
        self.price_history_bid[symbol].append(bid)
        self.price_history_ask[symbol].append(ask)
        
        if len(self.price_history_bid[symbol]) > self.max_price_history:
            self.price_history_bid[symbol].pop(0)
        if len(self.price_history_ask[symbol]) > self.max_price_history:
            self.price_history_ask[symbol].pop(0)

    def get_metrics(self) -> Dict[str, Any]:
        """
        Return quality metrics
        
        :return: Dictionary of quality metrics
        """
        total = self.metrics['total_processed']
        accepted = self.metrics['total_accepted']
        acceptance_rate = (accepted / total * 100) if total > 0 else 0.0
        
        return {
            **self.metrics,
            'acceptance_rate': acceptance_rate,
            'rejection_rate': 100.0 - acceptance_rate,
        }

    def reset_metrics(self):
        """
        Reset all metrics (useful for testing or periodic resets)
        """
        self.metrics = {
            'total_processed': 0,
            'total_accepted': 0,
            'outliers_rejected': 0,
            'duplicates_rejected': 0,
            'stale_rejected': 0,
            'missing_data_rejected': 0,
        }
