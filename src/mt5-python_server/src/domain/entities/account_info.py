"""
Account information entity
Immutable account data
"""
import dataclasses
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AccountInfo:
    """Immutable account information"""
    login: int
    currency: str
    leverage: int
    balance: float
    equity: float
    profit: float
    margin: float
    margin_free: float
    
    def update(self, **kwargs) -> 'AccountInfo':
        """
        Create updated copy with new values
        :param kwargs: Fields to update
        :return: New AccountInfo instance
        """
        return dataclasses.replace(self, **kwargs)
    
    def copy(self) -> 'AccountInfo':
        """Create a copy of this account info"""
        return dataclasses.replace(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AccountInfo':
        """
        Create AccountInfo from dictionary
        :param data: Dictionary with account data
        :return: AccountInfo instance
        """
        return cls(
            login=data.get('login', 0),
            currency=data.get('currency', 'USD'),
            leverage=data.get('leverage', 1),
            balance=data.get('balance', 0.0),
            equity=data.get('equity', 0.0),
            profit=data.get('profit', 0.0),
            margin=data.get('margin', 0.0),
            margin_free=data.get('margin_free', 0.0)
        )
