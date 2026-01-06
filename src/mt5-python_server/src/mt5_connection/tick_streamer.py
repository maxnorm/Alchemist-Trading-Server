"""
Class for the tick streaming operation from MT5
"""

import json
import os
import socket
import threading
import queue
from typing import Optional
from datetime import datetime

from database import Database
from utils.time_utils import print_with_datetime, parse_mt5_timestamp, get_utc_time
from utils.logging_config import get_logger
from utils.market_utils import check_if_market_open
from data.quality_gates import QualityGate
from events.normalizer import EventNormalizer

# Helper function for debug logging
def _write_debug_log(session_id, run_id, hypothesis_id, location, message, data, timestamp=None):
    """Write debug log entry"""
    try:
        if timestamp is None:
            from utils.time_utils import get_utc_time
            timestamp = int(get_utc_time().timestamp() * 1000)
        # Use absolute path from system reminder - calculate dynamically
        import os
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_dir)))
        log_path = os.path.join(project_root, '.cursor', 'debug.log')
        # Ensure directory exists
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                "sessionId": session_id,
                "runId": run_id,
                "hypothesisId": hypothesis_id,
                "location": location,
                "message": message,
                "data": data,
                "timestamp": timestamp
            }) + "\n")
    except Exception as e:
        # Log to stderr for debugging instrumentation issues
        import sys
        sys.stderr.write(f"Debug log write failed: {e}\n")


class MT5TickStreamer:
    """
    MT5 terminal connection for tick streaming
    """

    def __init__(
        self, sock, asset, stop_char="\n", verbose=False, console_lock=None, db=None
    ):
        self.__socket = sock
        self.__asset = asset
        self.__stop_char = stop_char
        self.__verbose = verbose
        self.__console_lock = console_lock
        # Use provided database instance or create new one (for backward compatibility)
        self.__db = db if db is not None else Database()

        # Initialize logger (structured if available, otherwise traditional)
        try:
            self.__logger = get_logger("tick_streamer", "tick_streamer.log")
            # Check if it's a structured logger
            if hasattr(self.__logger, "log_event"):
                self._use_structured = True
            else:
                self._use_structured = False
        except Exception:
            # Fallback to traditional logger
            from utils.logging_config import get_tick_streamer_logger

            self.__logger = get_tick_streamer_logger()
            self._use_structured = False

        symbol = asset.symbol if asset else "unknown"
        if self._use_structured:
            self.__logger.log_event(
                event_type="tick_streamer_initialized",
                message=f"Initializing tick streamer for symbol: {symbol}",
                symbol=symbol,
            )
        else:
            self.__logger.info(f"Initializing tick streamer for symbol: {symbol}")

        # Configure socket timeout to prevent indefinite blocking
        # Use a reasonable timeout (30 seconds) that allows for market pauses
        socket_timeout = float(os.getenv("MT5_SOCKET_TIMEOUT", "30.0"))
        try:
            self.__socket.settimeout(socket_timeout)
            # Enable TCP keepalive to detect dead connections
            self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if hasattr(socket, "TCP_KEEPIDLE"):
                self.__socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
            if hasattr(socket, "TCP_KEEPINTVL"):
                self.__socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 30)
            if hasattr(socket, "TCP_KEEPCNT"):
                self.__socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 4)
        except Exception as e:
            self.__logger.warning(
                f"Failed to configure socket options: {e}. Continuing with default settings."
            )

        # Tick buffering configuration
        self.__batch_size = int(os.getenv("TICK_BATCH_SIZE", "50"))
        self.__batch_interval = float(os.getenv("TICK_BATCH_INTERVAL", "2.0"))
        self.__buffer_max_size = int(os.getenv("TICK_BUFFER_MAX_SIZE", "200"))
        self.__feed_stale_threshold = float(
            os.getenv("FEED_STALE_THRESHOLD_SECONDS", "180")
        )

        # Thread-safe tick buffer
        self.__tick_buffer = []
        self.__buffer_lock = threading.Lock()
        self.__flush_timer = None
        self.__shutdown_flag = threading.Event()

        # MT5 timezone detection
        self.__mt5_timezone_offset = None  # Offset in hours from UTC
        self.__timezone_detected = False

        # Tick monitoring for market closure detection
        self.__last_tick_time = None
        self.__no_tick_warning_logged = False
        self.__last_feed_live_state = None

        # Buffer overflow protection
        self.__buffer_overflow_count = 0

        # Tick ordering validation
        self.__last_tick_timestamp = {}  # Track last timestamp per symbol

        # Quality gate for systematic quality checks
        self.quality_gate = QualityGate()

        # Event normalizer for canonical format conversion
        self.event_normalizer = EventNormalizer()

        # Async database write queue
        self.__db_write_queue = queue.Queue(maxsize=1000)
        self.__db_writer_thread = threading.Thread(
            target=self._db_writer_worker, daemon=True
        )
        self.__db_writer_thread.start()

        # Start periodic flush timer
        self.__start_flush_timer()
        self.__logger.log_event(
            event_type="tick_streamer_config",
            message="Tick streamer initialized",
            metrics={
                "batch_size": self.__batch_size,
                "batch_interval": self.__batch_interval,
                "buffer_max_size": self.__buffer_max_size,
            },
            symbol=symbol,
        )

    def __start_flush_timer(self):
        """Start the periodic flush timer"""
        if self.__flush_timer:
            self.__flush_timer.cancel()

        if not self.__shutdown_flag.is_set():
            self.__flush_timer = threading.Timer(
                self.__batch_interval, self.__flush_buffer
            )
            self.__flush_timer.daemon = True
            self.__flush_timer.start()

    def __detect_mt5_timezone(self, mt5_timestamp_str: str):
        """
        Detect MT5 broker timezone offset by comparing with UTC server time
        Fixed to properly handle timezone-aware comparisons

        :param mt5_timestamp_str: MT5 timestamp string in format "YYYY.MM.DD HH:MM:SS"
        """
        if self.__timezone_detected:
            return

        try:
            import pytz
            from datetime import datetime

            # Parse MT5 timestamp as naive (MT5 format) - handle both with and without milliseconds
            # Try parsing with milliseconds first (23 chars: "YYYY.MM.DD HH:MM:SS.mmm")
            if len(mt5_timestamp_str) == 23 and mt5_timestamp_str[19] == '.':
                mt5_dt_naive = datetime.strptime(mt5_timestamp_str, "%Y.%m.%d %H:%M:%S.%f")
            # Fallback to seconds-only format (19 chars: "YYYY.MM.DD HH:MM:SS")
            else:
                mt5_dt_naive = datetime.strptime(mt5_timestamp_str, "%Y.%m.%d %H:%M:%S")
            
            # Get current UTC time (timezone-aware)
            utc_now = get_utc_time()
            
            # #region agent log
            _write_debug_log("debug-session", "run1", "H2", "tick_streamer.py:__detect_mt5_timezone", "Starting timezone detection", {"mt5_timestamp_str": mt5_timestamp_str, "utc_now": utc_now.isoformat()})
            # #endregion
            
            # Try different timezone offsets to find the best match
            # Common broker timezones: UTC, GMT+2, GMT+3
            best_offset = 0.0
            min_diff = float('inf')
            
            for offset_hours in [0, 2, 3, -2, -3]:  # Common broker offsets
                test_tz = pytz.FixedOffset(int(offset_hours * 60))
                mt5_dt_tz = test_tz.localize(mt5_dt_naive)
                mt5_utc = mt5_dt_tz.astimezone(pytz.UTC)
                
                diff_seconds = abs((mt5_utc - utc_now).total_seconds())
                if diff_seconds < min_diff:
                    min_diff = diff_seconds
                    best_offset = offset_hours
            
            # #region agent log
            _write_debug_log("debug-session", "run1", "H2", "tick_streamer.py:__detect_mt5_timezone", "Timezone detection result", {"best_offset": best_offset, "min_diff_seconds": min_diff})
            # #endregion
            
            # If best match is still > 1 hour off, log warning
            if min_diff > 3600:
                self.__logger.log_event(
                    event_type="timezone_detection_warning",
                    message=f"Large time difference detected: {min_diff/3600:.1f} hours",
                    metrics={
                        "min_diff_hours": min_diff / 3600,
                        "detected_offset": best_offset,
                    },
                    level="WARNING",
                )
            
            self.__mt5_timezone_offset = best_offset
            self.__timezone_detected = True
            
            self.__logger.log_event(
                event_type="timezone_detected",
                message=f"Detected MT5 timezone offset: {self.__mt5_timezone_offset} hours from UTC",
                metrics={
                    "timezone_offset": self.__mt5_timezone_offset,
                    "mt5_timestamp": mt5_timestamp_str,
                    "utc_now": utc_now.strftime("%Y-%m-%d %H:%M:%S %Z"),
                    "time_diff_seconds": min_diff,
                },
            )
        except Exception as e:
            self.__logger.log_error(
                event_type="timezone_detection_failed",
                error=f"Failed to detect MT5 timezone, defaulting to UTC: {e}",
                exc_info=True,
            )
            self.__mt5_timezone_offset = 0.0
            self.__timezone_detected = True

    def __normalize_mt5_timestamp(self, date_time) -> datetime:
        """
        Normalize MT5 timestamp to UTC timezone, preserving microseconds

        :param date_time: MT5 timestamp string (either MT5 format "YYYY.MM.DD HH:MM:SS.mmm" or datetime object)
        :return: Normalized timezone-aware datetime object in UTC (preserves microseconds)
        """
        # If already a datetime object, just ensure it's UTC and timezone-aware
        if isinstance(date_time, datetime):
            from utils.time_utils import ensure_utc_timezone
            return ensure_utc_timezone(date_time)
        
        # Handle string input
        if isinstance(date_time, str):
            # Check if timestamp is already in standard format (normalized)
            # MT5 format uses dots: "YYYY.MM.DD", standard format uses dashes: "YYYY-MM-DD"
            if "-" in date_time and len(date_time) >= 19 and date_time[4] == '-':
                # Already normalized string format - parse it back to datetime
                try:
                    # Try parsing with microseconds if present
                    if len(date_time) > 19 and '.' in date_time:
                        dt = datetime.strptime(date_time[:26], "%Y-%m-%d %H:%M:%S.%f")
                    else:
                        dt = datetime.strptime(date_time[:19], "%Y-%m-%d %H:%M:%S")
                    from utils.time_utils import ensure_utc_timezone
                    return ensure_utc_timezone(dt)
                except ValueError:
                    # Fallback to parse_mt5_timestamp
                    pass
            
            # Detect timezone on first tick if not already detected
            if not self.__timezone_detected:
                self.__detect_mt5_timezone(date_time)

            # Parse and convert to UTC (preserves microseconds)
            return parse_mt5_timestamp(date_time, self.__mt5_timezone_offset)
        
        # Fallback: convert to string and try again
        return self.__normalize_mt5_timestamp(str(date_time))

    def __validate_tick(
        self, symbol: str, date_time: str, ask: float, bid: float
    ) -> bool:
        """
        Validate tick data quality
        :param symbol: Currency pair symbol
        :param date_time: Tick datetime string
        :param ask: Ask price
        :param bid: Bid price
        :return: True if valid, False otherwise
        """
        # Check for negative or zero prices
        if bid <= 0 or ask <= 0:
            self.__logger.log_error(
                event_type="invalid_tick_price",
                error=f"Invalid price: bid={bid}, ask={ask}",
                symbol=symbol,
                metrics={"bid": bid, "ask": ask},
                exc_info=False,
            )
            return False

        # Check for reversed prices (ask should be >= bid)
        if ask <= bid:
            self.__logger.log_error(
                event_type="reversed_tick_prices",
                error=f"Reversed prices: bid={bid}, ask={ask}",
                symbol=symbol,
                metrics={"bid": bid, "ask": ask},
                exc_info=False,
            )
            return False

        # Check for unrealistic price changes (>10% in one tick)
        if self.__asset.bid is not None and self.__asset.ask is not None:
            bid_change_pct = (
                abs(bid - self.__asset.bid) / self.__asset.bid
                if self.__asset.bid > 0
                else 0
            )
            ask_change_pct = (
                abs(ask - self.__asset.ask) / self.__asset.ask
                if self.__asset.ask > 0
                else 0
            )

            if bid_change_pct > 0.1 or ask_change_pct > 0.1:
                self.__logger.log_event(
                    event_type="unusual_price_change",
                    message=f"Unusual price change for {symbol}",
                    symbol=symbol,
                    metrics={
                        "bid_change_pct": bid_change_pct,
                        "ask_change_pct": ask_change_pct,
                        "previous_bid": self.__asset.bid,
                        "current_bid": bid,
                        "previous_ask": self.__asset.ask,
                        "current_ask": ask,
                    },
                    level="WARNING",
                )
                # Still process but log warning (might be legitimate market event)

        return True

    def __validate_tick_order(self, symbol: str, date_time: str) -> bool:
        """
        Validate tick timestamp ordering
        :param symbol: Currency pair symbol
        :param date_time: Tick datetime string (MT5 format, with or without milliseconds)
        :return: True if in order or first tick, False if out of order
        """
        try:
            from datetime import datetime

            # Try parsing with milliseconds first (23 chars: "YYYY.MM.DD HH:MM:SS.mmm")
            if len(date_time) == 23 and date_time[19] == '.':
                current_timestamp = datetime.strptime(date_time, "%Y.%m.%d %H:%M:%S.%f")
            # Fallback to seconds-only format (19 chars: "YYYY.MM.DD HH:MM:SS")
            else:
                current_timestamp = datetime.strptime(date_time, "%Y.%m.%d %H:%M:%S")

            if symbol in self.__last_tick_timestamp:
                last_timestamp = self.__last_tick_timestamp[symbol]

                # Reject ticks older than last processed (out of order)
                if current_timestamp < last_timestamp:
                    time_diff = (last_timestamp - current_timestamp).total_seconds()
                    self.__logger.log_event(
                        event_type="out_of_order_tick",
                        message=f"Out-of-order tick for {symbol}",
                        symbol=symbol,
                        metrics={
                            "time_diff_seconds": time_diff,
                            "current_timestamp": date_time,
                            "last_timestamp": last_timestamp.strftime(
                                "%Y.%m.%d %H:%M:%S"
                            ),
                        },
                        level="WARNING",
                    )
                    return False

            # Update last timestamp
            self.__last_tick_timestamp[symbol] = current_timestamp
            return True

        except Exception as e:
            self.__logger.log_error(
                event_type="tick_order_validation_error",
                error=f"Error validating tick order: {e}",
                symbol=symbol,
                exc_info=True,
            )
            return True  # Allow on error to not block processing

    def __add_tick_to_buffer(
        self, 
        symbol, 
        date_time, 
        ask, 
        bid,
        receive_time=None,
        latency_seconds=None,
        is_stale=False,
        stale_age_seconds=None
    ):
        """
        Add a tick to the buffer and flush if needed

        :param symbol: Currency pair symbol
        :param date_time: Tick datetime (event_time, string or datetime object, will be normalized to UTC)
        :param ask: Ask price
        :param bid: Bid price
        :param receive_time: When we received the tick (transaction time, optional)
        :param latency_seconds: Latency in seconds (optional)
        :param is_stale: Flag if original timestamp was stale (optional)
        :param stale_age_seconds: Age of stale timestamp in seconds (optional)
        """
        # #region agent log
        _write_debug_log("debug-session", "run1", "C", "tick_streamer.py:349", "__add_tick_to_buffer called", {"symbol": symbol, "date_time": str(date_time) if isinstance(date_time, datetime) else date_time, "bid": bid, "ask": ask})
        # #endregion
        # Normalize timestamp to UTC (returns datetime object, preserves microseconds)
        normalized_date_time = self.__normalize_mt5_timestamp(date_time)
        
        # Normalize receive_time if provided
        normalized_receive_time = None
        if receive_time is not None:
            from utils.time_utils import normalize_to_utc
            normalized_receive_time = normalize_to_utc(receive_time)

        with self.__buffer_lock:
            # Check buffer size - emergency overflow protection
            current_size = len(self.__tick_buffer)
            if current_size >= self.__buffer_max_size * 2:
                # Emergency: drop oldest 25% to prevent memory exhaustion
                drop_count = current_size // 4
                self.__tick_buffer = self.__tick_buffer[drop_count:]
                self.__buffer_overflow_count += 1
                self.__logger.log_event(
                    event_type="buffer_overflow",
                    message="Buffer overflow protection: dropped oldest ticks",
                    metrics={
                        "dropped_count": drop_count,
                        "buffer_size": current_size,
                        "max_size": self.__buffer_max_size * 2,
                        "overflow_count": self.__buffer_overflow_count,
                    },
                    level="WARNING",
                )

            # Store with bitemporal information: (symbol, event_time, ask, bid, receive_time, latency_seconds, is_stale, stale_age_seconds)
            self.__tick_buffer.append((
                symbol, normalized_date_time, ask, bid,
                normalized_receive_time, latency_seconds, is_stale, stale_age_seconds
            ))
            # #region agent log
            _write_debug_log("debug-session", "run1", "C", "tick_streamer.py:354", "Tick added to buffer", {"symbol": symbol, "buffer_size": len(self.__tick_buffer), "batch_size": self.__batch_size, "buffer_max_size": self.__buffer_max_size})
            # #endregion

            # Flush if buffer reaches max size
            if len(self.__tick_buffer) >= self.__buffer_max_size:
                self.__flush_buffer_internal()
            # Flush if batch size reached
            elif len(self.__tick_buffer) >= self.__batch_size:
                self.__flush_buffer_internal()

    def is_feed_live(self, max_age_seconds: Optional[float] = None) -> bool:
        """
        Return True when ticks have been received recently.
        Uses the last tick timestamp and a configurable staleness threshold.
        """
        threshold = (
            max_age_seconds
            if max_age_seconds is not None
            else self.__feed_stale_threshold
        )
        if self.__last_tick_time is None:
            return False
        age = (get_utc_time() - self.__last_tick_time).total_seconds()
        return age <= threshold

    def __flush_buffer_internal(self):
        """Internal flush method (must be called with buffer_lock held)"""
        if not self.__tick_buffer:
            return

        ticks_to_flush = self.__tick_buffer.copy()
        self.__tick_buffer.clear()
        # #region agent log
        _write_debug_log("debug-session", "run1", "D", "tick_streamer.py:428", "Flushing buffer to queue", {"tick_count": len(ticks_to_flush), "symbols": [t[0] for t in ticks_to_flush]})
        # #endregion

        # Non-blocking queue put (with timeout)
        try:
            self.__db_write_queue.put(ticks_to_flush, timeout=0.1)
        except queue.Full:
            # Queue full - log warning and drop oldest
            self.__logger.log_event(
                event_type="db_queue_full",
                message="DB write queue full, dropping oldest batch",
                metrics={
                    "queue_size": self.__db_write_queue.qsize(),
                    "batch_size": len(ticks_to_flush),
                },
                level="WARNING",
            )
            try:
                # Try to remove oldest item
                self.__db_write_queue.get_nowait()
                # Now try to put new item
                self.__db_write_queue.put(ticks_to_flush, timeout=0.1)
            except queue.Empty:
                # Queue was already empty, just put the new item
                self.__db_write_queue.put(ticks_to_flush, timeout=0.1)
            except queue.Full:
                # Still full after removing one, drop this batch
                self.__logger.log_error(
                    event_type="tick_dropped",
                    error=f"Dropping {len(ticks_to_flush)} ticks due to queue overflow",
                    metrics={"dropped_count": len(ticks_to_flush)},
                    exc_info=False,
                )

    def _db_writer_worker(self):
        """Dedicated thread for database writes"""
        while not self.__shutdown_flag.is_set():
            try:
                ticks = self.__db_write_queue.get(timeout=1.0)
                self.__flush_ticks_to_db(ticks)
                self.__db_write_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.__logger.log_error(
                    event_type="db_writer_thread_error",
                    error=f"Error in DB writer thread: {e}",
                    exc_info=True,
                )

    def __flush_buffer(self):
        """Flush buffer based on timer (called periodically)"""
        with self.__buffer_lock:
            self.__flush_buffer_internal()

        # Restart timer for next flush
        self.__start_flush_timer()

    def __flush_ticks_to_db(self, ticks):
        """
        Flush ticks to database in batch with bitemporal timestamps

        :param ticks: List of (symbol, date_time, ask, bid, receive_time, latency_seconds, is_stale, stale_age_seconds) tuples
        """
        if not ticks:
            return

        # #region agent log
        _write_debug_log("debug-session", "run1", "E", "tick_streamer.py:468", "__flush_ticks_to_db called", {"tick_count": len(ticks), "symbols": [t[0] for t in ticks]})
        # #endregion
        try:
            with self.__logger.performance_context(
                "flush_ticks_to_db", count=len(ticks)
            ):
                # Check if ticks have bitemporal data (new format) or old format
                if len(ticks) > 0 and len(ticks[0]) >= 8:
                    # New format with bitemporal data
                    # Convert to format expected by batch insert (for now, use individual inserts with metadata)
                    # TODO: Update insert_forex_ticks_batch to support bitemporal data
                    result = 0
                    for tick in ticks:
                        symbol, date_time, ask, bid, receive_time, latency_seconds, is_stale, stale_age_seconds = tick[:8]
                        try:
                            if self.__db.insert_forex_tick(
                                symbol, date_time, ask, bid,
                                receive_time=receive_time,
                                latency_seconds=latency_seconds,
                                is_stale=is_stale,
                                stale_age_seconds=stale_age_seconds,
                                timestamp_source='event'
                            ):
                                result += 1
                        except Exception as e2:
                            self.__logger.log_error(
                                event_type="individual_tick_insert_error",
                                error=f"Error inserting individual tick: {e2}",
                                symbol=symbol,
                                exc_info=True,
                            )
                else:
                    # Old format (backward compatibility)
                    # Convert to old format for batch insert
                    old_format_ticks = [(t[0], t[1], t[2], t[3]) for t in ticks]
                    result = self.__db.insert_forex_ticks_batch(old_format_ticks)
                
                # #region agent log
                _write_debug_log("debug-session", "run1", "E", "tick_streamer.py:481", "Database insert result", {"result": result, "tick_count": len(ticks)})
                # #endregion
                if result > 0:
                    self.__logger.log_event(
                        event_type="ticks_flushed",
                        message=f"Flushed {result} ticks to database",
                        metrics={"tick_count": result, "batch_size": len(ticks)},
                    )
                    if self.__verbose:
                        with self.__console_lock:
                            print_with_datetime(f"Flushed {result} ticks to database")
        except Exception as e:
            self.__logger.log_error(
                event_type="tick_flush_error",
                error=f"Error flushing ticks to database: {e}",
                metrics={"batch_size": len(ticks)},
                exc_info=True,
            )
            print_with_datetime(f"Error flushing ticks to database: {e}")
            # On error, try inserting individually as fallback
            for tick in ticks:
                try:
                    if len(tick) >= 8:
                        # New format with bitemporal data
                        symbol, date_time, ask, bid, receive_time, latency_seconds, is_stale, stale_age_seconds = tick[:8]
                        self.__db.insert_forex_tick(
                            symbol, date_time, ask, bid,
                            receive_time=receive_time,
                            latency_seconds=latency_seconds,
                            is_stale=is_stale,
                            stale_age_seconds=stale_age_seconds,
                            timestamp_source='event'
                        )
                    else:
                        # Old format
                        symbol, date_time, ask, bid = tick[:4]
                        self.__db.insert_forex_tick(symbol, date_time, ask, bid)
                except Exception as e2:
                    self.__logger.log_error(
                        event_type="individual_tick_insert_error",
                        error=f"Error inserting individual tick: {e2}",
                        symbol=tick[0] if tick else "unknown",
                        exc_info=True,
                    )
                    print_with_datetime(f"Error inserting individual tick: {e2}")

    def receive_tick(self):
        """
        Receive tick from mt5 client
        and store them in the database buffer
        """
        symbol = self.__asset.symbol if self.__asset else "unknown"
        self.__logger.log_event(
            event_type="tick_reception_started",
            message=f"Starting tick reception loop for {symbol}",
            symbol=symbol,
        )
        
        # Log socket connection status
        try:
            peer = self.__socket.getpeername()
            timeout = self.__socket.gettimeout()
            self.__logger.log_event(
                event_type="socket_info",
                message=f"Socket connected to {peer}, timeout={timeout}s",
                symbol=symbol,
                metrics={"peer": str(peer), "timeout": timeout},
            )
        except Exception as e:
            self.__logger.log_error(
                event_type="socket_info_error",
                error=f"Could not get socket info: {e}",
                symbol=symbol,
                exc_info=False,
            )
        
        cum_data = ""
        tick_count = 0
        last_market_check = get_utc_time()

        try:
            while not self.__shutdown_flag.is_set():
                # Periodically check if we should expect ticks (market open vs closed)
                current_time = get_utc_time()
                if (
                    current_time - last_market_check
                ).total_seconds() >= 300:  # Check every 5 minutes
                    last_market_check = current_time
                    market_open = check_if_market_open()
                    feed_live = self.is_feed_live()

                    # Log feed state transitions concisely
                    if (
                        self.__last_feed_live_state is None
                        or self.__last_feed_live_state != feed_live
                    ):
                        self.__logger.log_event(
                            event_type="feed_state_change",
                            message=f"Tick feed is {'LIVE' if feed_live else 'STALE'}",
                            metrics={
                                "feed_live": feed_live,
                                "seconds_since_last_tick": (
                                    (
                                        current_time - self.__last_tick_time
                                    ).total_seconds()
                                    if self.__last_tick_time
                                    else None
                                ),
                                "market_open": market_open,
                            },
                            level="INFO" if feed_live else "WARNING",
                        )
                        self.__last_feed_live_state = feed_live

                    # If market is open but no ticks received for a while, log warning
                    if market_open and self.__last_tick_time is not None:
                        time_since_last_tick = (
                            current_time - self.__last_tick_time
                        ).total_seconds()
                        if (
                            time_since_last_tick >= 300
                            and not self.__no_tick_warning_logged
                        ):  # 5 minutes
                            self.__logger.log_event(
                                event_type="no_ticks_received",
                                message=(
                                    f"No ticks received for {time_since_last_tick/60:.1f} "
                                    "minutes during market hours"
                                ),
                                metrics={
                                    "minutes_since_last_tick": time_since_last_tick
                                    / 60,
                                    "market_open": True,
                                },
                                level="WARNING",
                            )
                            self.__no_tick_warning_logged = True
                    elif not market_open and not self.__no_tick_warning_logged:
                        # Market is closed - this is expected, log info
                        self.__logger.log_event(
                            event_type="market_closed",
                            message="Market is closed - no ticks expected",
                            metrics={"market_open": False},
                        )
                        self.__no_tick_warning_logged = True

                # Receive data with proper error handling
                try:
                    raw_data = self.__socket.recv(1024)
                    if not raw_data:
                        # Empty data indicates connection closed
                        self.__logger.log_event(
                            event_type="connection_closed",
                            message="Socket connection closed by MT5 client (empty data received)",
                            level="WARNING",
                        )
                        break  # Exit the loop
                    
                    data = raw_data.decode("utf-8")
                except socket.timeout:
                    # Timeout is expected during quiet periods - just continue
                    # The periodic market check above will log if needed
                    continue
                except socket.error as e:
                    # Socket error (connection lost, etc.)
                    self.__logger.log_error(
                        event_type="socket_error",
                        error=f"Socket error while receiving tick data: {e}",
                        exc_info=True,
                    )
                    break  # Exit the loop
                except Exception as e:
                    # Unexpected error
                    self.__logger.log_error(
                        event_type="receive_error",
                        error=f"Unexpected error receiving tick data: {e}",
                        exc_info=True,
                    )
                    break  # Exit the loop

                cum_data += data

                if self.__stop_char in cum_data:
                    final_data = cum_data[: cum_data.index(self.__stop_char)]

                    if self.__verbose:
                        with self.__console_lock:
                            print_with_datetime(final_data)

                    try:
                        tick_info = json.loads(final_data)
                        if len(tick_info) == 4:
                            symbol = tick_info["symbol"]
                            date_time = tick_info["date_time"]
                            ask = tick_info["ask"]
                            bid = tick_info["bid"]
                            
                            # #region agent log
                            _write_debug_log("debug-session", "run1", "Z", "tick_streamer.py:656", "Tick received from socket", {"symbol": symbol, "date_time": date_time, "bid": bid, "ask": ask})
                            # #endregion

                            # Validate tick data quality
                            validate_result = self.__validate_tick(symbol, date_time, ask, bid)
                            # #region agent log
                            _write_debug_log("debug-session", "run1", "Z", "tick_streamer.py:664", "Basic validation result", {"symbol": symbol, "is_valid": validate_result})
                            # #endregion
                            if not validate_result:
                                continue  # Skip invalid tick

                            # Validate tick ordering
                            if not self.__validate_tick_order(symbol, date_time):
                                continue  # Skip out-of-order tick

                            # Detect timezone on first tick if not already detected (before quality gate)
                            if not self.__timezone_detected:
                                self.__detect_mt5_timezone(date_time)
                            
                            # #region agent log
                            _write_debug_log("debug-session", "run1", "H1", "tick_streamer.py:720", "Before quality gate", {"date_time": date_time, "mt5_timezone_offset": self.__mt5_timezone_offset, "timezone_detected": self.__timezone_detected})
                            # #endregion
                            
                            # Capture receive_time (when we received the tick)
                            receive_time = get_utc_time()
                            
                            # Quality gate validation
                            tick_info_dict = {
                                "symbol": symbol,
                                "date_time": date_time,  # Original event_time (preserved)
                                "ask": ask,
                                "bid": bid,
                                "_mt5_timezone_offset": self.__mt5_timezone_offset,  # Pass detected offset to normalizer
                                "_receive_time": receive_time,  # Pass receive_time to normalizer
                            }
                            current_time = receive_time
                            is_valid, rejection_reason, timestamp_metadata = self.quality_gate.validate(
                                tick_info_dict, symbol, current_time
                            )
                            # #region agent log
                            _write_debug_log("debug-session", "run1", "A", "tick_streamer.py:679", "Quality gate validation result", {"symbol": symbol, "is_valid": is_valid, "rejection_reason": rejection_reason, "bid": bid, "ask": ask, "has_metadata": timestamp_metadata is not None}, int(current_time.timestamp() * 1000))
                            # #endregion
                            if not is_valid:
                                # Insert into quarantine before skipping
                                if hasattr(self, '_MT5TickStreamer__db') and self.__db:
                                    try:
                                        self.__db.insert_quarantine_tick(
                                            symbol=symbol,
                                            date_time=date_time,
                                            ask=ask,
                                            bid=bid,
                                            rejection_reason=rejection_reason,
                                            receive_time=receive_time
                                        )
                                    except Exception as e:
                                        # Log but don't fail main flow if quarantine insert fails
                                        if self._use_structured:
                                            self.__logger.log_event(
                                                event_type="quarantine_insert_failed",
                                                message=f"Failed to insert rejected tick into quarantine: {e}",
                                                symbol=symbol,
                                                level="WARNING",
                                            )
                                        else:
                                            self.__logger.warning(
                                                f"Failed to insert rejected tick into quarantine for {symbol}: {e}"
                                            )
                                
                                if self._use_structured:
                                    self.__logger.log_event(
                                        event_type="quality_gate_rejection",
                                        message=f"Tick rejected by quality gate: {rejection_reason}",
                                        symbol=symbol,
                                        metrics={"rejection_reason": rejection_reason},
                                        level="WARNING",
                                    )
                                else:
                                    self.__logger.warning(
                                        f"Tick rejected by quality gate for {symbol}: {rejection_reason}"
                                    )
                                continue  # Skip tick rejected by quality gate
                            
                            # Pass timestamp_metadata to normalizer (preserve original event_time)
                            if timestamp_metadata:
                                tick_info_dict["_timestamp_metadata"] = timestamp_metadata
                                # Extract metadata values for database insert
                                metadata_receive_time = timestamp_metadata.get('receive_time')
                                if metadata_receive_time and isinstance(metadata_receive_time, datetime):
                                    receive_time = metadata_receive_time
                                latency_seconds = timestamp_metadata.get('latency_seconds')
                                is_stale = timestamp_metadata.get('is_stale', False)
                                stale_age_seconds = timestamp_metadata.get('stale_age_seconds')
                            else:
                                # No metadata - calculate latency
                                latency_seconds = None
                                is_stale = False
                                stale_age_seconds = None
                            
                            # Add acceptance logging
                            if self._use_structured:
                                self.__logger.log_event(
                                    event_type="tick_accepted_quality_gate",
                                    message=f"Tick passed quality gate for {symbol}",
                                    symbol=symbol,
                                    metrics={"bid": bid, "ask": ask},
                                    level="DEBUG",
                                )

                            # Normalize tick to canonical format
                            try:
                                normalized_tick = self.event_normalizer.normalize(
                                    tick_info_dict, source="mt5"
                                )
                                # #region agent log
                                _write_debug_log("debug-session", "run1", "B", "tick_streamer.py:709", "Normalization completed", {"symbol": symbol, "has_normalized_tick": normalized_tick is not None})
                                # #endregion
                                # Validate normalized event
                                validate_result = self.event_normalizer.validate(normalized_tick)
                                # #region agent log
                                _write_debug_log("debug-session", "run1", "B", "tick_streamer.py:713", "Event quality gate validation result", {"symbol": symbol, "is_valid": validate_result})
                                # #endregion
                                if not validate_result:
                                    self.__logger.warning(
                                        f"Normalized tick failed validation for {symbol}, skipping"
                                    )
                                    continue
                                
                                # Add acceptance logging after normalization
                                if self._use_structured:
                                    self.__logger.log_event(
                                        event_type="tick_accepted_normalization",
                                        message=f"Tick passed normalization for {symbol}",
                                        symbol=symbol,
                                        level="DEBUG",
                                    )
                            except Exception as e:
                                self.__logger.error(
                                    f"Failed to normalize tick for {symbol}: {e}",
                                    exc_info=True,
                                )
                                # Continue with original tick if normalization fails (backward compatibility)
                                normalized_tick = None

                            self.__asset.update(bid, ask)
                            # Add to buffer instead of direct insert
                            # Store normalized tick if available, otherwise use original format
                            # #region agent log
                            _write_debug_log("debug-session", "run1", "C", "tick_streamer.py:735", "About to add tick to buffer", {"symbol": symbol, "has_normalized_tick": normalized_tick is not None})
                            # #endregion
                            if normalized_tick:
                                # Extract normalized timestamp (event_time - preserved)
                                normalized_date_time = normalized_tick["timestamp"]
                                # Extract receive_time and metadata from normalized tick
                                normalized_receive_time = normalized_tick.get("receive_time")
                                normalized_metadata = normalized_tick.get("timestamp_metadata", {})
                                # Pass datetime object directly (preserves microseconds) with metadata
                                self.__add_tick_to_buffer(
                                    symbol, normalized_date_time, ask, bid,
                                    receive_time=normalized_receive_time or receive_time,
                                    latency_seconds=normalized_metadata.get('latency_seconds') or latency_seconds,
                                    is_stale=normalized_metadata.get('is_stale', False) or is_stale,
                                    stale_age_seconds=normalized_metadata.get('stale_age_seconds') or stale_age_seconds
                                )
                            else:
                                # Pass original MT5 string, will be normalized in __add_tick_to_buffer
                                # Use metadata from quality gate
                                self.__add_tick_to_buffer(
                                    symbol, date_time, ask, bid,
                                    receive_time=receive_time,
                                    latency_seconds=latency_seconds,
                                    is_stale=is_stale,
                                    stale_age_seconds=stale_age_seconds
                                )
                            tick_count += 1

                            # Update last tick time and reset warning flag
                            self.__last_tick_time = get_utc_time()
                            self.__no_tick_warning_logged = False
                            # Mark feed as live when a fresh tick arrives
                            if self.__last_feed_live_state is not True:
                                if self.__logger and hasattr(
                                    self.__logger, "log_event"
                                ):
                                    self.__logger.log_event(
                                        event_type="feed_state_change",
                                        message="Tick feed is LIVE",
                                        metrics={"feed_live": True, "symbol": symbol},
                                    )
                                self.__last_feed_live_state = True

                            # Log every 100 ticks for monitoring
                            if tick_count % 100 == 0:
                                self.__logger.log_event(
                                    event_type="tick_received",
                                    message=f"Received {tick_count} ticks for {symbol}",
                                    symbol=symbol,
                                    metrics={
                                        "tick_count": tick_count,
                                        "bid": bid,
                                        "ask": ask,
                                    },
                                    level="DEBUG",
                                )
                            
                            # Log quality metrics periodically (every 1000 ticks)
                            if tick_count % 1000 == 0:
                                metrics = self.quality_gate.get_metrics()
                                if self._use_structured:
                                    self.__logger.log_event(
                                        event_type="quality_metrics",
                                        message="Quality gate metrics",
                                        metrics=metrics,
                                    )
                                else:
                                    self.__logger.info(f"Quality gate metrics: {metrics}")
                        else:
                            self.__logger.log_error(
                                event_type="invalid_tick_format",
                                error=f"Wrong format of tick. Expected 4 fields, got {len(tick_info)}",
                                metrics={
                                    "expected_fields": 4,
                                    "received_fields": len(tick_info),
                                    "tick_data": tick_info,
                                },
                                exc_info=False,
                            )
                            print_with_datetime(
                                f"Error wrong format of tick. Tick received: {tick_info}"
                            )
                    except json.JSONDecodeError as e:
                        self.__logger.log_error(
                            event_type="tick_parse_error",
                            error=f"Failed to parse tick data: {e}",
                            metrics={"raw_data": final_data[:200]},  # Limit data size
                            exc_info=True,
                        )
                    except Exception as e:
                        self.__logger.log_error(
                            event_type="tick_processing_error",
                            error=f"Error processing tick: {e}",
                            exc_info=True,
                        )

                    cum_data = ""
        except Exception as e:
            self.__logger.log_error(
                event_type="tick_reception_loop_error",
                error=f"Error in receive_tick loop: {e}",
                exc_info=True,
            )
        finally:
            # Graceful shutdown: flush remaining ticks
            self.__logger.log_event(
                event_type="tick_streamer_shutdown",
                message=f"Shutting down tick streamer. Total ticks received: {tick_count}",
                metrics={"total_ticks": tick_count},
            )
            self.__shutdown_flag.set()
            if self.__flush_timer:
                self.__flush_timer.cancel()

            # Flush any remaining ticks
            with self.__buffer_lock:
                if self.__tick_buffer:
                    remaining_count = len(self.__tick_buffer)
                    remaining_ticks = self.__tick_buffer.copy()
                    self.__tick_buffer.clear()
                    self.__logger.log_event(
                        event_type="shutdown_flush",
                        message=f"Flushing {remaining_count} remaining ticks before shutdown",
                        metrics={"remaining_count": remaining_count},
                    )
                    try:
                        self.__db_write_queue.put(remaining_ticks, timeout=1.0)
                    except queue.Full:
                        # Queue full, write directly
                        self.__flush_ticks_to_db(remaining_ticks)

            # Wait for queue to drain (with timeout)
            self.__logger.log_event(
                event_type="queue_drain_wait",
                message="Waiting for database write queue to drain...",
            )
            try:
                self.__db_write_queue.join(timeout=5.0)
            except Exception:
                pass

    def __del__(self):
        """Cleanup on deletion"""
        self.__shutdown_flag.set()
        if self.__flush_timer:
            self.__flush_timer.cancel()

        # Flush any remaining ticks
        with self.__buffer_lock:
            if self.__tick_buffer:
                remaining_ticks = self.__tick_buffer.copy()
                self.__tick_buffer.clear()
                try:
                    self.__db_write_queue.put(remaining_ticks, timeout=1.0)
                except queue.Full:
                    # Queue full, write directly
                    self.__flush_ticks_to_db(remaining_ticks)

        if self.__socket:
            try:
                self.__socket.close()
            except Exception:
                pass
