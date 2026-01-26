"""
Pydantic schemas for experiments
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ExperimentCreate(BaseModel):
    """Experiment creation request"""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    features: List[str] = Field(..., min_length=1)
    currency_pairs: List[str] = Field(..., min_length=1)
    training_mode: str = Field(..., pattern="^(live|paper|historical)$")
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)


class ExperimentStartRequest(BaseModel):
    """Start experiment request"""

    confirm: bool = Field(default=False, description="Confirmation required to start")


class ExperimentResponse(BaseModel):
    """Experiment details response"""

    id: int
    name: str
    description: Optional[str] = None
    features: List[str]
    currency_pairs: List[str]
    training_mode: str
    hyperparameters: Dict[str, Any]
    status: str
    mlflow_run_id: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ExperimentListResponse(BaseModel):
    """List of experiments response"""

    experiments: List[ExperimentResponse]
    total: int
