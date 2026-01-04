"""
Pydantic schemas for Optuna hyperparameter search
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class OptunaSearchCreate(BaseModel):
    """Optuna search creation request"""

    experiment_id: int
    study_name: str = Field(..., min_length=1, max_length=200)
    n_trials: int = Field(..., gt=0, le=1000)
    optimize_metric: str = Field(default="sharpe_ratio")
    direction: str = Field(default="maximize", pattern="^(maximize|minimize)$")


class OptunaStudyResponse(BaseModel):
    """Optuna study response"""

    id: int
    experiment_id: int
    study_name: str
    n_trials: int
    optimize_metric: str
    direction: str
    status: str
    best_trial_number: Optional[int] = None
    best_value: Optional[float] = None
    best_params: Optional[Dict[str, Any]] = None
    param_importance: Optional[Dict[str, float]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TrialResponse(BaseModel):
    """Optuna trial response"""

    id: int
    study_id: int
    trial_number: int
    params: Dict[str, Any]
    value: Optional[float] = None
    state: str
    metrics: Optional[Dict[str, Any]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ParameterImportanceResponse(BaseModel):
    """Parameter importance response"""

    study_id: int
    importance: Dict[str, float]
