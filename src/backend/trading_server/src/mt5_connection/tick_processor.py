"""
Shared tick processing logic for MT5 tick streams.
Socket-agnostic and reusable across connection types (e.g., ZeroMQ).
"""

import os
import queue
import threading
from datetime import datetime
from typing import Callable, Optional

from database import Database
from data.quality_gates import QualityGate
from events.normalizer import EventNormalizer
from utils.logging_config import get_logger
from utils.market_utils import check_if_market_open
from utils.time_utils import get_utc_time, parse_mt5_timestamp, print_with_datetime


class TickProcessor:
    """
    Socket-agnostic tick processing pipeline.
    Handles validation, normalization, buffering, and DB writes.
    """

    def __init__(self, asset, verbose: bool = False, console_lock=None, db=None, on_tick_callback=None):
        self._asset = asset
        self._verbose = verbose
        self._console_lock = console_lock
        self._db = db if db is not None else Database()
        self._on_tick_callback = on_tick_callback  # Real-time callback before DB storage

        try:
            self._logger = get_logger("tick_streamer", "tick_streamer.log")
            self._use_structured = hasattr(self._logger, "log_event")
        except Exception:
            from utils.logging_config import get_tick_streamer_logger

            self._logger = get_tick_streamer_logger()
            self._use_structured = False

        symbol = asset.symbol if asset else "unknown"
        if self._use_structured:
            self._logger.log_event(
                event_type="tick_streamer_initialized",
                message=f"Initializing tick processor for symbol: {symbol}",
                symbol=symbol,
            )
        else:
            self._logger.info(f"Initializing tick processor for symbol: {symbol}")

        # Tick buffering configuration
        self._batch_size = int(os.getenv("TICK_BATCH_SIZE", "50"))
        self._batch_interval = float(os.getenv("TICK_BATCH_INTERVAL", "2.0"))
        self._buffer_max_size = int(os.getenv("TICK_BUFFER_MAX_SIZE", "200"))
        self._feed_stale_threshold = float(
            os.getenv("FEED_STALE_THRESHOLD_SECONDS", "180")
        )

        self._tick_buffer = []
        self._buffer_lock = threading.Lock()
        self._flush_timer = None
        self._shutdown_flag = threading.Event()

        # MT5 timezone detection
        self._mt5_timezone_offset = None
        self._timezone_detected = False

        # Tick monitoring for market closure detection
        self._last_tick_time = None
        self._no_tick_warning_logged = False
        self._last_feed_live_state = None

        # Connection health tracking
        self._last_heartbeat_time = get_utc_time()
        self._connection_health_check_interval = float(
            os.getenv("CONNECTION_HEALTH_CHECK_INTERVAL", "30.0")
        )
        self._connection_stale_threshold = float(
            os.getenv("CONNECTION_STALE_THRESHOLD_SECONDS", "60.0")
        )
        self._last_health_check_time = get_utc_time()
        self._connection_health_warnings = 0

        # Buffer overflow protection
        self._buffer_overflow_count = 0

        # Tick ordering validation
        self._last_tick_timestamp = {}

        self.quality_gate = QualityGate()
        self.event_normalizer = EventNormalizer()

        # Quality gate metrics sync configuration
        self._quality_metrics_sync_interval = int(
            os.getenv("QUALITY_METRICS_SYNC_INTERVAL_TICKS", "100")
        )  # Sync every N ticks
        self._quality_metrics_sync_counter = 0

        self._db_write_queue = queue.Queue(maxsize=1000)
        self._db_writer_thread = threading.Thread(
            target=self._db_writer_worker, daemon=True
        )
        self._db_writer_thread.start()

        self._start_flush_timer()
        self._logger.log_event(
            event_type="tick_streamer_config",
            message="Tick processor initialized",
            metrics={
                "batch_size": self._batch_size,
                "batch_interval": self._batch_interval,
                "buffer_max_size": self._buffer_max_size,
            },
            symbol=symbol,
        )

        self._tick_count = 0
        self._last_market_check = get_utc_time()

    def _start_flush_timer(self):
        if self._flush_timer:
            self._flush_timer.cancel()

        if not self._shutdown_flag.is_set():
            self._flush_timer = threading.Timer(
                self._batch_interval, self._flush_buffer
            )
            self._flush_timer.daemon = True
            self._flush_timer.start()

    def _detect_mt5_timezone(self, mt5_timestamp_str: str):
        if self._timezone_detected:
            return

        try:
            import pytz
            from datetime import datetime as dt

            if len(mt5_timestamp_str) == 23 and mt5_timestamp_str[19] == ".":
                mt5_dt_naive = dt.strptime(mt5_timestamp_str, "%Y.%m.%d %H:%M:%S.%f")
            else:
                mt5_dt_naive = dt.strptime(mt5_timestamp_str, "%Y.%m.%d %H:%M:%S")

            utc_now = get_utc_time()

            best_offset = 0.0
            min_diff = float("inf")

            for offset_hours in [0, 2, 3, -2, -3]:
                test_tz = pytz.FixedOffset(int(offset_hours * 60))
                mt5_dt_tz = test_tz.localize(mt5_dt_naive)
                mt5_utc = mt5_dt_tz.astimezone(pytz.UTC)

                diff_seconds = abs((mt5_utc - utc_now).total_seconds())
                if diff_seconds < min_diff:
                    min_diff = diff_seconds
                    best_offset = offset_hours

            if min_diff > 3600:
                self._logger.log_event(
                    event_type="timezone_detection_warning",
                    message=f"Large time difference detected: {min_diff/3600:.1f} hours",
                    metrics={
                        "min_diff_hours": min_diff / 3600,
                        "detected_offset": best_offset,
                    },
                    level="WARNING",
                )

            self._mt5_timezone_offset = best_offset
            self._timezone_detected = True

            self._logger.log_event(
                event_type="timezone_detected",
                message=f"Detected MT5 timezone offset: {self._mt5_timezone_offset} hours from UTC",
                metrics={
                    "timezone_offset": self._mt5_timezone_offset,
                    "mt5_timestamp": mt5_timestamp_str,
                    "utc_now": utc_now.strftime("%Y-%m-%d %H:%M:%S %Z"),
                    "time_diff_seconds": min_diff,
                },
            )
        except Exception as exc:
            self._logger.log_error(
                event_type="timezone_detection_failed",
                error=f"Failed to detect MT5 timezone, defaulting to UTC: {exc}",
                exc_info=True,
            )
            self._mt5_timezone_offset = 0.0
            self._timezone_detected = True

    def _normalize_mt5_timestamp(self, date_time) -> datetime:
        if isinstance(date_time, datetime):
            from utils.time_utils import ensure_utc_timezone

            return ensure_utc_timezone(date_time)

        if isinstance(date_time, str):
            if "-" in date_time and len(date_time) >= 19 and date_time[4] == "-":
                try:
                    if len(date_time) > 19 and "." in date_time:
                        dt = datetime.strptime(date_time[:26], "%Y-%m-%d %H:%M:%S.%f")
                    else:
                        dt = datetime.strptime(date_time[:19], "%Y-%m-%d %H:%M:%S")
                    from utils.time_utils import ensure_utc_timezone

                    return ensure_utc_timezone(dt)
                except ValueError:
                    pass

            if not self._timezone_detected:
                self._detect_mt5_timezone(date_time)

            return parse_mt5_timestamp(date_time, self._mt5_timezone_offset)

        return self._normalize_mt5_timestamp(str(date_time))

    def _validate_tick(self, symbol: str, date_time: str, ask: float, bid: float) -> bool:
        if bid <= 0 or ask <= 0:
            self._logger.log_error(
                event_type="invalid_tick_price",
                error=f"Invalid price: bid={bid}, ask={ask}",
                symbol=symbol,
                metrics={"bid": bid, "ask": ask},
                exc_info=False,
            )
            return False

        if ask <= bid:
            self._logger.log_error(
                event_type="reversed_tick_prices",
                error=f"Reversed prices: bid={bid}, ask={ask}",
                symbol=symbol,
                metrics={"bid": bid, "ask": ask},
                exc_info=False,
            )
            return False

        if self._asset.bid is not None and self._asset.ask is not None:
            bid_change_pct = (
                abs(bid - self._asset.bid) / self._asset.bid
                if self._asset.bid > 0
                else 0
            )
            ask_change_pct = (
                abs(ask - self._asset.ask) / self._asset.ask
                if self._asset.ask > 0
                else 0
            )

            if bid_change_pct > 0.1 or ask_change_pct > 0.1:
                self._logger.log_event(
                    event_type="unusual_price_change",
                    message=f"Unusual price change for {symbol}",
                    symbol=symbol,
                    metrics={
                        "bid_change_pct": bid_change_pct,
                        "ask_change_pct": ask_change_pct,
                        "previous_bid": self._asset.bid,
                        "current_bid": bid,
                        "previous_ask": self._asset.ask,
                        "current_ask": ask,
                    },
                    level="WARNING",
                )

        return True

    def _validate_tick_order(self, symbol: str, date_time: str) -> bool:
        try:
            if len(date_time) == 23 and date_time[19] == ".":
                current_timestamp = datetime.strptime(date_time, "%Y.%m.%d %H:%M:%S.%f")
            else:
                current_timestamp = datetime.strptime(date_time, "%Y.%m.%d %H:%M:%S")

            if symbol in self._last_tick_timestamp:
                last_timestamp = self._last_tick_timestamp[symbol]
                if current_timestamp < last_timestamp:
                    time_diff = (last_timestamp - current_timestamp).total_seconds()
                    self._logger.log_event(
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

            self._last_tick_timestamp[symbol] = current_timestamp
            return True
        except Exception as exc:
            self._logger.log_error(
                event_type="tick_order_validation_error",
                error=f"Error validating tick order: {exc}",
                symbol=symbol,
                exc_info=True,
            )
            return True

    def _add_tick_to_buffer(
        self,
        symbol,
        date_time,
        ask,
        bid,
        receive_time=None,
        latency_seconds=None,
        is_stale=False,
        stale_age_seconds=None,
    ):
        normalized_date_time = self._normalize_mt5_timestamp(date_time)

        normalized_receive_time = None
        if receive_time is not None:
            from utils.time_utils import normalize_to_utc

            normalized_receive_time = normalize_to_utc(receive_time)

        with self._buffer_lock:
            current_size = len(self._tick_buffer)
            if current_size >= self._buffer_max_size * 2:
                drop_count = current_size // 4
                self._tick_buffer = self._tick_buffer[drop_count:]
                self._buffer_overflow_count += 1
                self._logger.log_event(
                    event_type="buffer_overflow",
                    message="Buffer overflow protection: dropped oldest ticks",
                    metrics={
                        "dropped_count": drop_count,
                        "buffer_size": current_size,
                        "max_size": self._buffer_max_size * 2,
                        "overflow_count": self._buffer_overflow_count,
                    },
                    level="WARNING",
                )

            self._tick_buffer.append(
                (
                    symbol,
                    normalized_date_time,
                    ask,
                    bid,
                    normalized_receive_time,
                    latency_seconds,
                    is_stale,
                    stale_age_seconds,
                )
            )
            new_size = len(self._tick_buffer)

            if len(self._tick_buffer) >= self._buffer_max_size:
                self._flush_buffer_internal()
            elif len(self._tick_buffer) >= self._batch_size:
                self._flush_buffer_internal()

    def is_feed_live(self, max_age_seconds: Optional[float] = None) -> bool:
        threshold = max_age_seconds if max_age_seconds is not None else self._feed_stale_threshold
        if self._last_tick_time is None:
            return False
        age = (get_utc_time() - self._last_tick_time).total_seconds()
        return age <= threshold

    def _flush_buffer_internal(self):
        if not self._tick_buffer:
            return

        ticks_to_flush = self._tick_buffer.copy()
        self._tick_buffer.clear()

        try:
            self._db_write_queue.put(ticks_to_flush, timeout=0.1)
        except queue.Full:
            self._logger.log_event(
                event_type="db_queue_full",
                message="DB write queue full, dropping oldest batch",
                metrics={
                    "queue_size": self._db_write_queue.qsize(),
                    "batch_size": len(ticks_to_flush),
                },
                level="WARNING",
            )
            try:
                self._db_write_queue.get_nowait()
                self._db_write_queue.put(ticks_to_flush, timeout=0.1)
            except queue.Empty:
                self._db_write_queue.put(ticks_to_flush, timeout=0.1)
            except queue.Full:
                self._logger.log_error(
                    event_type="tick_dropped",
                    error=f"Dropping {len(ticks_to_flush)} ticks due to queue overflow",
                    metrics={"dropped_count": len(ticks_to_flush)},
                    exc_info=False,
                )

    def _db_writer_worker(self):
        while not self._shutdown_flag.is_set():
            try:
                ticks = self._db_write_queue.get(timeout=1.0)
                self._flush_ticks_to_db(ticks)
                self._db_write_queue.task_done()
            except queue.Empty:
                continue
            except Exception as exc:
                self._logger.log_error(
                    event_type="db_writer_thread_error",
                    error=f"Error in DB writer thread: {exc}",
                    exc_info=True,
                )

    def _flush_buffer(self):
        with self._buffer_lock:
            self._flush_buffer_internal()

        self._start_flush_timer()

    def _flush_ticks_to_db(self, ticks):
        if not ticks:
            return

        try:
            with self._logger.performance_context(
                "flush_ticks_to_db", count=len(ticks)
            ):
                if len(ticks) > 0 and len(ticks[0]) >= 8:
                    result = 0
                    for tick in ticks:
                        (
                            symbol,
                            date_time,
                            ask,
                            bid,
                            receive_time,
                            latency_seconds,
                            is_stale,
                            stale_age_seconds,
                        ) = tick[:8]
                        try:
                            insert_result = self._db.insert_forex_tick(
                                symbol,
                                date_time,
                                ask,
                                bid,
                                receive_time=receive_time,
                                latency_seconds=latency_seconds,
                                is_stale=is_stale,
                                stale_age_seconds=stale_age_seconds,
                                timestamp_source="event",
                            )
                            if insert_result:
                                result += 1
                        except Exception as exc:
                            self._logger.log_error(
                                event_type="individual_tick_insert_error",
                                error=f"Error inserting individual tick: {exc}",
                                symbol=symbol,
                                exc_info=True,
                            )
                else:
                    old_format_ticks = [(t[0], t[1], t[2], t[3]) for t in ticks]
                    result = self._db.insert_forex_ticks_batch(old_format_ticks)

                if result > 0:
                    self._logger.log_event(
                        event_type="ticks_flushed",
                        message=f"Flushed {result} ticks to database",
                        metrics={"tick_count": result, "batch_size": len(ticks)},
                    )
                    if self._verbose:
                        with self._console_lock:
                            print_with_datetime(f"Flushed {result} ticks to database")
        except Exception as exc:
            self._logger.log_error(
                event_type="tick_flush_error",
                error=f"Error flushing ticks to database: {exc}",
                metrics={"batch_size": len(ticks)},
                exc_info=True,
            )
            print_with_datetime(f"Error flushing ticks to database: {exc}")
            for tick in ticks:
                try:
                    if len(tick) >= 8:
                        (
                            symbol,
                            date_time,
                            ask,
                            bid,
                            receive_time,
                            latency_seconds,
                            is_stale,
                            stale_age_seconds,
                        ) = tick[:8]
                        self._db.insert_forex_tick(
                            symbol,
                            date_time,
                            ask,
                            bid,
                            receive_time=receive_time,
                            latency_seconds=latency_seconds,
                            is_stale=is_stale,
                            stale_age_seconds=stale_age_seconds,
                            timestamp_source="event",
                        )
                    else:
                        symbol, date_time, ask, bid = tick[:4]
                        self._db.insert_forex_tick(symbol, date_time, ask, bid)
                except Exception as exc:
                    self._logger.log_error(
                        event_type="individual_tick_insert_error",
                        error=f"Error inserting individual tick: {exc}",
                        symbol=tick[0] if tick else "unknown",
                        exc_info=True,
                    )
                    print_with_datetime(f"Error inserting individual tick: {exc}")

    def _check_connection_health(self, current_time: datetime):
        if self._last_tick_time is None:
            return
        seconds_since_last_tick = (
            current_time - self._last_tick_time
        ).total_seconds()
        if seconds_since_last_tick >= self._connection_stale_threshold:
            self._connection_health_warnings += 1
            self._logger.log_event(
                event_type="connection_health_warning",
                message="Tick feed appears stale",
                metrics={
                    "seconds_since_last_tick": seconds_since_last_tick,
                    "warning_count": self._connection_health_warnings,
                },
                level="WARNING",
            )

    def _process_tick_info(self, tick_info: dict, receive_time: datetime):
        if not isinstance(tick_info, dict):
            self._logger.log_error(
                event_type="invalid_tick_format",
                error="Tick info is not a dictionary",
                metrics={"tick_data": str(tick_info)[:200]},
                exc_info=False,
            )
            return

        if not all(key in tick_info for key in ("symbol", "datetime", "ask", "bid")):
            self._logger.log_error(
                event_type="invalid_tick_format",
                error="Missing required tick fields",
                metrics={"tick_data": tick_info},
                exc_info=False,
            )
            return

        symbol = tick_info["symbol"]
        date_time = tick_info["datetime"]
        ask = tick_info["ask"]
        bid = tick_info["bid"]

        if not self._validate_tick(symbol, date_time, ask, bid):
            return

        if not self._validate_tick_order(symbol, date_time):
            return

        if not self._timezone_detected:
            self._detect_mt5_timezone(date_time)

        tick_info_dict = {
            "symbol": symbol,
            "datetime": date_time,
            "ask": ask,
            "bid": bid,
            "_mt5_timezone_offset": self._mt5_timezone_offset,
            "_receive_time": receive_time,
            "_digits": self._asset.digits if self._asset else None,
        }
        current_time = receive_time

        # Track MT5 broker clock drift (if monitor available)
        try:
            from monitoring.mt5_clock_monitor import get_global_mt5_monitor

            mt5_monitor = get_global_mt5_monitor()
            if mt5_monitor:
                # Parse tick datetime for drift calculation
                normalized_tick_datetime = self._normalize_mt5_timestamp(date_time)
                mt5_monitor.track_tick(
                    tick_datetime=normalized_tick_datetime,
                    receive_time=receive_time,
                    symbol=symbol,
                )
        except Exception as e:
            # Don't fail tick processing if monitoring fails
            if self._use_structured:
                self._logger.log_event(
                    event_type="mt5_clock_monitor_error",
                    message=f"Error tracking tick in MT5 clock monitor: {e}",
                    symbol=symbol,
                    level="WARNING",
                )
            else:
                self._logger.warning(
                    f"Error tracking tick in MT5 clock monitor for {symbol}: {e}"
                )
        is_valid, rejection_reason, timestamp_metadata = self.quality_gate.validate(
            tick_info_dict, symbol, current_time
        )

        # Sync quality gate metrics to Prometheus periodically
        self._quality_metrics_sync_counter += 1
        if self._quality_metrics_sync_counter >= self._quality_metrics_sync_interval:
            self.quality_gate.sync_metrics_to_prometheus(symbol=symbol)
            self._quality_metrics_sync_counter = 0

        if not is_valid:
            if self._db:
                try:
                    self._db.insert_quarantine_tick(
                        symbol=symbol,
                        date_time=date_time,
                        ask=ask,
                        bid=bid,
                        rejection_reason=rejection_reason,
                        receive_time=receive_time,
                    )
                except Exception as exc:
                    if self._use_structured:
                        self._logger.log_event(
                            event_type="quarantine_insert_failed",
                            message=f"Failed to insert rejected tick into quarantine: {exc}",
                            symbol=symbol,
                            level="WARNING",
                        )
                    else:
                        self._logger.warning(
                            f"Failed to insert rejected tick into quarantine for {symbol}: {exc}"
                        )

            if self._use_structured:
                self._logger.log_event(
                    event_type="quality_gate_rejection",
                    message=f"Tick rejected by quality gate: {rejection_reason}",
                    symbol=symbol,
                    metrics={"rejection_reason": rejection_reason},
                    level="WARNING",
                )
            else:
                self._logger.warning(
                    f"Tick rejected by quality gate for {symbol}: {rejection_reason}"
                )
            return

        if timestamp_metadata:
            tick_info_dict["_timestamp_metadata"] = timestamp_metadata
            metadata_receive_time = timestamp_metadata.get("receive_time")
            if metadata_receive_time and isinstance(metadata_receive_time, datetime):
                receive_time = metadata_receive_time
            latency_seconds = timestamp_metadata.get("latency_seconds")
            is_stale = timestamp_metadata.get("is_stale", False)
            stale_age_seconds = timestamp_metadata.get("stale_age_seconds")
        else:
            latency_seconds = None
            is_stale = False
            stale_age_seconds = None

        if latency_seconds is not None and latency_seconds < 0:
            if self._use_structured:
                self._logger.log_event(
                    event_type="negative_latency_detected",
                    message=f"Negative latency detected for {symbol}: {latency_seconds:.3f}s",
                    symbol=symbol,
                    metrics={
                        "latency_seconds": latency_seconds,
                        "event_time": date_time,
                        "receive_time": receive_time.isoformat()
                        if isinstance(receive_time, datetime)
                        else str(receive_time),
                        "time_diff_seconds": (
                            (
                                receive_time - self._normalize_mt5_timestamp(date_time)
                            ).total_seconds()
                            if isinstance(receive_time, datetime)
                            else None
                        ),
                    },
                    level="WARNING",
                )
            else:
                self._logger.warning(
                    f"Negative latency detected for {symbol}: {latency_seconds:.3f}s "
                    f"(event_time: {date_time}, receive_time: {receive_time})"
                )

        if self._use_structured:
            self._logger.log_event(
                event_type="tick_accepted_quality_gate",
                message=f"Tick passed quality gate for {symbol}",
                symbol=symbol,
                metrics={"bid": bid, "ask": ask},
                level="DEBUG",
            )

        try:
            normalized_tick = self.event_normalizer.normalize(
                tick_info_dict, source="mt5"
            )
            validate_result = self.event_normalizer.validate(normalized_tick)
            if not validate_result:
                self._logger.warning(
                    f"Normalized tick failed validation for {symbol}, skipping"
                )
                return

            if self._use_structured:
                self._logger.log_event(
                    event_type="tick_accepted_normalization",
                    message=f"Tick passed normalization for {symbol}",
                    symbol=symbol,
                    level="DEBUG",
                )
        except Exception as exc:
            self._logger.error(
                f"Failed to normalize tick for {symbol}: {exc}",
                exc_info=True,
            )
            normalized_tick = None

        self._asset.update(bid, ask)

        # Prepare tick data for callback and buffer
        if normalized_tick:
            normalized_date_time = normalized_tick["timestamp"]
            normalized_receive_time = normalized_tick.get("receive_time")
            normalized_metadata = normalized_tick.get("timestamp_metadata", {})
            tick_data_for_callback = {
                "symbol": symbol,
                "datetime": normalized_date_time,
                "bid": bid,
                "ask": ask,
                "receive_time": normalized_receive_time or receive_time,
                "latency_seconds": normalized_metadata.get("latency_seconds") or latency_seconds,
                "is_stale": normalized_metadata.get("is_stale", False) or is_stale,
                "stale_age_seconds": normalized_metadata.get("stale_age_seconds") or stale_age_seconds,
            }
        else:
            normalized_date_time = date_time
            normalized_receive_time = receive_time
            normalized_metadata = {}
            tick_data_for_callback = {
                "symbol": symbol,
                "datetime": date_time,
                "bid": bid,
                "ask": ask,
                "receive_time": receive_time,
                "latency_seconds": latency_seconds,
                "is_stale": is_stale,
                "stale_age_seconds": stale_age_seconds,
            }

        # Call real-time callback BEFORE buffering for DB storage
        if self._on_tick_callback:
            try:
                self._on_tick_callback(tick_data_for_callback)
            except Exception as exc:
                self._logger.log_error(
                    event_type="tick_callback_error",
                    error=f"Error in real-time tick callback: {exc}",
                    symbol=symbol,
                    exc_info=True,
                )

        # Add to buffer for DB storage (happens after real-time processing)
        if normalized_tick:
            self._add_tick_to_buffer(
                symbol,
                normalized_date_time,
                ask,
                bid,
                receive_time=normalized_receive_time or receive_time,
                latency_seconds=normalized_metadata.get("latency_seconds")
                or latency_seconds,
                is_stale=normalized_metadata.get("is_stale", False) or is_stale,
                stale_age_seconds=normalized_metadata.get("stale_age_seconds")
                or stale_age_seconds,
            )
        else:
            self._add_tick_to_buffer(
                symbol,
                date_time,
                ask,
                bid,
                receive_time=receive_time,
                latency_seconds=latency_seconds,
                is_stale=is_stale,
                stale_age_seconds=stale_age_seconds,
            )

        self._tick_count += 1
        self._last_tick_time = get_utc_time()
        self._last_heartbeat_time = self._last_tick_time
        self._no_tick_warning_logged = False
        if self._connection_health_warnings > 0:
            self._connection_health_warnings = 0
        if self._last_feed_live_state is not True:
            if self._logger and hasattr(self._logger, "log_event"):
                self._logger.log_event(
                    event_type="feed_state_change",
                    message="Tick feed is LIVE",
                    metrics={"feed_live": True, "symbol": symbol},
                )
            self._last_feed_live_state = True

        # Log every tick at DEBUG level for debugging
        if self._verbose or self._tick_count % 100 == 0:
            self._logger.log_event(
                event_type="tick_received",
                message=f"Received tick #{self._tick_count} for {symbol}",
                symbol=symbol,
                metrics={
                    "tick_count": self._tick_count,
                    "bid": bid,
                    "ask": ask,
                    "datetime": date_time,
                    "receive_time": receive_time.isoformat() if isinstance(receive_time, datetime) else str(receive_time),
                },
                level="DEBUG",
            )

        if self._tick_count % 1000 == 0:
            metrics = self.quality_gate.get_metrics()
            if self._use_structured:
                self._logger.log_event(
                    event_type="quality_metrics",
                    message="Quality gate metrics",
                    metrics=metrics,
                )
            else:
                self._logger.info(f"Quality gate metrics: {metrics}")

    def receive_tick(self, message_reader: Callable[[], dict]):
        symbol = self._asset.symbol if self._asset else "unknown"
        self._logger.log_event(
            event_type="tick_reception_started",
            message=f"Starting tick reception loop for {symbol}",
            symbol=symbol,
        )

        try:
            loop_iteration = 0
            while not self._shutdown_flag.is_set():
                loop_iteration += 1
                current_time = get_utc_time()
                if (
                    current_time - self._last_health_check_time
                ).total_seconds() >= self._connection_health_check_interval:
                    self._last_health_check_time = current_time
                    self._check_connection_health(current_time)

                if (
                    current_time - self._last_market_check
                ).total_seconds() >= 300:
                    self._last_market_check = current_time
                    market_open = check_if_market_open()
                    feed_live = self.is_feed_live()

                    if (
                        self._last_feed_live_state is None
                        or self._last_feed_live_state != feed_live
                    ):
                        self._logger.log_event(
                            event_type="feed_state_change",
                            message=f"Tick feed is {'LIVE' if feed_live else 'STALE'}",
                            metrics={
                                "feed_live": feed_live,
                                "seconds_since_last_tick": (
                                    (
                                        current_time - self._last_tick_time
                                    ).total_seconds()
                                    if self._last_tick_time
                                    else None
                                ),
                                "market_open": market_open,
                            },
                            level="INFO" if feed_live else "WARNING",
                        )
                        self._last_feed_live_state = feed_live

                    if market_open and self._last_tick_time is not None:
                        time_since_last_tick = (
                            current_time - self._last_tick_time
                        ).total_seconds()
                        if (
                            time_since_last_tick >= 300
                            and not self._no_tick_warning_logged
                        ):
                            self._logger.log_event(
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
                            self._no_tick_warning_logged = True
                    elif not market_open and not self._no_tick_warning_logged:
                        self._logger.log_event(
                            event_type="market_closed",
                            message="Market is closed - no ticks expected",
                            metrics={"market_open": False},
                        )
                        self._no_tick_warning_logged = True

                try:
                    tick_info = message_reader()
                    # Log first few messages received to confirm reception is working
                    is_heartbeat = tick_info.get("heartbeat", False)
                    
                    # ALWAYS log first 20 messages, then every 100th
                    if self._tick_count < 20 or self._tick_count % 100 == 0:
                        if is_heartbeat:
                            self._logger.info(
                                f"✓ TickProcessor received HEARTBEAT message #{self._tick_count + 1} for {symbol} "
                                f"(bid={tick_info.get('bid', 'N/A')}, ask={tick_info.get('ask', 'N/A')})"
                            )
                        else:
                            self._logger.info(
                                f"✓ TickProcessor received message #{self._tick_count + 1} for {symbol}: "
                                f"{tick_info.get('symbol', 'N/A')} (bid={tick_info.get('bid', 'N/A')}, ask={tick_info.get('ask', 'N/A')})"
                            )
                except TimeoutError:
                    # Timeout is normal - no message available yet
                    # Log more frequently to diagnose why messages aren't being received
                    symbol = self._asset.symbol if self._asset else "unknown"
                    if self._tick_count == 0:
                        # Log every 10 seconds when no ticks received yet
                        import time
                        if not hasattr(self, '_last_timeout_log'):
                            self._last_timeout_log = time.time()
                        now = time.time()
                        if now - self._last_timeout_log >= 10.0:
                            self._logger.warning(
                                f"⚠️ TickProcessor waiting for messages for {symbol} (tick_count: {self._tick_count}) "
                                f"- No messages received in 10s. Check if discovery service is forwarding ticks to queue."
                            )
                            self._last_timeout_log = now
                    elif self._tick_count > 0 and self._tick_count % 1000 == 0:
                        self._logger.debug(
                            f"TickProcessor waiting for messages (tick_count: {self._tick_count})"
                        )
                    continue
                except Exception as exc:
                    self._logger.log_error(
                        event_type="receive_error",
                        error=f"Unexpected error receiving tick data: {exc}",
                        exc_info=True,
                    )
                    break

                if not tick_info:
                    continue

                if self._verbose:
                    with self._console_lock:
                        print_with_datetime(str(tick_info))

                receive_time = get_utc_time()
                try:
                    self._process_tick_info(tick_info, receive_time)
                except Exception as exc:
                    self._logger.log_error(
                        event_type="tick_processing_error",
                        error=f"Error processing tick: {exc}",
                        exc_info=True,
                    )
        except Exception as exc:
            self._logger.log_error(
                event_type="tick_reception_loop_error",
                error=f"Error in receive_tick loop: {exc}",
                exc_info=True,
            )
        finally:
            self._logger.log_event(
                event_type="tick_streamer_shutdown",
                message=f"Shutting down tick processor. Total ticks received: {self._tick_count}",
                metrics={"total_ticks": self._tick_count},
            )
            self._shutdown_flag.set()
            if self._flush_timer:
                self._flush_timer.cancel()

            with self._buffer_lock:
                if self._tick_buffer:
                    remaining_count = len(self._tick_buffer)
                    remaining_ticks = self._tick_buffer.copy()
                    self._tick_buffer.clear()
                    self._logger.log_event(
                        event_type="shutdown_flush",
                        message=f"Flushing {remaining_count} remaining ticks before shutdown",
                        metrics={"remaining_count": remaining_count},
                    )
                    try:
                        self._db_write_queue.put(remaining_ticks, timeout=1.0)
                    except queue.Full:
                        self._flush_ticks_to_db(remaining_ticks)

            self._logger.log_event(
                event_type="queue_drain_wait",
                message="Waiting for database write queue to drain...",
            )
            try:
                self._db_write_queue.join(timeout=5.0)
            except Exception:
                pass

    def __del__(self):
        self._shutdown_flag.set()
        if self._flush_timer:
            self._flush_timer.cancel()

        with self._buffer_lock:
            if self._tick_buffer:
                remaining_ticks = self._tick_buffer.copy()
                self._tick_buffer.clear()
                try:
                    self._db_write_queue.put(remaining_ticks, timeout=1.0)
                except queue.Full:
                    self._flush_ticks_to_db(remaining_ticks)
