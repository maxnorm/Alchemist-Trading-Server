"""
Feature catalog endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from dependencies import get_db
from services import feature_service
from services.feature_service import (
    get_feature_by_name,
    get_data_source_health,
)
from schemas.features import FeatureResponse, FeatureListResponse, DataSourceResponse

router = APIRouter()


@router.get("/features", response_model=FeatureListResponse)
async def list_features(
    source: Optional[str] = Query(None, description="Filter by data source"),
    category: Optional[str] = Query(None, description="Filter by category"),
    db: Session = Depends(get_db),
):
    """List all available features"""
    try:
        features = feature_service.get_all_features(
            db, source=source, category=category
        )
        return FeatureListResponse(features=features, total=len(features))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch features: {str(e)}"
        )


@router.get("/features/{name}", response_model=FeatureResponse)
async def get_feature(name: str, db: Session = Depends(get_db)):
    """Get feature details by name"""
    feature = get_feature_by_name(db, name)
    if not feature:
        raise HTTPException(status_code=404, detail=f"Feature '{name}' not found")
    return feature


@router.get("/features/sources", response_model=List[DataSourceResponse])
async def list_data_sources(db: Session = Depends(get_db)):
    """List all data sources"""
    try:
        sources = feature_service.get_all_data_sources(db)
        return sources
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch data sources: {str(e)}"
        )


@router.get("/features/sources/{id}/health", response_model=DataSourceResponse)
async def get_source_health(id: int, db: Session = Depends(get_db)):
    """Get data source health status"""
    source = get_data_source_health(db, id)
    if not source:
        raise HTTPException(
            status_code=404, detail=f"Data source with id {id} not found"
        )
    return source
