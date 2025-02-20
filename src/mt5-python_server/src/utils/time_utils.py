"""
Utils function
"""
from datetime import datetime


def print_with_datetime(msg):
    """
    Add the datetime to the message printed
    """
    now = get_current_datetime_str()
    print(f"{now} | {msg}")


def get_current_datetime_str():
    """
    Get the current datetime string formatted %Y-%m-%d %H:%M:%S
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_datetime(date):
    """
    Format datetime for "%B %d, %H:%M" to "%Y-%m-%d %H:%M:%S"

    :return: Formatted datetime string
    """
    date_format = "%b %d, %H:%M"
    date_object = datetime.strptime(date, date_format)
    year = datetime.now().strftime("%Y-")
    return year + date_object.strftime("%m-%d %H:%M:%S")
