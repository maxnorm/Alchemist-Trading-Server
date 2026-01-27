"""
Environment configuration
"""

import os
from dataclasses import dataclass

from domain.constants import TradingConstants


@dataclass
class EnvironmentConfig:
    """Configuration for trading environment"""

    window_size: int = TradingConstants.DEFAULT_WINDOW_SIZE
    features_per_pair: int = TradingConstants.DEFAULT_FEATURES_PER_PAIR
    normalization_method: str = "robust"

    def __post_init__(self):
        """Validate configuration parameters"""
        # Validate window_size
        if not (10 <= self.window_size <= 500):
            raise ValueError(
                f"window_size must be between 10 and 500, got {self.window_size}"
            )

        # Validate features_per_pair
        if not (1 <= self.features_per_pair <= 100):
            raise ValueError(
                f"features_per_pair must be between 1 and 100, got {self.features_per_pair}"
            )

        # Validate normalization_method
        valid_methods = {"standard", "minmax", "robust"}
        if self.normalization_method not in valid_methods:
            raise ValueError(
                f"normalization_method must be one of {valid_methods}, got {self.normalization_method}"
            )

    @classmethod
    def default(cls) -> "EnvironmentConfig":
        """Get default configuration"""
        return cls()

    @classmethod
    def from_env(cls) -> "EnvironmentConfig":
        """Load configuration from environment variables"""
        return cls(
            window_size=int(
                os.getenv("ENV_WINDOW_SIZE", str(TradingConstants.DEFAULT_WINDOW_SIZE))
            ),
            features_per_pair=int(
                os.getenv(
                    "ENV_FEATURES_PER_PAIR",
                    str(TradingConstants.DEFAULT_FEATURES_PER_PAIR),
                )
            ),
            normalization_method=os.getenv("ENV_NORMALIZATION_METHOD", "robust"),
        )
