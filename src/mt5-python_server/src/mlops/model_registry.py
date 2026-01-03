"""
Model Registry Module

Database-backed model registry that syncs with MLflow.
Tracks model lifecycle stages and links models to experiments.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ModelStage(Enum):
    """Model lifecycle stages"""

    TRAINING = "training"
    STAGING = "staging"
    PAPER = "paper"
    PRODUCTION = "production"
    ARCHIVED = "archived"


@dataclass
class Model:
    """Model registry entry"""

    id: Optional[int]
    version: str
    experiment_id: Optional[int]
    stage: ModelStage
    features: List[str]
    hyperparameters: Dict[str, Any]
    metrics: Optional[Dict[str, Any]]
    mlflow_model_uri: Optional[str]
    mlflow_run_id: Optional[str]
    paper_trading_results: Optional[Dict[str, Any]]
    created_at: datetime
    promoted_at: Optional[datetime]
    promoted_by: Optional[int]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "version": self.version,
            "experiment_id": self.experiment_id,
            "stage": self.stage.value,
            "features": self.features,
            "hyperparameters": self.hyperparameters,
            "metrics": self.metrics,
            "mlflow_model_uri": self.mlflow_model_uri,
            "mlflow_run_id": self.mlflow_run_id,
            "paper_trading_results": self.paper_trading_results,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "promoted_at": self.promoted_at.isoformat() if self.promoted_at else None,
            "promoted_by": self.promoted_by,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Model":
        """Create from dictionary"""
        # Parse datetime strings
        created_at = None
        promoted_at = None

        if data.get("created_at"):
            created_at = (
                datetime.fromisoformat(data["created_at"])
                if isinstance(data["created_at"], str)
                else data["created_at"]
            )
        if data.get("promoted_at"):
            promoted_at = (
                datetime.fromisoformat(data["promoted_at"])
                if isinstance(data["promoted_at"], str)
                else data["promoted_at"]
            )

        # Parse stage
        stage = ModelStage(data.get("stage", "staging"))

        return cls(
            id=data.get("id"),
            version=data["version"],
            experiment_id=data.get("experiment_id"),
            stage=stage,
            features=data.get("features", []),
            hyperparameters=data.get("hyperparameters", {}),
            metrics=data.get("metrics"),
            mlflow_model_uri=data.get("mlflow_model_uri"),
            mlflow_run_id=data.get("mlflow_run_id"),
            paper_trading_results=data.get("paper_trading_results"),
            created_at=created_at or datetime.now(),
            promoted_at=promoted_at,
            promoted_by=data.get("promoted_by"),
        )


class ModelRegistry:
    """
    Database-backed model registry that syncs with MLflow.

    Responsibilities:
    - Register models after training completes
    - Track model lifecycle stages in database
    - Sync with MLflow model registry
    - Link models to experiments
    - Store paper trading results
    """

    def __init__(self, database):
        """
        Initialize model registry

        :param database: Database instance
        """
        self.db = database

    def register_model(
        self,
        experiment_id: int,
        mlflow_run_id: str,
        features: List[str],
        hyperparameters: Dict[str, Any],
        mlflow_model_uri: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
        version: Optional[str] = None,
    ) -> Model:
        """
        Register a new model after training completes.

        :param experiment_id: Experiment ID
        :param mlflow_run_id: MLflow run ID
        :param features: List of feature names used
        :param hyperparameters: Hyperparameters dictionary
        :param mlflow_model_uri: Optional MLflow model URI
        :param metrics: Optional training metrics
        :param version: Optional version string (auto-generated if not provided)
        :return: Registered Model instance
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Generate version if not provided
            if not version:
                # Get latest version number for this experiment
                cursor.execute(
                    "SELECT COUNT(*) FROM models WHERE experiment_id = %s",
                    (experiment_id,),
                )
                count = cursor.fetchone()[0]
                version = f"v{count + 1}"

            # Check if version already exists
            cursor.execute("SELECT id FROM models WHERE version = %s", (version,))
            if cursor.fetchone():
                raise ValueError(f"Model version {version} already exists")

            # Insert model
            cursor.execute(
                """
                INSERT INTO models (
                    version, experiment_id, stage, features, hyperparameters,
                    metrics, mlflow_model_uri, mlflow_run_id, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    version,
                    experiment_id,
                    ModelStage.TRAINING.value,
                    json.dumps(features),
                    json.dumps(hyperparameters),
                    json.dumps(metrics) if metrics else None,
                    mlflow_model_uri,
                    mlflow_run_id,
                    datetime.now(),
                ),
            )

            model_id = cursor.lastrowid
            conn.commit()
            cursor.close()

            logger.info(
                f"Registered model {model_id} (version {version}) for experiment {experiment_id}"
            )

            # Auto-promote to staging
            self.update_model_stage(model_id, ModelStage.STAGING, promoted_by=None)

            return self.get_model(model_id)

        except Exception as e:
            logger.error(f"Error registering model: {e}", exc_info=True)
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def get_model(self, model_id: int) -> Optional[Model]:
        """
        Get model by ID

        :param model_id: Model ID
        :return: Model instance or None
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, version, experiment_id, stage, features, hyperparameters,
                       metrics, mlflow_model_uri, mlflow_run_id, paper_trading_results,
                       created_at, promoted_at, promoted_by
                FROM models
                WHERE id = %s
                """,
                (model_id,),
            )

            row = cursor.fetchone()
            cursor.close()

            if not row:
                return None

            # Parse row data
            (
                id_val,
                version,
                exp_id,
                stage_str,
                features_json,
                hyperparams_json,
                metrics_json,
                mlflow_uri,
                mlflow_run,
                paper_results_json,
                created_at,
                promoted_at,
                promoted_by,
            ) = row

            return Model(
                id=id_val,
                version=version,
                experiment_id=exp_id,
                stage=ModelStage(stage_str),
                features=json.loads(features_json) if features_json else [],
                hyperparameters=(
                    json.loads(hyperparams_json) if hyperparams_json else {}
                ),
                metrics=json.loads(metrics_json) if metrics_json else None,
                mlflow_model_uri=mlflow_uri,
                mlflow_run_id=mlflow_run,
                paper_trading_results=(
                    json.loads(paper_results_json) if paper_results_json else None
                ),
                created_at=created_at,
                promoted_at=promoted_at,
                promoted_by=promoted_by,
            )

        except Exception as e:
            logger.error(f"Error getting model {model_id}: {e}", exc_info=True)
            return None
        finally:
            if conn:
                conn.close()

    def get_model_by_version(self, version: str) -> Optional[Model]:
        """
        Get model by version string

        :param version: Version string
        :return: Model instance or None
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, version, experiment_id, stage, features, hyperparameters,
                       metrics, mlflow_model_uri, mlflow_run_id, paper_trading_results,
                       created_at, promoted_at, promoted_by
                FROM models
                WHERE version = %s
                """,
                (version,),
            )

            row = cursor.fetchone()
            cursor.close()

            if not row:
                return None

            # Parse row data
            (
                id_val,
                version,
                exp_id,
                stage_str,
                features_json,
                hyperparams_json,
                metrics_json,
                mlflow_uri,
                mlflow_run,
                paper_results_json,
                created_at,
                promoted_at,
                promoted_by,
            ) = row

            return Model(
                id=id_val,
                version=version,
                experiment_id=exp_id,
                stage=ModelStage(stage_str),
                features=json.loads(features_json) if features_json else [],
                hyperparameters=(
                    json.loads(hyperparams_json) if hyperparams_json else {}
                ),
                metrics=json.loads(metrics_json) if metrics_json else None,
                mlflow_model_uri=mlflow_uri,
                mlflow_run_id=mlflow_run,
                paper_trading_results=(
                    json.loads(paper_results_json) if paper_results_json else None
                ),
                created_at=created_at,
                promoted_at=promoted_at,
                promoted_by=promoted_by,
            )

        except Exception as e:
            logger.error(
                f"Error getting model by version {version}: {e}", exc_info=True
            )
            return None
        finally:
            if conn:
                conn.close()

    def get_models_by_stage(self, stage: ModelStage) -> List[Model]:
        """
        Get all models in a specific stage

        :param stage: Model stage
        :return: List of Model instances
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, version, experiment_id, stage, features, hyperparameters,
                       metrics, mlflow_model_uri, mlflow_run_id, paper_trading_results,
                       created_at, promoted_at, promoted_by
                FROM models
                WHERE stage = %s
                ORDER BY created_at DESC
                """,
                (stage.value,),
            )

            rows = cursor.fetchall()
            cursor.close()

            models = []
            for row in rows:
                (
                    id_val,
                    version,
                    exp_id,
                    stage_str,
                    features_json,
                    hyperparams_json,
                    metrics_json,
                    mlflow_uri,
                    mlflow_run,
                    paper_results_json,
                    created_at,
                    promoted_at,
                    promoted_by,
                ) = row

                models.append(
                    Model(
                        id=id_val,
                        version=version,
                        experiment_id=exp_id,
                        stage=ModelStage(stage_str),
                        features=json.loads(features_json) if features_json else [],
                        hyperparameters=(
                            json.loads(hyperparams_json) if hyperparams_json else {}
                        ),
                        metrics=json.loads(metrics_json) if metrics_json else None,
                        mlflow_model_uri=mlflow_uri,
                        mlflow_run_id=mlflow_run,
                        paper_trading_results=(
                            json.loads(paper_results_json)
                            if paper_results_json
                            else None
                        ),
                        created_at=created_at,
                        promoted_at=promoted_at,
                        promoted_by=promoted_by,
                    )
                )

            return models

        except Exception as e:
            logger.error(
                f"Error getting models by stage {stage.value}: {e}", exc_info=True
            )
            return []
        finally:
            if conn:
                conn.close()

    def update_model_stage(
        self, model_id: int, new_stage: ModelStage, promoted_by: Optional[int] = None
    ) -> bool:
        """
        Update model stage

        :param model_id: Model ID
        :param new_stage: New stage
        :param promoted_by: Optional user ID who promoted
        :return: True if successful
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE models
                SET stage = %s, promoted_at = %s, promoted_by = %s
                WHERE id = %s
                """,
                (new_stage.value, datetime.now(), promoted_by, model_id),
            )

            conn.commit()
            cursor.close()

            logger.info(f"Updated model {model_id} stage to {new_stage.value}")
            return True

        except Exception as e:
            logger.error(f"Error updating model stage: {e}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def store_paper_trading_results(
        self, model_id: int, results: Dict[str, Any]
    ) -> bool:
        """
        Store paper trading results for a model

        :param model_id: Model ID
        :param results: Paper trading results dictionary
        :return: True if successful
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE models
                SET paper_trading_results = %s
                WHERE id = %s
                """,
                (json.dumps(results), model_id),
            )

            conn.commit()
            cursor.close()

            logger.info(f"Stored paper trading results for model {model_id}")
            return True

        except Exception as e:
            logger.error(f"Error storing paper trading results: {e}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def list_all_models(self, experiment_id: Optional[int] = None) -> List[Model]:
        """
        List all models, optionally filtered by experiment

        :param experiment_id: Optional experiment ID filter
        :return: List of Model instances
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            if experiment_id:
                cursor.execute(
                    """
                    SELECT id, version, experiment_id, stage, features, hyperparameters,
                           metrics, mlflow_model_uri, mlflow_run_id, paper_trading_results,
                           created_at, promoted_at, promoted_by
                    FROM models
                    WHERE experiment_id = %s
                    ORDER BY created_at DESC
                    """,
                    (experiment_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, version, experiment_id, stage, features, hyperparameters,
                           metrics, mlflow_model_uri, mlflow_run_id, paper_trading_results,
                           created_at, promoted_at, promoted_by
                    FROM models
                    ORDER BY created_at DESC
                    """
                )

            rows = cursor.fetchall()
            cursor.close()

            models = []
            for row in rows:
                (
                    id_val,
                    version,
                    exp_id,
                    stage_str,
                    features_json,
                    hyperparams_json,
                    metrics_json,
                    mlflow_uri,
                    mlflow_run,
                    paper_results_json,
                    created_at,
                    promoted_at,
                    promoted_by,
                ) = row

                models.append(
                    Model(
                        id=id_val,
                        version=version,
                        experiment_id=exp_id,
                        stage=ModelStage(stage_str),
                        features=json.loads(features_json) if features_json else [],
                        hyperparameters=(
                            json.loads(hyperparams_json) if hyperparams_json else {}
                        ),
                        metrics=json.loads(metrics_json) if metrics_json else None,
                        mlflow_model_uri=mlflow_uri,
                        mlflow_run_id=mlflow_run,
                        paper_trading_results=(
                            json.loads(paper_results_json)
                            if paper_results_json
                            else None
                        ),
                        created_at=created_at,
                        promoted_at=promoted_at,
                        promoted_by=promoted_by,
                    )
                )

            return models

        except Exception as e:
            logger.error(f"Error listing models: {e}", exc_info=True)
            return []
        finally:
            if conn:
                conn.close()
