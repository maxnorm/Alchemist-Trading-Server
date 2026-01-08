"""
Database interaction from server to PostgreSQL Docker Container
"""

import os
import time
import threading
from contextlib import contextmanager
from typing import List, Dict, Tuple, Optional, Any
import json
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError
from utils.time_utils import print_with_datetime, normalize_to_utc, ensure_utc_timezone


class Database:
    """
    Database class
    """

    def __init__(self):
        self.__user = os.getenv("DB_USER")
        self.__password = os.getenv("DB_PASSWORD")
        self.__host = os.getenv("DB_HOST")
        self.__port = int(os.getenv("DB_PORT"))
        self.__db = os.getenv("DB_NAME")

        # Retry configuration
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

        # Initialize SQLAlchemy engine with connection pooling
        self.engine = self.__create_engine()

    def __create_engine(self, retries=None, delay=None):
        """
        Create SQLAlchemy engine with connection pooling and exponential backoff retry

        :param retries: Number of retry attempts (defaults to self.__max_retries)
        :param delay: Initial delay in seconds (defaults to self.__retry_delay)
        :return: SQLAlchemy Engine
        """
        if retries is None:
            retries = self.__max_retries
        if delay is None:
            delay = self.__retry_delay

        # Build PostgreSQL connection URL
        database_url = f"postgresql+psycopg2://{self.__user}:{self.__password}@{self.__host}:{self.__port}/{self.__db}"

        for attempt in range(retries):
            try:
                engine = create_engine(
                    database_url,
                    poolclass=QueuePool,
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True,  # Verify connections before using
                    pool_recycle=3600,  # Recycle connections after 1 hour
                    connect_args={
                        "connect_timeout": 10,
                        "options": "-c statement_timeout=30000",
                    },
                    echo=False,
                )
                if attempt > 0:
                    print_with_datetime(
                        f"Successfully created SQLAlchemy engine after {attempt} retries"
                    )
                return engine
            except Exception as e:
                if attempt < retries - 1:
                    wait_time = delay * (2**attempt)  # Exponential backoff
                    print_with_datetime(
                        f"Error creating SQLAlchemy engine (attempt {attempt + 1}/{retries}): {e}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    with self.__metrics_lock:
                        self.__metrics["connection_retries"] += 1
                    time.sleep(wait_time)
                else:
                    with self.__metrics_lock:
                        self.__metrics["connection_failures"] += 1
                    print_with_datetime(
                        f"Failed to create SQLAlchemy engine after {retries} attempts: {e}"
                    )
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
        with self.engine.connect() as conn:
            trans = conn.begin()
            try:
                yield conn
                trans.commit()
            except Exception:
                trans.rollback()
                raise

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

        except Exception as e:
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
