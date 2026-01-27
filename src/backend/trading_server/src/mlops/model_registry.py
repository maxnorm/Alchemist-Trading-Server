"""
Model Registry Module

Database-backed model registry that syncs with MLflow.
Tracks model lifecycle stages and links models to experiments.
"""

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Try to import MLflow for model downloading
try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False

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
    ) -> Optional[Model]:
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
        try:
            # Generate version if not provided
            if not version:
                # Get latest version number for this experiment
                result = self.db.execute_one(
                    "SELECT COUNT(*) FROM models WHERE experiment_id = :experiment_id",
                    {"experiment_id": experiment_id},
                )
                count = result[0] if result else 0
                version = f"v{count + 1}"

            # Check if version already exists
            existing = self.db.execute_one(
                "SELECT id FROM models WHERE version = :version", {"version": version}
            )
            if existing:
                raise ValueError(f"Model version {version} already exists")

            # Insert model
            query = """
                INSERT INTO models (
                    version, experiment_id, stage, features, hyperparameters,
                    metrics, mlflow_model_uri, mlflow_run_id, created_at
                ) VALUES (:version, :experiment_id, :stage, :features, :hyperparameters,
                    :metrics, :mlflow_model_uri, :mlflow_run_id, :created_at)
                RETURNING id
            """

            params = {
                "version": version,
                "experiment_id": experiment_id,
                "stage": ModelStage.TRAINING.value,
                "features": json.dumps(features),
                "hyperparameters": json.dumps(hyperparameters),
                "metrics": json.dumps(metrics) if metrics else None,
                "mlflow_model_uri": mlflow_model_uri,
                "mlflow_run_id": mlflow_run_id,
                "created_at": datetime.now(),
            }

            result = self.db.execute_one(query, params)
            if result:
                model_id = result[0]
                logger.info(
                    f"Registered model {model_id} (version {version}) for experiment {experiment_id}"
                )

                # Auto-promote to staging
                self.update_model_stage(model_id, ModelStage.STAGING, promoted_by=None)

                model = self.get_model(model_id)
                if model is None:
                    raise ValueError(f"Model {model_id} not found after registration")
                return model
            raise RuntimeError("Failed to register model")

        except SQLAlchemyError as e:
            logger.error(f"Error registering model: {e}", exc_info=True)
            raise

    def get_model(self, model_id: int) -> Optional[Model]:
        """
        Get model by ID

        :param model_id: Model ID
        :return: Model instance or None
        """
        try:
            query = """
                SELECT id, version, experiment_id, stage, features, hyperparameters,
                       metrics, mlflow_model_uri, mlflow_run_id, paper_trading_results,
                       created_at, promoted_at, promoted_by
                FROM models
                WHERE id = :model_id
            """

            params = {"model_id": model_id}
            row = self.db.execute_one(query, params)

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

        except SQLAlchemyError as e:
            logger.error(f"Error getting model {model_id}: {e}", exc_info=True)
            return None

    def get_model_by_version(self, version: str) -> Optional[Model]:
        """
        Get model by version string

        :param version: Version string
        :return: Model instance or None
        """
        try:
            query = """
                SELECT id, version, experiment_id, stage, features, hyperparameters,
                       metrics, mlflow_model_uri, mlflow_run_id, paper_trading_results,
                       created_at, promoted_at, promoted_by
                FROM models
                WHERE version = :version
            """

            params = {"version": version}
            row = self.db.execute_one(query, params)

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

        except SQLAlchemyError as e:
            logger.error(
                f"Error getting model by version {version}: {e}", exc_info=True
            )
            return None

    def get_models_by_stage(self, stage: ModelStage) -> List[Model]:
        """
        Get all models in a specific stage

        :param stage: Model stage
        :return: List of Model instances
        """
        try:
            query = """
                SELECT id, version, experiment_id, stage, features, hyperparameters,
                       metrics, mlflow_model_uri, mlflow_run_id, paper_trading_results,
                       created_at, promoted_at, promoted_by
                FROM models
                WHERE stage = :stage
                ORDER BY created_at DESC
            """

            params = {"stage": stage.value}
            rows = self.db.execute_with_result(query, params)

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

        except SQLAlchemyError as e:
            logger.error(
                f"Error getting models by stage {stage.value}: {e}", exc_info=True
            )
            return []

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
        try:
            query = """
                UPDATE models
                SET stage = :stage, promoted_at = :promoted_at, promoted_by = :promoted_by
                WHERE id = :model_id
            """

            params = {
                "stage": new_stage.value,
                "promoted_at": datetime.now(),
                "promoted_by": promoted_by,
                "model_id": model_id,
            }

            with self.db.execute_query() as conn:
                conn.execute(text(query), params)

            logger.info(f"Updated model {model_id} stage to {new_stage.value}")
            return True

        except SQLAlchemyError as e:
            logger.error(f"Error updating model stage: {e}", exc_info=True)
            return False

    def store_paper_trading_results(
        self, model_id: int, results: Dict[str, Any]
    ) -> bool:
        """
        Store paper trading results for a model

        :param model_id: Model ID
        :param results: Paper trading results dictionary
        :return: True if successful
        """
        try:
            query = """
                UPDATE models
                SET paper_trading_results = :paper_trading_results
                WHERE id = :model_id
            """

            params = {
                "paper_trading_results": json.dumps(results),
                "model_id": model_id,
            }

            with self.db.execute_query() as conn:
                conn.execute(text(query), params)

            logger.info(f"Stored paper trading results for model {model_id}")
            return True

        except SQLAlchemyError as e:
            logger.error(f"Error storing paper trading results: {e}", exc_info=True)
            return False

    def list_all_models(self, experiment_id: Optional[int] = None) -> List[Model]:
        """
        List all models, optionally filtered by experiment

        :param experiment_id: Optional experiment ID filter
        :return: List of Model instances
        """
        try:
            if experiment_id:
                query = """
                    SELECT id, version, experiment_id, stage, features, hyperparameters,
                           metrics, mlflow_model_uri, mlflow_run_id, paper_trading_results,
                           created_at, promoted_at, promoted_by
                    FROM models
                    WHERE experiment_id = :experiment_id
                    ORDER BY created_at DESC
                """
                params = {"experiment_id": experiment_id}
            else:
                query = """
                    SELECT id, version, experiment_id, stage, features, hyperparameters,
                           metrics, mlflow_model_uri, mlflow_run_id, paper_trading_results,
                           created_at, promoted_at, promoted_by
                    FROM models
                    ORDER BY created_at DESC
                """
                params = None

            rows = self.db.execute_with_result(query, params)

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

        except SQLAlchemyError as e:
            logger.error(f"Error listing models: {e}", exc_info=True)
            return []

    def get_model_path(self, model_id: int, download_dir: Optional[str] = None) -> Optional[str]:
        """
        Get model path for loading a trained model.
        
        If model has MLflow URI, downloads it to a local directory and returns the path.
        Otherwise returns None if no model URI is available.
        
        :param model_id: Model ID
        :param download_dir: Optional directory to download model to (creates temp dir if None)
        :return: Local directory path containing the model files, or None if model not found
        """
        try:
            model = self.get_model(model_id)
            if not model:
                logger.warning(f"Model {model_id} not found")
                return None
            
            if not model.mlflow_model_uri:
                logger.warning(
                    f"Model {model_id} has no MLflow model URI. "
                    "Cannot determine model path for loading."
                )
                return None
            
            # If it's already a local path, return it
            if os.path.exists(model.mlflow_model_uri) and os.path.isdir(model.mlflow_model_uri):
                return model.mlflow_model_uri
            
            # If it's an MLflow URI, download it
            if MLFLOW_AVAILABLE and model.mlflow_model_uri.startswith(("runs:/", "models:/", "file:/")):
                try:
                    # Create download directory if not provided
                    if download_dir is None:
                        download_dir = tempfile.mkdtemp(prefix=f"model_{model_id}_")
                    else:
                        os.makedirs(download_dir, exist_ok=True)
                    
                    # Download model from MLflow
                    logger.info(f"Downloading model {model_id} from MLflow URI: {model.mlflow_model_uri}")
                    mlflow.artifacts.download_artifacts(
                        artifact_uri=model.mlflow_model_uri,
                        dst_path=download_dir
                    )
                    
                    # MLflow downloads to a subdirectory, find the actual model directory
                    # The structure is usually: download_dir/model/...
                    model_dir = download_dir
                    if os.path.exists(os.path.join(download_dir, "model")):
                        model_dir = os.path.join(download_dir, "model")
                    
                    logger.info(f"Model {model_id} downloaded to: {model_dir}")
                    return model_dir
                    
                except Exception as e:
                    logger.error(
                        f"Failed to download model {model_id} from MLflow: {e}",
                        exc_info=True
                    )
                    return None
            else:
                # Not an MLflow URI and not a local path
                logger.warning(
                    f"Model {model_id} has unsupported URI format: {model.mlflow_model_uri}"
                )
                return None
            
        except Exception as e:
            logger.error(f"Error getting model path for model {model_id}: {e}", exc_info=True)
            return None
