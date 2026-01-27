"""
World Bank connector for global economic indicators
Implements IDataSourceConnector for economic data from World Bank API (completely free, no API key)
"""

import time
from typing import Dict, Any, Iterator, Optional, Tuple
from datetime import datetime, timedelta
from utils.logging_config import get_logger
from events.normalizer import EventNormalizer
from .base import IDataSourceConnector, ConnectorConfig
from utils.time_utils import normalize_to_utc, ensure_utc_timezone

try:
    import wbdata
except ImportError:
    wbdata = None  # type: ignore[assignment]


class WorldBankConnector(IDataSourceConnector):
    """
    World Bank connector for global economic indicators
    Uses World Bank Data API (completely free, no API key required)
    """

    # Key World Bank indicators
    KEY_INDICATORS = {
        "NY.GDP.MKTP.CD": "GDP (current US$)",
        "NY.GDP.MKTP.KD.ZG": "GDP growth (annual %)",
        "FP.CPI.TOTL.ZG": "Inflation, consumer prices (annual %)",
        "NE.TRD.GNFS.ZS": "Trade (% of GDP)",
        "SL.UEM.TOTL.ZS": "Unemployment, total (% of total labor force)",
    }

    # Country codes (ISO 3-letter)
    KEY_COUNTRIES = {
        "USA": "United States",
        "GBR": "United Kingdom",
        "JPN": "Japan",
        "DEU": "Germany",
        "FRA": "France",
        "CHN": "China",
        "IND": "India",
        "BRA": "Brazil",
        "RUS": "Russia",
        "EUU": "Euro area",
    }

    def __init__(self, config: ConnectorConfig):
        """
        Initialize World Bank connector

        :param config: Connector configuration
        """
        self.config = config
        self.normalizer = EventNormalizer()
        self.logger = get_logger("world_bank_connector", "world_bank_connector.log")

        if wbdata is None:
            self.logger.error(
                "wbdata library not installed. Install with: pip install wbdata"
            )
            self._available = False
        else:
            self._available = True
            self.logger.info("World Bank connector initialized successfully")

        self._is_connected = False
        self._latest_timestamp: Optional[datetime] = None

        # Rate limiting: be respectful to free API
        self._last_request_time = 0.0
        self._min_request_interval = 1.0  # 1 second between requests

    def connect(self) -> bool:
        """
        Establish connection to World Bank API

        :return: True if connection successful, False otherwise
        """
        if not self._available:
            self.logger.error(
                "World Bank connector not available. Install wbdata library."
            )
            return False

        try:
            # Test connection by fetching a simple indicator
            test_indicator = list(self.KEY_INDICATORS.keys())[0]
            test_country = list(self.KEY_COUNTRIES.keys())[0]
            data = wbdata.get_data(
                test_indicator, country=test_country, date=(2000, 2001)  # type: ignore[arg-type]
            )
            if data is not None:
                self._is_connected = True
                self.logger.info("Connected to World Bank API")
                return True
            else:
                self.logger.warning("World Bank API connection test returned no data")
                return False
        except Exception as e:
            self.logger.error(f"Failed to connect to World Bank API: {e}")
            return False

    def disconnect(self) -> None:
        """Close connection to World Bank API"""
        self._is_connected = False
        self.logger.info("Disconnected from World Bank API")

    def is_connected(self) -> bool:
        """Check if connector is currently connected"""
        return self._is_connected and self._available

    def _rate_limit(self):
        """Enforce rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _fetch_indicator_data(
        self,
        indicator_id: str,
        country_code: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        Fetch data for a World Bank indicator

        :param indicator_id: World Bank indicator ID
        :param country_code: ISO 3-letter country code
        :param start_date: Start date (optional)
        :param end_date: End date (optional)
        :return: Iterator of normalized event dictionaries
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to World Bank API")

        try:
            self._rate_limit()

            # Convert datetime to year tuples for wbdata
            if start_date and end_date:
                date_range = (start_date.year, end_date.year)
            elif start_date:
                date_range = (start_date.year, datetime.now().year)
            elif end_date:
                date_range = (1950, end_date.year)  # World Bank data starts around 1960
            else:
                date_range = None

            # Fetch data from World Bank
            if date_range is not None:
                data = wbdata.get_data(
                    indicator_id, country=country_code, date=date_range  # type: ignore[arg-type]
                )
            else:
                data = wbdata.get_data(indicator_id, country=country_code)

            if data is None or len(data) == 0:
                self.logger.warning(
                    f"No data returned for indicator {indicator_id}, country {country_code}"
                )
                return

            # Get indicator metadata for frequency
            try:
                self._rate_limit()
                indicators = wbdata.get_indicators(indicator_id)
                if indicators:
                    # Most World Bank indicators are annual
                    frequency = "ANNUAL"
                else:
                    frequency = "ANNUAL"
            except Exception as e:
                self.logger.warning(f"Could not get frequency for {indicator_id}: {e}")
                frequency = "ANNUAL"

            # Convert to normalized events
            for record in data:
                value = record.get("value")
                if value is None:
                    continue

                # Parse date from record
                date_str = record.get("date")
                if not date_str:
                    continue

                try:
                    # World Bank dates are typically "YYYY" or "YYYY-MM-DD"
                    if len(date_str) == 4:
                        # Annual data - use January 1st
                        timestamp_dt = datetime(int(date_str), 1, 1)
                    else:
                        timestamp_dt = datetime.strptime(date_str, "%Y-%m-%d")
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Could not parse date {date_str}: {e}")
                    continue

                # Normalize timestamp to UTC
                timestamp_utc = normalize_to_utc(timestamp_dt)

                # Create series_id combining indicator and country
                series_id = f"{indicator_id}_{country_code}"

                # Create raw event
                raw_event = {
                    "timestamp": timestamp_utc,
                    "series_id": series_id,
                    "value": float(value),
                    "source": "WORLD_BANK",
                    "country": country_code,
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
                f"Error fetching World Bank indicator {indicator_id} for {country_code}: {e}",
                exc_info=True,
            )
            raise

    def _normalize_economic_indicator(self, raw_event: Dict) -> Dict[str, Any]:
        """
        Normalize economic indicator event to contract format

        :param raw_event: Raw World Bank event dictionary
        :return: Normalized event dictionary conforming to economic indicator contract
        """
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
        Stream latest economic indicators from World Bank

        :param start_time: Optional start time (defaults to last year)
        :return: Iterator of normalized event dictionaries
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to World Bank API")

        # For streaming, fetch latest data for all key indicators and countries
        # World Bank data is typically updated annually/quarterly
        if start_time is None:
            start_time = datetime.now() - timedelta(days=365)

        for indicator_id in self.KEY_INDICATORS.keys():
            for country_code in self.KEY_COUNTRIES.keys():
                try:
                    yield from self._fetch_indicator_data(
                        indicator_id, country_code, start_date=start_time
                    )
                except Exception as e:
                    self.logger.error(
                        f"Error streaming {indicator_id} for {country_code}: {e}"
                    )
                    continue

    def batch(
        self, start_time: datetime, end_time: datetime
    ) -> Iterator[Dict[str, Any]]:
        """
        Fetch historical economic indicators from database (not implemented for World Bank)

        :param start_time: Start time for historical data
        :param end_time: End time for historical data
        :return: Iterator of normalized event dictionaries
        """
        # World Bank connector doesn't read from database
        # Use backfill() for historical data from World Bank API
        self.logger.warning(
            "batch() not implemented for World Bank. Use backfill() instead."
        )
        return iter([])

    def backfill(
        self, start_time: datetime, end_time: datetime, batch_size: int = 1000
    ) -> Iterator[Dict[str, Any]]:
        """
        Fetch historical economic indicators from World Bank API

        :param start_time: Start time for historical data
        :param end_time: End time for historical data
        :param batch_size: Batch size (not used, World Bank handles batching)
        :return: Iterator of normalized event dictionaries
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to World Bank API")

        if start_time >= end_time:
            raise ValueError("start_time must be before end_time")

        # Fetch all key indicators and countries for the time range
        for indicator_id in self.KEY_INDICATORS.keys():
            for country_code in self.KEY_COUNTRIES.keys():
                try:
                    yield from self._fetch_indicator_data(
                        indicator_id,
                        country_code,
                        start_date=start_time,
                        end_date=end_time,
                    )
                except Exception as e:
                    self.logger.error(
                        f"Error backfilling {indicator_id} for {country_code}: {e}"
                    )
                    continue

    def get_available_range(self) -> Tuple[datetime, datetime]:
        """
        Get the available data range from World Bank API

        :return: Tuple of (earliest_available_time, latest_available_time)
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to World Bank API")

        try:
            # Get range from first key indicator and country
            indicator_id = list(self.KEY_INDICATORS.keys())[0]
            country_code = list(self.KEY_COUNTRIES.keys())[0]

            self._rate_limit()
            data = wbdata.get_data(indicator_id, country=country_code)

            if data is None or len(data) == 0:
                raise ValueError("No data available from World Bank")

            # Get earliest and latest dates
            dates = []
            for record in data:
                date_str = record.get("date")
                if date_str:
                    try:
                        if len(date_str) == 4:
                            dates.append(datetime(int(date_str), 1, 1))
                        else:
                            dates.append(datetime.strptime(date_str, "%Y-%m-%d"))
                    except (ValueError, TypeError):
                        continue

            if not dates:
                raise ValueError("No valid dates found in World Bank data")

            earliest = min(dates)
            latest = max(dates)

            return (normalize_to_utc(earliest), normalize_to_utc(latest))

        except Exception as e:
            self.logger.error(f"Error getting available range from World Bank: {e}")
            raise ConnectionError(f"Failed to get available range: {e}")

    def get_schema(self) -> Dict[str, Any]:
        """
        Return World Bank connector schema definition

        :return: Schema dictionary
        """
        return {
            "source": "WORLD_BANK",
            "data_type": "economic",
            "fields": {
                "timestamp": "datetime",
                "series_id": "string",
                "value": "float",
                "source": "string",
                "country": "string",
                "frequency": "string",
            },
            "key_indicators": self.KEY_INDICATORS,
            "key_countries": self.KEY_COUNTRIES,
        }

    def get_latest_timestamp(self) -> Optional[datetime]:
        """
        Get timestamp of most recent data available

        :return: Datetime of most recent data, or None if no data available
        """
        return self._latest_timestamp
