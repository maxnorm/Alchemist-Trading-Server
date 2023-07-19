from datetime import datetime


def check_if_market_open():
    """
    Check if the market is open
    """
    now = datetime.now()

    if now.weekday() == 5:
        return False
    elif now.weekday() == 4 and now.hour > 17:
        return False
    elif now.weekday() == 6 and now.hour > 17:
        return True
    else:
        return True
