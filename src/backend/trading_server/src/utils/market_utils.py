from typing import Iterable, Optional, Any
from datetime import timedelta
from utils.time_utils import get_utc_time, get_est_timezone
import pytz  # type: ignore[import-untyped]


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
    next_open_naive = now_est.replace(tzinfo=None).replace(
        hour=target_hour, minute=0, second=0, microsecond=0
    )
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
    connectors: Optional[Iterable[Any]] = None, max_feed_age_seconds: float = 180.0
) -> dict:
    """
    Combined status helper for calendar + feed freshness.

    :param connectors: Iterable of connectors implementing is_stale(max_age_seconds)
    :param max_feed_age_seconds: Max age before feed considered stale
    :return: Dict with market_open, feed_live, ready flags
    """
    market_open = check_if_market_open()
    feed_live = False

    if connectors:
        for connector in connectors:
            is_stale = getattr(connector, "is_stale", None)
            try:
                if callable(is_stale) and not is_stale(max_feed_age_seconds):
                    feed_live = True
                    break
            except Exception:
                # Ignore connector errors; treat as stale
                continue

    return {
        "market_open": market_open,
        "feed_live": feed_live,
        "ready": market_open and feed_live,
    }


def calculate_pip_value_from_digits(digits: int) -> float:
    """
    Calculate pip value from symbol digits.

    For forex pairs:
    - digits <= 3 (JPY pairs, Gold/XAU pairs): pip = 0.01 (pip is at 2nd decimal place)
    - digits >= 4 (standard pairs): pip = 0.0001 (pip is at 4th decimal place)

    :param digits: Number of decimal places for the symbol
    :return: Pip value (0.01 for JPY-like/XAU, 0.0001 for standard)
    """
    if digits <= 3:
        return 0.01  # JPY-like pairs (USDJPY, EURJPY, etc.)
    else:
        return 0.0001  # Standard pairs (EURUSD, GBPUSD, etc.)


def infer_pip_value_from_price(price: float) -> float:
    """
    Infer pip value from price decimal precision.

    Automatically detects pip value based on price format:
    - JPY pairs: typically 50-200 range, 2-3 decimal places → pip = 0.01
    - Gold (XAU) pairs: typically 2000-2500 range, 2-3 decimal places → pip = 0.01
    - Other pairs: typically 0.5-2.0 range, 4-5 decimal places → pip = 0.0001

    :param price: Price value (bid or ask)
    :return: Pip value (0.01 for JPY-like/XAU, 0.0001 for standard)
    """
    # Convert to string to count significant decimal places
    # Use high precision format then strip trailing zeros
    price_str = f"{price:.10f}".rstrip("0").rstrip(".")

    # Count decimal places
    if "." in price_str:
        decimal_places = len(price_str.split(".")[1])
    else:
        decimal_places = 0

    # Infer pip value based on price magnitude and decimal places
    # JPY pairs: high price (>10) with 2-3 decimals → pip = 0.01
    # Gold (XAU) pairs: high price (>10) with 2-3 decimals → pip = 0.01
    # Standard pairs: low price (<10) with 4-5 decimals → pip = 0.0001
    # More robust: prioritize price magnitude for JPY/XAU pairs
    if price > 10:
        # High price likely JPY or XAU pair
        if decimal_places <= 3:
            return 0.01  # JPY-like or XAU pairs
        else:
            # Unusual case: high price with many decimals, but still likely JPY/XAU
            return 0.01
    elif price < 10 and decimal_places >= 4:
        return 0.0001  # Standard pairs
    else:
        # Default heuristic: use decimal places
        if decimal_places <= 3:
            return 0.01
        else:
            return 0.0001
