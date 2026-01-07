"""
Base connector interface for data sources
Defines unified interface enabling plug-and-play data sources
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Iterator, Optional
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class ConnectorConfig:
    """
    Configuration for data source connectors

    :param source: Source identifier (e.g., "mt5", "api")
    :param symbol: Trading symbol (e.g., "EURUSD")
    :param batch_size: Batch size for historical data fetching
    :param timeout: Connection timeout in seconds
    :param retry_count: Number of retry attempts on failure
    :param extra_config: Additional source-specific configuration
    """

    source: str
    symbol: str
    batch_size: int = 1000
    timeout: float = 30.0
    retry_count: int = 3
    extra_config: Dict[str, Any] = field(default_factory=dict)


class IDataSourceConnector(ABC):
    """
    Unified interface for data source connectors
    All connectors must implement this interface to enable plug-and-play data sources

    All methods return normalized events (canonical format).
    Connectors handle their own normalization internally.
    """

    @abstractmethod
    def stream(self, start_time: Optional[datetime] = None) -> Iterator[Dict[str, Any]]:
        """
        Stream events in real-time, yielding normalized events

        :param start_time: Optional start time for streaming (if None, streams from now)
        :return: Iterator of normalized event dictionaries
        :raises ConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def batch(
        self, start_time: datetime, end_time: datetime
    ) -> Iterator[Dict[str, Any]]:
        """
        Fetch historical data in batches, yielding normalized events

        :param start_time: Start time for historical data
        :param end_time: End time for historical data
        :return: Iterator of normalized event dictionaries
        :raises ValueError: If start_time >= end_time
        :raises ConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """
        Return source schema definition

        :return: Schema dictionary describing the source's event structure
        """
        pass

    @abstractmethod
    def get_latest_timestamp(self) -> Optional[datetime]:
        """
        Get timestamp of most recent data available

        :return: Datetime of most recent data, or None if no data available
        """
        pass

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to data source

        :return: True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Close connection to data source
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if connector is currently connected

        :return: True if connected, False otherwise
        """
        pass
