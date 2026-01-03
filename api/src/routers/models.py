"""
Model registry endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import Optional
from dependencies import get_db
from services import model_service
from schemas.models import (
    ModelResponse,
    ModelListResponse,
    ModelPromoteRequest,
    PaperSessionResponse,
    PaperSessionListResponse,
    StartPaperSessionRequest,
    ValidationResultResponse,
)

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=ModelListResponse)
async def list_models(
    stage: Optional[str] = Query(None, description="Filter by stage"),
    experiment_id: Optional[int] = Query(None, description="Filter by experiment ID"),
    db: Session = Depends(get_db),
):
    """List all models with optional filters"""
    try:
        models = model_service.get_all_models(
            db, stage=stage, experiment_id=experiment_id
        )
        return ModelListResponse(models=models, total=len(models))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch models: {str(e)}")


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(model_id: int, db: Session = Depends(get_db)):
    """Get model details by ID"""
    model = model_service.get_model_by_id(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return model


@router.post("/{model_id}/promote/staging", response_model=ModelResponse)
async def promote_to_staging(model_id: int, db: Session = Depends(get_db)):
    """Promote model to staging"""
    model = model_service.get_model_by_id(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

    if model.stage == "staging":
        raise HTTPException(status_code=400, detail="Model is already in staging")

    try:
        promoted = model_service.promote_model(db, model_id, "staging")
        return promoted
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to promote model: {str(e)}"
        )


@router.post("/{model_id}/promote/paper", response_model=ModelResponse)
async def promote_to_paper(model_id: int, db: Session = Depends(get_db)):
    """Promote model to paper trading stage"""
    from websocket import channels as ws_channels

    model = model_service.get_model_by_id(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

    if model.stage != "staging":
        raise HTTPException(
            status_code=400, detail=f"Model must be in staging, currently {model.stage}"
        )

    try:
        promoted = model_service.promote_model(db, model_id, "paper")

        # Broadcast stage change
        await ws_channels.broadcast_model_stage_change(
            model_id=model_id,
            old_stage=model.stage,
            new_stage="paper",
            promoted_by=None,
        )

        return promoted
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to promote model: {str(e)}"
        )


@router.post("/{model_id}/promote/production", response_model=ModelResponse)
async def promote_to_production(
    model_id: int,
    request: ModelPromoteRequest = Body(...),
    db: Session = Depends(get_db),
):
    """Promote model to production (requires 2FA)"""
    if not request.confirm:
        raise HTTPException(status_code=400, detail="Confirmation required")

    model = model_service.get_model_by_id(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

    if model.stage != "paper":
        raise HTTPException(
            status_code=400,
            detail=f"Model must be in paper stage, currently {model.stage}",
        )

    # Verify 2FA token
    if not request.totp_token:
        raise HTTPException(
            status_code=400, detail="2FA token required for production promotion"
        )

    # Verify 2FA (simplified for now - in production, verify against user's secret)
    if len(request.totp_token) != 6 or not request.totp_token.isdigit():
        raise HTTPException(status_code=400, detail="Invalid 2FA token format")

    # Validate model meets production criteria
    validation = model_service.validate_model_for_production(db, model_id)
    if not validation["passed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Model validation failed: {', '.join(validation['messages'])}",
        )

    from websocket import channels as ws_channels

    old_stage = model.stage

    try:
        promoted = model_service.promote_model(
            db, model_id, "production", totp_token=request.totp_token
        )

        # Broadcast stage change
        await ws_channels.broadcast_model_stage_change(
            model_id=model_id,
            old_stage=old_stage,
            new_stage="production",
            promoted_by=None,
        )

        return promoted
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to promote model: {str(e)}"
        )


@router.post("/{model_id}/rollback", response_model=ModelResponse)
async def rollback_production(
    model_id: int,
    to_model_id: Optional[int] = Query(
        None, description="Target model ID to rollback to"
    ),
    confirm: bool = Query(False, description="Confirmation required"),
    db: Session = Depends(get_db),
):
    """Rollback production model"""
    if not confirm:
        raise HTTPException(status_code=400, detail="Confirmation required")

    model = model_service.get_model_by_id(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

    if model.stage != "production":
        raise HTTPException(
            status_code=400, detail="Only production models can be rolled back"
        )

    try:
        rolled_back = model_service.rollback_production(db, model_id, to_model_id)
        return rolled_back
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rollback: {str(e)}")


@router.get("/{model_id}/paper-sessions", response_model=PaperSessionListResponse)
async def get_paper_sessions(model_id: int, db: Session = Depends(get_db)):
    """Get paper trading sessions for a model"""
    sessions = model_service.get_paper_sessions(db, model_id)
    return PaperSessionListResponse(sessions=sessions, total=len(sessions))


@router.post("/{model_id}/paper-sessions/start", response_model=PaperSessionResponse)
async def start_paper_session(
    model_id: int,
    request: StartPaperSessionRequest = Body(...),
    db: Session = Depends(get_db),
):
    """Start a paper trading session"""
    from websocket import channels as ws_channels

    model = model_service.get_model_by_id(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

    if model.stage != "paper":
        raise HTTPException(status_code=400, detail="Model must be in paper stage")

    try:
        session = model_service.start_paper_session(db, model_id, request.start_balance)

        # Broadcast session start
        await ws_channels.broadcast_paper_session_update(
            model_id=model_id,
            session_id=session.id,
            status="running",
            metrics={"start_balance": request.start_balance},
        )

        return session
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start paper session: {str(e)}"
        )


@router.post(
    "/{model_id}/paper-sessions/{session_id}/stop", response_model=PaperSessionResponse
)
async def stop_paper_session(
    model_id: int, session_id: int, db: Session = Depends(get_db)
):
    """Stop a paper trading session"""
    from websocket import channels as ws_channels

    session = model_service.get_paper_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if session.model_id != model_id:
        raise HTTPException(
            status_code=400, detail="Session does not belong to this model"
        )

    try:
        stopped = model_service.stop_paper_session(db, session_id)

        # Broadcast session end
        await ws_channels.broadcast_paper_session_update(
            model_id=model_id,
            session_id=session_id,
            status="completed",
            metrics={
                "total_trades": stopped.total_trades,
                "winning_trades": stopped.winning_trades,
                "pnl": float(stopped.pnl),
                "sharpe_ratio": (
                    float(stopped.sharpe_ratio) if stopped.sharpe_ratio else None
                ),
                "max_drawdown": (
                    float(stopped.max_drawdown) if stopped.max_drawdown else None
                ),
            },
        )

        # Broadcast validation update
        validation = model_service.validate_model_for_production(db, model_id)
        await ws_channels.broadcast_validation_update(model_id, validation)

        return stopped
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to stop paper session: {str(e)}"
        )


@router.get("/{model_id}/validation", response_model=ValidationResultResponse)
async def get_validation_status(model_id: int, db: Session = Depends(get_db)):
    """Get validation status for a model"""
    model = model_service.get_model_by_id(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

    validation = model_service.validate_model_for_production(db, model_id)
    return ValidationResultResponse(**validation)
