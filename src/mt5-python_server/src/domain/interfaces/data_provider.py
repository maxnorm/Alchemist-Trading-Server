"""
Data provider protocol
Defines contract for data providers
"""

from typing import Protocol, Dict, Any, Callable


class IDataProvider(Protocol):
    """Protocol for data providers"""

    def get_current_data(self) -> Dict[str, Any]:
        """
        Get current data in standardized format
        :return: Dictionary with current data
        """
        ...

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Subscribe to data updates
        :param callback: Callback function to receive updates
        """
        ...
