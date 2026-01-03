"""
Trade request value object
Immutable data container for trade execution requests
"""

from dataclasses import dataclass
from typing import Optional

from domain.action_type import ActionType
from models.account import Account
from models.currency_pair import CurrencyPair


@dataclass(frozen=True)
class TradeRequest:
    """
    Immutable value object representing a trade request
    """

    account: Account
    pair: CurrencyPair
    action_type: ActionType
    entry_price: float
    lot_size: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    def __post_init__(self):
        """Validate trade request data"""
        if self.lot_size <= 0:
            raise ValueError(f"Lot size must be positive, got {self.lot_size}")

        if self.entry_price <= 0:
            raise ValueError(f"Entry price must be positive, got {self.entry_price}")

        if self.stop_loss is not None and self.stop_loss <= 0:
            raise ValueError(f"Stop loss must be positive, got {self.stop_loss}")

        if self.take_profit is not None and self.take_profit <= 0:
            raise ValueError(f"Take profit must be positive, got {self.take_profit}")

        # Validate stop loss and take profit relative to entry price
        if self.action_type == ActionType.BUY:
            if self.stop_loss is not None and self.stop_loss >= self.entry_price:
                raise ValueError("Stop loss for BUY must be below entry price")
            if self.take_profit is not None and self.take_profit <= self.entry_price:
                raise ValueError("Take profit for BUY must be above entry price")
        elif self.action_type == ActionType.SELL:
            if self.stop_loss is not None and self.stop_loss <= self.entry_price:
                raise ValueError("Stop loss for SELL must be above entry price")
            if self.take_profit is not None and self.take_profit >= self.entry_price:
                raise ValueError("Take profit for SELL must be below entry price")

    @property
    def is_long(self) -> bool:
        """Check if this is a long position (BUY)"""
        return self.action_type == ActionType.BUY

    @property
    def is_short(self) -> bool:
        """Check if this is a short position (SELL)"""
        return self.action_type == ActionType.SELL
