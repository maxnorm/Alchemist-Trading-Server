"""
Training configuration
"""

import os
from dataclasses import dataclass

from domain.constants import TradingConstants


@dataclass
class TrainingConfig:
    """Configuration for training"""

    decision_interval: int = TradingConstants.DEFAULT_DECISION_INTERVAL_SECONDS
    episode_duration_hours: int = TradingConstants.DEFAULT_EPISODE_DURATION_HOURS
    min_experiences_before_training: int = (
        TradingConstants.DEFAULT_MIN_EXPERIENCES_BEFORE_TRAINING
    )
    save_freq_steps: int = TradingConstants.DEFAULT_SAVE_FREQUENCY_STEPS
    training_enabled: bool = True
    trading_enabled: bool = False

    @classmethod
    def default(cls) -> "TrainingConfig":
        """Get default configuration"""
        return cls()

    @classmethod
    def from_env(cls) -> "TrainingConfig":
        """Load configuration from environment variables"""
        return cls(
            decision_interval=int(
                os.getenv(
                    "AI_DECISION_INTERVAL",
                    str(TradingConstants.DEFAULT_DECISION_INTERVAL_SECONDS),
                )
            ),
            episode_duration_hours=int(
                os.getenv(
                    "AI_EPISODE_DURATION_HOURS",
                    str(TradingConstants.DEFAULT_EPISODE_DURATION_HOURS),
                )
            ),
            min_experiences_before_training=int(
                os.getenv(
                    "AI_MIN_EXPERIENCES",
                    str(TradingConstants.DEFAULT_MIN_EXPERIENCES_BEFORE_TRAINING),
                )
            ),
            save_freq_steps=int(
                os.getenv(
                    "AI_SAVE_FREQ_STEPS",
                    str(TradingConstants.DEFAULT_SAVE_FREQUENCY_STEPS),
                )
            ),
            training_enabled=os.getenv("AI_TRAINING_ENABLED", "true").lower() == "true",
            trading_enabled=os.getenv("AI_TRADING_ENABLED", "false").lower() == "true",
        )
