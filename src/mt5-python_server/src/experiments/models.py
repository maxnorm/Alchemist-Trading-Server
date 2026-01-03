"""
Experiment Model

Defines the Experiment dataclass and database operations for experiment management.
"""
import json
import logging
import mariadb
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ExperimentStatus(Enum):
    """Experiment status enumeration"""
    CREATED = 'created'
    TRAINING = 'training'
    COMPLETED = 'completed'
    FAILED = 'failed'
    PAUSED = 'paused'


@dataclass
class Experiment:
    """Experiment configuration and metadata"""
    id: Optional[int]
    name: str
    description: str
    features: List[str]  # Feature names from catalog
    currency_pairs: List[str]
    training_mode: str  # 'live' or 'historical'
    hyperparameters: Dict[str, Any]
    status: ExperimentStatus
    mlflow_run_id: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'features': self.features,
            'currency_pairs': self.currency_pairs,
            'training_mode': self.training_mode,
            'hyperparameters': self.hyperparameters,
            'status': self.status.value,
            'mlflow_run_id': self.mlflow_run_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Experiment':
        """Create from dictionary"""
        # Parse datetime strings
        created_at = None
        started_at = None
        completed_at = None
        
        if data.get('created_at'):
            created_at = datetime.fromisoformat(data['created_at']) if isinstance(data['created_at'], str) else data['created_at']
        if data.get('started_at'):
            started_at = datetime.fromisoformat(data['started_at']) if isinstance(data['started_at'], str) else data['started_at']
        if data.get('completed_at'):
            completed_at = datetime.fromisoformat(data['completed_at']) if isinstance(data['completed_at'], str) else data['completed_at']
        
        # Parse status
        status = ExperimentStatus(data.get('status', 'created'))
        
        return cls(
            id=data.get('id'),
            name=data['name'],
            description=data.get('description', ''),
            features=data.get('features', []),
            currency_pairs=data.get('currency_pairs', []),
            training_mode=data.get('training_mode', 'live'),
            hyperparameters=data.get('hyperparameters', {}),
            status=status,
            mlflow_run_id=data.get('mlflow_run_id'),
            created_at=created_at or datetime.now(),
            started_at=started_at,
            completed_at=completed_at,
        )


class ExperimentRepository:
    """Database operations for experiments"""
    
    def __init__(self, database):
        """
        Initialize experiment repository
        
        :param database: Database instance
        """
        self.db = database
    
    def create_experiment(self, experiment: Experiment) -> int:
        """
        Create a new experiment in the database
        
        :param experiment: Experiment instance
        :return: Experiment ID
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                INSERT INTO experiments (
                    name, description, features, currency_pairs, training_mode,
                    hyperparameters, status, mlflow_run_id, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    experiment.name,
                    experiment.description,
                    json.dumps(experiment.features),
                    json.dumps(experiment.currency_pairs),
                    experiment.training_mode,
                    json.dumps(experiment.hyperparameters),
                    experiment.status.value,
                    experiment.mlflow_run_id,
                    experiment.created_at,
                )
            )
            
            experiment_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            
            logger.info(f"Created experiment {experiment_id}: {experiment.name}")
            return experiment_id
            
        except Exception as e:
            logger.error(f"Error creating experiment: {e}", exc_info=True)
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    def get_experiment(self, experiment_id: int) -> Optional[Experiment]:
        """
        Get experiment by ID
        
        :param experiment_id: Experiment ID
        :return: Experiment instance or None
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT id, name, description, features, currency_pairs, training_mode,
                       hyperparameters, status, mlflow_run_id, created_at, started_at, completed_at
                FROM experiments
                WHERE id = %s
                """,
                (experiment_id,)
            )
            
            row = cursor.fetchone()
            cursor.close()
            
            if not row:
                return None
            
            # Parse row data
            (id_val, name, description, features_json, pairs_json, training_mode,
             hyperparams_json, status_str, mlflow_run_id, created_at, started_at, completed_at) = row
            
            return Experiment(
                id=id_val,
                name=name,
                description=description or '',
                features=json.loads(features_json) if features_json else [],
                currency_pairs=json.loads(pairs_json) if pairs_json else [],
                training_mode=training_mode,
                hyperparameters=json.loads(hyperparams_json) if hyperparams_json else {},
                status=ExperimentStatus(status_str),
                mlflow_run_id=mlflow_run_id,
                created_at=created_at,
                started_at=started_at,
                completed_at=completed_at,
            )
            
        except Exception as e:
            logger.error(f"Error getting experiment {experiment_id}: {e}", exc_info=True)
            return None
        finally:
            if conn:
                conn.close()
    
    def update_experiment_status(
        self,
        experiment_id: int,
        status: ExperimentStatus,
        mlflow_run_id: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None
    ) -> bool:
        """
        Update experiment status
        
        :param experiment_id: Experiment ID
        :param status: New status
        :param mlflow_run_id: Optional MLflow run ID
        :param started_at: Optional start timestamp
        :param completed_at: Optional completion timestamp
        :return: True if successful
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Build update query dynamically
            updates = ["status = ?"]
            params = [status.value]
            
            if mlflow_run_id is not None:
                updates.append("mlflow_run_id = ?")
                params.append(mlflow_run_id)
            
            if started_at is not None:
                updates.append("started_at = ?")
                params.append(started_at)
            
            if completed_at is not None:
                updates.append("completed_at = ?")
                params.append(completed_at)
            
            params.append(experiment_id)
            
            cursor.execute(
                f"UPDATE experiments SET {', '.join(updates)} WHERE id = %s",
                params
            )
            
            conn.commit()
            cursor.close()
            
            logger.info(f"Updated experiment {experiment_id} status to {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating experiment status: {e}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    def list_experiments(self, status: Optional[ExperimentStatus] = None) -> List[Experiment]:
        """
        List all experiments, optionally filtered by status
        
        :param status: Optional status filter
        :return: List of Experiment instances
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            if status:
                cursor.execute(
                    """
                    SELECT id, name, description, features, currency_pairs, training_mode,
                           hyperparameters, status, mlflow_run_id, created_at, started_at, completed_at
                    FROM experiments
                    WHERE status = %s
                    ORDER BY created_at DESC
                    """,
                    (status.value,)
                )
            else:
                cursor.execute(
                    """
                    SELECT id, name, description, features, currency_pairs, training_mode,
                           hyperparameters, status, mlflow_run_id, created_at, started_at, completed_at
                    FROM experiments
                    ORDER BY created_at DESC
                    """
                )
            
            rows = cursor.fetchall()
            cursor.close()
            
            experiments = []
            for row in rows:
                (id_val, name, description, features_json, pairs_json, training_mode,
                 hyperparams_json, status_str, mlflow_run_id, created_at, started_at, completed_at) = row
                
                experiments.append(Experiment(
                    id=id_val,
                    name=name,
                    description=description or '',
                    features=json.loads(features_json) if features_json else [],
                    currency_pairs=json.loads(pairs_json) if pairs_json else [],
                    training_mode=training_mode,
                    hyperparameters=json.loads(hyperparams_json) if hyperparams_json else {},
                    status=ExperimentStatus(status_str),
                    mlflow_run_id=mlflow_run_id,
                    created_at=created_at,
                    started_at=started_at,
                    completed_at=completed_at,
                ))
            
            return experiments
            
        except Exception as e:
            logger.error(f"Error listing experiments: {e}", exc_info=True)
            return []
        finally:
            if conn:
                conn.close()
