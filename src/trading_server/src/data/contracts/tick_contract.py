"""
Tick data contract validator
Validates tick data against schema contract v1.0.0
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from .base import IContractValidator
from utils.market_utils import infer_pip_value_from_price


class TickContractValidator(IContractValidator):
    """
    Validator for tick data contract v1.0.0
    Validates structure, types, formats, and constraints for tick data
    """

    CONTRACT_VERSION = "1.0.0"
    DATA_TYPE = "tick"

    # Required fields
    REQUIRED_FIELDS = ["symbol", "datetime", "bid", "ask"]

    # Optional fields with defaults
    OPTIONAL_FIELDS = [
        "receive_time",
        "latency_seconds",
        "is_stale",
        "stale_age_seconds",
        "timestamp_source",
        "volume",
    ]

    def get_contract_version(self) -> str:
        """Return contract version"""
        return self.CONTRACT_VERSION

    def get_data_type(self) -> str:
        """Return data type identifier"""
        return self.DATA_TYPE

    def validate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate tick data against contract

        :param data: Tick data dictionary
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

        # Validate bid type and constraints
        bid_error = self.validate_field_type(data["bid"], float, "bid")
        if bid_error:
            return False, bid_error

        try:
            bid = float(data["bid"])
            if bid <= 0:
                return False, "Field 'bid' must be positive"
        except (ValueError, TypeError):
            return False, "Field 'bid' must be a number"

        # Validate ask type and constraints
        ask_error = self.validate_field_type(data["ask"], float, "ask")
        if ask_error:
            return False, ask_error

        try:
            ask = float(data["ask"])
            if ask <= 0:
                return False, "Field 'ask' must be positive"
        except (ValueError, TypeError):
            return False, "Field 'ask' must be a number"

        # Validate spread
        spread = ask - bid
        if spread <= 0:
            return False, "Invalid spread: ask must be greater than bid"

        # Infer pip value from price (more maintainable than hardcoding currencies)
        mid_price = (bid + ask) / 2
        pip_value = infer_pip_value_from_price(mid_price)

        # Maximum spread: 100 pips (reasonable for most market conditions)
        max_spread_pips = 100
        max_spread_value = pip_value * max_spread_pips

        if spread > max_spread_value:
            spread_pips = spread / pip_value
            return (
                False,
                f"Unrealistic spread: {spread:.6f} ({spread_pips:.1f} pips > {max_spread_pips} pips)",
            )

        # Validate optional receive_time
        if "receive_time" in data and data["receive_time"] is not None:
            receive_time_error = self.validate_datetime_utc(
                data["receive_time"], "receive_time"
            )
            if receive_time_error:
                return False, receive_time_error

            # Validate timestamp ordering
            if isinstance(data["datetime"], datetime) and isinstance(
                data["receive_time"], datetime
            ):
                if data["receive_time"] < data["datetime"]:
                    return False, "receive_time must be >= datetime"

        # Validate optional latency_seconds
        if "latency_seconds" in data and data["latency_seconds"] is not None:
            latency_error = self.validate_field_type(
                data["latency_seconds"], int, "latency_seconds"
            )
            if latency_error:
                return False, latency_error

            try:
                latency = int(data["latency_seconds"])
                if latency < 0:
                    return False, "Field 'latency_seconds' must be >= 0"
            except (ValueError, TypeError):
                return False, "Field 'latency_seconds' must be an integer"

        # Validate optional is_stale
        if "is_stale" in data and data["is_stale"] is not None:
            stale_error = self.validate_field_type(data["is_stale"], bool, "is_stale")
            if stale_error:
                return False, stale_error

        # Validate optional stale_age_seconds
        if "stale_age_seconds" in data and data["stale_age_seconds"] is not None:
            stale_age_error = self.validate_field_type(
                data["stale_age_seconds"], int, "stale_age_seconds"
            )
            if stale_age_error:
                return False, stale_age_error

            try:
                stale_age = int(data["stale_age_seconds"])
                if stale_age < 0:
                    return False, "Field 'stale_age_seconds' must be >= 0"
            except (ValueError, TypeError):
                return False, "Field 'stale_age_seconds' must be an integer"

        # Validate optional timestamp_source
        if "timestamp_source" in data and data["timestamp_source"] is not None:
            if not isinstance(data["timestamp_source"], str):
                return False, "Field 'timestamp_source' must be a string"

            valid_sources = ["event", "receive", "estimated"]
            if data["timestamp_source"] not in valid_sources:
                return (
                    False,
                    f"Field 'timestamp_source' must be one of {valid_sources}, got '{data['timestamp_source']}'",
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

        # All validations passed
        return True, None
