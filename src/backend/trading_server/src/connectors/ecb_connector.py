"""
ECB (European Central Bank) connector for Eurozone economic indicators
Implements IDataSourceConnector for economic data from ECB Statistical Data Warehouse (SDW) API
(completely free, no API key required)
"""

import time
import requests
from typing import Dict, Any, Iterator, Optional, Tuple
from datetime import datetime, timedelta
from utils.logging_config import get_logger
from events.normalizer import EventNormalizer
from .base import IDataSourceConnector, ConnectorConfig
from utils.time_utils import normalize_to_utc, ensure_utc_timezone


class ECBConnector(IDataSourceConnector):
    """
    ECB connector for Eurozone economic indicators
    Uses ECB Statistical Data Warehouse (SDW) RESTful API (completely free, no API key)
    """

    # ECB SDW API base URL
    ECB_API_BASE = "https://sdw-wsrest.ecb.europa.eu/service"

    # Key ECB dataflow IDs (series codes)
    KEY_SERIES = {
        "FM.M.U2.EUR.HSTA": "ECB Interest Rate (Main Refinancing Operations)",
        "ICP.M.U2.N.000000.4.ANR": "HICP - All items (Annual rate of change)",
        "MNA.Q.Y.I8.W2.S1.S1.B.B1GQ._Z._Z._Z.EUR.LR.N": "GDP - Euro area",
        "LFSI.M.ES.S.UNEHRT.TOTAL0.15_74.T": "Unemployment Rate - Euro area",
    }

    def __init__(self, config: ConnectorConfig):
        """
        Initialize ECB connector

        :param config: Connector configuration
        """
        self.config = config
        self.normalizer = EventNormalizer()
        self.logger = get_logger("ecb_connector", "ecb_connector.log")

        self._is_connected = False
        self._latest_timestamp: Optional[datetime] = None

        # Rate limiting: be respectful to free API
        self._last_request_time = 0.0
        self._min_request_interval = 1.0  # 1 second between requests

    def connect(self) -> bool:
        """
        Establish connection to ECB API

        :return: True if connection successful, False otherwise
        """
        try:
            # Test connection by fetching a simple series
            test_series = list(self.KEY_SERIES.keys())[0]
            url = f"{self.ECB_API_BASE}/data/{test_series}?lastNObservations=1"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                self._is_connected = True
                self.logger.info("Connected to ECB API")
                return True
            else:
                self.logger.warning(
                    f"ECB API connection test returned status {response.status_code}"
                )
                return False
        except Exception as e:
            self.logger.error(f"Failed to connect to ECB API: {e}")
            return False

    def disconnect(self) -> None:
        """Close connection to ECB API"""
        self._is_connected = False
        self.logger.info("Disconnected from ECB API")

    def is_connected(self) -> bool:
        """Check if connector is currently connected"""
        return self._is_connected

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
        Fetch data for an ECB series

        :param series_id: ECB series ID (dataflow key)
        :param start_date: Start date (optional)
        :param end_date: End date (optional)
        :return: Iterator of normalized event dictionaries
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to ECB API")

        try:
            self._rate_limit()

            # Build URL with date filters
            url = f"{self.ECB_API_BASE}/data/{series_id}"
            params = []

            if start_date:
                start_str = start_date.strftime("%Y-%m-%d")
                params.append(f"startPeriod={start_str}")

            if end_date:
                end_str = end_date.strftime("%Y-%m-%d")
                params.append(f"endPeriod={end_str}")

            if params:
                url += "?" + "&".join(params)

            # Fetch data from ECB API
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Parse XML response (ECB API returns XML)
            import xml.etree.ElementTree as ET

            root = ET.fromstring(response.content)

            # ECB XML structure: GenericData -> DataSet -> Series -> Obs
            # Extract observations
            namespaces = {
                "generic": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic",
                "common": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common",
            }

            # Determine frequency from series metadata or default
            frequency = "MONTHLY"  # Most ECB series are monthly

            observations = []
            for series in root.findall(".//generic:Series", namespaces):
                for obs in series.findall("generic:Obs", namespaces):
                    # Get observation time
                    time_elem = obs.find("generic:ObsDimension", namespaces)
                    if time_elem is None:
                        continue

                    time_value = time_elem.get("value")
                    if not time_value:
                        continue

                    # Get observation value
                    value_elem = obs.find("generic:ObsValue", namespaces)
                    if value_elem is None:
                        continue

                    value = value_elem.get("value")
                    if value is None:
                        continue

                    try:
                        value_float = float(value)
                    except (ValueError, TypeError):
                        continue

                    # Parse time value (format: YYYY-MM or YYYY-MM-DD or YYYY-Q1/Q2/Q3/Q4)
                    try:
                        if "-Q" in time_value:
                            # Quarterly data
                            year, quarter = time_value.split("-Q")
                            month = (int(quarter) - 1) * 3 + 1
                            timestamp_dt = datetime(int(year), month, 1)
                            frequency = "QUARTERLY"
                        elif len(time_value) == 7:  # YYYY-MM
                            timestamp_dt = datetime.strptime(time_value, "%Y-%m")
                            frequency = "MONTHLY"
                        elif len(time_value) == 10:  # YYYY-MM-DD
                            timestamp_dt = datetime.strptime(time_value, "%Y-%m-%d")
                            frequency = "DAILY"
                        else:
                            # Try year only
                            timestamp_dt = datetime(int(time_value), 1, 1)
                            frequency = "ANNUAL"
                    except (ValueError, TypeError) as e:
                        self.logger.warning(f"Could not parse time {time_value}: {e}")
                        continue

                    observations.append((timestamp_dt, value_float))

            if not observations:
                self.logger.warning(f"No observations found for series {series_id}")
                return

            # Convert to normalized events
            for timestamp_dt, value in observations:
                # Normalize timestamp to UTC
                timestamp_utc = normalize_to_utc(timestamp_dt)

                # Create raw event
                raw_event = {
                    "timestamp": timestamp_utc,
                    "series_id": series_id,
                    "value": value,
                    "source": "ECB",
                    "country": "EU",  # Eurozone
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
                f"Error fetching ECB series {series_id}: {e}", exc_info=True
            )
            raise

    def _normalize_economic_indicator(self, raw_event: Dict) -> Dict[str, Any]:
        """
        Normalize economic indicator event to contract format

        :param raw_event: Raw ECB event dictionary
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
        Stream latest economic indicators from ECB

        :param start_time: Optional start time (defaults to last 3 months)
        :return: Iterator of normalized event dictionaries
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to ECB API")

        # For streaming, fetch latest data for all key series
        # ECB data is typically updated monthly
        if start_time is None:
            start_time = datetime.now() - timedelta(days=90)

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
        Fetch historical economic indicators from database (not implemented for ECB)

        :param start_time: Start time for historical data
        :param end_time: End time for historical data
        :return: Iterator of normalized event dictionaries
        """
        # ECB connector doesn't read from database
        # Use backfill() for historical data from ECB API
        self.logger.warning("batch() not implemented for ECB. Use backfill() instead.")
        return iter([])

    def backfill(
        self, start_time: datetime, end_time: datetime, batch_size: int = 1000
    ) -> Iterator[Dict[str, Any]]:
        """
        Fetch historical economic indicators from ECB API

        :param start_time: Start time for historical data
        :param end_time: End time for historical data
        :param batch_size: Batch size (not used, ECB handles batching)
        :return: Iterator of normalized event dictionaries
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to ECB API")

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
        Get the available data range from ECB API

        :return: Tuple of (earliest_available_time, latest_available_time)
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to ECB API")

        try:
            # Get range from first key series
            series_id = list(self.KEY_SERIES.keys())[0]
            self._rate_limit()
            url = f"{self.ECB_API_BASE}/data/{series_id}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Parse XML to get date range
            import xml.etree.ElementTree as ET

            root = ET.fromstring(response.content)
            namespaces = {
                "generic": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic",
            }

            dates = []
            for series in root.findall(".//generic:Series", namespaces):
                for obs in series.findall("generic:Obs", namespaces):
                    time_elem = obs.find("generic:ObsDimension", namespaces)
                    if time_elem is None:
                        continue

                    time_value = time_elem.get("value")
                    if not time_value:
                        continue

                    try:
                        if "-Q" in time_value:
                            year, quarter = time_value.split("-Q")
                            month = (int(quarter) - 1) * 3 + 1
                            dates.append(datetime(int(year), month, 1))
                        elif len(time_value) == 7:
                            dates.append(datetime.strptime(time_value, "%Y-%m"))
                        elif len(time_value) == 10:
                            dates.append(datetime.strptime(time_value, "%Y-%m-%d"))
                        else:
                            dates.append(datetime(int(time_value), 1, 1))
                    except (ValueError, TypeError):
                        continue

            if not dates:
                raise ValueError("No valid dates found in ECB data")

            earliest = min(dates)
            latest = max(dates)

            return (normalize_to_utc(earliest), normalize_to_utc(latest))

        except Exception as e:
            self.logger.error(f"Error getting available range from ECB: {e}")
            raise ConnectionError(f"Failed to get available range: {e}")

    def get_schema(self) -> Dict[str, Any]:
        """
        Return ECB connector schema definition

        :return: Schema dictionary
        """
        return {
            "source": "ECB",
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
