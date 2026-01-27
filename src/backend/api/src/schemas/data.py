"""
Data-related response schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime as dt


class QuarantineTickResponse(BaseModel):
    """Response schema for a quarantined tick"""

    id: int
    symbol: str
    datetime: dt
    receive_time: Optional[dt] = None
    bid: float
    ask: float
    rejection_reason: str
    rejection_category: str
    quarantined_at: dt

    class Config:
        from_attributes = True


class QuarantineListResponse(BaseModel):
    """Response schema for quarantine list with pagination"""

    ticks: List[QuarantineTickResponse]
    total: int
    limit: int
    offset: int
    rejection_stats: dict = Field(
        default_factory=dict, description="Count of rejections by category"
    )
