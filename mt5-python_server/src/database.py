"""
Database interaction from server to MariaDB Docker Container
"""

import mariadb
from dotenv import dotenv_values


class Database:
    """
    Database class
    """

    def __init__(self):
        try:
            config = dotenv_values("../../.env")
            self.__conn = mariadb.connect(
                user=config['DB_USERNAME'],
                password=config['DB_PASSWORD'],
                host=config['DB_HOST'],
                port=int(config['DB_PORT']),
                database=config['DB_DATABASE']
            )
            self.__conn.autocommit = True
            self.__cursor = self.__conn.cursor()
        except mariadb.Error as e:
            print(f"Error connecting to MariaDB Platform: {e}")
            raise e

    def insert_forex_tick(self, tick: str) -> bool:
        """
        Insert a tick to the database
        :param tick: tick [symbol, datetime, ask, bid]
        :return True if insert is done
        """
        tick_info = tick.split(",")
        if len(tick_info) == 4:
            symbol, date_time, ask, bid = tick_info

            try:
                self.__cursor.callproc(
                    'insert_tick_forex',
                    (date_time, ask, bid, symbol[:3], symbol[3:]))
                return True
            except mariadb.Error as e:
                print(f"Error: {e}")
                return False
        else:
            print("Error wrong format of tick: 'symbol,datetime,ask,bid'")
            return False

    def __del__(self):
        self.__conn.close()
