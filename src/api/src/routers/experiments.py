"""
Experiment management endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, Dict
from dependencies import get_db
from middleware.auth import get_current_user
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
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all experiments"""
    try:
        experiments = experiment_service.get_all_experiments(db, status=status)
        return ExperimentListResponse(experiments=experiments, total=len(experiments))
    except HTTPException:
        # Re-raise HTTPException to preserve status code (e.g., 503 from get_db)
        raise
    except SQLAlchemyError as e:
        # Database errors should return 503
        raise HTTPException(
            status_code=503,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch experiments: {str(e)}"
        )


@router.post("/experiments", response_model=ExperimentResponse, status_code=201)
async def create_experiment(
    experiment: ExperimentCreate,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new experiment"""
    try:
        return experiment_service.create_experiment(db, experiment)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to create experiment: {str(e)}"
        )


@router.get("/experiments/{id}", response_model=ExperimentResponse)
async def get_experiment(
    id: int,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get experiment details"""
    experiment = experiment_service.get_experiment_by_id(db, id)
    if not experiment:
        raise HTTPException(status_code=404, detail=f"Experiment {id} not found")
    return experiment


@router.post("/experiments/{id}/start", response_model=ExperimentResponse)
async def start_experiment(
    id: int,
    request: ExperimentStartRequest,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start experiment training"""
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Set 'confirm' to true to start training.",
        )

    experiment = experiment_service.get_experiment_by_id(db, id)
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
async def stop_experiment(
    id: int,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stop experiment training"""
    experiment = experiment_service.get_experiment_by_id(db, id)
    if not experiment:
        raise HTTPException(status_code=404, detail=f"Experiment {id} not found")

    if experiment.status != "training":
        raise HTTPException(
            status_code=400, detail="Experiment is not currently training"
        )

    try:
        # Update status to completed (or failed)
        updated = experiment_service.update_experiment_status(db, id, "completed")
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
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clone an experiment"""
    cloned = experiment_service.clone_experiment(db, id, new_name)
    if not cloned:
        raise HTTPException(status_code=404, detail=f"Experiment {id} not found")
    return cloned


@router.delete("/experiments/{id}", status_code=204)
async def delete_experiment(
    id: int,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an experiment"""
    success = experiment_service.delete_experiment(db, id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Experiment {id} not found")


# Optuna endpoints for experiments
@router.get("/experiments/{id}/optuna/trials")
async def get_experiment_optuna_trials(
    id: int,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get Optuna trials for an experiment"""
    from services import optuna_service
    from schemas.hyperparameters import TrialResponse
    from typing import List
    
    # Get study by experiment ID
    study = optuna_service.get_study_by_experiment_id(db, id)
    if not study:
        raise HTTPException(
            status_code=404,
            detail=f"No Optuna study found for experiment {id}",
        )
    
    # Get trials by study ID
    trials = optuna_service.get_trials_by_study_id(db, study.id)
    return trials


@router.get("/experiments/{id}/optuna/best")
async def get_experiment_optuna_best(
    id: int,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get best Optuna trial for an experiment"""
    from services import optuna_service
    
    # Get study by experiment ID
    study = optuna_service.get_study_by_experiment_id(db, id)
    if not study:
        raise HTTPException(
            status_code=404,
            detail=f"No Optuna study found for experiment {id}",
        )
    
    if not study.best_value:
        raise HTTPException(status_code=404, detail="No completed trials found")
    
    # Return best params and value
    return {
        "params": study.best_params or {},
        "value": study.best_value,
    }


@router.get("/experiments/{id}/optuna/importance")
async def get_experiment_optuna_importance(
    id: int,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get parameter importance for an experiment's Optuna study"""
    from services import optuna_service
    from schemas.hyperparameters import ParameterImportanceResponse
    
    # Get study by experiment ID
    study = optuna_service.get_study_by_experiment_id(db, id)
    if not study:
        raise HTTPException(
            status_code=404,
            detail=f"No Optuna study found for experiment {id}",
        )
    
    # Get parameter importance
    importance = optuna_service.get_parameter_importance(db, study.id)
    if not importance:
        raise HTTPException(
            status_code=404, detail="Parameter importance not available"
        )
    
    return ParameterImportanceResponse(study_id=study.id, importance=importance)
