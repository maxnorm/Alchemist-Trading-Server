"""
Agent configuration
"""
import os
from dataclasses import dataclass

from domain.constants import TradingConstants


@dataclass
class AgentConfig:
    """Configuration for DQN agent"""
    learning_rate: float = TradingConstants.DEFAULT_LEARNING_RATE
    discount_factor: float = TradingConstants.DEFAULT_DISCOUNT_FACTOR
    epsilon: float = TradingConstants.DEFAULT_EPSILON
    epsilon_min: float = TradingConstants.DEFAULT_EPSILON_MIN
    epsilon_decay: float = TradingConstants.DEFAULT_EPSILON_DECAY
    memory_size: int = TradingConstants.DEFAULT_MEMORY_SIZE
    batch_size: int = TradingConstants.DEFAULT_BATCH_SIZE
    target_update_freq: int = TradingConstants.DEFAULT_TARGET_UPDATE_FREQ
    use_double_dqn: bool = True
    
    @classmethod
    def default(cls) -> 'AgentConfig':
        """Get default configuration"""
        return cls()
    
    @classmethod
    def for_live_trading(cls) -> 'AgentConfig':
        """Get configuration optimized for live trading"""
        return cls(
            epsilon=TradingConstants.DEFAULT_LIVE_EPSILON,
            epsilon_decay=TradingConstants.DEFAULT_LIVE_EPSILON_DECAY
        )
    
    @classmethod
    def from_env(cls) -> 'AgentConfig':
        """Load configuration from environment variables"""
        return cls(
            learning_rate=float(os.getenv('AI_LEARNING_RATE', str(TradingConstants.DEFAULT_LEARNING_RATE))),
            discount_factor=float(os.getenv('AI_DISCOUNT_FACTOR', str(TradingConstants.DEFAULT_DISCOUNT_FACTOR))),
            epsilon=float(os.getenv('AI_EPSILON', str(TradingConstants.DEFAULT_EPSILON))),
            epsilon_min=float(os.getenv('AI_EPSILON_MIN', str(TradingConstants.DEFAULT_EPSILON_MIN))),
            epsilon_decay=float(os.getenv('AI_EPSILON_DECAY', str(TradingConstants.DEFAULT_EPSILON_DECAY))),
            memory_size=int(os.getenv('AI_MEMORY_SIZE', str(TradingConstants.DEFAULT_MEMORY_SIZE))),
            batch_size=int(os.getenv('AI_BATCH_SIZE', str(TradingConstants.DEFAULT_BATCH_SIZE))),
            target_update_freq=int(os.getenv('AI_TARGET_UPDATE_FREQ', str(TradingConstants.DEFAULT_TARGET_UPDATE_FREQ))),
            use_double_dqn=os.getenv('AI_USE_DOUBLE_DQN', 'true').lower() == 'true'
        )
