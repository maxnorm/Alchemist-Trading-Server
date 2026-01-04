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
