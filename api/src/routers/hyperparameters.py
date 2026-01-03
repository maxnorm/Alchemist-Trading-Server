"""
Hyperparameter search endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from dependencies import get_db
from services import optuna_service
from schemas.hyperparameters import (
    OptunaSearchCreate,
    OptunaStudyResponse,
    TrialResponse,
    ParameterImportanceResponse
)

router = APIRouter()


@router.post("/hyperparameters/search", response_model=OptunaStudyResponse, status_code=201)
async def start_optuna_search(
    search: OptunaSearchCreate,
    db: Session = Depends(get_db)
):
    """Start Optuna hyperparameter search"""
    try:
        # Verify experiment exists
        from services import experiment_service
        experiment = experiment_service.get_experiment_by_id(db, search.experiment_id)
        if not experiment:
            raise HTTPException(status_code=404, detail=f"Experiment {search.experiment_id} not found")
        
        study = create_optuna_study(db, search)
        return study
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start Optuna search: {str(e)}")


@router.get("/hyperparameters/search/{id}", response_model=OptunaStudyResponse)
async def get_search_status(
    id: int,
    db: Session = Depends(get_db)
):
    """Get Optuna search status"""
    study = optuna_service.get_study_by_id(db, id)
    if not study:
        raise HTTPException(status_code=404, detail=f"Optuna study {id} not found")
    return study


@router.get("/experiments/{experiment_id}/optuna/status", response_model=OptunaStudyResponse)
async def get_experiment_optuna_status(
    experiment_id: int,
    db: Session = Depends(get_db)
):
    """Get Optuna study status for an experiment"""
    study = get_study_by_experiment_id(db, experiment_id)
    if not study:
        raise HTTPException(status_code=404, detail=f"No Optuna study found for experiment {experiment_id}")
    return study


@router.get("/hyperparameters/search/{id}/trials", response_model=List[TrialResponse])
async def get_trials(
    id: int,
    db: Session = Depends(get_db)
):
    """Get all trials for an Optuna study"""
    study = optuna_service.get_study_by_id(db, id)
    if not study:
        raise HTTPException(status_code=404, detail=f"Optuna study {id} not found")
    
    trials = get_trials_by_study_id(db, id)
    return trials


@router.get("/hyperparameters/search/{id}/best", response_model=OptunaStudyResponse)
async def get_best_trial(
    id: int,
    db: Session = Depends(get_db)
):
    """Get best trial for an Optuna study"""
    study = optuna_service.get_study_by_id(db, id)
    if not study:
        raise HTTPException(status_code=404, detail=f"Optuna study {id} not found")
    
    if not study.best_value:
        raise HTTPException(status_code=404, detail="No completed trials found")
    
    return study


@router.post("/hyperparameters/search/{id}/stop", response_model=OptunaStudyResponse)
async def stop_search(
    id: int,
    db: Session = Depends(get_db)
):
    """Stop an Optuna search"""
    study = optuna_service.get_study_by_id(db, id)
    if not study:
        raise HTTPException(status_code=404, detail=f"Optuna study {id} not found")
    
    if study.status != "running":
        raise HTTPException(status_code=400, detail=f"Study is not running (status: {study.status})")
    
    updated = optuna_service.update_study_status(db, id, "completed")
    return updated


@router.get("/hyperparameters/search/{id}/importance", response_model=ParameterImportanceResponse)
async def get_parameter_importance(
    id: int,
    db: Session = Depends(get_db)
):
    """Get parameter importance for an Optuna study"""
    study = optuna_service.get_study_by_id(db, id)
    if not study:
        raise HTTPException(status_code=404, detail=f"Optuna study {id} not found")
    
    importance = get_parameter_importance(db, id)
    if not importance:
        raise HTTPException(status_code=404, detail="Parameter importance not available")
    
    return ParameterImportanceResponse(study_id=id, importance=importance)
