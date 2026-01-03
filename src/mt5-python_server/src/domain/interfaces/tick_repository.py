"""
Tick repository protocol
Defines contract for tick data repositories
"""

from typing import Protocol, List, Dict, Any, Optional
from datetime import datetime


class ITickRepository(Protocol):
    """Protocol for tick data repositories"""

    def save_ticks(self, ticks: List[Dict[str, Any]]) -> None:
        """
        Save tick data
        :param ticks: List of tick dictionaries
        """
        ...

    def get_recent_ticks(
        self, symbol: str, hours: int = 24, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent tick data for a symbol
        :param symbol: Currency pair symbol
        :param hours: Number of hours to look back
        :param limit: Maximum number of ticks to return
        :return: List of tick dictionaries
        """
        ...

    def get_ticks_between(
        self, symbol: str, start_time: datetime, end_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get ticks between two timestamps
        :param symbol: Currency pair symbol
        :param start_time: Start timestamp
        :param end_time: End timestamp
        :return: List of tick dictionaries
        """
        ...
