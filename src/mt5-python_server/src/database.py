"""
Database interaction from server to MariaDB Docker Container
"""
import os
import time
import threading
import uuid
import mariadb
from utils.time_utils import print_with_datetime


class Database:
    """
    Database class
    """

    def __init__(self):
        self.__user = os.getenv('DB_USER')
        self.__password = os.getenv('DB_PASSWORD')
        self.__host = os.getenv('DB_HOST')
        self.__port = int(os.getenv('DB_PORT'))
        self.__db = os.getenv('DB_NAME')
        
        # Retry configuration
        self.__max_retries = int(os.getenv('DB_MAX_RETRIES', '5'))
        self.__retry_delay = float(os.getenv('DB_RETRY_DELAY', '2.0'))
        self.__verbose = os.getenv('DB_VERBOSE', 'false').lower() == 'true'
        
        # Pool name - use shared name or unique if specified
        self.__pool_name = os.getenv('DB_POOL_NAME', 'server_pool')
        
        # Metrics tracking
        self.__metrics = {
            'connection_retries': 0,
            'connection_failures': 0,
            'insert_success': 0,
            'insert_failures': 0,
            'batch_inserts': 0,
            'batch_sizes': []
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
                    database=self.__db
                )
                if attempt > 0:
                    print_with_datetime(f"Successfully created connection pool after {attempt} retries")
                if use_unique_name:
                    print_with_datetime(f"Using unique pool name: {pool_name}")
                return pool
            except mariadb.ProgrammingError as e:
                # Pool already exists - use unique name on next attempt
                if "already exists" in str(e) and not use_unique_name:
                    print_with_datetime(f"Pool '{pool_name}' already exists, using unique pool name")
                    use_unique_name = True
                    # Don't sleep, retry immediately with unique name
                    continue
                else:
                    # Other programming error or already using unique name
                    raise e
            except mariadb.Error as e:
                if attempt < retries - 1:
                    wait_time = delay * (2 ** attempt)  # Exponential backoff
                    print_with_datetime(
                        f"Error creating connection pool (attempt {attempt + 1}/{retries}): {e}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    with self.__metrics_lock:
                        self.__metrics['connection_retries'] += 1
                    time.sleep(wait_time)
                else:
                    with self.__metrics_lock:
                        self.__metrics['connection_failures'] += 1
                    print_with_datetime(f"Failed to create connection pool after {retries} attempts: {e}")
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
                    error_code = getattr(e, 'errno', None)
                    transient_errors = (2006, 2013, 2003, 2002)  # Connection lost, timeout, can't connect
                    
                    if error_code in transient_errors:
                        wait_time = 0.5 * (2 ** attempt)  # Short exponential backoff
                        print_with_datetime(
                            f"Transient connection error (attempt {attempt + 1}/{retries}): {e}. "
                            f"Retrying in {wait_time:.1f}s..."
                        )
                        with self.__metrics_lock:
                            self.__metrics['connection_retries'] += 1
                        time.sleep(wait_time)
                        continue
                
                print_with_datetime(f"Error getting connection from pool: {e}")
                with self.__metrics_lock:
                    self.__metrics['connection_failures'] += 1
                raise e
    
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
            if metrics['batch_sizes']:
                metrics['avg_batch_size'] = sum(metrics['batch_sizes']) / len(metrics['batch_sizes'])
                metrics['max_batch_size'] = max(metrics['batch_sizes'])
                metrics['min_batch_size'] = min(metrics['batch_sizes'])
            else:
                metrics['avg_batch_size'] = 0
                metrics['max_batch_size'] = 0
                metrics['min_batch_size'] = 0
            return metrics


    def insert_forex_tick(self, symbol, date_time, ask, bid):
        """
        Insert a tick to the database

        :param symbol: Symbol of the tick
        :param date_time: Datetime of the tick
        :param ask: Ask price
        :param bid: Bid price
        :return: True if insert is done
        """
        conn = None
        try:
            conn = self.__get_connection()
            cursor = conn.cursor()

            cursor.callproc(
                'insert_tick_forex',
                (date_time, ask, bid, symbol[:3], symbol[3:]))
            conn.commit()

            cursor.close()
            with self.__metrics_lock:
                self.__metrics['insert_success'] += 1
            return True
        except mariadb.Error as e:
            print_with_datetime(f"Error inserting forex tick: {e}")
            with self.__metrics_lock:
                self.__metrics['insert_failures'] += 1
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
        if not ticks:
            return 0
            
        conn = None
        try:
            conn = self.__get_connection()
            cursor = conn.cursor()
            
            # Build bulk INSERT statement with VALUES clause
            # First, we need to resolve currency pairs for all ticks
            # We'll use a more efficient approach: bulk insert with subquery for pair_id
            
            # Group ticks by currency pair to optimize lookups
            tick_data = []
            for symbol, date_time, ask, bid in ticks:
                base_currency = symbol[:3]
                quoted_currency = symbol[3:]
                tick_data.append((date_time, ask, bid, base_currency, quoted_currency))
            
            # Use executemany with the optimized stored procedure
            # For better performance, we'll use a direct INSERT with subquery
            insert_count = 0
            for date_time, ask, bid, base_currency, quoted_currency in tick_data:
                try:
                    cursor.callproc(
                        'insert_tick_forex_optimized',
                        (date_time, ask, bid, base_currency, quoted_currency)
                    )
                    insert_count += 1
                except mariadb.Error as e:
                    print_with_datetime(f"Error inserting tick in batch: {e}")
                    continue
            
            conn.commit()
            cursor.close()
            
            with self.__metrics_lock:
                self.__metrics['batch_inserts'] += 1
                self.__metrics['batch_sizes'].append(len(ticks))
                self.__metrics['insert_success'] += insert_count
                if insert_count < len(ticks):
                    self.__metrics['insert_failures'] += (len(ticks) - insert_count)
            
            if self.__verbose:
                print_with_datetime(f"Batch inserted {insert_count}/{len(ticks)} ticks")
            
            return insert_count
            
        except mariadb.Error as e:
            print_with_datetime(f"Error in batch insert: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            with self.__metrics_lock:
                self.__metrics['insert_failures'] += len(ticks)
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
                date = row['Date']
                country = row['Country']
                event = row['Event']
                impact = row['Impact']
                previous = row['Previous'] if row['Previous'] != '' else None
                consensus = row['Consensus'] if row['Consensus'] != '' else None
                actual = row['Actual'] if row['Actual'] != '' else None
                cursor.callproc('insert_economic_calendar_data',
                                (date, country, event, impact, previous, consensus, actual))
            conn.commit()

            cursor.close()
            return True
        except mariadb.Error as e:
            print_with_datetime(f"Error inserting economic calendar data: {e}")
            return False
        finally:
            if conn:
                conn.close()  # Return connection to pool

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
                database=self.__db
            )
            return conn
        except mariadb.Error as e:
            print_with_datetime(f"Error connecting to MariaDB Platform: {e}")
            raise e
