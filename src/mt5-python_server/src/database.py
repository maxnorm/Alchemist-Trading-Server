"""
Database interaction from server to MariaDB Docker Container
"""

import os
import time
import threading
import uuid
import mariadb
import json
from datetime import datetime
from typing import List, Dict
from utils.time_utils import print_with_datetime, normalize_to_utc, ensure_utc_timezone


# Helper function for debug logging
def _write_debug_log(
    session_id, run_id, hypothesis_id, location, message, data, timestamp=None
):
    """Write debug log entry"""
    try:
        if timestamp is None:
            from utils.time_utils import get_utc_time

            timestamp = int(get_utc_time().timestamp() * 1000)
        # Use absolute path from system reminder - calculate dynamically
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(current_file_dir))
        )
        log_path = os.path.join(project_root, ".cursor", "debug.log")
        # Ensure directory exists
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "sessionId": session_id,
                        "runId": run_id,
                        "hypothesisId": hypothesis_id,
                        "location": location,
                        "message": message,
                        "data": data,
                        "timestamp": timestamp,
                    }
                )
                + "\n"
            )
    except Exception as e:
        # Log to stderr for debugging instrumentation issues
        import sys

        sys.stderr.write(f"Debug log write failed: {e}\n")


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

        # Pool name - use shared name or unique if specified
        self.__pool_name = os.getenv("DB_POOL_NAME", "server_pool")

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

        # Initialize connection pool and lock
        self.__connection_lock = threading.Lock()
        self.__pool = self.__create_pool()

    def __create_pool(self, retries=None, delay=None):
        """
        Create the database connection pool with exponential backoff retry
        Uses unique pool name if default pool already exists

        :param retries: Number of retry attempts (defaults to self.__max_retries)
        :param delay: Initial delay in seconds (defaults to self.__retry_delay)
        :return: MariaDB connection pool
        """
        if retries is None:
            retries = self.__max_retries
        if delay is None:
            delay = self.__retry_delay

        pool_name = self.__pool_name
        use_unique_name = False

        for attempt in range(retries):
            try:
                # If previous attempt failed due to pool existing, use unique name
                if use_unique_name:
                    pool_name = f"{self.__pool_name}_{uuid.uuid4().hex[:8]}"

                pool = mariadb.ConnectionPool(
                    pool_name=pool_name,
                    pool_size=20,
                    user=self.__user,
                    password=self.__password,
                    host=self.__host,
                    port=self.__port,
                    database=self.__db,
                )
                if attempt > 0:
                    print_with_datetime(
                        f"Successfully created connection pool after {attempt} retries"
                    )
                if use_unique_name:
                    print_with_datetime(f"Using unique pool name: {pool_name}")
                return pool
            except mariadb.ProgrammingError as e:
                # Pool already exists - use unique name on next attempt
                if "already exists" in str(e) and not use_unique_name:
                    print_with_datetime(
                        f"Pool '{pool_name}' already exists, using unique pool name"
                    )
                    use_unique_name = True
                    # Don't sleep, retry immediately with unique name
                    continue
                else:
                    # Other programming error or already using unique name
                    raise e
            except mariadb.Error as e:
                if attempt < retries - 1:
                    wait_time = delay * (2**attempt)  # Exponential backoff
                    print_with_datetime(
                        f"Error creating connection pool (attempt {attempt + 1}/{retries}): {e}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    with self.__metrics_lock:
                        self.__metrics["connection_retries"] += 1
                    time.sleep(wait_time)
                else:
                    with self.__metrics_lock:
                        self.__metrics["connection_failures"] += 1
                    print_with_datetime(
                        f"Failed to create connection pool after {retries} attempts: {e}"
                    )
                    raise e

    def __get_connection(self, retries=3):
        """
        Get a connection from the pool in a thread-safe manner with retry logic

        :param retries: Number of retry attempts for transient failures
        :return: MariaDB connection
        """
        for attempt in range(retries):
            try:
                with self.__connection_lock:
                    return self.__pool.get_connection()
            except mariadb.Error as e:
                if attempt < retries - 1:
                    # Check if it's a transient error (connection lost, timeout, etc.)
                    error_code = getattr(e, "errno", None)
                    transient_errors = (
                        2006,
                        2013,
                        2003,
                        2002,
                    )  # Connection lost, timeout, can't connect

                    if error_code in transient_errors:
                        wait_time = 0.5 * (2**attempt)  # Short exponential backoff
                        print_with_datetime(
                            f"Transient connection error (attempt {attempt + 1}/{retries}): {e}. "
                            f"Retrying in {wait_time:.1f}s..."
                        )
                        with self.__metrics_lock:
                            self.__metrics["connection_retries"] += 1
                        time.sleep(wait_time)
                        continue

                print_with_datetime(f"Error getting connection from pool: {e}")
                with self.__metrics_lock:
                    self.__metrics["connection_failures"] += 1
                raise e

    def get_connection(self, retries=3):
        """
        Public method to get a database connection from the pool.

        :param retries: Number of retry attempts for transient failures
        :return: MariaDB connection
        """
        return self.__get_connection(retries)

    def check_connection_health(self):
        """
        Check if the database connection is healthy

        :return: True if healthy, False otherwise
        """
        try:
            conn = self.__get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            conn.close()
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
        conn = None
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

            conn = self.__get_connection()
            cursor = conn.cursor()

            # Use direct INSERT to support bitemporal columns
            # Get pair_id first
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

            cursor.execute(
                """
                INSERT INTO ticks_forex (
                    datetime, ask, bid, forex_pairs_id,
                    receive_time, latency_seconds, is_stale,
                    stale_age_seconds, timestamp_source,
                    schema_version, schema_type
                )
                SELECT ?, ?, ?, fp.id, ?, ?, ?, ?, ?, ?, ?
                FROM currency c1
                CROSS JOIN currency c2
                INNER JOIN forex_pairs fp ON fp.base_currency_id = c1.id AND fp.quote_currency_id = c2.id
                WHERE c1.iso_code = ? AND c2.iso_code = ?
                LIMIT 1
            """,
                (
                    normalized_date_time,
                    ask,
                    bid,
                    normalized_receive_time,
                    latency_seconds,
                    is_stale,
                    stale_age_seconds,
                    timestamp_source,
                    schema_version,
                    schema_type,
                    base_currency,
                    quoted_currency,
                ),
            )

            conn.commit()

            # Check if a row was actually inserted
            if cursor.rowcount == 0:
                # No row inserted - currency pair not found or lookup failed
                print_with_datetime(
                    f"WARNING: Currency pair '{symbol}' (normalized: '{symbol_upper}', "
                    f"base: '{base_currency}', quote: '{quoted_currency}') not found in "
                    f"database - tick not inserted. Please verify the symbol exists in "
                    f"the forex_pairs table."
                )
                cursor.close()
                with self.__metrics_lock:
                    self.__metrics["insert_failures"] += 1
                return False

            cursor.close()
            with self.__metrics_lock:
                self.__metrics["insert_success"] += 1
            return True
        except mariadb.Error as e:
            print_with_datetime(f"Error inserting forex tick: {e}")
            with self.__metrics_lock:
                self.__metrics["insert_failures"] += 1
            return False
        finally:
            if conn:
                conn.close()  # Return connection to pool

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
        conn = None
        try:
            # Normalize timestamps to UTC
            normalized_date_time = self._normalize_timestamp(date_time)
            normalized_receive_time = None
            if receive_time is not None:
                normalized_receive_time = self._normalize_timestamp(receive_time)

            # Categorize rejection reason
            rejection_category = self._categorize_rejection_reason(rejection_reason)

            conn = self.__get_connection()
            cursor = conn.cursor()

            # Insert into quarantine_ticks table
            cursor.execute(
                """
                INSERT INTO quarantine_ticks
                (symbol, datetime, receive_time, bid, ask, rejection_reason, rejection_category)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    symbol,
                    normalized_date_time,
                    normalized_receive_time,
                    bid,
                    ask,
                    rejection_reason,
                    rejection_category,
                ),
            )

            conn.commit()
            cursor.close()

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
        except mariadb.Error as e:
            print_with_datetime(f"Error inserting quarantine tick: {e}")
            with self.__metrics_lock:
                self.__metrics["quarantine_insert_failures"] += 1
            return False
        except Exception as e:
            print_with_datetime(f"Unexpected error inserting quarantine tick: {e}")
            with self.__metrics_lock:
                self.__metrics["quarantine_insert_failures"] += 1
            return False
        finally:
            if conn:
                conn.close()  # Return connection to pool

    def insert_forex_ticks_batch(self, ticks):
        """
        Insert multiple ticks to the database in a single transaction using bulk insert

        :param ticks: List of tuples, each tuple contains (symbol, date_time, ask, bid)
        :return: Number of successfully inserted ticks, or -1 on error
        """
        # #region agent log
        _write_debug_log(
            "debug-session",
            "run1",
            "F",
            "database.py:269",
            "insert_forex_ticks_batch called",
            {"tick_count": len(ticks) if ticks else 0},
        )
        # #endregion
        if not ticks:
            return 0

        conn = None
        try:
            conn = self.__get_connection()
            # #region agent log
            _write_debug_log(
                "debug-session",
                "run1",
                "F",
                "database.py:281",
                "Database connection obtained",
                {"has_connection": conn is not None},
            )
            # #endregion
            cursor = conn.cursor()

            # Build bulk INSERT statement with VALUES clause
            # First, we need to resolve currency pairs for all ticks
            # We'll use a more efficient approach: bulk insert with subquery for pair_id

            # Group ticks by currency pair to optimize lookups
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

            for (
                date_time,
                ask,
                bid,
                base_currency,
                quoted_currency,
                symbol_upper,
            ) in tick_data:
                try:
                    # Use direct INSERT with subquery to get pair_id
                    # This way we can check if the pair exists and get feedback
                    cursor.execute(
                        """
                        INSERT INTO ticks_forex (datetime, ask, bid, forex_pairs_id)
                        SELECT ?, ?, ?, fp.id
                        FROM currency c1
                        CROSS JOIN currency c2
                        INNER JOIN forex_pairs fp ON fp.base_currency_id = c1.id AND fp.quote_currency_id = c2.id
                        WHERE c1.iso_code = ? AND c2.iso_code = ?
                        LIMIT 1
                    """,
                        (date_time, ask, bid, base_currency, quoted_currency),
                    )

                    # Check if a row was actually inserted
                    # #region agent log
                    _write_debug_log(
                        "debug-session",
                        "run1",
                        "F",
                        "database.py:319",
                        "Insert attempt result",
                        {"symbol": symbol_upper, "rowcount": cursor.rowcount},
                    )
                    # #endregion
                    if cursor.rowcount > 0:
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
                except mariadb.Error as e:
                    symbol = base_currency + quoted_currency
                    failed_symbols.add(symbol)
                    # #region agent log
                    _write_debug_log(
                        "debug-session",
                        "run1",
                        "F",
                        "database.py:357",
                        "Database insert error",
                        {"symbol": symbol, "error": str(e)},
                    )
                    # #endregion
                    print_with_datetime(f"Error inserting tick for {symbol}: {e}")
                    continue

            if failed_symbols:
                print_with_datetime(
                    f"WARNING: Failed to insert ticks for {len(failed_symbols)} "
                    f"symbol(s): {', '.join(sorted(failed_symbols))}. "
                    f"These currency pairs may not exist in the forex_pairs table."
                )

            conn.commit()
            # #region agent log
            _write_debug_log(
                "debug-session",
                "run1",
                "G",
                "database.py:341",
                "Transaction committed",
                {
                    "insert_count": insert_count,
                    "total_ticks": len(ticks),
                    "failed_symbols": list(failed_symbols),
                },
            )
            # #endregion
            cursor.close()

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
            # #region agent log
            _write_debug_log(
                "debug-session",
                "run1",
                "F",
                "database.py:400",
                "Database insert exception",
                {"error": str(e), "error_type": type(e).__name__},
            )
            # #endregion
        except mariadb.Error as e:
            print_with_datetime(f"Error in batch insert: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            with self.__metrics_lock:
                self.__metrics["insert_failures"] += len(ticks)
            return -1
        finally:
            if conn:
                conn.close()  # Return connection to pool

    def insert_economic_calendar_data(self, data):
        """
        Insert multiple data from the economic calendar

        :param data: Pandas Dataframe
        """
        conn = None
        try:
            conn = self.__get_connection()
            cursor = conn.cursor()

            for _, row in data.iterrows():
                # Normalize timestamp to EST before storing
                date = self._normalize_timestamp(row["Date"])
                country = row["Country"]
                event = row["Event"]
                impact = row["Impact"]
                previous = row["Previous"] if row["Previous"] != "" else None
                consensus = row["Consensus"] if row["Consensus"] != "" else None
                actual = row["Actual"] if row["Actual"] != "" else None
                cursor.callproc(
                    "insert_economic_calendar_data",
                    (date, country, event, impact, previous, consensus, actual),
                )
            conn.commit()

            cursor.close()
            return True
        except mariadb.Error as e:
            print_with_datetime(f"Error inserting economic calendar data: {e}")
            return False
        finally:
            if conn:
                conn.close()  # Return connection to pool

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
        conn = None
        try:
            # Extract base and quote currencies from symbol
            base_currency = symbol[:3]
            quote_currency = symbol[3:]

            conn = self.__get_connection()
            cursor = conn.cursor()

            # Determine which timestamp column to use for filtering and ordering
            if query_by == "receive_time":
                # Query by receive_time (transaction time) for point-in-time training
                time_column = "COALESCE(tf.receive_time, tf.datetime)"  # Fallback to datetime if receive_time is NULL
                order_by = "COALESCE(tf.receive_time, tf.datetime)"
            else:
                # Query by event_time (datetime) for pattern learning
                time_column = "tf.datetime"
                order_by = "tf.datetime"

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
                WHERE c1.iso_code = %s AND c2.iso_code = %s
                AND {time_column} >= DATE_SUB(NOW(), INTERVAL %s HOUR)
                ORDER BY {order_by} ASC
                LIMIT %s
            """

            cursor.execute(query, (base_currency, quote_currency, hours, limit))
            results = cursor.fetchall()

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

            cursor.close()
            return ticks

        except mariadb.Error as e:
            print_with_datetime(f"Error retrieving recent ticks for {symbol}: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_upcoming_events(self, hours_ahead: int = 24) -> List[Dict]:
        """
        Get upcoming economic events

        :param hours_ahead: Number of hours to look ahead
        :return: List of dictionaries with event information
        """
        conn = None
        try:
            conn = self.__get_connection()
            cursor = conn.cursor()

            query = """
                SELECT datetime, event, impact, country, previous, consensus, actual
                FROM economic_calendar
                WHERE datetime >= NOW()
                AND datetime <= DATE_ADD(NOW(), INTERVAL %s HOUR)
                ORDER BY datetime ASC
            """

            cursor.execute(query, (hours_ahead,))
            results = cursor.fetchall()

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

            cursor.close()
            return events

        except mariadb.Error as e:
            print_with_datetime(f"Error retrieving upcoming events: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def __create_conn(self):
        """
        Create the database connection

        :return: MariaDB connection
        """
        try:
            conn = mariadb.connect(
                user=self.__user,
                password=self.__password,
                host=self.__host,
                port=self.__port,
                database=self.__db,
            )
            return conn
        except mariadb.Error as e:
            print_with_datetime(f"Error connecting to MariaDB Platform: {e}")
            raise e
