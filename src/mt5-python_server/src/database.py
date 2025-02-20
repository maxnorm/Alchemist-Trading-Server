"""
Database interaction from server to MariaDB Docker Container
"""
import os
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

    def __create_pool(self):
        """
        Create the database connection pool

        :return: MariaDB connection pool
        """
        try:
            return mariadb.ConnectionPool(
                pool_name="server_pool",
                pool_size=20,
                user=self.__user,
                password=self.__password,
                host=self.__host,
                port=self.__port,
                database=self.__db
            )
        except mariadb.Error as e:
            print_with_datetime(f"Error creating connection pool: {e}")
            raise e
         
    def __get_connection(self):
        """
        Get a connection from the pool in a thread-safe manner

        :return: MariaDB connection
        """
        with self.__connection_lock:
            try:
                return self.__pool.get_connection()
            except mariadb.Error as e:
                print_with_datetime(f"Error getting connection from pool: {e}")
                raise e


    def insert_forex_tick(self, symbol, date_time, ask, bid):
        """
        Insert a tick to the database

        :param symbol: Symbol of the tick
        :param date_time: Datetime of the tick
        :param ask: Ask price
        :param bid: Bid price
        :return: True if insert is done
        """

        conn = self.__create_conn()
        cursor = conn.cursor()

        try:
            cursor.callproc(
                'insert_tick_forex',
                (date_time, ask, bid, symbol[:3], symbol[3:]))
            conn.commit()

            cursor.close()
            conn.close()

            return True
        except mariadb.Error as e:
            print(f"Error: {e}")
            return False

    def insert_economic_calendar_data(self, data):
        """
        Insert multiple data from the economic calendar

        :param data: Pandas Dataframe
        """
        conn = self.__create_conn()
        cursor = conn.cursor()

        try:
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
            conn.close()

            return True
        except mariadb.Error as e:
            print_with_datetime(f"Error: {e}")
            return False

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
