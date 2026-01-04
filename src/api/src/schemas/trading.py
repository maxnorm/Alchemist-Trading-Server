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
    open_positions: int
    total_pnl: Optional[float] = None
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
    loss_threshold: Optional[float] = None
    current_loss: Optional[float] = None
    activated_at: Optional[datetime] = None


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
    status: str


class TradeHistoryResponse(BaseModel):
    """Trade history response"""

    trades: List[PositionResponse]
    total: int


class CurrencyPairsResponse(BaseModel):
    """Currency pairs response"""

    pairs: List[str]
    total: int
