"""
Systematic quality pipeline for tick validation
"""

import os
from typing import Dict, Any, Optional, Tuple, List, Union
from datetime import datetime
from collections import defaultdict
import statistics
import pytz

# Import contract validation
from .contracts import get_contract_registry
from utils.market_utils import infer_pip_value_from_price


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

        # Capture-all mode: prioritize data completeness over strict filtering
        # Only reject clearly invalid data (missing fields, invalid prices, extreme errors)
        self.capture_all_mode = config.get(
            "capture_all_mode",
            os.getenv("QUALITY_GATE_CAPTURE_ALL_MODE", "true").lower() == "true",
        )

        # Outlier threshold - only reject extreme outliers in capture-all mode
        default_outlier_threshold = 10.0 if self.capture_all_mode else 3.0
        self.outlier_z_threshold = config.get(
            "outlier_z_threshold", default_outlier_threshold
        )

        # Staleness threshold - very lenient in capture-all mode (accept all with timestamp override)
        default_staleness_threshold = float(
            os.getenv(
                "QUALITY_GATE_STALENESS_THRESHOLD_SECONDS",
                "3600" if self.capture_all_mode else "300",
            )
        )
        self.staleness_threshold_seconds = config.get(
            "staleness_threshold_seconds", default_staleness_threshold
        )
        # Change default duplicate tolerance to milliseconds (configurable via env var)
        default_duplicate_tolerance = float(
            os.getenv("QUALITY_GATE_DUPLICATE_TOLERANCE_SECONDS", "0.001")
        )
        self.duplicate_tolerance_seconds = config.get(
            "duplicate_tolerance_seconds", default_duplicate_tolerance
        )
        self.use_iqr_method = config.get("use_iqr_method", False)

        # Metrics tracking
        self.metrics = {
            "total_processed": 0,
            "total_accepted": 0,
            "outliers_rejected": 0,
            "duplicates_rejected": 0,
            "stale_rejected": 0,
            "missing_data_rejected": 0,
            "stale_accepted_price_change": 0,  # Stale ticks accepted due to price change
            "timestamp_overrides": 0,  # Timestamps overridden due to staleness + price change
        }

        # Track recent ticks for duplicate detection and outlier calculation
        # Store (symbol, timestamp, bid, ask) tuples
        self.recent_ticks: Dict[str, List[Tuple[datetime, float, float]]] = defaultdict(
            list
        )
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
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Validate tick quality

        :param tick: Tick data dictionary with keys: symbol, datetime, ask, bid
        :param symbol: Currency pair symbol
        :param current_time: Current datetime for staleness check
        :return: Tuple of (is_valid, rejection_reason, timestamp_metadata)
                 timestamp_metadata contains bitemporal timestamp information (is_stale, latency, etc.)
        """
        self.metrics["total_processed"] += 1

        # Parse datetime string to datetime object if needed (contract validator requires datetime object)
        # EA sends datetime as string in MT5 format ("YYYY.MM.DD HH:MM:SS.mmm"), must convert to datetime object
        datetime_value = tick.get("datetime")
        if datetime_value is not None and not isinstance(datetime_value, datetime):
            try:
                mt5_timezone_offset = tick.get("_mt5_timezone_offset")
                tick["datetime"] = self._parse_datetime(datetime_value, mt5_timezone_offset)
            except (ValueError, TypeError) as e:
                # If parsing fails, contract validation will catch it with a better error message
                pass

        # Check 0: Schema Contract Validation (NEW)
        # This validates structure, types, formats, and basic constraints
        contract_registry = get_contract_registry()
        contract_valid, contract_error = contract_registry.validate("tick", tick)
        if not contract_valid:
            self.metrics["missing_data_rejected"] += 1
            return False, f"Schema contract violation: {contract_error}", None

        # Check 1: Missing Data (legacy check - may be redundant with contract validation)
        missing_reason = self._check_missing_data(tick, symbol)
        if missing_reason:
            self.metrics["missing_data_rejected"] += 1
            return False, missing_reason, None

        # Extract tick data
        try:
            # Get MT5 timezone offset if available
            mt5_timezone_offset = tick.get("_mt5_timezone_offset")
            tick_datetime = self._parse_datetime(
                tick.get("datetime"), mt5_timezone_offset
            )
            ask = float(tick.get("ask", 0))
            bid = float(tick.get("bid", 0))
        except (ValueError, TypeError) as e:
            self.metrics["missing_data_rejected"] += 1
            return False, f"Invalid data types: {e}", None

        # Check 2: Staleness (pass bid/ask to allow price-aware staleness check)
        staleness_result = self._check_staleness(
            tick_datetime, current_time, symbol, bid, ask
        )
        if isinstance(staleness_result, tuple):
            # Staleness check returned (rejection_reason, metadata)
            staleness_reason, timestamp_metadata = staleness_result
            if staleness_reason:
                self.metrics["stale_rejected"] += 1
                return False, staleness_reason, None
            # Accepted with metadata - return metadata
            return True, None, timestamp_metadata
        elif staleness_result:
            # Staleness check returned rejection reason (string)
            self.metrics["stale_rejected"] += 1
            return False, staleness_result, None

        # Check 3: Duplicates (pass bid/ask for price comparison)
        duplicate_reason = self._check_duplicates(tick_datetime, symbol, bid, ask)
        if duplicate_reason:
            self.metrics["duplicates_rejected"] += 1
            return False, duplicate_reason, None

        # Check 4: Outliers (only reject extreme outliers in capture-all mode)
        outlier_reason = self._check_outliers(bid, ask, symbol)
        if outlier_reason:
            self.metrics["outliers_rejected"] += 1
            return False, outlier_reason, None

        # All checks passed - update tracking data
        self._update_tracking(symbol, tick_datetime, bid, ask)
        self.metrics["total_accepted"] += 1
        return True, None, None

    def _check_missing_data(self, tick: Dict[str, Any], symbol: str) -> Optional[str]:
        """
        Check for missing required fields

        :param tick: Tick data dictionary
        :param symbol: Currency pair symbol
        :return: Rejection reason if invalid, None otherwise
        """
        # Check symbol
        if not tick.get("symbol") and not symbol:
            return "Missing symbol"

        # Check datetime
        if not tick.get("datetime"):
            return "Missing datetime"

        # Check ask
        ask = tick.get("ask")
        if ask is None:
            return "Missing ask price"
        try:
            float(ask)
        except (ValueError, TypeError):
            return "Invalid ask price type"

        # Check bid
        bid = tick.get("bid")
        if bid is None:
            return "Missing bid price"
        try:
            float(bid)
        except (ValueError, TypeError):
            return "Invalid bid price type"

        return None

    def _check_staleness(
        self,
        tick_datetime: datetime,
        current_time: datetime,
        symbol: str,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
    ) -> Union[Optional[str], Tuple[Optional[str], Optional[Dict]]]:
        """
        Check if tick is too old (stale)

        IMPORTANT: This method preserves the original event_time and returns metadata
        about staleness instead of overriding the timestamp. This enables bitemporal
        timestamp tracking and prevents timeseries misalignment.

        :param tick_datetime: Tick datetime (event_time - preserved)
        :param current_time: Current datetime (server receive time)
        :param symbol: Currency pair symbol
        :param bid: Bid price (optional, for price-aware staleness check)
        :param ask: Ask price (optional, for price-aware staleness check)
        :return:
            - If rejected: rejection reason (string)
            - If accepted with metadata: (None, metadata_dict)
            - If accepted without issues: None
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

        # If tick is stale, return metadata instead of overriding timestamp
        if age_seconds > self.staleness_threshold_seconds:
            # Check if price has changed (for acceptance decision)
            price_changed = False
            if bid is not None and ask is not None:
                if symbol in self.last_seen_prices:
                    last_bid, last_ask = self.last_seen_prices[symbol]
                    # Use relative price difference to account for floating point precision
                    bid_diff = abs(bid - last_bid) / max(abs(bid), abs(last_bid), 1e-10)
                    ask_diff = abs(ask - last_ask) / max(abs(ask), abs(last_ask), 1e-10)
                    price_changed = bid_diff > 1e-6 or ask_diff > 1e-6
                else:
                    # No previous price - assume this is a new price
                    price_changed = True

            # In capture-all mode: always accept stale ticks (with metadata)
            # Otherwise: only accept if price changed
            if self.capture_all_mode or price_changed:
                # Accept the tick with metadata (preserve original event_time)
                self.metrics["stale_accepted_price_change"] += 1
                # Build metadata dict
                metadata = {
                    "is_stale": True,
                    "stale_age_seconds": int(age_seconds),
                    "receive_time": current_time,
                    "latency_seconds": int(age_seconds),
                    "timestamp_source": "event",  # Preserve original timestamp
                }
                return (None, metadata)

            # Reject stale tick (no price change and not in capture-all mode)
            return f"Tick is stale: {age_seconds:.1f}s old (threshold: {self.staleness_threshold_seconds}s)"

        # Not stale - return None (no issues)
        return None

    def _check_duplicates(
        self,
        tick_datetime: datetime,
        symbol: str,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
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
            time_diff_microseconds = abs(
                (tick_dt - last_dt).total_seconds() * 1_000_000
            )
            time_diff_seconds = time_diff_microseconds / 1_000_000

            # Check if timestamp is within tolerance (now in milliseconds)
            if time_diff_seconds <= self.duplicate_tolerance_seconds:
                # Check if price has changed (only if we have price info for both current and last tick)
                if (
                    bid is not None
                    and ask is not None
                    and symbol in self.last_seen_prices
                ):
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
                    # Price is same - this is a true duplicate
                    # CRITICAL FIX: Update state even when rejecting to prevent same tick from being processed repeatedly
                    # This prevents the same tick from being rejected hundreds of times if it's re-queued
                    self.last_seen_timestamps[symbol] = tick_dt
                    self.last_seen_prices[symbol] = (bid, ask)
                    return (
                        f"Duplicate tick: {time_diff_microseconds:.0f}μs from last tick "
                        f"(tolerance: {self.duplicate_tolerance_seconds*1_000_000:.0f}μs), same price"
                    )
                elif bid is not None and ask is not None:
                    # We have price info for current tick but not for last tick
                    # This means last tick didn't have prices, so allow this one through and update tracking
                    self.last_seen_timestamps[symbol] = tick_dt
                    self.last_seen_prices[symbol] = (bid, ask)
                    return None

                # Timestamp within tolerance but no price info available to compare
                # Without price info, we can't determine if it's a duplicate
                # For safety, reject it as a potential duplicate
                # CRITICAL FIX: Update state even when rejecting to prevent same tick from being processed repeatedly
                self.last_seen_timestamps[symbol] = tick_dt
                if bid is not None and ask is not None:
                    self.last_seen_prices[symbol] = (bid, ask)
                return (
                    f"Duplicate tick: {time_diff_microseconds:.0f}μs from last tick "
                    f"(tolerance: {self.duplicate_tolerance_seconds*1_000_000:.0f}μs), no price info to compare"
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

        In capture-all mode: Only reject extreme outliers (>10% price change)
        Otherwise: Use standard z-score/IQR thresholds

        :param bid: Bid price
        :param ask: Ask price
        :param symbol: Currency pair symbol
        :return: Rejection reason if outlier, None otherwise
        """
        # Check spread - always reject invalid spreads
        spread = ask - bid
        if spread <= 0:
            return "Invalid spread: ask <= bid"

        # Infer pip value from price (more maintainable than hardcoding currencies)
        mid_price = (bid + ask) / 2
        pip_value = infer_pip_value_from_price(mid_price)

        # Check for unrealistic spread - more lenient in capture-all mode
        # Maximum spread: 100 pips in capture-all mode, 10 pips otherwise
        max_spread_pips = 100 if self.capture_all_mode else 10
        max_spread_value = pip_value * max_spread_pips

        if spread > max_spread_value:
            spread_pips = spread / pip_value
            return (
                f"Unrealistic spread: {spread:.6f} ({spread_pips:.1f} pips > {max_spread_pips} pips)"
            )

        # In capture-all mode: Only check for extreme outliers (>10% price change)
        if self.capture_all_mode:
            if symbol in self.last_seen_prices:
                last_bid, last_ask = self.last_seen_prices[symbol]
                bid_change_pct = abs(bid - last_bid) / max(
                    abs(bid), abs(last_bid), 1e-10
                )
                ask_change_pct = abs(ask - last_ask) / max(
                    abs(ask), abs(last_ask), 1e-10
                )

                # Only reject if price changed by more than 10% (extreme outlier, likely error)
                if bid_change_pct > 0.10 or ask_change_pct > 0.10:
                    return f"Extreme price change: bid {bid_change_pct*100:.2f}%, ask {ask_change_pct*100:.2f}% (>10%)"
            # Not enough history or no extreme change - accept
            return None

        # Standard outlier detection (not in capture-all mode)
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

    def _parse_datetime(
        self, dt_value: Any, mt5_timezone_offset: Optional[float] = None
    ) -> datetime:
        """
        Parse datetime from various formats

        :param dt_value: Datetime value (string or datetime object)
        :param mt5_timezone_offset: Optional MT5 timezone offset in hours (for MT5 timestamps)
        :return: Parsed datetime (timezone-aware in UTC)
        """
        if isinstance(dt_value, datetime):
            # If already a datetime object, ensure it's timezone-aware and in UTC
            from utils.time_utils import ensure_utc_timezone

            return ensure_utc_timezone(dt_value)

        if isinstance(dt_value, str):
            import pytz
            from utils.time_utils import get_server_timezone

            # Try MT5 format with milliseconds: "YYYY.MM.DD HH:MM:SS.mmm" (23 chars)
            if "." in dt_value and len(dt_value) == 23 and dt_value[19] == ".":
                dt = datetime.strptime(dt_value, "%Y.%m.%d %H:%M:%S.%f")
            # Try MT5 format without milliseconds: "YYYY.MM.DD HH:MM:SS" (19 chars)
            elif "." in dt_value and len(dt_value) == 19:
                dt = datetime.strptime(dt_value, "%Y.%m.%d %H:%M:%S")
            # Try standard format: "YYYY-MM-DD HH:MM:SS" (19 chars)
            elif "-" in dt_value and len(dt_value) == 19:
                dt = datetime.strptime(dt_value, "%Y-%m-%d %H:%M:%S")
            else:
                raise ValueError(f"Unsupported datetime format: {dt_value}")

            # Apply timezone offset if provided (for MT5 timestamps)
            if mt5_timezone_offset is not None:
                source_tz = pytz.FixedOffset(int(mt5_timezone_offset * 60))
                dt = source_tz.localize(dt)
                return dt.astimezone(get_server_timezone())
            else:
                # Default to UTC for naive datetimes
                utc_tz = pytz.UTC
                dt = utc_tz.localize(dt)
                return dt.astimezone(get_server_timezone())

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
        total = self.metrics["total_processed"]
        accepted = self.metrics["total_accepted"]
        acceptance_rate = (accepted / total * 100) if total > 0 else 0.0

        return {
            **self.metrics,
            "acceptance_rate": acceptance_rate,
            "rejection_rate": 100.0 - acceptance_rate,
        }

    def reset_metrics(self):
        """
        Reset all metrics (useful for testing or periodic resets)
        """
        self.metrics = {
            "total_processed": 0,
            "total_accepted": 0,
            "outliers_rejected": 0,
            "duplicates_rejected": 0,
            "stale_rejected": 0,
            "missing_data_rejected": 0,
            "stale_accepted_price_change": 0,
            "timestamp_overrides": 0,
        }
