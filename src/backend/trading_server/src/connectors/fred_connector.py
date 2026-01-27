"""
FRED (Federal Reserve Economic Data) connector
Implements IDataSourceConnector for US economic indicators from FRED API
"""

import os
import time
from typing import Dict, Any, Iterator, Optional, Tuple
from datetime import datetime, timedelta
from utils.logging_config import get_logger
from events.normalizer import EventNormalizer
from .base import IDataSourceConnector, ConnectorConfig
from utils.time_utils import normalize_to_utc, ensure_utc_timezone

try:
    from fredapi import Fred
except ImportError:
    Fred = None


class FREDConnector(IDataSourceConnector):
    """
    FRED connector for US economic indicators
    Uses FRED API (free API key required from https://fred.stlouisfed.org/)
    """

    # Key FRED series IDs for US economic indicators
    KEY_SERIES = {
        "FEDFUNDS": "Federal Funds Rate",
        "UNRATE": "Unemployment Rate",
        "CPIAUCSL": "Consumer Price Index",
        "GDP": "Gross Domestic Product",
        "PAYEMS": "Nonfarm Payrolls",
        "INDPRO": "Industrial Production Index",
    }

    def __init__(self, config: ConnectorConfig):
        """
        Initialize FRED connector

        :param config: Connector configuration
        """
        self.config = config
        self.normalizer = EventNormalizer()
        self.logger = get_logger("fred_connector", "fred_connector.log")

        # Get API key from environment
        api_key = os.getenv("FRED_API_KEY")
        if not api_key:
            self.logger.warning(
                "FRED_API_KEY not found in environment. FRED connector will not work."
            )
            self.fred = None
        else:
            if Fred is None:
                self.logger.error(
                    "fredapi library not installed. Install with: pip install fredapi"
                )
                self.fred = None
            else:
                try:
                    self.fred = Fred(api_key=api_key)
                    self.logger.info("FRED connector initialized successfully")
                except Exception as e:
                    self.logger.error(f"Failed to initialize FRED client: {e}")
                    self.fred = None

        self._is_connected = False
        self._latest_timestamp: Optional[datetime] = None

        # Rate limiting: 120 requests/minute (free tier)
        self._last_request_time = 0.0
        self._min_request_interval = 0.5  # 0.5 seconds = 120 requests/minute

    def connect(self) -> bool:
        """
        Establish connection to FRED API

        :return: True if connection successful, False otherwise
        """
        if self.fred is None:
            self.logger.error("FRED client not initialized. Check FRED_API_KEY.")
            return False

        try:
            # Test connection by fetching a simple series
            test_series = list(self.KEY_SERIES.keys())[0]
            data = self.fred.get_series(test_series, limit=1)
            if data is not None and len(data) > 0:
                self._is_connected = True
                self.logger.info("Connected to FRED API")
                return True
            else:
                self.logger.warning("FRED API connection test returned no data")
                return False
        except Exception as e:
            self.logger.error(f"Failed to connect to FRED API: {e}")
            return False

    def disconnect(self) -> None:
        """Close connection to FRED API"""
        self._is_connected = False
        self.logger.info("Disconnected from FRED API")

    def is_connected(self) -> bool:
        """Check if connector is currently connected"""
        return self._is_connected and self.fred is not None

    def _rate_limit(self):
        """Enforce rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _fetch_series_data(
        self,
        series_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        Fetch data for a FRED series

        :param series_id: FRED series ID
        :param start_date: Start date (optional)
        :param end_date: End date (optional)
        :return: Iterator of normalized event dictionaries
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to FRED API")

        if self.fred is None:
            raise ConnectionError("FRED client not initialized")

        try:
            self._rate_limit()

            # Fetch data from FRED
            if start_date and end_date:
                data = self.fred.get_series(
                    series_id, observation_start=start_date, observation_end=end_date
                )
            elif start_date:
                data = self.fred.get_series(series_id, observation_start=start_date)
            elif end_date:
                data = self.fred.get_series(series_id, observation_end=end_date)
            else:
                data = self.fred.get_series(series_id)

            if data is None or len(data) == 0:
                self.logger.warning(f"No data returned for series {series_id}")
                return

            # Get series metadata for frequency
            try:
                self._rate_limit()
                series_info = self.fred.get_series_info(series_id)
                frequency = series_info.get("frequency", "MONTHLY")
                # Map FRED frequency to our format
                freq_map = {
                    "Daily": "DAILY",
                    "Weekly": "WEEKLY",
                    "Monthly": "MONTHLY",
                    "Quarterly": "QUARTERLY",
                    "Annual": "ANNUAL",
                }
                frequency = freq_map.get(frequency, "MONTHLY")
            except Exception as e:
                self.logger.warning(f"Could not get frequency for {series_id}: {e}")
                frequency = "MONTHLY"

            # Convert to normalized events
            for timestamp, value in data.items():
                if value is None or (
                    isinstance(value, float) and (value != value)
                ):  # Check for NaN
                    continue

                # Convert pandas Timestamp to datetime
                if hasattr(timestamp, "to_pydatetime"):
                    timestamp_dt = timestamp.to_pydatetime()
                else:
                    timestamp_dt = datetime.fromtimestamp(timestamp.timestamp())

                # Normalize timestamp to UTC
                timestamp_utc = normalize_to_utc(timestamp_dt)

                # Create raw event
                raw_event = {
                    "timestamp": timestamp_utc,
                    "series_id": series_id,
                    "value": float(value),
                    "source": "FRED",
                    "country": "US",
                    "frequency": frequency,
                    "_receive_time": ensure_utc_timezone(datetime.now()),
                }

                # Normalize event
                normalized = self._normalize_economic_indicator(raw_event)

                # Update latest timestamp
                if (
                    self._latest_timestamp is None
                    or timestamp_utc > self._latest_timestamp
                ):
                    self._latest_timestamp = timestamp_utc

                yield normalized

        except Exception as e:
            self.logger.error(
                f"Error fetching FRED series {series_id}: {e}", exc_info=True
            )
            raise

    def _normalize_economic_indicator(self, raw_event: Dict) -> Dict[str, Any]:
        """
        Normalize economic indicator event to contract format

        :param raw_event: Raw FRED event dictionary
        :return: Normalized event dictionary conforming to economic indicator contract
        """
        # Economic indicators use a different format than economic calendar events
        # They are time series data, not scheduled events
        normalized = {
            "timestamp": raw_event["timestamp"],
            "series_id": raw_event["series_id"],
            "value": raw_event["value"],
            "source": raw_event["source"],
            "country": raw_event.get("country"),
            "frequency": raw_event.get("frequency"),
            "receive_time": raw_event.get("_receive_time"),
        }
        return normalized

    def stream(self, start_time: Optional[datetime] = None) -> Iterator[Dict[str, Any]]:
        """
        Stream latest economic indicators from FRED

        :param start_time: Optional start time (defaults to last 24 hours)
        :return: Iterator of normalized event dictionaries
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to FRED API")

        # For streaming, fetch latest data for all key series
        # FRED data is typically updated daily, so we check for updates
        if start_time is None:
            start_time = datetime.now() - timedelta(days=1)

        for series_id in self.KEY_SERIES.keys():
            try:
                yield from self._fetch_series_data(series_id, start_date=start_time)
            except Exception as e:
                self.logger.error(f"Error streaming {series_id}: {e}")
                continue

    def batch(
        self, start_time: datetime, end_time: datetime
    ) -> Iterator[Dict[str, Any]]:
        """
        Fetch historical economic indicators from database (not implemented for FRED)

        :param start_time: Start time for historical data
        :param end_time: End time for historical data
        :return: Iterator of normalized event dictionaries
        """
        # FRED connector doesn't read from database
        # Use backfill() for historical data from FRED API
        self.logger.warning("batch() not implemented for FRED. Use backfill() instead.")
        return iter([])

    def backfill(
        self, start_time: datetime, end_time: datetime, batch_size: int = 1000
    ) -> Iterator[Dict[str, Any]]:
        """
        Fetch historical economic indicators from FRED API

        :param start_time: Start time for historical data
        :param end_time: End time for historical data
        :param batch_size: Batch size (not used, FRED handles batching)
        :return: Iterator of normalized event dictionaries
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to FRED API")

        if start_time >= end_time:
            raise ValueError("start_time must be before end_time")

        # Fetch all key series for the time range
        for series_id in self.KEY_SERIES.keys():
            try:
                yield from self._fetch_series_data(
                    series_id, start_date=start_time, end_date=end_time
                )
            except Exception as e:
                self.logger.error(f"Error backfilling {series_id}: {e}")
                continue

    def get_available_range(self) -> Tuple[datetime, datetime]:
        """
        Get the available data range from FRED API

        :return: Tuple of (earliest_available_time, latest_available_time)
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to FRED API")

        if self.fred is None:
            raise ConnectionError("FRED client not initialized")

        try:
            # Get range from first key series (FEDFUNDS has long history)
            series_id = "FEDFUNDS"
            self._rate_limit()
            data = self.fred.get_series(series_id, limit=1)

            if data is None or len(data) == 0:
                raise ValueError("No data available from FRED")

            # Get earliest and latest dates
            earliest = data.index.min()
            latest = data.index.max()

            # Convert to datetime
            if hasattr(earliest, "to_pydatetime"):
                earliest_dt = earliest.to_pydatetime()
                latest_dt = latest.to_pydatetime()
            else:
                earliest_dt = datetime.fromtimestamp(earliest.timestamp())
                latest_dt = datetime.fromtimestamp(latest.timestamp())

            return (normalize_to_utc(earliest_dt), normalize_to_utc(latest_dt))

        except Exception as e:
            self.logger.error(f"Error getting available range from FRED: {e}")
            raise ConnectionError(f"Failed to get available range: {e}")

    def get_schema(self) -> Dict[str, Any]:
        """
        Return FRED connector schema definition

        :return: Schema dictionary
        """
        return {
            "source": "FRED",
            "data_type": "economic",
            "fields": {
                "timestamp": "datetime",
                "series_id": "string",
                "value": "float",
                "source": "string",
                "country": "string",
                "frequency": "string",
            },
            "key_series": self.KEY_SERIES,
        }

    def get_latest_timestamp(self) -> Optional[datetime]:
        """
        Get timestamp of most recent data available

        :return: Datetime of most recent data, or None if no data available
        """
        return self._latest_timestamp
