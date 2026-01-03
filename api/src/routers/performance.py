"""
Performance metrics endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from dependencies import get_db
from services import performance_service
from schemas.performance import (
    PortfolioPerformanceResponse,
    EquityCurveResponse,
    ModelPerformanceResponse,
    PerformanceBreakdownResponse,
    AllocationResponse,
    TradeHistoryResponse
)

router = APIRouter()


@router.get("/performance/portfolio", response_model=PortfolioPerformanceResponse)
async def get_portfolio_performance(
    start_date: Optional[datetime] = Query(None, description="Start date for period"),
    end_date: Optional[datetime] = Query(None, description="End date for period"),
    period: str = Query("all_time", description="Time period (daily, weekly, monthly, yearly, all_time)"),
    db: Session = Depends(get_db)
):
    """Get portfolio performance summary"""
    try:
        return performance_service.get_portfolio_performance(db, start_date, end_date, period)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get portfolio performance: {str(e)}")


@router.get("/performance/portfolio/equity-curve", response_model=EquityCurveResponse)
async def get_portfolio_equity_curve(
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    db: Session = Depends(get_db)
):
    """Get portfolio equity curve data"""
    try:
        return performance_service.get_portfolio_equity_curve(db, start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get equity curve: {str(e)}")


@router.get("/performance/portfolio/breakdown", response_model=List[PerformanceBreakdownResponse])
async def get_performance_breakdown(
    period: str = Query("day", description="Breakdown period"),
    db: Session = Depends(get_db)
):
    """Get P&L breakdown by period"""
    try:
        return performance_service.get_performance_breakdown(db, period)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get performance breakdown: {str(e)}")


@router.get("/performance/portfolio/allocation", response_model=AllocationResponse)
async def get_allocation(db: Session = Depends(get_db)):
    """Get allocation by pair/model"""
    try:
        return performance_service.get_allocation(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get allocation: {str(e)}")


@router.get("/performance/models", response_model=List[ModelPerformanceResponse])
async def list_model_performance(
    db: Session = Depends(get_db)
):
    """List all model performance summaries"""
    try:
        return performance_service.list_model_performance(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list model performance: {str(e)}")


@router.get("/performance/models/{model_id}", response_model=ModelPerformanceResponse)
async def get_model_performance(
    model_id: int,
    period: str = Query("all_time", description="Time period"),
    db: Session = Depends(get_db)
):
    """Get detailed model performance"""
    try:
        perf = performance_service.get_model_performance(db, model_id, period)
        if not perf:
            raise HTTPException(status_code=404, detail=f"Model ID {model_id} not found")
        return perf
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get model performance: {str(e)}")


@router.get("/performance/models/{model_id}/equity-curve", response_model=EquityCurveResponse)
async def get_model_equity_curve(
    model_id: int,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db)
):
    """Get model equity curve"""
    try:
        return performance_service.get_model_equity_curve(db, model_id, start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get model equity curve: {str(e)}")


@router.get("/performance/models/{model_id}/trades", response_model=TradeHistoryResponse)
async def get_model_trades(
    model_id: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db)
):
    """Get model trade history"""
    try:
        trades, total = performance_service.get_model_trades(
            db, model_id, limit, offset, start_date, end_date
        )
        return TradeHistoryResponse(trades=trades, total=total)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get model trades: {str(e)}")


@router.get("/performance/models/{model_id}/statistics")
async def get_model_statistics(
    model_id: int,
    period: str = Query("all_time", description="Time period"),
    db: Session = Depends(get_db)
):
    """Get detailed model statistics (win streaks, avg duration, etc.)"""
    try:
        return performance_service.get_model_statistics(db, model_id, period)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get model statistics: {str(e)}")


@router.get("/performance/models/{model_id}/comparison")
async def get_model_comparison(
    model_id: int,
    db: Session = Depends(get_db)
):
    """Compare paper vs live trading performance"""
    try:
        return performance_service.get_model_comparison(db, model_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get model comparison: {str(e)}")


@router.get("/performance/metrics/realtime")
async def get_realtime_metrics(db: Session = Depends(get_db)):
    """Get real-time performance metrics for all active models"""
    try:
        return performance_service.get_realtime_metrics(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get real-time metrics: {str(e)}")


@router.get("/performance/portfolio/export")
async def export_portfolio_report(
    format: str = Query("csv", description="Export format (csv or pdf)"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db)
):
    """Export portfolio report (PDF/CSV)"""
    try:
        return performance_service.export_portfolio_report(db, format, start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export portfolio report: {str(e)}")


@router.get("/performance/models/{model_id}/export")
async def export_model_report(
    model_id: int,
    format: str = Query("csv", description="Export format (csv or pdf)"),
    db: Session = Depends(get_db)
):
    """Export model report (PDF/CSV)"""
    try:
        return performance_service.export_model_report(db, model_id, format)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export model report: {str(e)}")
