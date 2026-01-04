"""
Economic calendar collector
Collects economic calendar data on a schedule
"""

import time
import threading
from typing import Optional

from web_scraper.web_scraper_myfxbook import WebScraperMyfxbook
from database import Database
from utils.time_utils import print_with_datetime, get_utc_time


class EconomicCalendarCollector:
    """Collects economic calendar data on a schedule"""

    def __init__(
        self,
        database: Database,
        scraper: WebScraperMyfxbook,
        verbose: bool = False,
        console_lock=None,
    ):
        """
        Initialize economic calendar collector
        :param database: Database instance
        :param scraper: Web scraper instance
        :param verbose: Enable verbose logging
        :param console_lock: Thread lock for console output
        """
        self.database = database
        self.scraper = scraper
        self.verbose = verbose
        self.console_lock = console_lock
        self.is_running = False
        self.collection_thread: Optional[threading.Thread] = None

    def start_scheduled_collection(self, hour: int, minute: int):
        """
        Start scheduled collection
        :param hour: Hour to collect (0-23)
        :param minute: Minute to collect (0-59)
        """
        if self.is_running:
            return

        self.is_running = True
        self.collection_thread = threading.Thread(
            target=self._collection_loop, args=(hour, minute), daemon=True
        )
        self.collection_thread.start()

    def stop(self):
        """Stop collection"""
        self.is_running = False

    def _collection_loop(self, hour: int, minute: int):
        """Collection loop"""
        while self.is_running:
            # Use UTC timezone for scheduling (convert hour/minute to UTC if needed)
            # Note: hour and minute parameters should be in EST/EDT for the intended collection time
            # We'll convert to UTC for comparison
            from utils.time_utils import get_est_timezone

            now_utc = get_utc_time()
            est_tz = get_est_timezone()
            now_est = now_utc.astimezone(est_tz)

            # Check if it's the scheduled time in EST/EDT
            if (
                now_est.hour == hour
                and now_est.minute == minute
                and now_est.weekday() < 5
            ):
                try:
                    data = self.scraper.download_economic_calendar()
                    self.database.insert_economic_calendar_data(data)

                    if self.verbose:
                        if self.console_lock:
                            with self.console_lock:
                                print_with_datetime("Economic Calendar was downloaded")
                        else:
                            print_with_datetime("Economic Calendar was downloaded")
                except Exception as e:
                    if self.console_lock:
                        with self.console_lock:
                            print_with_datetime(
                                f"Error while downloading economic calendar: {e}"
                            )
                    else:
                        print_with_datetime(
                            f"Error while downloading economic calendar: {e}"
                        )

            time.sleep(60)
