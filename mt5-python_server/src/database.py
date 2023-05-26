"""
Database interaction from server to MariaDB Docker Container
"""

import mariadb


class Database:
    """
    Database class
    """

    def __init__(self, user: str, password: str, host="127.0.0.1", port=3306, database="db_forex"):
        try:
            self.__conn = mariadb.connect(
                user=user,
                password=password,
                host=host,
                port=port,
                database=database
            )
            self.__conn.autocommit = False
            self.__cursor = self.__conn.cursor()

        except mariadb.Error as e:
            print(f"Error connecting to MariaDB Platform: {e}")

    def insert_tick(self, tick: str) -> bool:
        """
        Insert a tick to the database
        :param tick: tick (symobol, datetime, ask, bid)
        :return True if insert is done
        """
        tick_info = tick.split(",")
        if len(tick_info) == 4:
            symbol, date_time, ask, bid = tick_info

            try:
                self.__cursor.execute(
                    "INSERT INTO eurusd (symbol, datetime, ask, bid) VALUES (?, ?, ?, ?)",
                    (symbol, date_time, ask, bid))
                return True
            except mariadb.Error as e:
                print(f"Error: {e}")
                return False
        else:
            print("Error wrong format of tick: symbol,datetime,ask,bid")
            return False

    def __del__(self):
        self.__conn.close()
