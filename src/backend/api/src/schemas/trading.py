"""
Pydantic schemas for trading control
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class TradingStatusResponse(BaseModel):
    """Trading status response"""

    is_active: bool
    active_experiments: List[int]
    open_positions: int  # Keep for backward compatibility
    active_positions: int  # Alias for dashboard compatibility
    total_pnl: Optional[float] = None
    total_equity: Optional[float] = None  # Total equity across all accounts
    total_balance: Optional[float] = None  # Total balance across all accounts
    kill_switch_active: bool
    circuit_breaker_active: bool


class KillSwitchStatusResponse(BaseModel):
    """Kill switch status response"""

    is_active: bool
    reason: Optional[str] = None
    activated_at: Optional[datetime] = None


class CircuitBreakerStatusResponse(BaseModel):
    """Circuit breaker status response"""

    is_active: bool
    reason: Optional[str] = None
    breaker_type: Optional[str] = None  # Alias for reason, for dashboard compatibility
    loss_threshold: Optional[float] = None
    threshold_value: Optional[float] = None  # Alias for loss_threshold
    current_loss: Optional[float] = None
    trigger_value: Optional[float] = None  # Alias for current_loss
    activated_at: Optional[datetime] = None
    triggered_at: Optional[datetime] = None  # Alias for activated_at


class PositionResponse(BaseModel):
    """Position response"""

    id: int
    experiment_id: int
    account_login: int
    symbol: str
    order_type: str
    entry_price: float
    volume: float
    pnl: Optional[float] = None
    entry_time: datetime
    opened_at: Optional[str] = None  # ISO format string for dashboard compatibility
    status: str
    current_price: Optional[float] = None  # Current market price
    unrealized_pnl: Optional[float] = None  # Unrealized P&L
    unrealized_pnl_pct: Optional[float] = None  # Unrealized P&L percentage


class TradeHistoryResponse(BaseModel):
    """Trade history response"""

    trades: List[PositionResponse]
    total: int


class CurrencyPairsResponse(BaseModel):
    """Currency pairs response"""

    pairs: List[str]
    total: int
