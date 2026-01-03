"""
Pydantic schemas for feature catalog
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class FeatureResponse(BaseModel):
    """Feature details response"""

    id: int
    name: str
    data_type: str
    source: str
    description: Optional[str] = None
    category: Optional[str] = None
    is_available: bool = True
    statistics: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FeatureListResponse(BaseModel):
    """List of features response"""

    features: List[FeatureResponse]
    total: int


class DataSourceResponse(BaseModel):
    """Data source information"""

    id: int
    name: str
    provider_class: str
    is_enabled: bool = True
    health_status: str = "unknown"
    last_health_check: Optional[datetime] = None
    config: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True
