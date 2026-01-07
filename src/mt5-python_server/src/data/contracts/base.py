"""
Base classes for schema contract validation
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import pytz


class ContractValidationError(Exception):
    """Exception raised when contract validation fails"""

    pass


class IContractValidator(ABC):
    """
    Base interface for all contract validators
    Each data type implements this interface to provide validation
    """

    @abstractmethod
    def validate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate data against contract

        :param data: Data dictionary to validate
        :return: Tuple of (is_valid, error_message)
        """
        pass

    @abstractmethod
    def get_contract_version(self) -> str:
        """
        Return contract version

        :return: Semantic version string (e.g., "1.0.0")
        """
        pass

    @abstractmethod
    def get_data_type(self) -> str:
        """
        Return data type identifier

        :return: Data type string (e.g., "tick", "bar")
        """
        pass

    def validate_field_type(
        self, value: Any, expected_type: type, field_name: str
    ) -> Optional[str]:
        """
        Validate field type

        :param value: Field value
        :param expected_type: Expected Python type
        :param field_name: Field name for error message
        :return: Error message if invalid, None otherwise
        """
        if value is None:
            return None  # None is handled by required field check

        # Handle type checking with conversions
        if expected_type == float:
            try:
                float(value)
            except (ValueError, TypeError):
                return (
                    f"Field '{field_name}' must be a number, got {type(value).__name__}"
                )
        elif expected_type == int:
            try:
                int(value)
            except (ValueError, TypeError):
                return f"Field '{field_name}' must be an integer, got {type(value).__name__}"
        elif expected_type == str:
            if not isinstance(value, str):
                return (
                    f"Field '{field_name}' must be a string, got {type(value).__name__}"
                )
        elif expected_type == bool:
            if not isinstance(value, bool):
                return f"Field '{field_name}' must be a boolean, got {type(value).__name__}"
        elif expected_type == datetime:
            if not isinstance(value, datetime):
                return f"Field '{field_name}' must be a datetime, got {type(value).__name__}"
        else:
            if not isinstance(value, expected_type):
                return f"Field '{field_name}' must be {expected_type.__name__}, got {type(value).__name__}"

        return None

    def validate_datetime_utc(self, dt: Any, field_name: str) -> Optional[str]:
        """
        Validate datetime is UTC and timezone-aware

        :param dt: Datetime value
        :param field_name: Field name for error message
        :return: Error message if invalid, None otherwise
        """
        if dt is None:
            return None

        if not isinstance(dt, datetime):
            return f"Field '{field_name}' must be a datetime object"

        if dt.tzinfo is None:
            return f"Field '{field_name}' must be timezone-aware"

        # Check if it's UTC (or can be normalized to UTC)
        try:
            dt.astimezone(pytz.UTC)  # If conversion succeeds, it's valid
        except Exception as e:
            return f"Field '{field_name}' has invalid timezone: {e}"

        return None

    def validate_symbol_format(self, symbol: str) -> Optional[str]:
        """
        Validate currency pair symbol format

        :param symbol: Symbol string
        :return: Error message if invalid, None otherwise
        """
        if not isinstance(symbol, str):
            return "Symbol must be a string"

        symbol_upper = symbol.upper().strip()

        if len(symbol_upper) != 6:
            return f"Symbol must be exactly 6 characters, got '{symbol}' ({len(symbol_upper)} chars)"

        if not symbol_upper.isalpha():
            return f"Symbol must contain only letters, got '{symbol}'"

        return None
