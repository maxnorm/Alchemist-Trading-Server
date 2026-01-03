"""
Experiment Tracker Module

MLflow integration for experiment tracking, model logging, and artifact management.
Provides a clean interface for tracking training runs, hyperparameters, metrics,
and model artifacts.
"""

import os
import sys
import json
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Union

try:
    import mlflow
    from mlflow.tracking import MlflowClient
    from mlflow.models.signature import infer_signature

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False


class ExperimentTracker:
    """
    MLflow integration for experiment tracking.

    Provides a simplified interface for:
    - Starting and managing experiment runs
    - Logging hyperparameters
    - Logging metrics at each step
    - Logging model artifacts
    - Registering models to the registry

    Usage:
        tracker = ExperimentTracker(
            tracking_uri="http://localhost:5000",
            experiment_name="trading-dqn"
        )

        run_id = tracker.start_run("training-v1")
        tracker.log_params({'learning_rate': 0.001, 'gamma': 0.99})

        for step in range(1000):
            metrics = train_step()
            tracker.log_metrics(metrics, step=step)

        tracker.log_model(model, "model", registered_model_name="trading-dqn")
        tracker.end_run()
    """

    def __init__(
        self,
        tracking_uri: str = None,
        experiment_name: str = "trading-dqn",
        create_experiment: bool = True,
    ):
        """
        Initialize experiment tracker.

        Args:
            tracking_uri: MLflow tracking server URI (default: from env or localhost:5000)
            experiment_name: Name of the experiment
            create_experiment: Whether to create experiment if it doesn't exist
        """
        if not MLFLOW_AVAILABLE:
            raise ImportError(
                "MLflow is not installed. Install with: pip install mlflow>=2.10.0"
            )

        self.tracking_uri = tracking_uri or os.getenv(
            "MLFLOW_TRACKING_URI", "http://localhost:5000"
        )
        self.experiment_name = experiment_name

        # Configure MLflow
        mlflow.set_tracking_uri(self.tracking_uri)

        # Get or create experiment
        if create_experiment:
            experiment = mlflow.get_experiment_by_name(experiment_name)
            if experiment is None:
                mlflow.create_experiment(experiment_name)

        mlflow.set_experiment(experiment_name)

        self.client = MlflowClient(self.tracking_uri)
        self.run = None
        self._run_id = None

        self.logger = logging.getLogger(__name__)

    @property
    def run_id(self) -> Optional[str]:
        """Get current run ID"""
        return self._run_id

    @property
    def is_run_active(self) -> bool:
        """Check if a run is currently active"""
        return self.run is not None

    def start_run(
        self,
        run_name: str = None,
        tags: Dict[str, str] = None,
        description: str = None,
        experiment_id: Optional[int] = None,
    ) -> str:
        """
        Start a new experiment run.

        Args:
            run_name: Name for this run (default: timestamp-based)
            tags: Additional tags for the run
            description: Description of the run
            experiment_id: Optional experiment ID to link this run to

        Returns:
            run_id: The ID of the started run
        """
        if self.run is not None:
            self.logger.warning("Run already active. Ending previous run.")
            self.end_run()

        run_name = run_name or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        self.run = mlflow.start_run(run_name=run_name)
        self._run_id = self.run.info.run_id

        # Log system information
        self._log_system_info()

        # Link to experiment if provided
        if experiment_id is not None:
            mlflow.set_tag("experiment_id", str(experiment_id))
            if tags is None:
                tags = {}
            tags["experiment_id"] = str(experiment_id)

        # Log additional tags
        if tags:
            mlflow.set_tags(tags)

        if description:
            mlflow.set_tag("mlflow.note.content", description)

        self.logger.info(f"Started MLflow run: {run_name} (ID: {self._run_id})")

        return self._run_id

    def _log_system_info(self) -> None:
        """Log system information for reproducibility"""
        mlflow.log_param("python_version", sys.version.split()[0])
        mlflow.log_param("platform", sys.platform)

        # Log git commit if available
        git_commit = self._get_git_commit()
        if git_commit:
            mlflow.log_param("git_commit", git_commit)

        # Log timestamp
        mlflow.log_param("start_time", datetime.now().isoformat())

        # Log environment info
        try:
            import tensorflow as tf

            mlflow.log_param("tensorflow_version", tf.__version__)
        except ImportError:
            pass

        try:
            import numpy as np

            mlflow.log_param("numpy_version", np.__version__)
        except ImportError:
            pass

    def _get_git_commit(self) -> Optional[str]:
        """Get current git commit hash"""
        try:
            import subprocess

            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=os.getcwd(),
            )
            if result.returncode == 0:
                return result.stdout.strip()[:8]
        except Exception:
            pass
        return None

    def log_params(self, params: Dict[str, Any]) -> None:
        """
        Log hyperparameters.

        Args:
            params: Dictionary of parameter names and values
        """
        if not self.is_run_active:
            raise RuntimeError("No active run. Call start_run() first.")

        # Convert non-string values to strings
        clean_params = {}
        for key, value in params.items():
            if isinstance(value, (list, dict)):
                clean_params[key] = json.dumps(value)
            else:
                clean_params[key] = str(value)

        mlflow.log_params(clean_params)

    def log_param(self, key: str, value: Any) -> None:
        """Log a single parameter"""
        self.log_params({key: value})

    def log_metrics(self, metrics: Dict[str, float], step: int = None) -> None:
        """
        Log metrics at a given step.

        Args:
            metrics: Dictionary of metric names and values
            step: Step number (optional)
        """
        if not self.is_run_active:
            raise RuntimeError("No active run. Call start_run() first.")

        for key, value in metrics.items():
            if value is not None:
                try:
                    mlflow.log_metric(key, float(value), step=step)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Could not log metric {key}: {e}")

    def log_metric(self, key: str, value: float, step: int = None) -> None:
        """Log a single metric"""
        self.log_metrics({key: value}, step=step)

    def log_model(
        self,
        model,
        artifact_path: str = "model",
        registered_model_name: str = None,
        signature=None,
        input_example=None,
    ) -> str:
        """
        Log a Keras model and optionally register it.

        Args:
            model: Keras model to log
            artifact_path: Path within the run's artifact directory
            registered_model_name: Name to register model under (optional)
            signature: Model signature for inputs/outputs
            input_example: Example input for documentation

        Returns:
            model_uri: URI of the logged model
        """
        if not self.is_run_active:
            raise RuntimeError("No active run. Call start_run() first.")

        # Infer signature if not provided
        if signature is None and input_example is not None:
            try:
                output = model.predict(input_example, verbose=0)
                signature = infer_signature(input_example, output)
            except Exception as e:
                self.logger.warning(f"Could not infer signature: {e}")

        # Log the model
        mlflow.keras.log_model(
            model,
            artifact_path,
            registered_model_name=registered_model_name,
            signature=signature,
            input_example=input_example,
        )

        model_uri = f"runs:/{self._run_id}/{artifact_path}"
        self.logger.info(f"Logged model to: {model_uri}")

        return model_uri

    def log_artifact(self, local_path: str, artifact_path: str = None) -> None:
        """
        Log a file or directory as an artifact.

        Args:
            local_path: Path to local file or directory
            artifact_path: Destination path within artifacts (optional)
        """
        if not self.is_run_active:
            raise RuntimeError("No active run. Call start_run() first.")

        if os.path.isdir(local_path):
            mlflow.log_artifacts(local_path, artifact_path)
        else:
            mlflow.log_artifact(local_path, artifact_path)

    def log_dict(self, dictionary: Dict, artifact_file: str) -> None:
        """
        Log a dictionary as a JSON artifact.

        Args:
            dictionary: Dictionary to log
            artifact_file: Filename for the artifact (e.g., "config.json")
        """
        if not self.is_run_active:
            raise RuntimeError("No active run. Call start_run() first.")

        mlflow.log_dict(dictionary, artifact_file)

    def log_dataset_info(
        self,
        version: str,
        path: str,
        data_hash: str = None,
        row_count: int = None,
        date_range: Dict[str, str] = None,
    ) -> None:
        """
        Log dataset information for reproducibility.

        Args:
            version: Dataset version string
            path: Path to dataset
            data_hash: Hash of dataset for verification
            row_count: Number of rows in dataset
            date_range: Date range of data
        """
        if not self.is_run_active:
            raise RuntimeError("No active run. Call start_run() first.")

        mlflow.log_param("data_version", version)
        mlflow.log_param("data_path", path)

        if data_hash:
            mlflow.log_param("data_hash", data_hash)
        if row_count:
            mlflow.log_param("data_row_count", row_count)
        if date_range:
            mlflow.log_param("data_start_date", date_range.get("start", ""))
            mlflow.log_param("data_end_date", date_range.get("end", ""))

    def log_figure(self, figure, artifact_file: str) -> None:
        """
        Log a matplotlib figure.

        Args:
            figure: Matplotlib figure
            artifact_file: Filename for the figure
        """
        if not self.is_run_active:
            raise RuntimeError("No active run. Call start_run() first.")

        mlflow.log_figure(figure, artifact_file)

    def set_tag(self, key: str, value: str) -> None:
        """Set a tag on the current run"""
        if not self.is_run_active:
            raise RuntimeError("No active run. Call start_run() first.")

        mlflow.set_tag(key, value)

    def end_run(self, status: str = "FINISHED") -> None:
        """
        End the current run.

        Args:
            status: Final status ("FINISHED", "FAILED", "KILLED")
        """
        if self.run is None:
            return

        # Log end time
        mlflow.log_param("end_time", datetime.now().isoformat())

        mlflow.end_run(status=status)

        self.logger.info(f"Ended MLflow run: {self._run_id} (status: {status})")

        self.run = None
        self._run_id = None

    def get_run(self, run_id: str) -> Optional[Any]:
        """Get run information by ID"""
        try:
            return self.client.get_run(run_id)
        except Exception as e:
            self.logger.error(f"Failed to get run {run_id}: {e}")
            return None

    def search_runs(
        self,
        filter_string: str = "",
        max_results: int = 100,
        order_by: List[str] = None,
    ) -> List:
        """
        Search for runs matching criteria.

        Args:
            filter_string: SQL-like filter (e.g., "params.learning_rate > 0.001")
            max_results: Maximum number of results
            order_by: List of columns to order by

        Returns:
            List of matching runs
        """
        experiment = mlflow.get_experiment_by_name(self.experiment_name)
        if experiment is None:
            return []

        return mlflow.search_runs(
            experiment_ids=[experiment.experiment_id],
            filter_string=filter_string,
            max_results=max_results,
            order_by=order_by,
        )

    def get_best_run(
        self, metric: str = "final_reward", ascending: bool = False
    ) -> Optional[Any]:
        """
        Get the best run based on a metric.

        Args:
            metric: Metric to optimize
            ascending: If True, lower is better

        Returns:
            Best run or None
        """
        order = "ASC" if ascending else "DESC"
        runs = self.search_runs(order_by=[f"metrics.{metric} {order}"], max_results=1)

        if len(runs) > 0:
            return runs.iloc[0]
        return None

    @staticmethod
    def compute_data_hash(file_path: str) -> str:
        """
        Compute MD5 hash of a file for versioning.

        Args:
            file_path: Path to file

        Returns:
            MD5 hash string
        """
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()[:8]

    def __enter__(self):
        """Context manager entry"""
        return self

    def log_experiment_config(self, experiment) -> None:
        """
        Log experiment configuration as MLflow params and tags.

        Args:
            experiment: Experiment instance with configuration
        """
        if not self.is_run_active:
            raise RuntimeError("No active run. Call start_run() first.")

        # Log experiment metadata as tags
        mlflow.set_tag("experiment_name", experiment.name)
        mlflow.set_tag("experiment_id", str(experiment.id))
        mlflow.set_tag("training_mode", experiment.training_mode)
        mlflow.set_tag("currency_pairs", ",".join(experiment.currency_pairs))
        mlflow.set_tag("features", ",".join(experiment.features))

        # Log experiment description
        if experiment.description:
            mlflow.set_tag("experiment_description", experiment.description)

        # Log feature count and pair count
        mlflow.log_param("num_features", len(experiment.features))
        mlflow.log_param("num_currency_pairs", len(experiment.currency_pairs))

        self.logger.info(
            f"Logged experiment configuration for experiment {experiment.id}"
        )

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if exc_type is not None:
            self.end_run(status="FAILED")
        else:
            self.end_run(status="FINISHED")
        return False


class DummyExperimentTracker:
    """
    Dummy tracker for when MLflow is not available.

    Provides the same interface but does nothing.
    Useful for testing or when MLflow is not installed.
    """

    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        self.logger.warning("MLflow not available - using dummy tracker")

    @property
    def run_id(self) -> Optional[str]:
        return None

    @property
    def is_run_active(self) -> bool:
        return False

    def start_run(self, *args, **kwargs) -> str:
        return "dummy-run-id"

    def log_params(self, params: Dict) -> None:
        pass

    def log_param(self, key: str, value: Any) -> None:
        pass

    def log_metrics(self, metrics: Dict, step: int = None) -> None:
        pass

    def log_metric(self, key: str, value: float, step: int = None) -> None:
        pass

    def log_model(self, *args, **kwargs) -> str:
        return "dummy-model-uri"

    def log_artifact(self, *args, **kwargs) -> None:
        pass

    def log_dict(self, *args, **kwargs) -> None:
        pass

    def log_dataset_info(self, *args, **kwargs) -> None:
        pass

    def set_tag(self, *args, **kwargs) -> None:
        pass

    def end_run(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def get_experiment_tracker(
    tracking_uri: str = None,
    experiment_name: str = "trading-dqn",
    allow_dummy: bool = True,
) -> Union[ExperimentTracker, DummyExperimentTracker]:
    """
    Get an experiment tracker, falling back to dummy if MLflow unavailable.

    Args:
        tracking_uri: MLflow tracking URI
        experiment_name: Experiment name
        allow_dummy: If True, return dummy tracker when MLflow unavailable

    Returns:
        ExperimentTracker or DummyExperimentTracker
    """
    if MLFLOW_AVAILABLE:
        try:
            return ExperimentTracker(
                tracking_uri=tracking_uri, experiment_name=experiment_name
            )
        except Exception as e:
            logging.warning(f"Failed to create MLflow tracker: {e}")
            if allow_dummy:
                return DummyExperimentTracker()
            raise
    else:
        if allow_dummy:
            return DummyExperimentTracker()
        raise ImportError("MLflow is not installed")
