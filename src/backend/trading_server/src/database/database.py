"""
Database interaction from server to PostgreSQL Docker Container

Uses local database connector package for connection management.
"""

import os
import threading
from contextlib import contextmanager
from typing import List, Dict, Tuple, Optional, Any
import json
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Import from local database connector package (relative imports)
from .core import init_db, get_engine
from .connection import execute_query as _execute_query

from utils.time_utils import print_with_datetime, normalize_to_utc, ensure_utc_timezone


class Database:
    """
    Database class

    Uses centralized database connection module while maintaining
    backward-compatible interface with domain-specific methods.
    """

    def __init__(self):
        # Retry configuration (kept for metrics tracking)
        self.__max_retries = int(os.getenv("DB_MAX_RETRIES", "5"))
        self.__retry_delay = float(os.getenv("DB_RETRY_DELAY", "2.0"))
        self.__verbose = os.getenv("DB_VERBOSE", "false").lower() == "true"

        # Metrics tracking
        self.__metrics = {
            "connection_retries": 0,
            "connection_failures": 0,
            "insert_success": 0,
            "insert_failures": 0,
            "batch_inserts": 0,
            "batch_sizes": [],
            "quarantine_insert_success": 0,
            "quarantine_insert_failures": 0,
        }
        self.__metrics_lock = threading.Lock()

        # Initialize centralized database connection
        try:
            init_db()
            self.engine = get_engine()
        except Exception as e:
            with self.__metrics_lock:
                self.__metrics["connection_failures"] += 1
            print_with_datetime(f"Failed to initialize database connection: {e}")
            raise e

    @contextmanager
    def execute_query(self):
        """
        Context manager for executing queries with automatic transaction handling.

        Automatically commits on success, rolls back on error.
        Connections are automatically returned to the pool.

        Usage:
            with self.execute_query() as conn:
                result = conn.execute(text("SELECT * FROM table WHERE id = :id"), {"id": 1})
        """
        # Use centralized execute_query from database.connection
        with _execute_query() as conn:
            yield conn

    def execute_with_result(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Tuple]:
        """
        Execute query and return all results

        :param query: SQL query string with named parameters (:param_name)
        :param params: Dictionary of parameters
        :return: List of result tuples
        """
        with self.execute_query() as conn:
            result = conn.execute(text(query), params or {})
            return result.fetchall()

    def execute_one(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[Tuple]:
        """
        Execute query and return single result

        :param query: SQL query string with named parameters (:param_name)
        :param params: Dictionary of parameters
        :return: Single result tuple or None
        """
        with self.execute_query() as conn:
            result = conn.execute(text(query), params or {})
            return result.fetchone()

    def execute_transaction(
        self, queries_with_params: List[Tuple[str, Dict[str, Any]]]
    ):
        """
        Execute multiple queries in a single transaction

        :param queries_with_params: List of (query, params) tuples
        """
        with self.execute_query() as conn:
            for query, params in queries_with_params:
                conn.execute(text(query), params or {})

    def check_connection_health(self):
        """
        Check if the database connection is healthy

        :return: True if healthy, False otherwise
        """
        try:
            with self.execute_query() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            return True
        except Exception as e:
            print_with_datetime(f"Health check failed: {e}")
            return False

    def get_metrics(self):
        """
        Get database operation metrics

        :return: Dictionary of metrics
        """
        with self.__metrics_lock:
            metrics = self.__metrics.copy()
            if metrics["batch_sizes"]:
                metrics["avg_batch_size"] = sum(metrics["batch_sizes"]) / len(
                    metrics["batch_sizes"]
                )
                metrics["max_batch_size"] = max(metrics["batch_sizes"])
                metrics["min_batch_size"] = min(metrics["batch_sizes"])
            else:
                metrics["avg_batch_size"] = 0
                metrics["max_batch_size"] = 0
                metrics["min_batch_size"] = 0
            return metrics

    def _normalize_timestamp(self, date_time):
        """
        Normalize timestamp to UTC timezone for database storage

        Note: We use UTC consistently throughout the system. This avoids DST issues
        and provides a universal standard. All timestamps are stored in UTC.
        Preserves microsecond precision.

        :param date_time: datetime object or string
        :return: Normalized timezone-aware datetime object in UTC (preserves microseconds)
        """
        if isinstance(date_time, datetime):
            # Convert datetime object to UTC (preserves microseconds)
            return ensure_utc_timezone(date_time)
        elif isinstance(date_time, str):
            # Parse string and normalize to UTC
            # Try to parse with microseconds if present
            try:
                # Try standard format with microseconds: "YYYY-MM-DD HH:MM:SS.microseconds"
                if len(date_time) > 19 and "." in date_time:
                    try:
                        # Try parsing with microseconds (up to 6 digits)
                        dt = datetime.strptime(date_time[:26], "%Y-%m-%d %H:%M:%S.%f")
                    except ValueError:
                        # Fallback to seconds-only
                        dt = datetime.strptime(date_time[:19], "%Y-%m-%d %H:%M:%S")
                else:
                    # Standard format without microseconds
                    dt = datetime.strptime(date_time[:19], "%Y-%m-%d %H:%M:%S")
                return normalize_to_utc(dt)
            except ValueError:
                # If parsing fails, try MT5 format or other formats via normalize_to_utc
                return normalize_to_utc(date_time)
        else:
            # Convert to string and try again
            return normalize_to_utc(str(date_time))

    def insert_forex_tick(
        self,
        symbol,
        date_time,
        ask,
        bid,
        receive_time=None,
        latency_seconds=None,
        is_stale=False,
        stale_age_seconds=None,
        timestamp_source="event",
        schema_version="1.0.0",
        schema_type="tick",
    ):
        """
        Insert a tick to the database with bitemporal timestamps

        :param symbol: Symbol of the tick
        :param date_time: Datetime of the tick (event_time, datetime object or string, will be normalized to UTC)
        :param ask: Ask price
        :param bid: Bid price
        :param receive_time: When we received the tick (transaction time, optional)
        :param latency_seconds: Latency in seconds (optional, calculated if not provided)
        :param is_stale: Flag if original timestamp was stale (optional)
        :param stale_age_seconds: Age of stale timestamp in seconds (optional)
        :param timestamp_source: Source of timestamp ('event', 'receive', 'estimated', optional)
        :param schema_version: Schema contract version used (default: '1.0.0')
        :param schema_type: Data type identifier (default: 'tick')
        :return: True if insert is done
        """
        try:
            # Normalize timestamps to UTC (returns datetime object, preserves microseconds)
            normalized_date_time = self._normalize_timestamp(date_time)
            normalized_receive_time = None
            if receive_time is not None:
                normalized_receive_time = self._normalize_timestamp(receive_time)

            # Calculate latency if not provided and both timestamps available
            if latency_seconds is None and normalized_receive_time is not None:
                latency_seconds = int(
                    (normalized_receive_time - normalized_date_time).total_seconds()
                )

            # Normalize symbol to uppercase for consistency (MT5 symbols are typically uppercase)
            symbol_upper = symbol.upper().strip()
            base_currency = symbol_upper[:3]
            quoted_currency = symbol_upper[3:]

            # Validate symbol format
            if len(symbol_upper) != 6:
                print_with_datetime(
                    f"ERROR: Invalid symbol format '{symbol}' (expected 6 characters, got {len(symbol_upper)})"
                )
                with self.__metrics_lock:
                    self.__metrics["insert_failures"] += 1
                return False

            query = """
                INSERT INTO ticks_forex (
                    datetime, ask, bid, forex_pairs_id,
                    receive_time, latency_seconds, is_stale,
                    stale_age_seconds, timestamp_source,
                    schema_version, schema_type
                )
                SELECT :datetime, :ask, :bid, fp.id, :receive_time, :latency_seconds,
                       :is_stale, :stale_age_seconds, :timestamp_source, :schema_version, :schema_type
                FROM currency c1
                CROSS JOIN currency c2
                INNER JOIN forex_pairs fp ON fp.base_currency_id = c1.id AND fp.quote_currency_id = c2.id
                WHERE c1.iso_code = :base_currency AND c2.iso_code = :quoted_currency
                LIMIT 1
            """

            params = {
                "datetime": normalized_date_time,
                "ask": ask,
                "bid": bid,
                "receive_time": normalized_receive_time,
                "latency_seconds": latency_seconds,
                "is_stale": is_stale,
                "stale_age_seconds": stale_age_seconds,
                "timestamp_source": timestamp_source,
                "schema_version": schema_version,
                "schema_type": schema_type,
                "base_currency": base_currency,
                "quoted_currency": quoted_currency,
            }

            with self.execute_query() as conn:
                result = conn.execute(text(query), params)
                rowcount = result.rowcount

            # Check if a row was actually inserted
            if rowcount == 0:
                # No row inserted - currency pair not found or lookup failed
                print_with_datetime(
                    f"WARNING: Currency pair '{symbol}' (normalized: '{symbol_upper}', "
                    f"base: '{base_currency}', quote: '{quoted_currency}') not found in "
                    f"database - tick not inserted. Please verify the symbol exists in "
                    f"the forex_pairs table."
                )
                with self.__metrics_lock:
                    self.__metrics["insert_failures"] += 1
                return False

            with self.__metrics_lock:
                self.__metrics["insert_success"] += 1
            return True
        except SQLAlchemyError as e:
            print_with_datetime(f"Error inserting forex tick: {e}")
            with self.__metrics_lock:
                self.__metrics["insert_failures"] += 1
            return False

    def _categorize_rejection_reason(self, rejection_reason: str) -> str:
        """
        Categorize rejection reason into predefined categories

        :param rejection_reason: Detailed rejection reason string
        :return: Category string (outlier, duplicate, stale, missing_data, invalid_spread)
        """
        reason_lower = rejection_reason.lower()
        if "outlier" in reason_lower or "extreme price" in reason_lower:
            return "outlier"
        elif "duplicate" in reason_lower:
            return "duplicate"
        elif "stale" in reason_lower:
            return "stale"
        elif "missing" in reason_lower or "invalid data types" in reason_lower:
            return "missing_data"
        elif "spread" in reason_lower or "ask <= bid" in reason_lower:
            return "invalid_spread"
        else:
            return "unknown"

    def insert_quarantine_tick(
        self,
        symbol: str,
        date_time,
        ask: float,
        bid: float,
        rejection_reason: str,
        receive_time=None,
    ) -> bool:
        """
        Insert a rejected tick into the quarantine table

        :param symbol: Currency pair symbol
        :param date_time: Event time (datetime object or string, will be normalized to UTC)
        :param ask: Ask price
        :param bid: Bid price
        :param rejection_reason: Detailed reason for rejection
        :param receive_time: When tick was received (optional)
        :return: True if insert is successful, False otherwise
        """
        try:
            # Normalize timestamps to UTC
            normalized_date_time = self._normalize_timestamp(date_time)
            normalized_receive_time = None
            if receive_time is not None:
                normalized_receive_time = self._normalize_timestamp(receive_time)

            # Categorize rejection reason
            rejection_category = self._categorize_rejection_reason(rejection_reason)

            query = """
                INSERT INTO quarantine_ticks
                (symbol, datetime, receive_time, bid, ask, rejection_reason, rejection_category)
                VALUES (:symbol, :datetime, :receive_time, :bid, :ask, :rejection_reason, :rejection_category)
            """

            params = {
                "symbol": symbol,
                "datetime": normalized_date_time,
                "receive_time": normalized_receive_time,
                "bid": bid,
                "ask": ask,
                "rejection_reason": rejection_reason,
                "rejection_category": rejection_category,
            }

            with self.execute_query() as conn:
                conn.execute(text(query), params)

            with self.__metrics_lock:
                self.__metrics["quarantine_insert_success"] += 1

            # Update Prometheus metrics
            try:
                from monitoring.metrics import quarantine_ticks_total

                quarantine_ticks_total.labels(
                    symbol=symbol, rejection_category=rejection_category
                ).inc()
            except Exception as e:
                # Don't fail if metrics update fails
                print_with_datetime(
                    f"Warning: Failed to update quarantine metrics: {e}"
                )

            return True
        except SQLAlchemyError as e:
            print_with_datetime(f"Error inserting quarantine tick: {e}")
            with self.__metrics_lock:
                self.__metrics["quarantine_insert_failures"] += 1
            return False
        except Exception as e:
            print_with_datetime(f"Unexpected error inserting quarantine tick: {e}")
            with self.__metrics_lock:
                self.__metrics["quarantine_insert_failures"] += 1
            return False

    def insert_forex_ticks_batch(self, ticks):
        """
        Insert multiple ticks to the database in a single transaction using bulk insert

        :param ticks: List of tuples, each tuple contains (symbol, date_time, ask, bid)
        :return: Number of successfully inserted ticks, or -1 on error
        """
        if not ticks:
            return 0

        try:
            # Normalize all timestamps to UTC (returns datetime objects, preserves microseconds)
            tick_data = []
            for symbol, date_time, ask, bid in ticks:
                # Normalize symbol to uppercase for consistency (MT5 symbols are typically uppercase)
                symbol_upper = symbol.upper().strip()
                if len(symbol_upper) != 6:
                    print_with_datetime(
                        f"WARNING: Skipping invalid symbol format '{symbol}' "
                        f"(expected 6 characters, got {len(symbol_upper)})"
                    )
                    continue
                base_currency = symbol_upper[:3]
                quoted_currency = symbol_upper[3:]
                # Normalize returns datetime object (preserves microseconds)
                normalized_date_time = self._normalize_timestamp(date_time)
                tick_data.append(
                    (
                        normalized_date_time,
                        ask,
                        bid,
                        base_currency,
                        quoted_currency,
                        symbol_upper,
                    )
                )

            # Use direct INSERT instead of stored procedure for better error handling
            # This allows us to verify inserts actually happened
            insert_count = 0
            failed_symbols = set()

            query = """
                INSERT INTO ticks_forex (datetime, ask, bid, forex_pairs_id)
                SELECT :datetime, :ask, :bid, fp.id
                FROM currency c1
                CROSS JOIN currency c2
                INNER JOIN forex_pairs fp ON fp.base_currency_id = c1.id AND fp.quote_currency_id = c2.id
                WHERE c1.iso_code = :base_currency AND c2.iso_code = :quoted_currency
                LIMIT 1
            """

            with self.execute_query() as conn:
                for (
                    date_time,
                    ask,
                    bid,
                    base_currency,
                    quoted_currency,
                    symbol_upper,
                ) in tick_data:
                    try:
                        params = {
                            "datetime": date_time,
                            "ask": ask,
                            "bid": bid,
                            "base_currency": base_currency,
                            "quoted_currency": quoted_currency,
                        }
                        result = conn.execute(text(query), params)
                        rowcount = result.rowcount

                        # Check if a row was actually inserted
                        if rowcount > 0:
                            insert_count += 1
                        else:
                            # No row inserted - pair doesn't exist
                            failed_symbols.add(symbol_upper)
                            if self.__verbose:
                                print_with_datetime(
                                    f"WARNING: Currency pair {symbol_upper} "
                                    f"(base: {base_currency}, quote: {quoted_currency}) "
                                    f"not found in database - tick not inserted"
                                )
                    except SQLAlchemyError as e:
                        symbol = base_currency + quoted_currency
                        failed_symbols.add(symbol)
                        print_with_datetime(f"Error inserting tick for {symbol}: {e}")
                        continue

            if failed_symbols:
                print_with_datetime(
                    f"WARNING: Failed to insert ticks for {len(failed_symbols)} "
                    f"symbol(s): {', '.join(sorted(failed_symbols))}. "
                    f"These currency pairs may not exist in the forex_pairs table."
                )

            with self.__metrics_lock:
                self.__metrics["batch_inserts"] += 1
                self.__metrics["batch_sizes"].append(len(ticks))
                self.__metrics["insert_success"] += insert_count
                if insert_count < len(ticks):
                    self.__metrics["insert_failures"] += len(ticks) - insert_count

            if self.__verbose:
                print_with_datetime(f"Batch inserted {insert_count}/{len(ticks)} ticks")

            return insert_count

        except SQLAlchemyError as e:
            print_with_datetime(f"Error in batch insert: {e}")
            with self.__metrics_lock:
                self.__metrics["insert_failures"] += len(ticks)
            return -1

    def insert_economic_calendar_data(self, data):
        """
        Insert multiple data from the economic calendar

        :param data: Pandas Dataframe
        """
        try:
            query = (
                "SELECT insert_economic_calendar_data(:date, :country, :event, "
                ":impact, :previous, :consensus, :actual)"
            )

            with self.execute_query() as conn:
                for _, row in data.iterrows():
                    # Normalize timestamp to EST before storing
                    date = self._normalize_timestamp(row["Date"])
                    country = row["Country"]
                    event = row["Event"]
                    impact = row["Impact"]
                    previous = row["Previous"] if row["Previous"] != "" else None
                    consensus = row["Consensus"] if row["Consensus"] != "" else None
                    actual = row["Actual"] if row["Actual"] != "" else None

                    params = {
                        "date": date,
                        "country": country,
                        "event": event,
                        "impact": impact,
                        "previous": previous,
                        "consensus": consensus,
                        "actual": actual,
                    }
                    conn.execute(text(query), params)

            return True
        except SQLAlchemyError as e:
            print_with_datetime(f"Error inserting economic calendar data: {e}")
            return False

    def insert_forex_bar(
        self,
        symbol: str,
        datetime_val: datetime,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: Optional[float],
        timeframe: str,
        receive_time: Optional[datetime] = None,
    ) -> bool:
        """
        Insert a single OHLCV bar to the database

        :param symbol: Trading symbol (e.g., "EURUSD")
        :param datetime_val: Bar datetime (event time)
        :param open_price: Open price
        :param high: High price
        :param low: Low price
        :param close: Close price
        :param volume: Volume (optional)
        :param timeframe: Timeframe (M1, M5, M15, M30, H1, H4, D1)
        :param receive_time: Receive time (transaction time, optional)
        :return: True if inserted successfully, False otherwise
        """
        try:
            # Normalize symbol
            symbol_upper = symbol.upper().strip()
            if len(symbol_upper) != 6:
                print_with_datetime(
                    f"WARNING: Invalid symbol format '{symbol}' "
                    f"(expected 6 characters, got {len(symbol_upper)})"
                )
                return False

            base_currency = symbol_upper[:3]
            quoted_currency = symbol_upper[3:]

            # Normalize timestamps
            normalized_datetime = self._normalize_timestamp(datetime_val)
            if receive_time:
                normalized_receive_time = self._normalize_timestamp(receive_time)
                latency_seconds = int(
                    (normalized_receive_time - normalized_datetime).total_seconds()
                )
            else:
                normalized_receive_time = ensure_utc_timezone(datetime.now())
                latency_seconds = None

            query = text("""
                INSERT INTO bars_forex
                (datetime, open, high, low, close, volume, timeframe, forex_pairs_id,
                 receive_time, latency_seconds, schema_version, schema_type)
                SELECT :datetime, :open, :high, :low, :close, :volume, :timeframe, fp.id,
                       :receive_time, :latency_seconds, '1.0.0', 'bar'
                FROM currency c1
                CROSS JOIN currency c2
                INNER JOIN forex_pairs fp ON fp.base_currency_id = c1.id AND fp.quote_currency_id = c2.id
                WHERE c1.iso_code = :base_currency AND c2.iso_code = :quoted_currency
                LIMIT 1
                ON CONFLICT (forex_pairs_id, timeframe, datetime) DO NOTHING
            """)

            params = {
                "datetime": normalized_datetime,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "timeframe": timeframe,
                "base_currency": base_currency,
                "quoted_currency": quoted_currency,
                "receive_time": normalized_receive_time,
                "latency_seconds": latency_seconds,
            }

            with self.execute_query() as conn:
                conn.execute(query, params)
            return True

        except SQLAlchemyError as e:
            print_with_datetime(f"Error inserting bar for {symbol}: {e}")
            return False

    def insert_forex_bars_batch(self, bars: List[Dict]) -> int:
        """
        Insert multiple OHLCV bars to the database in a single transaction

        :param bars: List of bar dictionaries, each containing:
                     symbol, datetime, open, high, low, close, volume (optional), timeframe
        :return: Number of successfully inserted bars, or -1 on error
        """
        if not bars:
            return 0

        try:
            insert_count = 0
            failed_symbols = set()

            query = text("""
                INSERT INTO bars_forex
                (datetime, open, high, low, close, volume, timeframe, forex_pairs_id,
                 receive_time, latency_seconds, schema_version, schema_type)
                SELECT :datetime, :open, :high, :low, :close, :volume, :timeframe, fp.id,
                       :receive_time, :latency_seconds, '1.0.0', 'bar'
                FROM currency c1
                CROSS JOIN currency c2
                INNER JOIN forex_pairs fp ON fp.base_currency_id = c1.id AND fp.quote_currency_id = c2.id
                WHERE c1.iso_code = :base_currency AND c2.iso_code = :quoted_currency
                LIMIT 1
                ON CONFLICT (forex_pairs_id, timeframe, datetime) DO NOTHING
            """)

            with self.execute_query() as conn:
                for bar in bars:
                    try:
                        symbol = bar.get("symbol", "").upper().strip()
                        if len(symbol) != 6:
                            continue

                        base_currency = symbol[:3]
                        quoted_currency = symbol[3:]

                        # Normalize timestamps
                        datetime_val = self._normalize_timestamp(bar["datetime"])
                        receive_time = bar.get("receive_time")
                        if receive_time:
                            normalized_receive_time = self._normalize_timestamp(
                                receive_time
                            )
                            latency_seconds = int(
                                (normalized_receive_time - datetime_val).total_seconds()
                            )
                        else:
                            normalized_receive_time = ensure_utc_timezone(
                                datetime.now()
                            )
                            latency_seconds = None

                        params = {
                            "datetime": datetime_val,
                            "open": bar["open"],
                            "high": bar["high"],
                            "low": bar["low"],
                            "close": bar["close"],
                            "volume": bar.get("volume"),
                            "timeframe": bar["timeframe"],
                            "base_currency": base_currency,
                            "quoted_currency": quoted_currency,
                            "receive_time": normalized_receive_time,
                            "latency_seconds": latency_seconds,
                        }

                        result = conn.execute(query, params)
                        if result.rowcount > 0:
                            insert_count += 1
                        else:
                            # Check if it's a conflict (duplicate) or missing pair
                            check_query = text("""
                                SELECT COUNT(*) FROM forex_pairs fp
                                JOIN currency c1 ON fp.base_currency_id = c1.id
                                JOIN currency c2 ON fp.quote_currency_id = c2.id
                                WHERE c1.iso_code = :base_currency
                                  AND c2.iso_code = :quoted_currency
                            """)
                            check_result = conn.execute(
                                check_query,
                                {
                                    "base_currency": base_currency,
                                    "quoted_currency": quoted_currency,
                                },
                            )
                            if check_result.scalar() == 0:
                                failed_symbols.add(symbol)

                    except SQLAlchemyError as e:
                        symbol = bar.get("symbol", "unknown")
                        failed_symbols.add(symbol)
                        print_with_datetime(f"Error inserting bar for {symbol}: {e}")
                        continue

            if failed_symbols:
                print_with_datetime(
                    f"WARNING: Failed to insert bars for {len(failed_symbols)} "
                    f"symbol(s): {', '.join(sorted(failed_symbols))}"
                )

            return insert_count

        except SQLAlchemyError as e:
            print_with_datetime(f"Error in batch bar insert: {e}")
            return -1

    def get_bars_by_timeframe(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
        query_time: Optional[datetime] = None,
    ) -> List[Dict]:
        """
        Get OHLCV bars for a symbol and timeframe within a time range
        Supports point-in-time queries (only returns bars with datetime <= query_time)

        :param symbol: Trading symbol
        :param timeframe: Timeframe (M1, M5, M15, M30, H1, H4, D1)
        :param start_time: Start time (inclusive)
        :param end_time: End time (inclusive)
        :param query_time: Optional point-in-time query (only bars with datetime <= query_time)
        :return: List of bar dictionaries
        """
        try:
            symbol_upper = symbol.upper().strip()
            if len(symbol_upper) != 6:
                return []

            base_currency = symbol_upper[:3]
            quoted_currency = symbol_upper[3:]

            # Normalize timestamps
            normalized_start = self._normalize_timestamp(start_time)
            normalized_end = self._normalize_timestamp(end_time)

            # Build query with optional point-in-time filter
            time_filter = "tf.datetime >= :start_time AND tf.datetime <= :end_time"
            if query_time:
                normalized_query_time = self._normalize_timestamp(query_time)
                time_filter += " AND tf.datetime <= :query_time"

            query = f"""
                SELECT
                    tf.datetime,
                    tf.open,
                    tf.high,
                    tf.low,
                    tf.close,
                    tf.volume,
                    tf.timeframe,
                    tf.receive_time,
                    tf.latency_seconds
                FROM bars_forex tf
                JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
                JOIN currency c1 ON fp.base_currency_id = c1.id
                JOIN currency c2 ON fp.quote_currency_id = c2.id
                WHERE c1.iso_code = :base_currency
                  AND c2.iso_code = :quoted_currency
                  AND tf.timeframe = :timeframe
                  AND {time_filter}
                ORDER BY tf.datetime ASC
            """

            params = {
                "base_currency": base_currency,
                "quoted_currency": quoted_currency,
                "timeframe": timeframe,
                "start_time": normalized_start,
                "end_time": normalized_end,
            }

            if query_time:
                params["query_time"] = normalized_query_time

            results = self.execute_with_result(query, params)

            bars = []
            for row in results:
                bars.append(
                    {
                        "datetime": row[0],
                        "open": float(row[1]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                        "close": float(row[4]),
                        "volume": float(row[5]) if row[5] is not None else None,
                        "timeframe": row[6],
                        "receive_time": row[7],
                        "latency_seconds": row[8],
                    }
                )

            return bars

        except SQLAlchemyError as e:
            print_with_datetime(f"Error retrieving bars for {symbol}: {e}")
            return []

    def get_latest_bar(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """
        Get the most recent bar for a symbol and timeframe

        :param symbol: Trading symbol
        :param timeframe: Timeframe (M1, M5, M15, M30, H1, H4, D1)
        :return: Bar dictionary or None if not found
        """
        try:
            symbol_upper = symbol.upper().strip()
            if len(symbol_upper) != 6:
                return None

            base_currency = symbol_upper[:3]
            quoted_currency = symbol_upper[3:]

            query = text("""
                SELECT
                    tf.datetime,
                    tf.open,
                    tf.high,
                    tf.low,
                    tf.close,
                    tf.volume,
                    tf.timeframe,
                    tf.receive_time
                FROM bars_forex tf
                JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
                JOIN currency c1 ON fp.base_currency_id = c1.id
                JOIN currency c2 ON fp.quote_currency_id = c2.id
                WHERE c1.iso_code = :base_currency
                  AND c2.iso_code = :quoted_currency
                  AND tf.timeframe = :timeframe
                ORDER BY tf.datetime DESC
                LIMIT 1
            """)

            params = {
                "base_currency": base_currency,
                "quoted_currency": quoted_currency,
                "timeframe": timeframe,
            }

            results = self.execute_with_result(query, params)

            if results and len(results) > 0:
                row = results[0]
                return {
                    "datetime": row[0],
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]) if row[5] is not None else None,
                    "timeframe": row[6],
                    "receive_time": row[7],
                }

            return None

        except SQLAlchemyError as e:
            print_with_datetime(f"Error retrieving latest bar for {symbol}: {e}")
            return None

    def get_recent_ticks(
        self,
        symbol: str,
        limit: int = 100,
        hours: int = 24,
        query_by: str = "event_time",
    ):
        """
        Get recent tick data for a symbol with bitemporal information

        :param symbol: Currency pair symbol (e.g., 'EURUSD')
        :param limit: Maximum number of ticks to return
        :param hours: Number of hours to look back
        :param query_by: Query by 'event_time' (datetime column) or 'receive_time' (for point-in-time training)
        :return: List of dictionaries with bitemporal timestamp information
        """
        try:
            # Extract base and quote currencies from symbol
            base_currency = symbol[:3]
            quote_currency = symbol[3:]

            # Determine which timestamp column to use for filtering and ordering
            # Use conditional logic instead of f-string interpolation for security
            if query_by == "receive_time":
                # Query by receive_time (transaction time) for point-in-time training
                time_filter = "COALESCE(tf.receive_time, tf.datetime) >= NOW() - INTERVAL :hours HOUR"
                order_clause = "ORDER BY COALESCE(tf.receive_time, tf.datetime) ASC"
            else:
                # Query by event_time (datetime) for pattern learning
                time_filter = "tf.datetime >= NOW() - INTERVAL :hours HOUR"
                order_clause = "ORDER BY tf.datetime ASC"

            query = f"""
                SELECT
                    tf.datetime as event_time,
                    tf.receive_time,
                    (tf.ask + tf.bid) / 2 as mid_price,
                    tf.ask,
                    tf.bid,
                    tf.latency_seconds,
                    tf.is_stale,
                    tf.stale_age_seconds,
                    tf.timestamp_source
                FROM ticks_forex tf
                JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
                JOIN currency c1 ON fp.base_currency_id = c1.id
                JOIN currency c2 ON fp.quote_currency_id = c2.id
                WHERE c1.iso_code = :base_currency AND c2.iso_code = :quote_currency
                AND {time_filter}
                {order_clause}
                LIMIT :limit
            """

            params = {
                "base_currency": base_currency,
                "quote_currency": quote_currency,
                "hours": hours,
                "limit": limit,
            }

            results = self.execute_with_result(query, params)

            ticks = []
            for row in results:
                ticks.append(
                    {
                        "event_time": row[0],
                        "receive_time": row[1],
                        "mid_price": float(row[2]),
                        "ask": float(row[3]),
                        "bid": float(row[4]),
                        "latency_seconds": row[5],
                        "is_stale": bool(row[6]) if row[6] is not None else False,
                        "stale_age_seconds": row[7],
                        "timestamp_source": row[8],
                    }
                )

            return ticks

        except SQLAlchemyError as e:
            print_with_datetime(f"Error retrieving recent ticks for {symbol}: {e}")
            return []

    def insert_economic_indicator(
        self,
        series_id: str,
        timestamp: datetime,
        value: float,
        source: str,
        country: Optional[str] = None,
        frequency: Optional[str] = None,
        receive_time: Optional[datetime] = None,
    ) -> bool:
        """
        Insert a single economic indicator to the database

        :param series_id: Source-specific series identifier (e.g., "FEDFUNDS" for FRED)
        :param timestamp: Indicator observation time (event time)
        :param value: Indicator value
        :param source: Data source ("FRED", "WORLD_BANK", "ECB", "OTHER")
        :param country: ISO country code (2-3 characters, optional)
        :param frequency: Data frequency ("DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "ANNUAL", optional)
        :param receive_time: Receive time (transaction time, optional)
        :return: True if inserted successfully, False otherwise
        """
        try:
            # Normalize timestamps
            normalized_timestamp = self._normalize_timestamp(timestamp)
            if receive_time:
                normalized_receive_time = self._normalize_timestamp(receive_time)
                latency_seconds = int(
                    (normalized_receive_time - normalized_timestamp).total_seconds()
                )
            else:
                normalized_receive_time = ensure_utc_timezone(datetime.now())
                latency_seconds = None

            query = text("""
                INSERT INTO economic_indicators
                (timestamp, series_id, value, source, country, frequency,
                 receive_time, latency_seconds, schema_version, schema_type)
                VALUES (:timestamp, :series_id, :value, :source, :country, :frequency,
                        :receive_time, :latency_seconds, '1.0.0', 'economic')
                ON CONFLICT (series_id, timestamp) DO NOTHING
            """)

            params = {
                "timestamp": normalized_timestamp,
                "series_id": series_id,
                "value": value,
                "source": source,
                "country": country,
                "frequency": frequency,
                "receive_time": normalized_receive_time,
                "latency_seconds": latency_seconds,
            }

            with self.execute_query() as conn:
                conn.execute(query, params)
            return True

        except SQLAlchemyError as e:
            print_with_datetime(f"Error inserting economic indicator {series_id}: {e}")
            return False

    def insert_economic_indicators_batch(self, indicators: List[Dict]) -> int:
        """
        Insert multiple economic indicators to the database in a single transaction

        :param indicators: List of indicator dictionaries, each containing:
                          series_id, timestamp, value, source, country (optional), frequency (optional)
        :return: Number of successfully inserted indicators, or -1 on error
        """
        if not indicators:
            return 0

        try:
            insert_count = 0
            failed_series = set()

            query = text("""
                INSERT INTO economic_indicators
                (timestamp, series_id, value, source, country, frequency,
                 receive_time, latency_seconds, schema_version, schema_type)
                VALUES (:timestamp, :series_id, :value, :source, :country, :frequency,
                        :receive_time, :latency_seconds, '1.0.0', 'economic')
                ON CONFLICT (series_id, timestamp) DO NOTHING
            """)

            with self.execute_query() as conn:
                for indicator in indicators:
                    try:
                        # Normalize timestamps
                        timestamp_val = self._normalize_timestamp(
                            indicator["timestamp"]
                        )
                        receive_time = indicator.get("receive_time")
                        if receive_time:
                            normalized_receive_time = self._normalize_timestamp(
                                receive_time
                            )
                            latency_seconds = int(
                                (
                                    normalized_receive_time - timestamp_val
                                ).total_seconds()
                            )
                        else:
                            normalized_receive_time = ensure_utc_timezone(
                                datetime.now()
                            )
                            latency_seconds = None

                        params = {
                            "timestamp": timestamp_val,
                            "series_id": indicator["series_id"],
                            "value": indicator["value"],
                            "source": indicator["source"],
                            "country": indicator.get("country"),
                            "frequency": indicator.get("frequency"),
                            "receive_time": normalized_receive_time,
                            "latency_seconds": latency_seconds,
                        }

                        result = conn.execute(query, params)
                        if result.rowcount > 0:
                            insert_count += 1

                    except SQLAlchemyError as e:
                        series_id = indicator.get("series_id", "unknown")
                        failed_series.add(series_id)
                        print_with_datetime(
                            f"Error inserting indicator {series_id}: {e}"
                        )
                        continue

            if failed_series:
                print_with_datetime(
                    f"WARNING: Failed to insert {len(failed_series)} "
                    f"indicator(s): {', '.join(sorted(failed_series))}"
                )

            with self.__metrics_lock:
                self.__metrics["batch_inserts"] += 1
                self.__metrics["batch_sizes"].append(len(indicators))
                self.__metrics["insert_success"] += insert_count
                if insert_count < len(indicators):
                    self.__metrics["insert_failures"] += len(indicators) - insert_count

            return insert_count

        except SQLAlchemyError as e:
            print_with_datetime(f"Error in batch economic indicator insert: {e}")
            with self.__metrics_lock:
                self.__metrics["insert_failures"] += len(indicators)
            return -1

    def get_economic_indicators(
        self,
        series_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        source: Optional[str] = None,
        country: Optional[str] = None,
    ) -> List[Dict]:
        """
        Query economic indicators with optional filters

        :param series_id: Filter by series ID (optional)
        :param start_time: Start time for query (optional, point-in-time safe)
        :param end_time: End time for query (optional, point-in-time safe)
        :param source: Filter by source (optional)
        :param country: Filter by country (optional)
        :return: List of indicator dictionaries
        """
        try:
            conditions = []
            params = {}

            if series_id:
                conditions.append("series_id = :series_id")
                params["series_id"] = series_id

            if start_time:
                normalized_start = self._normalize_timestamp(start_time)
                conditions.append("timestamp >= :start_time")
                params["start_time"] = normalized_start

            if end_time:
                normalized_end = self._normalize_timestamp(end_time)
                conditions.append("timestamp <= :end_time")
                params["end_time"] = normalized_end

            if source:
                conditions.append("source = :source")
                params["source"] = source

            if country:
                conditions.append("country = :country")
                params["country"] = country

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            query = text(f"""
                SELECT timestamp, series_id, value, source, country, frequency,
                       receive_time, latency_seconds
                FROM economic_indicators
                WHERE {where_clause}
                ORDER BY timestamp ASC
            """)

            with self.execute_query() as conn:
                result = conn.execute(query, params)
                rows = result.fetchall()

                indicators = []
                for row in rows:
                    indicators.append(
                        {
                            "timestamp": row[0],
                            "series_id": row[1],
                            "value": row[2],
                            "source": row[3],
                            "country": row[4],
                            "frequency": row[5],
                            "receive_time": row[6],
                            "latency_seconds": row[7],
                        }
                    )

                return indicators

        except SQLAlchemyError as e:
            print_with_datetime(f"Error querying economic indicators: {e}")
            return []

    def get_latest_indicator(self, series_id: str) -> Optional[Dict]:
        """
        Get the most recent indicator value for a series

        :param series_id: Series identifier
        :return: Latest indicator dictionary or None if not found
        """
        try:
            query = text("""
                SELECT timestamp, series_id, value, source, country, frequency,
                       receive_time, latency_seconds
                FROM economic_indicators
                WHERE series_id = :series_id
                ORDER BY timestamp DESC
                LIMIT 1
            """)

            with self.execute_query() as conn:
                result = conn.execute(query, {"series_id": series_id})
                row = result.fetchone()

                if row:
                    return {
                        "timestamp": row[0],
                        "series_id": row[1],
                        "value": row[2],
                        "source": row[3],
                        "country": row[4],
                        "frequency": row[5],
                        "receive_time": row[6],
                        "latency_seconds": row[7],
                    }

                return None

        except SQLAlchemyError as e:
            print_with_datetime(f"Error getting latest indicator for {series_id}: {e}")
            return None

    def check_news_exists(self, url: str) -> bool:
        """
        Check if a news article with the given URL already exists

        :param url: Article URL
        :return: True if article exists, False otherwise
        """
        try:
            query = text("""
                SELECT COUNT(*) FROM news_articles WHERE url = :url
            """)

            with self.execute_query() as conn:
                result = conn.execute(query, {"url": url})
                count = result.scalar()
                return count > 0

        except SQLAlchemyError as e:
            print_with_datetime(f"Error checking news existence for URL: {e}")
            return False

    def insert_news_article(
        self,
        timestamp: datetime,
        source: str,
        title: str,
        url: str,
        content: Optional[str] = None,
        symbol: Optional[str] = None,
        sentiment_score: Optional[float] = None,
        sentiment_label: Optional[str] = None,
        entities: Optional[Dict] = None,
        receive_time: Optional[datetime] = None,
    ) -> bool:
        """
        Insert a single news article to the database with URL deduplication

        :param timestamp: Article publication time (event time)
        :param source: News source identifier
        :param title: Article headline
        :param url: Article URL (used for deduplication)
        :param content: Full article content (optional)
        :param symbol: Trading symbol if article is symbol-specific (optional)
        :param sentiment_score: Sentiment score (-1 to 1, optional)
        :param sentiment_label: Sentiment label (positive/negative/neutral, optional)
        :param entities: Extracted entities as dictionary (optional, will be stored as JSONB)
        :param receive_time: Receive time (transaction time, optional)
        :return: True if inserted successfully, False otherwise (including if duplicate)
        """
        try:
            # Check for duplicate URL
            if self.check_news_exists(url):
                if self.__verbose:
                    print_with_datetime(
                        f"Article with URL already exists: {url[:50]}..."
                    )
                return False

            # Normalize timestamps
            normalized_timestamp = self._normalize_timestamp(timestamp)
            if receive_time:
                normalized_receive_time = self._normalize_timestamp(receive_time)
                latency_seconds = int(
                    (normalized_receive_time - normalized_timestamp).total_seconds()
                )
            else:
                normalized_receive_time = ensure_utc_timezone(datetime.now())
                latency_seconds = None

            # Get forex_pairs_id if symbol is provided
            forex_pairs_id = None
            if symbol:
                symbol_upper = symbol.upper().strip()
                if len(symbol_upper) == 6:
                    base_currency = symbol_upper[:3]
                    quoted_currency = symbol_upper[3:]
                    query_pair = text("""
                        SELECT fp.id FROM forex_pairs fp
                        JOIN currency c1 ON fp.base_currency_id = c1.id
                        JOIN currency c2 ON fp.quote_currency_id = c2.id
                        WHERE c1.iso_code = :base_currency AND c2.iso_code = :quoted_currency
                        LIMIT 1
                    """)
                    with self.execute_query() as conn:
                        result = conn.execute(
                            query_pair,
                            {
                                "base_currency": base_currency,
                                "quoted_currency": quoted_currency,
                            },
                        )
                        row = result.fetchone()
                        if row:
                            forex_pairs_id = row[0]

            # Convert entities dict to JSONB string
            entities_json = json.dumps(entities) if entities else None

            query = text("""
                INSERT INTO news_articles
                (timestamp, source, title, content, url, symbol, forex_pairs_id,
                 sentiment_score, sentiment_label, entities,
                 receive_time, latency_seconds, schema_version, schema_type)
                VALUES (:timestamp, :source, :title, :content, :url, :symbol, :forex_pairs_id,
                        :sentiment_score, :sentiment_label, CAST(:entities AS jsonb),
                        :receive_time, :latency_seconds, '1.0.0', 'news')
            """)

            params = {
                "timestamp": normalized_timestamp,
                "source": source,
                "title": title[:500],  # Enforce max length
                "content": content[:10000] if content else None,  # Enforce max length
                "url": url[:1000],  # Enforce max length
                "symbol": symbol,
                "forex_pairs_id": forex_pairs_id,
                "sentiment_score": sentiment_score,
                "sentiment_label": sentiment_label,
                "entities": entities_json,
                "receive_time": normalized_receive_time,
                "latency_seconds": latency_seconds,
            }

            with self.execute_query() as conn:
                conn.execute(query, params)
            return True

        except SQLAlchemyError as e:
            print_with_datetime(f"Error inserting news article: {e}")
            return False

    def insert_news_articles_batch(self, articles: List[Dict]) -> int:
        """
        Insert multiple news articles to the database in a single transaction with URL deduplication

        :param articles: List of article dictionaries, each containing:
                        timestamp, source, title, url, content (optional), symbol (optional),
                        sentiment_score (optional), sentiment_label (optional), entities (optional)
        :return: Number of successfully inserted articles, or -1 on error
        """
        if not articles:
            return 0

        try:
            insert_count = 0
            duplicate_count = 0

            query = text("""
                INSERT INTO news_articles
                (timestamp, source, title, content, url, symbol, forex_pairs_id,
                 sentiment_score, sentiment_label, entities,
                 receive_time, latency_seconds, schema_version, schema_type)
                VALUES (:timestamp, :source, :title, :content, :url, :symbol, :forex_pairs_id,
                        :sentiment_score, :sentiment_label, :entities::jsonb,
                        :receive_time, :latency_seconds, '1.0.0', 'news')
            """)

            with self.execute_query() as conn:
                # First, get all forex_pairs_id mappings for symbols
                symbol_to_pair_id = {}
                for article in articles:
                    symbol = article.get("symbol")
                    if symbol and symbol not in symbol_to_pair_id:
                        symbol_upper = symbol.upper().strip()
                        if len(symbol_upper) == 6:
                            base_currency = symbol_upper[:3]
                            quoted_currency = symbol_upper[3:]
                            query_pair = text("""
                                SELECT fp.id FROM forex_pairs fp
                                JOIN currency c1 ON fp.base_currency_id = c1.id
                                JOIN currency c2 ON fp.quote_currency_id = c2.id
                                WHERE c1.iso_code = :base_currency AND c2.iso_code = :quoted_currency
                                LIMIT 1
                            """)
                            result = conn.execute(
                                query_pair,
                                {
                                    "base_currency": base_currency,
                                    "quoted_currency": quoted_currency,
                                },
                            )
                            row = result.fetchone()
                            if row:
                                symbol_to_pair_id[symbol] = row[0]

                # Now insert articles
                for article in articles:
                    try:
                        # Normalize timestamps
                        timestamp_val = self._normalize_timestamp(article["timestamp"])
                        receive_time = article.get("receive_time")
                        if receive_time:
                            normalized_receive_time = self._normalize_timestamp(
                                receive_time
                            )
                            latency_seconds = int(
                                (
                                    normalized_receive_time - timestamp_val
                                ).total_seconds()
                            )
                        else:
                            normalized_receive_time = ensure_utc_timezone(
                                datetime.now()
                            )
                            latency_seconds = None

                        symbol = article.get("symbol")
                        forex_pairs_id = (
                            symbol_to_pair_id.get(symbol) if symbol else None
                        )

                        # Convert entities dict to JSONB string
                        entities = article.get("entities")
                        entities_json = json.dumps(entities) if entities else None

                        params = {
                            "timestamp": timestamp_val,
                            "source": article["source"],
                            "title": article["title"][:500],
                            "content": (
                                article.get("content", "")[:10000]
                                if article.get("content")
                                else None
                            ),
                            "url": article["url"][:1000],
                            "symbol": symbol,
                            "forex_pairs_id": forex_pairs_id,
                            "sentiment_score": article.get("sentiment_score"),
                            "sentiment_label": article.get("sentiment_label"),
                            "entities": entities_json,
                            "receive_time": normalized_receive_time,
                            "latency_seconds": latency_seconds,
                        }

                        result = conn.execute(query, params)
                        if result.rowcount > 0:
                            insert_count += 1
                        else:
                            duplicate_count += 1

                    except SQLAlchemyError as e:
                        url = article.get("url", "unknown")
                        print_with_datetime(
                            f"Error inserting article {url[:50]}...: {e}"
                        )
                        continue

            if duplicate_count > 0 and self.__verbose:
                print_with_datetime(f"Skipped {duplicate_count} duplicate articles")

            with self.__metrics_lock:
                self.__metrics["batch_inserts"] += 1
                self.__metrics["batch_sizes"].append(len(articles))
                self.__metrics["insert_success"] += insert_count
                if insert_count < len(articles):
                    self.__metrics["insert_failures"] += len(articles) - insert_count

            return insert_count

        except SQLAlchemyError as e:
            print_with_datetime(f"Error in batch news article insert: {e}")
            with self.__metrics_lock:
                self.__metrics["insert_failures"] += len(articles)
            return -1

    def get_recent_news(
        self, symbol: Optional[str] = None, hours: int = 24, limit: int = 100
    ) -> List[Dict]:
        """
        Get recent news articles with optional symbol filter

        :param symbol: Filter by trading symbol (optional)
        :param hours: Number of hours to look back (default 24)
        :param limit: Maximum number of articles to return (default 100)
        :return: List of article dictionaries
        """
        try:
            conditions = ["timestamp >= NOW() - INTERVAL :hours HOUR"]
            params = {"hours": hours, "limit": limit}

            if symbol:
                conditions.append("symbol = :symbol")
                params["symbol"] = symbol.upper().strip()

            where_clause = " AND ".join(conditions)

            query = text(f"""
                SELECT timestamp, source, title, content, url, symbol,
                       sentiment_score, sentiment_label, entities,
                       receive_time, latency_seconds
                FROM news_articles
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT :limit
            """)

            with self.execute_query() as conn:
                result = conn.execute(query, params)
                rows = result.fetchall()

                articles = []
                for row in rows:
                    entities_dict = json.loads(row[8]) if row[8] else None
                    articles.append(
                        {
                            "timestamp": row[0],
                            "source": row[1],
                            "title": row[2],
                            "content": row[3],
                            "url": row[4],
                            "symbol": row[5],
                            "sentiment_score": row[6],
                            "sentiment_label": row[7],
                            "entities": entities_dict,
                            "receive_time": row[9],
                            "latency_seconds": row[10],
                        }
                    )

                return articles

        except SQLAlchemyError as e:
            print_with_datetime(f"Error querying recent news: {e}")
            return []

    def get_news_by_timeframe(
        self,
        start_time: datetime,
        end_time: datetime,
        symbol: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get news articles within a time range (point-in-time safe)

        :param start_time: Start time for query (point-in-time safe)
        :param end_time: End time for query (point-in-time safe)
        :param symbol: Filter by trading symbol (optional)
        :return: List of article dictionaries
        """
        try:
            normalized_start = self._normalize_timestamp(start_time)
            normalized_end = self._normalize_timestamp(end_time)

            conditions = [
                "timestamp >= :start_time",
                "timestamp <= :end_time",
            ]
            params = {
                "start_time": normalized_start,
                "end_time": normalized_end,
            }

            if symbol:
                conditions.append("symbol = :symbol")
                params["symbol"] = symbol.upper().strip()

            where_clause = " AND ".join(conditions)

            query = text(f"""
                SELECT timestamp, source, title, content, url, symbol,
                       sentiment_score, sentiment_label, entities,
                       receive_time, latency_seconds
                FROM news_articles
                WHERE {where_clause}
                ORDER BY timestamp ASC
            """)

            with self.execute_query() as conn:
                result = conn.execute(query, params)
                rows = result.fetchall()

                articles = []
                for row in rows:
                    entities_dict = json.loads(row[8]) if row[8] else None
                    articles.append(
                        {
                            "timestamp": row[0],
                            "source": row[1],
                            "title": row[2],
                            "content": row[3],
                            "url": row[4],
                            "symbol": row[5],
                            "sentiment_score": row[6],
                            "sentiment_label": row[7],
                            "entities": entities_dict,
                            "receive_time": row[9],
                            "latency_seconds": row[10],
                        }
                    )

                return articles

        except SQLAlchemyError as e:
            print_with_datetime(f"Error querying news by timeframe: {e}")
            return []

    def get_upcoming_events(self, hours_ahead: int = 24) -> List[Dict]:
        """
        Get upcoming economic events

        :param hours_ahead: Number of hours to look ahead
        :return: List of dictionaries with event information
        """
        try:
            query = """
                SELECT datetime, event, impact, country, previous, consensus, actual
                FROM economic_calendar
                WHERE datetime >= NOW()
                AND datetime <= NOW() + INTERVAL :hours_ahead HOUR
                ORDER BY datetime ASC
            """

            params = {"hours_ahead": hours_ahead}
            results = self.execute_with_result(query, params)

            events = []
            for row in results:
                events.append(
                    {
                        "datetime": row[0],
                        "event": row[1],
                        "impact": row[2],
                        "country": row[3],
                        "previous": row[4],
                        "consensus": row[5],
                        "actual": row[6],
                    }
                )

            return events

        except SQLAlchemyError as e:
            print_with_datetime(f"Error retrieving upcoming events: {e}")
            return []

    def insert_feature_distribution(
        self,
        feature_name: str,
        symbol: str,
        timestamp: datetime,
        mean: float,
        std: float,
        min_value: float,
        max_value: float,
        percentile_25: float,
        percentile_50: float,
        percentile_75: float,
        percentile_95: float,
        percentile_99: float,
        sample_size: int,
    ) -> bool:
        """
        Insert feature distribution statistics

        :param feature_name: Name of the feature
        :param symbol: Trading symbol
        :param timestamp: Timestamp for the distribution
        :param mean: Mean value
        :param std: Standard deviation
        :param min_value: Minimum value
        :param max_value: Maximum value
        :param percentile_25: 25th percentile
        :param percentile_50: 50th percentile (median)
        :param percentile_75: 75th percentile
        :param percentile_95: 95th percentile
        :param percentile_99: 99th percentile
        :param sample_size: Number of samples
        :return: True if successful, False otherwise
        """
        try:
            normalized_timestamp = self._normalize_timestamp(timestamp)

            query = text("""
                INSERT INTO feature_distributions
                (feature_name, symbol, timestamp, mean, std, min_value, max_value,
                 percentile_25, percentile_50, percentile_75, percentile_95, percentile_99, sample_size)
                VALUES (:feature_name, :symbol, :timestamp, :mean, :std, :min_value, :max_value,
                        :percentile_25, :percentile_50, :percentile_75, :percentile_95, :percentile_99, :sample_size)
                ON CONFLICT DO NOTHING
            """)

            params = {
                "feature_name": feature_name,
                "symbol": symbol.upper().strip(),
                "timestamp": normalized_timestamp,
                "mean": mean,
                "std": std,
                "min_value": min_value,
                "max_value": max_value,
                "percentile_25": percentile_25,
                "percentile_50": percentile_50,
                "percentile_75": percentile_75,
                "percentile_95": percentile_95,
                "percentile_99": percentile_99,
                "sample_size": sample_size,
            }

            with self.execute_query() as conn:
                conn.execute(query, params)
            return True

        except SQLAlchemyError as e:
            print_with_datetime(f"Error inserting feature distribution: {e}")
            return False

    def get_feature_distributions(
        self,
        feature_name: str,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict]:
        """
        Get feature distributions for a time range

        :param feature_name: Feature name
        :param symbol: Trading symbol
        :param start_time: Start time
        :param end_time: End time
        :return: List of distribution dictionaries
        """
        try:
            normalized_start = self._normalize_timestamp(start_time)
            normalized_end = self._normalize_timestamp(end_time)

            query = text("""
                SELECT feature_name, symbol, timestamp, mean, std, min_value, max_value,
                       percentile_25, percentile_50, percentile_75, percentile_95, percentile_99, sample_size
                FROM feature_distributions
                WHERE feature_name = :feature_name
                  AND symbol = :symbol
                  AND timestamp >= :start_time
                  AND timestamp <= :end_time
                ORDER BY timestamp ASC
            """)

            params = {
                "feature_name": feature_name,
                "symbol": symbol.upper().strip(),
                "start_time": normalized_start,
                "end_time": normalized_end,
            }

            with self.execute_query() as conn:
                result = conn.execute(query, params)
                rows = result.fetchall()

                distributions = []
                for row in rows:
                    distributions.append(
                        {
                            "feature_name": row[0],
                            "symbol": row[1],
                            "timestamp": row[2],
                            "mean": float(row[3]) if row[3] is not None else None,
                            "std": float(row[4]) if row[4] is not None else None,
                            "min_value": float(row[5]) if row[5] is not None else None,
                            "max_value": float(row[6]) if row[6] is not None else None,
                            "percentile_25": (
                                float(row[7]) if row[7] is not None else None
                            ),
                            "percentile_50": (
                                float(row[8]) if row[8] is not None else None
                            ),
                            "percentile_75": (
                                float(row[9]) if row[9] is not None else None
                            ),
                            "percentile_95": (
                                float(row[10]) if row[10] is not None else None
                            ),
                            "percentile_99": (
                                float(row[11]) if row[11] is not None else None
                            ),
                            "sample_size": row[12],
                        }
                    )

                return distributions

        except SQLAlchemyError as e:
            print_with_datetime(f"Error querying feature distributions: {e}")
            return []

    def insert_drift_detection(
        self,
        feature_name: str,
        symbol: str,
        detection_time: datetime,
        psi_score: Optional[float],
        ks_statistic: Optional[float],
        ks_pvalue: Optional[float],
        drift_severity: str,
        drift_detected: bool,
        baseline_window_start: datetime,
        baseline_window_end: datetime,
        current_window_start: datetime,
        current_window_end: datetime,
        baseline_size: int,
        current_size: int,
        baseline_mean: float,
        baseline_std: float,
        current_mean: float,
        current_std: float,
        mean_change_pct: float,
        std_change_pct: float,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """
        Insert drift detection result

        :param feature_name: Feature name
        :param symbol: Trading symbol
        :param detection_time: When detection was performed
        :param psi_score: PSI score
        :param ks_statistic: KS statistic
        :param ks_pvalue: KS p-value
        :param drift_severity: Drift severity ('none', 'minor', 'major')
        :param drift_detected: Whether drift was detected
        :param baseline_window_start: Baseline window start
        :param baseline_window_end: Baseline window end
        :param current_window_start: Current window start
        :param current_window_end: Current window end
        :param baseline_size: Baseline sample size
        :param current_size: Current sample size
        :param baseline_mean: Baseline mean
        :param baseline_std: Baseline std
        :param current_mean: Current mean
        :param current_std: Current std
        :param mean_change_pct: Mean change percentage
        :param std_change_pct: Std change percentage
        :param metadata: Additional metadata
        :return: True if successful, False otherwise
        """
        try:
            normalized_detection_time = self._normalize_timestamp(detection_time)
            normalized_baseline_start = self._normalize_timestamp(baseline_window_start)
            normalized_baseline_end = self._normalize_timestamp(baseline_window_end)
            normalized_current_start = self._normalize_timestamp(current_window_start)
            normalized_current_end = self._normalize_timestamp(current_window_end)

            metadata_json = json.dumps(metadata) if metadata else None

            query = text("""
                INSERT INTO drift_detections
                (feature_name, symbol, detection_time, psi_score, ks_statistic, ks_pvalue,
                 drift_severity, drift_detected, baseline_window_start, baseline_window_end,
                 current_window_start, current_window_end, baseline_size, current_size,
                 baseline_mean, baseline_std, current_mean, current_std,
                 mean_change_pct, std_change_pct, metadata)
                VALUES (:feature_name, :symbol, :detection_time, :psi_score, :ks_statistic, :ks_pvalue,
                        :drift_severity, :drift_detected, :baseline_window_start, :baseline_window_end,
                        :current_window_start, :current_window_end, :baseline_size, :current_size,
                        :baseline_mean, :baseline_std, :current_mean, :current_std,
                        :mean_change_pct, :std_change_pct, :metadata::jsonb)
            """)

            params = {
                "feature_name": feature_name,
                "symbol": symbol.upper().strip(),
                "detection_time": normalized_detection_time,
                "psi_score": psi_score,
                "ks_statistic": ks_statistic,
                "ks_pvalue": ks_pvalue,
                "drift_severity": drift_severity,
                "drift_detected": drift_detected,
                "baseline_window_start": normalized_baseline_start,
                "baseline_window_end": normalized_baseline_end,
                "current_window_start": normalized_current_start,
                "current_window_end": normalized_current_end,
                "baseline_size": baseline_size,
                "current_size": current_size,
                "baseline_mean": baseline_mean,
                "baseline_std": baseline_std,
                "current_mean": current_mean,
                "current_std": current_std,
                "mean_change_pct": mean_change_pct,
                "std_change_pct": std_change_pct,
                "metadata": metadata_json,
            }

            with self.execute_query() as conn:
                conn.execute(query, params)
            return True

        except SQLAlchemyError as e:
            print_with_datetime(f"Error inserting drift detection: {e}")
            return False
