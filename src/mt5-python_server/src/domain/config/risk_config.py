"""
Risk management configuration
"""
import os
from dataclasses import dataclass

from domain.constants import TradingConstants


@dataclass
class RiskConfig:
    """Configuration for risk management"""
    max_position_size: float = TradingConstants.DEFAULT_MAX_POSITION_SIZE
    max_daily_loss: float = TradingConstants.DEFAULT_MAX_DAILY_LOSS
    max_drawdown: float = TradingConstants.DEFAULT_MAX_DRAWDOWN
    stop_loss_pct: float = TradingConstants.DEFAULT_STOP_LOSS_PCT
    take_profit_pct: float = TradingConstants.DEFAULT_TAKE_PROFIT_PCT
    max_open_positions: int = TradingConstants.DEFAULT_MAX_OPEN_POSITIONS
    
    @classmethod
    def default(cls) -> 'RiskConfig':
        """Get default configuration"""
        return cls()
    
    @classmethod
    def from_env(cls) -> 'RiskConfig':
        """Load configuration from environment variables"""
        return cls(
            max_position_size=float(os.getenv('RISK_MAX_POSITION_SIZE', str(TradingConstants.DEFAULT_MAX_POSITION_SIZE))),
            max_daily_loss=float(os.getenv('RISK_MAX_DAILY_LOSS', str(TradingConstants.DEFAULT_MAX_DAILY_LOSS))),
            max_drawdown=float(os.getenv('RISK_MAX_DRAWDOWN', str(TradingConstants.DEFAULT_MAX_DRAWDOWN))),
            stop_loss_pct=float(os.getenv('RISK_STOP_LOSS_PCT', str(TradingConstants.DEFAULT_STOP_LOSS_PCT))),
            take_profit_pct=float(os.getenv('RISK_TAKE_PROFIT_PCT', str(TradingConstants.DEFAULT_TAKE_PROFIT_PCT))),
            max_open_positions=int(os.getenv('RISK_MAX_OPEN_POSITIONS', str(TradingConstants.DEFAULT_MAX_OPEN_POSITIONS)))
        )
