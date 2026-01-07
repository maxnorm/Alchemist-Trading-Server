"""
Bar/OHLCV data contract validator
Validates bar data against schema contract v1.0.0
"""

from typing import Dict, Any, Optional, Tuple
from .base import IContractValidator


class BarContractValidator(IContractValidator):
    """
    Validator for bar data contract v1.0.0
    Validates structure, types, formats, and constraints for OHLCV bar data
    """

    CONTRACT_VERSION = "1.0.0"
    DATA_TYPE = "bar"

    # Required fields
    REQUIRED_FIELDS = [
        "symbol",
        "datetime",
        "open",
        "high",
        "low",
        "close",
        "timeframe",
    ]

    # Optional fields
    OPTIONAL_FIELDS = ["volume", "receive_time"]

    # Valid timeframes
    VALID_TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]

    def get_contract_version(self) -> str:
        """Return contract version"""
        return self.CONTRACT_VERSION

    def get_data_type(self) -> str:
        """Return data type identifier"""
        return self.DATA_TYPE

    def validate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate bar data against contract

        :param data: Bar data dictionary
        :return: Tuple of (is_valid, error_message)
        """
        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in data or data[field] is None:
                return False, f"Missing required field: {field}"

        # Validate symbol format
        symbol_error = self.validate_symbol_format(data["symbol"])
        if symbol_error:
            return False, symbol_error

        # Validate datetime
        datetime_error = self.validate_datetime_utc(data["datetime"], "datetime")
        if datetime_error:
            return False, datetime_error

        # Validate OHLC fields
        ohlc_fields = ["open", "high", "low", "close"]
        ohlc_values = {}

        for field in ohlc_fields:
            error = self.validate_field_type(data[field], float, field)
            if error:
                return False, error

            try:
                value = float(data[field])
                if value <= 0:
                    return False, f"Field '{field}' must be positive"
                ohlc_values[field] = value
            except (ValueError, TypeError):
                return False, f"Field '{field}' must be a number"

        # Validate OHLC consistency
        high = ohlc_values["high"]
        low = ohlc_values["low"]
        open_price = ohlc_values["open"]
        close_price = ohlc_values["close"]

        if high < low:
            return False, "Invalid OHLC: high must be >= low"

        if high < max(open_price, close_price):
            return False, "Invalid OHLC: high must be >= max(open, close)"

        if low > min(open_price, close_price):
            return False, "Invalid OHLC: low must be <= min(open, close)"

        # Validate timeframe
        if not isinstance(data["timeframe"], str):
            return False, "Field 'timeframe' must be a string"

        if data["timeframe"] not in self.VALID_TIMEFRAMES:
            return (
                False,
                f"Field 'timeframe' must be one of {self.VALID_TIMEFRAMES}, got '{data['timeframe']}'",
            )

        # Validate optional volume
        if "volume" in data and data["volume"] is not None:
            volume_error = self.validate_field_type(data["volume"], float, "volume")
            if volume_error:
                return False, volume_error

            try:
                volume = float(data["volume"])
                if volume < 0:
                    return False, "Field 'volume' must be >= 0"
            except (ValueError, TypeError):
                return False, "Field 'volume' must be a number"

        # Validate optional receive_time
        if "receive_time" in data and data["receive_time"] is not None:
            receive_time_error = self.validate_datetime_utc(
                data["receive_time"], "receive_time"
            )
            if receive_time_error:
                return False, receive_time_error

        # All validations passed
        return True, None
