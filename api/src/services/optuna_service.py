"""
Optuna service
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict, Any
from schemas.hyperparameters import (
    OptunaSearchCreate,
    OptunaStudyResponse,
    TrialResponse,
)
import json
import logging

logger = logging.getLogger(__name__)


def create_optuna_study(
    db: Session, search_data: OptunaSearchCreate
) -> OptunaStudyResponse:
    """Create a new Optuna study"""
    query = """
        INSERT INTO optuna_studies
        (experiment_id, study_name, n_trials, optimize_metric, direction, status)
        VALUES (:experiment_id, :study_name, :n_trials, :optimize_metric, :direction, 'running')
    """

    params = {
        "experiment_id": search_data.experiment_id,
        "study_name": search_data.study_name,
        "n_trials": search_data.n_trials,
        "optimize_metric": search_data.optimize_metric,
        "direction": search_data.direction,
    }

    result = db.execute(text(query), params)
    db.commit()

    study_id = result.lastrowid
    return get_study_by_id(db, study_id)


def get_study_by_id(db: Session, study_id: int) -> Optional[OptunaStudyResponse]:
    """Get Optuna study by ID"""
    result = db.execute(
        text("SELECT * FROM optuna_studies WHERE id = :id"), {"id": study_id}
    )
    row = result.fetchone()

    if not row:
        return None

    row_dict = dict(row._mapping)
    # Parse JSON fields
    for json_field in ["best_params", "param_importance"]:
        if row_dict.get(json_field) and isinstance(row_dict[json_field], str):
            try:
                row_dict[json_field] = json.loads(row_dict[json_field])
            except (ValueError, TypeError):
                row_dict[json_field] = {}

    return OptunaStudyResponse(**row_dict)


def get_study_by_experiment_id(
    db: Session, experiment_id: int
) -> Optional[OptunaStudyResponse]:
    """Get Optuna study by experiment ID"""
    result = db.execute(
        text(
            "SELECT * FROM optuna_studies WHERE experiment_id = :experiment_id ORDER BY created_at DESC LIMIT 1"
        ),
        {"experiment_id": experiment_id},
    )
    row = result.fetchone()

    if not row:
        return None

    row_dict = dict(row._mapping)
    # Parse JSON fields
    for json_field in ["best_params", "param_importance"]:
        if row_dict.get(json_field) and isinstance(row_dict[json_field], str):
            try:
                row_dict[json_field] = json.loads(row_dict[json_field])
            except (ValueError, TypeError):
                row_dict[json_field] = {}

    return OptunaStudyResponse(**row_dict)


def update_study_status(
    db: Session,
    study_id: int,
    status: str,
    best_trial_number: Optional[int] = None,
    best_value: Optional[float] = None,
    best_params: Optional[Dict[str, Any]] = None,
) -> Optional[OptunaStudyResponse]:
    """Update study status"""
    update_fields = ["status = :status"]
    params = {"id": study_id, "status": status}

    if best_trial_number is not None:
        update_fields.append("best_trial_number = :best_trial_number")
        params["best_trial_number"] = best_trial_number

    if best_value is not None:
        update_fields.append("best_value = :best_value")
        params["best_value"] = best_value

    if best_params is not None:
        update_fields.append("best_params = :best_params")
        params["best_params"] = json.dumps(best_params)

    if status == "completed":
        update_fields.append("completed_at = NOW()")

    query = f"UPDATE optuna_studies SET {', '.join(update_fields)} WHERE id = :id"

    result = db.execute(text(query), params)
    db.commit()

    if result.rowcount == 0:
        return None

    return get_study_by_id(db, study_id)


def get_trials_by_study_id(db: Session, study_id: int) -> List[TrialResponse]:
    """Get all trials for a study"""
    result = db.execute(
        text(
            "SELECT * FROM optuna_trials WHERE study_id = :study_id ORDER BY trial_number"
        ),
        {"study_id": study_id},
    )
    rows = result.fetchall()

    trials = []
    for row in rows:
        row_dict = dict(row._mapping)
        # Parse JSON fields
        for json_field in ["params", "metrics"]:
            if row_dict.get(json_field) and isinstance(row_dict[json_field], str):
                try:
                    row_dict[json_field] = json.loads(row_dict[json_field])
                except:
                    row_dict[json_field] = {} if json_field == "params" else {}
        trials.append(TrialResponse(**row_dict))

    return trials


def get_parameter_importance(db: Session, study_id: int) -> Optional[Dict[str, float]]:
    """Get parameter importance for a study"""
    study = get_study_by_id(db, study_id)
    if not study or not study.param_importance:
        return None
    return study.param_importance
