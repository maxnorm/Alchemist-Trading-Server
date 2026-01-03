"""
Experiment management endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from dependencies import get_db
from services import experiment_service
from schemas.experiments import (
    ExperimentCreate,
    ExperimentResponse,
    ExperimentListResponse,
    ExperimentStartRequest,
)

router = APIRouter()


@router.get("/experiments", response_model=ExperimentListResponse)
async def list_experiments(
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
):
    """List all experiments"""
    try:
        experiments = get_all_experiments(db, status=status)
        return ExperimentListResponse(experiments=experiments, total=len(experiments))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch experiments: {str(e)}"
        )


@router.post("/experiments", response_model=ExperimentResponse, status_code=201)
async def create_experiment(
    experiment: ExperimentCreate, db: Session = Depends(get_db)
):
    """Create a new experiment"""
    try:
        return experiment_service.create_experiment(db, experiment)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to create experiment: {str(e)}"
        )


@router.get("/experiments/{id}", response_model=ExperimentResponse)
async def get_experiment(id: int, db: Session = Depends(get_db)):
    """Get experiment details"""
    experiment = get_experiment_by_id(db, id)
    if not experiment:
        raise HTTPException(status_code=404, detail=f"Experiment {id} not found")
    return experiment


@router.post("/experiments/{id}/start", response_model=ExperimentResponse)
async def start_experiment(
    id: int, request: ExperimentStartRequest, db: Session = Depends(get_db)
):
    """Start experiment training"""
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Set 'confirm' to true to start training.",
        )

    experiment = get_experiment_by_id(db, id)
    if not experiment:
        raise HTTPException(status_code=404, detail=f"Experiment {id} not found")

    if experiment.status == "training":
        raise HTTPException(status_code=400, detail="Experiment is already training")

    try:
        # Update status to training
        # In a real implementation, this would trigger the training loop
        updated = experiment_service.update_experiment_status(db, id, "training")
        return updated
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start experiment: {str(e)}"
        )


@router.post("/experiments/{id}/stop", response_model=ExperimentResponse)
async def stop_experiment(id: int, db: Session = Depends(get_db)):
    """Stop experiment training"""
    experiment = get_experiment_by_id(db, id)
    if not experiment:
        raise HTTPException(status_code=404, detail=f"Experiment {id} not found")

    if experiment.status != "training":
        raise HTTPException(
            status_code=400, detail="Experiment is not currently training"
        )

    try:
        # Update status to completed (or failed)
        updated = update_experiment_status(db, id, "completed")
        return updated
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to stop experiment: {str(e)}"
        )


@router.post(
    "/experiments/{id}/clone", response_model=ExperimentResponse, status_code=201
)
async def clone_experiment(
    id: int,
    new_name: str = Query(..., description="Name for the cloned experiment"),
    db: Session = Depends(get_db),
):
    """Clone an experiment"""
    cloned = experiment_service.clone_experiment(db, id, new_name)
    if not cloned:
        raise HTTPException(status_code=404, detail=f"Experiment {id} not found")
    return cloned


@router.delete("/experiments/{id}", status_code=204)
async def delete_experiment(id: int, db: Session = Depends(get_db)):
    """Delete an experiment"""
    success = delete_experiment(db, id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Experiment {id} not found")
