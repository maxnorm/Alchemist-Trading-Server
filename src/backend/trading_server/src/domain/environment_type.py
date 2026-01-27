"""
Environment type enumeration for trading environments
"""

from enum import Enum


class EnvironmentType(str, Enum):
    """Trading environment types"""

    LIVE = "live"
    PAPER = "paper"
    HISTORICAL = "historical"

    def __str__(self) -> str:
        """Return human-readable name"""
        return self.value

    @classmethod
    def from_string(cls, value: str) -> "EnvironmentType":
        """
        Convert string to EnvironmentType
        :param value: String value ("live", "paper", "historical")
        :return: EnvironmentType enum
        :raises ValueError: If value is invalid
        """
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(
                f"Invalid environment type: {value}. Must be one of: {', '.join([e.value for e in cls])}"
            )
