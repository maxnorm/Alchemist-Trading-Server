"""
Risk manager factory
Creates risk managers with proper configuration
"""

from typing import Optional

from utils.risk_management import RiskManager
from domain.config.risk_config import RiskConfig


class RiskManagerFactory:
    """Factory for creating risk managers"""

    @staticmethod
    def create_risk_manager(config: Optional[RiskConfig] = None) -> RiskManager:
        """
        Create a risk manager
        :param config: Risk configuration (uses default if not provided)
        :return: Configured risk manager
        """
        # Use provided config or default
        if config is None:
            config = RiskConfig.default()

        # Create risk manager with configuration
        return RiskManager(
            max_position_size=config.max_position_size,
            max_daily_loss=config.max_daily_loss,
            max_drawdown=config.max_drawdown,
            stop_loss_pct=config.stop_loss_pct,
            take_profit_pct=config.take_profit_pct,
            max_open_positions=config.max_open_positions,
        )
