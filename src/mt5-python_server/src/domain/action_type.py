"""
Action type enumeration for trading actions
"""
from enum import IntEnum


class ActionType(IntEnum):
    """Trading action types"""
    HOLD = 0
    BUY = 1
    SELL = 2
    CLOSE = 3
    
    @classmethod
    def from_value(cls, value: int) -> 'ActionType':
        """
        Convert integer to ActionType
        :param value: Integer value (0-3)
        :return: ActionType enum
        :raises ValueError: If value is invalid
        """
        try:
            return cls(value)
        except ValueError:
            raise ValueError(f"Invalid action type: {value}. Must be 0-3")
    
    def __str__(self) -> str:
        """Return human-readable name"""
        return self.name
    
    @property
    def is_trade_action(self) -> bool:
        """Check if action involves trading (not HOLD)"""
        return self != ActionType.HOLD
    
    @property
    def is_open_action(self) -> bool:
        """Check if action opens a position"""
        return self in (ActionType.BUY, ActionType.SELL)
    
    @property
    def is_close_action(self) -> bool:
        """Check if action closes a position"""
        return self == ActionType.CLOSE
