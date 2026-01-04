from abc import ABC, abstractmethod
from typing import Any, List, Optional
from dataclasses import dataclass
import pandas as pd


@dataclass
class Feature:
    """Feature metadata for data providers"""

    name: str  # Unique feature identifier
    data_type: type  # Python type (float, int, str, etc.)
    source: str  # Provider name
    description: str  # Human-readable description
    category: Optional[str] = (
        None  # Feature category (price, technical, economic, etc.)
    )

    def __post_init__(self):
        """Validate feature data"""
        if not self.name:
            raise ValueError("Feature name cannot be empty")
        if not self.source:
            raise ValueError("Feature source cannot be empty")


class DataProvider(ABC):
    """Base class for all data providers"""

    @abstractmethod
    def get_current_data(self):
        """Return current data in standardized json format"""
        pass

    @abstractmethod
    def subscribe(self, callback):
        """Subscribe to data updates"""
        pass

    @abstractmethod
    def get_features(self) -> List[Feature]:
        """
        Return list of features this provider offers.

        Each provider must declare all features it provides with metadata.
        This enables auto-discovery and feature catalog population.

        :return: List of Feature objects with metadata
        """
        pass

    def collect_historical(self, start: Any, end: Any) -> Optional[pd.DataFrame]:
        """
        Optional method to collect historical data for backtesting.

        :param start: Start timestamp/date
        :param end: End timestamp/date
        :return: DataFrame with historical data, or None if not supported
        """
        return None
