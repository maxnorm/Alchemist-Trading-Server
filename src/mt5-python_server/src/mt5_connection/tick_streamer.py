"""
Class for the tick streaming operation from MT5
"""

import json
import os
import threading
import queue

from database import Database
from utils.time_utils import print_with_datetime, parse_mt5_timestamp, get_utc_time
from utils.logging_config import get_logger
from utils.market_utils import check_if_market_open


class MT5TickStreamer:
    """
    MT5 terminal connection for tick streaming
    """

    def __init__(
        self, socket, asset, stop_char="\n", verbose=False, console_lock=None, db=None
    ):
        self.__socket = socket
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

        :param mt5_timestamp_str: MT5 timestamp string in format "YYYY.MM.DD HH:MM:SS"
        """
        if self.__timezone_detected:
            return

        try:
            # Parse MT5 timestamp (assume UTC initially for comparison)
            from datetime import datetime

            mt5_dt = datetime.strptime(mt5_timestamp_str, "%Y.%m.%d %H:%M:%S")
            utc_now = get_utc_time()

            # Calculate offset: difference between MT5 time (as UTC) and actual UTC
            # If MT5 time is ahead of UTC, offset is positive
            time_diff = (mt5_dt - utc_now.replace(tzinfo=None)).total_seconds() / 3600.0

            # Round to nearest hour (most brokers use whole hour offsets)
            self.__mt5_timezone_offset = round(time_diff)

            self.__timezone_detected = True
            self.__logger.log_event(
                event_type="timezone_detected",
                message=f"Detected MT5 timezone offset: {self.__mt5_timezone_offset} hours from UTC",
                metrics={
                    "timezone_offset": self.__mt5_timezone_offset,
                    "mt5_timestamp": mt5_timestamp_str,
                    "utc_now": utc_now.strftime("%Y-%m-%d %H:%M:%S %Z"),
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

    def __normalize_mt5_timestamp(self, date_time: str) -> str:
        """
        Normalize MT5 timestamp to UTC timezone

        :param date_time: MT5 timestamp string
        :return: Normalized timestamp string in UTC timezone (format: "YYYY-MM-DD HH:MM:SS")
        """
        # Detect timezone on first tick if not already detected
        if not self.__timezone_detected:
            self.__detect_mt5_timezone(date_time)

        # Parse and convert to UTC
        utc_dt = parse_mt5_timestamp(date_time, self.__mt5_timezone_offset)

        # Return as string in standard format for database storage
        return utc_dt.strftime("%Y-%m-%d %H:%M:%S")

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
        :param date_time: Tick datetime string (MT5 format)
        :return: True if in order or first tick, False if out of order
        """
        try:
            from datetime import datetime

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

    def __add_tick_to_buffer(self, symbol, date_time, ask, bid):
        """
        Add a tick to the buffer and flush if needed

        :param symbol: Currency pair symbol
        :param date_time: Tick datetime (MT5 format string, will be normalized to EST)
        :param ask: Ask price
        :param bid: Bid price
        """
        # Normalize timestamp to EST before buffering
        normalized_date_time = self.__normalize_mt5_timestamp(date_time)

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

            self.__tick_buffer.append((symbol, normalized_date_time, ask, bid))

            # Flush if buffer reaches max size
            if len(self.__tick_buffer) >= self.__buffer_max_size:
                self.__flush_buffer_internal()
            # Flush if batch size reached
            elif len(self.__tick_buffer) >= self.__batch_size:
                self.__flush_buffer_internal()

    def is_feed_live(self, max_age_seconds: float = None) -> bool:
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
        Flush ticks to database in batch

        :param ticks: List of (symbol, date_time, ask, bid) tuples
        """
        if not ticks:
            return

        try:
            with self.__logger.performance_context(
                "flush_ticks_to_db", count=len(ticks)
            ):
                result = self.__db.insert_forex_ticks_batch(ticks)
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
            for symbol, date_time, ask, bid in ticks:
                try:
                    self.__db.insert_forex_tick(symbol, date_time, ask, bid)
                except Exception as e2:
                    self.__logger.log_error(
                        event_type="individual_tick_insert_error",
                        error=f"Error inserting individual tick: {e2}",
                        symbol=symbol,
                        exc_info=True,
                    )
                    print_with_datetime(f"Error inserting individual tick: {e2}")

    def receive_tick(self):
        """
        Receive tick from mt5 client
        and store them in the database buffer
        """
        self.__logger.log_event(
            event_type="tick_reception_started", message="Starting tick reception loop"
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

                data = self.__socket.recv(1024).decode("utf-8")

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

                            # Validate tick data quality
                            if not self.__validate_tick(symbol, date_time, ask, bid):
                                continue  # Skip invalid tick

                            # Validate tick ordering
                            if not self.__validate_tick_order(symbol, date_time):
                                continue  # Skip out-of-order tick

                            self.__asset.update(bid, ask)
                            # Add to buffer instead of direct insert
                            self.__add_tick_to_buffer(symbol, date_time, ask, bid)
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
