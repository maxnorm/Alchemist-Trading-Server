"""
Utils function
"""

from datetime import datetime
from typing import Optional, Union
import pytz  # type: ignore[import-untyped]

# UTC timezone - used consistently throughout the system (no DST issues)
_UTC_TIMEZONE = pytz.UTC
# EST/EDT timezone (for market hours and display only)
_EST_TIMEZONE = pytz.timezone("America/New_York")


def get_server_timezone():
    """
    Get the server timezone (UTC - used consistently throughout the system)

    :return: pytz timezone object for UTC
    """
    return _UTC_TIMEZONE


def get_est_timezone():
    """
    Get EST/EDT timezone (for market hours and display only)

    :return: pytz timezone object for EST/EDT
    """
    return _EST_TIMEZONE


def normalize_to_utc(
    dt: Union[datetime, str], source_timezone: Optional[pytz.BaseTzInfo] = None
) -> datetime:
    """
    Convert any datetime to UTC timezone (used consistently throughout the system)

    Supports datetime strings in formats:
    - MT5 format with milliseconds: "YYYY.MM.DD HH:MM:SS.mmm"
    - MT5 format without milliseconds: "YYYY.MM.DD HH:MM:SS"
    - Standard format: "YYYY-MM-DD HH:MM:SS"

    :param dt: datetime object (naive or timezone-aware) or datetime string
    :param source_timezone: Source timezone if dt is naive or string. If None, assumes UTC for naive datetimes
    :return: timezone-aware datetime in UTC
    """
    utc_tz = get_server_timezone()

    # Handle string input
    parsed_dt: datetime
    if isinstance(dt, str):
        # Try to parse common formats
        try:
            # MT5 format with milliseconds: "YYYY.MM.DD HH:MM:SS.mmm" (23 chars)
            if "." in dt and len(dt) == 23 and dt[19] == ".":
                parsed_dt = datetime.strptime(dt, "%Y.%m.%d %H:%M:%S.%f")
            # MT5 format without milliseconds: "YYYY.MM.DD HH:MM:SS" (19 chars)
            elif "." in dt and len(dt) == 19:
                parsed_dt = datetime.strptime(dt, "%Y.%m.%d %H:%M:%S")
            # Standard format: "YYYY-MM-DD HH:MM:SS" (19 chars)
            elif "-" in dt and len(dt) == 19:
                parsed_dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
            else:
                raise ValueError(f"Unsupported datetime string format: {dt}")
        except ValueError as e:
            raise ValueError(f"Failed to parse datetime string '{dt}': {e}")
    else:
        parsed_dt = dt

    # Handle naive datetime
    if parsed_dt.tzinfo is None:
        if source_timezone is None:
            # Default to UTC for naive datetimes
            source_timezone = pytz.UTC
        parsed_dt = source_timezone.localize(parsed_dt)

    # Convert to UTC (no DST issues)
    return parsed_dt.astimezone(utc_tz)


def normalize_to_est(
    dt: Union[datetime, str], source_timezone: Optional[pytz.BaseTzInfo] = None
) -> datetime:
    """
    Convert any datetime to EST/EDT timezone (for display/market hours only)

    :param dt: datetime object (naive or timezone-aware) or datetime string
    :param source_timezone: Source timezone if dt is naive or string. If None, assumes UTC for naive datetimes
    :return: timezone-aware datetime in EST/EDT
    """
    est_tz = get_est_timezone()

    # Handle string input
    parsed_dt: datetime
    if isinstance(dt, str):
        try:
            # MT5 format with milliseconds: "YYYY.MM.DD HH:MM:SS.mmm" (23 chars)
            if "." in dt and len(dt) == 23 and dt[19] == ".":
                parsed_dt = datetime.strptime(dt, "%Y.%m.%d %H:%M:%S.%f")
            # MT5 format without milliseconds: "YYYY.MM.DD HH:MM:SS" (19 chars)
            elif "." in dt and len(dt) == 19:
                parsed_dt = datetime.strptime(dt, "%Y.%m.%d %H:%M:%S")
            # Standard format: "YYYY-MM-DD HH:MM:SS" (19 chars)
            elif "-" in dt and len(dt) == 19:
                parsed_dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
            else:
                raise ValueError(f"Unsupported datetime string format: {dt}")
        except ValueError as e:
            raise ValueError(f"Failed to parse datetime string '{dt}': {e}")
    else:
        parsed_dt = dt

    # Handle naive datetime
    if parsed_dt.tzinfo is None:
        if source_timezone is None:
            source_timezone = pytz.UTC
        parsed_dt = source_timezone.localize(parsed_dt)

    # Convert to EST/EDT
    return parsed_dt.astimezone(est_tz)


def parse_mt5_timestamp(
    timestamp_str: str, mt5_timezone_offset: Optional[float] = None
) -> datetime:
    """
    Parse MT5 timestamp string and convert to UTC timezone

    MT5 format: "YYYY.MM.DD HH:MM:SS" or "YYYY.MM.DD HH:MM:SS.mmm" (with milliseconds)

    :param timestamp_str: MT5 timestamp string
    :param mt5_timezone_offset: Offset in hours from UTC (e.g., 3.0 for GMT+3). If None, will try to detect
    :return: timezone-aware datetime in UTC
    """
    try:
        # Try parsing with milliseconds first (23 chars: "YYYY.MM.DD HH:MM:SS.mmm")
        if len(timestamp_str) == 23 and timestamp_str[19] == ".":
            dt = datetime.strptime(timestamp_str, "%Y.%m.%d %H:%M:%S.%f")
        # Fallback to seconds-only format (19 chars: "YYYY.MM.DD HH:MM:SS")
        else:
            dt = datetime.strptime(timestamp_str, "%Y.%m.%d %H:%M:%S")

        # If offset provided, use it
        if mt5_timezone_offset is not None:
            source_tz = pytz.FixedOffset(int(mt5_timezone_offset * 60))
        else:
            # Default to UTC if no offset provided (will need to be detected elsewhere)
            source_tz = pytz.UTC

        # Localize and convert to UTC
        dt = source_tz.localize(dt)
        return dt.astimezone(get_server_timezone())
    except ValueError as e:
        raise ValueError(f"Failed to parse MT5 timestamp '{timestamp_str}': {e}")


def parse_scraped_timestamp(
    timestamp_str: str, source_timezone: Optional[Union[str, pytz.BaseTzInfo]] = None
) -> datetime:
    """
    Parse scraped timestamp string and convert to UTC timezone

    :param timestamp_str: Scraped timestamp string (various formats)
    :param source_timezone: Source timezone (string like 'UTC' or pytz timezone object). Defaults to UTC
    :return: timezone-aware datetime in UTC
    """
    # Default to UTC if not specified
    source_tz: pytz.BaseTzInfo
    if source_timezone is None:
        source_tz = pytz.UTC
    elif isinstance(source_timezone, str):
        source_tz = pytz.timezone(source_timezone)
    else:
        source_tz = source_timezone

    # Try to parse common formats
    formats = [
        "%b %d, %H:%M",  # "Jan 15, 14:30"
        "%Y-%m-%d %H:%M:%S",  # "2024-01-15 14:30:00"
        "%Y.%m.%d %H:%M:%S",  # "2024.01.15 14:30:00"
        "%Y-%m-%d %H:%M",  # "2024-01-15 14:30"
    ]

    dt = None
    for fmt in formats:
        try:
            dt = datetime.strptime(timestamp_str, fmt)
            break
        except ValueError:
            continue

    if dt is None:
        raise ValueError(
            f"Failed to parse scraped timestamp '{timestamp_str}' with any known format"
        )

    # Add current year if not present (for formats like "%b %d, %H:%M")
    if dt.year == 1900:
        dt = dt.replace(year=datetime.now().year)

    # Localize and convert to UTC
    dt = source_tz.localize(dt)
    return dt.astimezone(get_server_timezone())


def get_utc_time() -> datetime:
    """
    Get current time in UTC timezone

    :return: timezone-aware datetime in UTC
    """
    return datetime.now(get_server_timezone())


def get_est_time() -> datetime:
    """
    Get current time in EST/EDT timezone (for display/market hours only)

    :return: timezone-aware datetime in EST/EDT
    """
    return datetime.now(get_est_timezone())


def ensure_utc_timezone(dt: datetime) -> datetime:
    """
    Ensure datetime is in UTC timezone (convert if needed)

    :param dt: datetime object (naive or timezone-aware)
    :return: timezone-aware datetime in UTC
    """
    return normalize_to_utc(dt)


def ensure_est_timezone(dt: datetime) -> datetime:
    """
    Ensure datetime is in EST/EDT timezone (convert if needed) - for display/market hours only

    :param dt: datetime object (naive or timezone-aware)
    :return: timezone-aware datetime in EST/EDT
    """
    return normalize_to_est(dt)


def print_with_datetime(msg):
    """
    Add the datetime to the message printed (using EST timezone)
    """
    now = get_current_datetime_str()
    print(f"{now} | {msg}")


def get_current_datetime_str():
    """
    Get the current datetime string formatted %Y-%m-%d %H:%M:%S in UTC timezone
    """
    return get_utc_time().strftime("%Y-%m-%d %H:%M:%S")


def format_datetime(date: str, source_timezone: Optional[str] = None) -> str:
    """
    Format datetime for "%b %d, %H:%M" to "%Y-%m-%d %H:%M:%S" in UTC timezone

    :param date: Date string in format "%b %d, %H:%M" (e.g., "Jan 15, 14:30")
    :param source_timezone: Source timezone (defaults to UTC). Can be 'UTC', 'EST', etc.
    :return: Formatted datetime string in UTC timezone
    """
    # Parse the date string
    date_format = "%b %d, %H:%M"
    date_object = datetime.strptime(date, date_format)

    # Add current year
    date_object = date_object.replace(year=datetime.now().year)

    # Determine source timezone
    source_tz: pytz.BaseTzInfo
    if source_timezone is None:
        source_tz = pytz.UTC  # Default to UTC for scraped data
    else:
        source_tz = pytz.timezone(source_timezone)

    # Localize and convert to UTC
    date_object = source_tz.localize(date_object)
    utc_datetime = date_object.astimezone(get_server_timezone())

    # Return formatted string
    return utc_datetime.strftime("%Y-%m-%d %H:%M:%S")
