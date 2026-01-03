from datetime import datetime, timedelta
from typing import Iterable
from utils.time_utils import get_utc_time, get_est_timezone
import pytz


def check_if_market_open():
    """
    Check if the forex market is open
    
    Market hours: Sunday 17:00 Asia time (UTC+8/9) to Friday 17:00 EST
    
    :return: True if market is open, False if closed
    """
    # Get current time in UTC
    now_utc = get_utc_time()
    
    # Convert to EST/EDT for market hours checking
    est_tz = get_est_timezone()
    now_est = now_utc.astimezone(est_tz)
    
    weekday = now_est.weekday()  # 0=Monday, 6=Sunday
    hour = now_est.hour
    
    # Saturday (5) - always closed
    if weekday == 5:
        return False
    
    # Friday - closed after 17:00 EST (22:00 UTC in winter, 21:00 UTC in summer)
    if weekday == 4 and hour >= 17:
        return False
    
    # Sunday - market opens at 17:00 Asia time
    # Asia time (UTC+8/9) = EST+13/14 hours (depending on DST)
    # So 17:00 Asia = approximately 03:00-04:00 EST (Sunday morning)
    if weekday == 6:
        # Market opens Sunday around 3-4 AM EST (17:00 Asia time)
        # For simplicity, check if it's after 3 AM EST on Sunday
        return hour >= 3
    
    # Monday-Thursday - always open
    return True


def is_market_closed():
    """
    Check if the market is closed (inverse of check_if_market_open)
    
    :return: True if market is closed, False if open
    """
    return not check_if_market_open()


def get_next_market_open_time():
    """
    Get the next market open time in UTC timezone
    
    :return: datetime object in UTC timezone for next market open
    """
    now_utc = get_utc_time()
    est_tz = get_est_timezone()
    now_est = now_utc.astimezone(est_tz)
    
    weekday = now_est.weekday()
    hour = now_est.hour
    
    # If it's Saturday, next open is Sunday 3 AM EST
    if weekday == 5:
        days_ahead = 1
        target_hour = 3
    # If it's Friday after 17:00, next open is Sunday 3 AM EST
    elif weekday == 4 and hour >= 17:
        days_ahead = 2
        target_hour = 3
    # If it's Sunday before 3 AM, next open is today at 3 AM
    elif weekday == 6 and hour < 3:
        days_ahead = 0
        target_hour = 3
    # Otherwise, market should be open (return current time + 1 hour as fallback)
    else:
        return now_utc + timedelta(hours=1)
    
    # Calculate next open time in EST
    # Create naive datetime for the target time
    next_open_naive = now_est.replace(tzinfo=None).replace(hour=target_hour, minute=0, second=0, microsecond=0)
    next_open_naive += timedelta(days=days_ahead)
    
    # Localize to EST/EDT (pytz handles DST automatically)
    try:
        next_open_est = est_tz.localize(next_open_naive, is_dst=None)
    except pytz.AmbiguousTimeError:
        # During fall back, use DST=True
        next_open_est = est_tz.localize(next_open_naive, is_dst=True)
    except pytz.NonExistentTimeError:
        # During spring forward, use DST=True
        next_open_est = est_tz.localize(next_open_naive, is_dst=True)
    
    # Convert back to UTC
    next_open_utc = next_open_est.astimezone(pytz.UTC)
    
    return next_open_utc


def get_market_feed_status(
    data_providers: Iterable = None,
    max_feed_age_seconds: float = 180.0
) -> dict:
    """
    Combined status helper for calendar + feed freshness.
    
    :param data_providers: Iterable of providers implementing is_stale(max_age_seconds)
    :param max_feed_age_seconds: Max age before feed considered stale
    :return: Dict with market_open, feed_live, ready flags
    """
    market_open = check_if_market_open()
    feed_live = False
    
    if data_providers:
        for provider in data_providers:
            is_stale = getattr(provider, "is_stale", None)
            try:
                if callable(is_stale) and not is_stale(max_feed_age_seconds):
                    feed_live = True
                    break
            except Exception:
                # Ignore provider errors; treat as stale
                continue
    
    return {
        "market_open": market_open,
        "feed_live": feed_live,
        "ready": market_open and feed_live
    }
