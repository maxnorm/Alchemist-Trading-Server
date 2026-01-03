"""
Trading control endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from dependencies import get_db
from services.trading_service import (
    get_trading_status,
    check_kill_switch_status,
    get_kill_switch_status,
    trigger_kill_switch,
    reset_kill_switch,
    get_circuit_breaker_status,
    reset_circuit_breaker,
    get_open_positions,
    get_trade_history,
    get_available_currency_pairs,
)
from schemas.trading import (
    TradingStatusResponse,
    KillSwitchStatusResponse,
    CircuitBreakerStatusResponse,
    PositionResponse,
    TradeHistoryResponse,
    CurrencyPairsResponse,
)

router = APIRouter()


@router.get("/trading/status", response_model=TradingStatusResponse)
async def get_trading_status(db: Session = Depends(get_db)):
    """Get trading status"""
    try:
        return trading_service.get_trading_status(db)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get trading status: {str(e)}"
        )


@router.post("/trading/start")
async def start_trading(
    confirm: bool = Query(False, description="Confirmation required to start trading"),
    db: Session = Depends(get_db),
):
    """Start live trading"""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Set 'confirm' to true to start trading.",
        )

    # Check kill switch
    if check_kill_switch_status():
        raise HTTPException(
            status_code=400, detail="Cannot start trading: kill switch is active"
        )

    # In a real implementation, this would start the trading server
    return {"message": "Trading started", "status": "active"}


@router.post("/trading/stop")
async def stop_trading(db: Session = Depends(get_db)):
    """Stop trading"""
    # In a real implementation, this would stop the trading server
    return {"message": "Trading stopped", "status": "inactive"}


@router.post("/trading/kill")
async def emergency_kill_switch(
    confirm: bool = Query(
        False, description="Confirmation required for emergency kill"
    ),
    reason: str = Query("API emergency kill", description="Reason for kill switch"),
    db: Session = Depends(get_db),
):
    """Emergency kill switch"""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Set 'confirm' to true to trigger kill switch.",
        )

    success = trading_service.trigger_kill_switch(reason)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to trigger kill switch")

    return {"message": "Kill switch activated", "reason": reason}


@router.get("/trading/kill-switch/status", response_model=KillSwitchStatusResponse)
async def get_kill_switch_status():
    """Get kill switch status"""
    return get_kill_switch_status()


@router.post("/trading/kill-switch/trigger")
async def trigger_kill_switch(
    reason: str = Query("API trigger", description="Reason for kill switch")
):
    """Trigger kill switch"""
    success = trading_service.trigger_kill_switch(reason)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to trigger kill switch")
    return {"message": "Kill switch activated", "reason": reason}


@router.post("/trading/kill-switch/reset")
async def reset_kill_switch():
    """Reset kill switch"""
    success = trading_service.reset_kill_switch()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to reset kill switch")
    return {"message": "Kill switch reset"}


@router.get(
    "/trading/circuit-breaker/status", response_model=CircuitBreakerStatusResponse
)
async def get_circuit_breaker_status(db: Session = Depends(get_db)):
    """Get circuit breaker status"""
    return get_circuit_breaker_status(db)


@router.post("/trading/circuit-breaker/reset")
async def reset_circuit_breaker(db: Session = Depends(get_db)):
    """Reset circuit breaker"""
    success = trading_service.reset_circuit_breaker(db)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to reset circuit breaker")
    return {"message": "Circuit breaker reset"}


@router.get("/trading/positions", response_model=List[PositionResponse])
async def get_positions(db: Session = Depends(get_db)):
    """Get open positions"""
    try:
        return get_open_positions(db)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get positions: {str(e)}"
        )


@router.get("/trading/history", response_model=TradeHistoryResponse)
async def get_trade_history(
    experiment_id: Optional[int] = Query(None, description="Filter by experiment ID"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of trades to return"
    ),
    db: Session = Depends(get_db),
):
    """Get trade history"""
    try:
        trades = get_trade_history(db, experiment_id=experiment_id, limit=limit)
        return TradeHistoryResponse(trades=trades, total=len(trades))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get trade history: {str(e)}"
        )


@router.get("/trading/currency-pairs", response_model=CurrencyPairsResponse)
async def get_currency_pairs(db: Session = Depends(get_db)):
    """Get available currency pairs from database"""
    try:
        pairs = get_available_currency_pairs(db)
        return CurrencyPairsResponse(pairs=pairs, total=len(pairs))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get currency pairs: {str(e)}"
        )
