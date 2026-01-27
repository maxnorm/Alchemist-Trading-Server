"""
Execution context value object
Immutable context for action execution
"""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from models.account import Account
from models.currency_pair import CurrencyPair
from environments.live_env import LiveTradingEnv
from utils.risk_management import RiskManager

if TYPE_CHECKING:
    from performance import TradeLogger


@dataclass(frozen=True)
class ExecutionContext:
    """
    Immutable value object representing execution context for actions
    """

    account: Account
    pair: CurrencyPair
    environment: LiveTradingEnv
    risk_manager: RiskManager
    previous_balance: float
    has_position: bool
    trading_enabled: bool = False
    # Performance tracking (optional - set when model is assigned to account)
    model_id: Optional[int] = None
    session_id: Optional[int] = None
    trade_logger: Optional["TradeLogger"] = None

    @property
    def current_balance(self) -> float:
        """Get current account balance"""
        return self.account.balance if self.account else 0.0

    @property
    def balance_change(self) -> float:
        """Calculate balance change since previous state"""
        return self.current_balance - self.previous_balance

    @property
    def can_trade(self) -> tuple[bool, str]:
        """Check if trading is allowed"""
        if not self.trading_enabled:
            return False, "Trading is disabled"
        return self.risk_manager.can_trade(self.account)

    @property
    def position_count(self) -> int:
        """Get number of open positions"""
        return len(self.account.current_trade) if self.account else 0
