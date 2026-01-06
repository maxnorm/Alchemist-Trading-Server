"""
Data-related endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from datetime import datetime
from dependencies import get_db
from schemas.data import QuarantineTickResponse, QuarantineListResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/data/quarantine", response_model=QuarantineListResponse)
async def get_quarantine_ticks(
    symbol: Optional[str] = Query(None, description="Filter by currency pair symbol"),
    rejection_category: Optional[str] = Query(
        None, 
        description="Filter by rejection category (outlier, duplicate, stale, missing_data, invalid_spread)"
    ),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (datetime)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (datetime)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
):
    """
    Get quarantined ticks with optional filtering and pagination
    
    Returns ticks that were rejected by quality gates for review and analysis.
    """
    try:
        # Build query with filters
        query = "SELECT * FROM quarantine_ticks WHERE 1=1"
        count_query = "SELECT COUNT(*) as total FROM quarantine_ticks WHERE 1=1"
        params = {}
        
        if symbol:
            query += " AND symbol = :symbol"
            count_query += " AND symbol = :symbol"
            params["symbol"] = symbol
        
        if rejection_category:
            query += " AND rejection_category = :rejection_category"
            count_query += " AND rejection_category = :rejection_category"
            params["rejection_category"] = rejection_category
        
        if start_date:
            query += " AND datetime >= :start_date"
            count_query += " AND datetime >= :start_date"
            params["start_date"] = start_date
        
        if end_date:
            query += " AND datetime <= :end_date"
            count_query += " AND datetime <= :end_date"
            params["end_date"] = end_date
        
        # Get total count
        count_result = db.execute(text(count_query), params)
        total = count_result.scalar()
        
        # Add ordering and pagination
        query += " ORDER BY quarantined_at DESC, datetime DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset
        
        # Execute query
        result = db.execute(text(query), params)
        rows = result.fetchall()
        
        # Convert rows to response models
        ticks = []
        for row in rows:
            row_dict = dict(row._mapping)
            ticks.append(QuarantineTickResponse(**row_dict))
        
        # Get rejection statistics
        stats_query = """
            SELECT rejection_category, COUNT(*) as count
            FROM quarantine_ticks
            WHERE 1=1
        """
        stats_params = {}
        
        if symbol:
            stats_query += " AND symbol = :symbol"
            stats_params["symbol"] = symbol
        
        if start_date:
            stats_query += " AND datetime >= :start_date"
            stats_params["start_date"] = start_date
        
        if end_date:
            stats_query += " AND datetime <= :end_date"
            stats_params["end_date"] = end_date
        
        stats_query += " GROUP BY rejection_category"
        
        stats_result = db.execute(text(stats_query), stats_params)
        rejection_stats = {row[0]: row[1] for row in stats_result.fetchall()}
        
        return QuarantineListResponse(
            ticks=ticks,
            total=total,
            limit=limit,
            offset=offset,
            rejection_stats=rejection_stats
        )
    except Exception as e:
        logger.error(f"Error fetching quarantine ticks: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch quarantine ticks: {str(e)}"
        )
