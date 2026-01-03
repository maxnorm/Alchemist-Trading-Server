"""
Experiment service
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from schemas.experiments import ExperimentCreate, ExperimentResponse
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def create_experiment(
    db: Session, experiment_data: ExperimentCreate
) -> ExperimentResponse:
    """Create a new experiment"""
    # Validate features exist
    # Validate currency pairs exist
    # Insert into database
    query = """
        INSERT INTO experiments (name, description, features, currency_pairs, training_mode, hyperparameters, status)
        VALUES (:name, :description, :features, :currency_pairs, :training_mode, :hyperparameters, 'created')
    """

    params = {
        "name": experiment_data.name,
        "description": experiment_data.description,
        "features": json.dumps(experiment_data.features),
        "currency_pairs": json.dumps(experiment_data.currency_pairs),
        "training_mode": experiment_data.training_mode,
        "hyperparameters": json.dumps(experiment_data.hyperparameters),
    }

    result = db.execute(text(query), params)
    db.commit()

    experiment_id = result.lastrowid
    return get_experiment_by_id(db, experiment_id)


def get_all_experiments(
    db: Session, status: Optional[str] = None
) -> List[ExperimentResponse]:
    """Get all experiments with optional status filter"""
    query = "SELECT * FROM experiments WHERE 1=1"
    params = {}

    if status:
        query += " AND status = :status"
        params["status"] = status

    query += " ORDER BY created_at DESC"

    result = db.execute(text(query), params)
    rows = result.fetchall()

    experiments = []
    for row in rows:
        row_dict = dict(row._mapping)
        # Parse JSON fields
        for json_field in ["features", "currency_pairs", "hyperparameters"]:
            if row_dict.get(json_field) and isinstance(row_dict[json_field], str):
                try:
                    row_dict[json_field] = json.loads(row_dict[json_field])
                except (ValueError, TypeError):
                    row_dict[json_field] = (
                        [] if json_field in ["features", "currency_pairs"] else {}
                    )
        experiments.append(ExperimentResponse(**row_dict))

    return experiments


def get_experiment_by_id(
    db: Session, experiment_id: int
) -> Optional[ExperimentResponse]:
    """Get experiment by ID"""
    result = db.execute(
        text("SELECT * FROM experiments WHERE id = :id"), {"id": experiment_id}
    )
    row = result.fetchone()

    if not row:
        return None

    row_dict = dict(row._mapping)
    # Parse JSON fields
    for json_field in ["features", "currency_pairs", "hyperparameters"]:
        if row_dict.get(json_field) and isinstance(row_dict[json_field], str):
            try:
                row_dict[json_field] = json.loads(row_dict[json_field])
            except:
                row_dict[json_field] = (
                    [] if json_field in ["features", "currency_pairs"] else {}
                )

    return ExperimentResponse(**row_dict)


def update_experiment_status(
    db: Session, experiment_id: int, status: str, mlflow_run_id: Optional[str] = None
) -> Optional[ExperimentResponse]:
    """Update experiment status"""
    update_fields = ["status = :status"]
    params = {"id": experiment_id, "status": status}

    if status == "training" and mlflow_run_id:
        update_fields.append("mlflow_run_id = :mlflow_run_id")
        params["mlflow_run_id"] = mlflow_run_id
        update_fields.append("started_at = NOW()")
    elif status in ["completed", "failed"]:
        update_fields.append("completed_at = NOW()")

    query = f"UPDATE experiments SET {', '.join(update_fields)} WHERE id = :id"

    result = db.execute(text(query), params)
    db.commit()

    if result.rowcount == 0:
        return None

    return get_experiment_by_id(db, experiment_id)


def delete_experiment(db: Session, experiment_id: int) -> bool:
    """Delete experiment"""
    result = db.execute(
        text("DELETE FROM experiments WHERE id = :id"), {"id": experiment_id}
    )
    db.commit()
    return result.rowcount > 0


def clone_experiment(
    db: Session, experiment_id: int, new_name: str
) -> Optional[ExperimentResponse]:
    """Clone an experiment"""
    original = get_experiment_by_id(db, experiment_id)
    if not original:
        return None

    # Create new experiment with same config but new name
    experiment_data = ExperimentCreate(
        name=new_name,
        description=original.description,
        features=original.features,
        currency_pairs=original.currency_pairs,
        training_mode=original.training_mode,
        hyperparameters=original.hyperparameters,
    )

    return create_experiment(db, experiment_data)
