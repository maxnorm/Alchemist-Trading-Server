from utils.market_utils import check_if_market_open
from utils.time_utils import get_utc_time


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
        Set the datetime for when the last message was received (in UTC timezone)
        """
        self.__last_msg = get_utc_time()

    def is_inactive(self):
        """
        Check if the socket is inactive based on last message
        Only checks for inactivity when market is open (no inactivity expected during market closure)

        :return: True if inactive (only when market is open), False otherwise
        """
        # Don't check for inactivity when market is closed (no ticks expected)
        if not check_if_market_open():
            return False

        # Only check inactivity when market is open
        if self.__last_msg is None:
            return False

        now_utc = get_utc_time()
        span = now_utc - self.__last_msg
        return span.total_seconds() >= (self.__minute_inactivity_allowed * 60)
