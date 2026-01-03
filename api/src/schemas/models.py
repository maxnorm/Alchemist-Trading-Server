"""
Pydantic schemas for model registry
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ModelResponse(BaseModel):
    """Model details response"""

    id: int
    version: str
    experiment_id: Optional[int] = None
    stage: str
    features: List[str]
    hyperparameters: Dict[str, Any]
    metrics: Optional[Dict[str, Any]] = None
    mlflow_model_uri: Optional[str] = None
    mlflow_run_id: Optional[str] = None
    paper_trading_results: Optional[Dict[str, Any]] = None
    created_at: datetime
    promoted_at: Optional[datetime] = None
    promoted_by: Optional[int] = None

    class Config:
        from_attributes = True


class ModelListResponse(BaseModel):
    """List of models response"""

    models: List[ModelResponse]
    total: int


class ModelPromoteRequest(BaseModel):
    """Model promotion request"""

    target_stage: str = Field(
        ..., description="Target stage: staging, paper, production, archived"
    )
    totp_token: Optional[str] = Field(
        None, description="2FA token (required for production promotion)"
    )
    confirm: bool = Field(
        default=False, description="Confirmation required for promotion"
    )


class PaperSessionResponse(BaseModel):
    """Paper trading session response"""

    id: int
    model_id: int
    status: str
    start_balance: float
    current_balance: float
    total_trades: int
    winning_trades: int
    pnl: float
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    started_at: datetime
    ended_at: Optional[datetime] = None


class PaperSessionListResponse(BaseModel):
    """List of paper trading sessions"""

    sessions: List[PaperSessionResponse]
    total: int


class StartPaperSessionRequest(BaseModel):
    """Start paper trading session request"""

    start_balance: float = Field(
        10000.0, description="Starting balance for paper trading"
    )


class ValidationResultResponse(BaseModel):
    """Validation result response"""

    passed: bool
    checks: Dict[str, bool]
    metrics: Dict[str, float]
    messages: List[str]
