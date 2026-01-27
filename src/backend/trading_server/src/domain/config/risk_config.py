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

    # Pre-trade control parameters
    max_total_exposure_pct: float = TradingConstants.DEFAULT_MAX_TOTAL_EXPOSURE_PCT
    max_trades_per_minute: int = TradingConstants.DEFAULT_MAX_TRADES_PER_MINUTE
    max_trades_per_hour: int = TradingConstants.DEFAULT_MAX_TRADES_PER_HOUR
    max_leverage: float = TradingConstants.DEFAULT_MAX_LEVERAGE
    trading_hours_start: int = TradingConstants.DEFAULT_TRADING_HOURS_START
    trading_hours_end: int = TradingConstants.DEFAULT_TRADING_HOURS_END

    @classmethod
    def default(cls) -> "RiskConfig":
        """Get default configuration"""
        return cls()

    @classmethod
    def from_env(cls) -> "RiskConfig":
        """Load configuration from environment variables"""
        return cls(
            max_position_size=float(
                os.getenv(
                    "RISK_MAX_POSITION_SIZE",
                    str(TradingConstants.DEFAULT_MAX_POSITION_SIZE),
                )
            ),
            max_daily_loss=float(
                os.getenv(
                    "RISK_MAX_DAILY_LOSS", str(TradingConstants.DEFAULT_MAX_DAILY_LOSS)
                )
            ),
            max_drawdown=float(
                os.getenv(
                    "RISK_MAX_DRAWDOWN", str(TradingConstants.DEFAULT_MAX_DRAWDOWN)
                )
            ),
            stop_loss_pct=float(
                os.getenv(
                    "RISK_STOP_LOSS_PCT", str(TradingConstants.DEFAULT_STOP_LOSS_PCT)
                )
            ),
            take_profit_pct=float(
                os.getenv(
                    "RISK_TAKE_PROFIT_PCT",
                    str(TradingConstants.DEFAULT_TAKE_PROFIT_PCT),
                )
            ),
            max_open_positions=int(
                os.getenv(
                    "RISK_MAX_OPEN_POSITIONS",
                    str(TradingConstants.DEFAULT_MAX_OPEN_POSITIONS),
                )
            ),
            # Pre-trade control parameters
            max_total_exposure_pct=float(
                os.getenv(
                    "PRE_TRADE_MAX_TOTAL_EXPOSURE_PCT",
                    str(TradingConstants.DEFAULT_MAX_TOTAL_EXPOSURE_PCT),
                )
            ),
            max_trades_per_minute=int(
                os.getenv(
                    "PRE_TRADE_MAX_TRADES_PER_MINUTE",
                    str(TradingConstants.DEFAULT_MAX_TRADES_PER_MINUTE),
                )
            ),
            max_trades_per_hour=int(
                os.getenv(
                    "PRE_TRADE_MAX_TRADES_PER_HOUR",
                    str(TradingConstants.DEFAULT_MAX_TRADES_PER_HOUR),
                )
            ),
            max_leverage=float(
                os.getenv(
                    "PRE_TRADE_MAX_LEVERAGE",
                    str(TradingConstants.DEFAULT_MAX_LEVERAGE),
                )
            ),
            trading_hours_start=int(
                os.getenv(
                    "PRE_TRADE_HOURS_START",
                    str(TradingConstants.DEFAULT_TRADING_HOURS_START),
                )
            ),
            trading_hours_end=int(
                os.getenv(
                    "PRE_TRADE_HOURS_END",
                    str(TradingConstants.DEFAULT_TRADING_HOURS_END),
                )
            ),
        )
