from datetime import datetime
from utils.market_utils import check_if_market_open


class InactivityManager:
    """
    Class for managing socket inactivity
    """
    # TODO See if this class is necessary

    def __init__(self, minute_inactivity_allowed):
        self.__minute_inactivity_allowed = minute_inactivity_allowed
        self.__last_msg = None

    def reset_time(self):
        """
        Set the datetime for when the last message was receive
        """
        self.__last_msg = datetime.now()

    def is_inactive(self):
        """
        Check if the socket is inactive based on last message
        """
        span = datetime.now() - self.__last_msg
        return check_if_market_open() and span.total_seconds() >= (self.__minute_inactivity_allowed * 60)