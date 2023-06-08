"""
Database interaction from server to MariaDB Docker Container
"""
import datetime

import mariadb
from dotenv import dotenv_values
from utils import print_with_datetime


class Database:
    """
    Database class
    """

    def __init__(self):
        config = dotenv_values("../../.env")
        self.__user = config['DB_USERNAME']
        self.__password = config['DB_PASSWORD']
        self.__host = config['DB_HOST']
        self.__port = int(config['DB_PORT'])
        self.__db = config['DB_DATABASE']

    def insert_forex_tick(self, tick):
        """
        Insert a tick to the database
        
        :param tick: [symbol, datetime, ask, bid]
        :return: True if insert is done
        """

        tick_info = tick.split("|")
        if len(tick_info) == 4:
            symbol, date_time, ask, bid = tick_info

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
        else:
            print_with_datetime(f"Error wrong format of tick: 'symbol|datetime|ask|bid' | {tick_info}")
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
