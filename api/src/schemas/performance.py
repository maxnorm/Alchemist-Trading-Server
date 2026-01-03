"""
Pydantic schemas for performance metrics
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class EquityCurvePoint(BaseModel):
    """Equity curve data point"""

    timestamp: datetime
    balance: float
    equity: float


class EquityCurveResponse(BaseModel):
    """Equity curve response"""

    experiment_id: Optional[int] = None
    model_version: Optional[str] = None
    data: List[EquityCurvePoint]
    total_points: int


class PortfolioPerformanceResponse(BaseModel):
    """Portfolio performance summary"""

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_pnl_pct: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    profit_factor: Optional[float] = None
    expectancy: Optional[float] = None
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


class ModelPerformanceResponse(BaseModel):
    """Model performance details"""

    model_version: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    paper_trading_pnl: Optional[float] = None
    live_trading_pnl: Optional[float] = None


class TradeHistoryResponse(BaseModel):
    """Trade history response"""

    trades: List[Dict[str, Any]]
    total: int


class PerformanceBreakdownResponse(BaseModel):
    """P&L breakdown by period"""

    period: str
    pnl: float
    trades: int
    win_rate: float


class AllocationResponse(BaseModel):
    """Allocation by pair/model"""

    by_pair: Dict[str, float]
    by_model: Dict[str, float]
