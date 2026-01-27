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
import threading
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
        tracking_uri: Optional[str] = None,
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

        # Initialize logger early so it's available for all initialization code
        self.logger = logging.getLogger(__name__)

        tracking_uri_value = tracking_uri or os.getenv(
            "MLFLOW_TRACKING_URI", "http://localhost:5000"
        )
        self.tracking_uri: str = (
            tracking_uri_value
            if tracking_uri_value is not None
            else "http://localhost:5000"
        )
        self.experiment_name = experiment_name

        # Configure MLflow
        mlflow.set_tracking_uri(self.tracking_uri)

        # Suppress urllib3 retry warnings for MLflow connections
        # These are expected when MLflow server is not available
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)

        # Initialize MLflow components asynchronously to avoid blocking server startup
        # All initialization happens in background threads without waiting
        self.client = None
        self._mlflow_initialized = False

        # Store logger reference for use in nested function
        logger_ref = self.logger

        def _init_mlflow_async():
            """Initialize MLflow components in background without blocking"""
            try:
                # Get or create experiment
                if create_experiment:
                    try:
                        experiment = mlflow.get_experiment_by_name(experiment_name)
                        if experiment is None:
                            mlflow.create_experiment(experiment_name)
                    except Exception as e:
                        logger_ref.debug(f"Could not create MLflow experiment: {e}")

                # Set experiment
                try:
                    mlflow.set_experiment(experiment_name)
                except Exception as e:
                    logger_ref.debug(f"Could not set MLflow experiment: {e}")

                # Create client
                try:
                    self.client = MlflowClient(self.tracking_uri)
                    self._mlflow_initialized = True
                    logger_ref.info(
                        f"MLflow initialized successfully at {self.tracking_uri}"
                    )
                except Exception as e:
                    logger_ref.debug(f"Could not create MLflow client: {e}")
                    self.client = None
            except Exception as e:
                logger_ref.debug(f"MLflow initialization error: {e}")
                self.client = None

        # Start initialization in background thread - don't wait for it
        init_thread = threading.Thread(target=_init_mlflow_async, daemon=True)
        init_thread.start()
        # Don't join - let it run in background
        self.run: Optional[Any] = None
        self._run_id: Optional[str] = None

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
        run_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
        experiment_id: Optional[int] = None,
        log_data_versions: bool = True,
        log_reproducibility: bool = True,
    ) -> str:
        """
        Start a new experiment run.

        Args:
            run_name: Name for this run (default: timestamp-based)
            tags: Additional tags for the run
            description: Description of the run
            experiment_id: Optional experiment ID to link this run to
            log_data_versions: Whether to log DVC data versions (default: True)
            log_reproducibility: Whether to log reproducibility metadata (default: True)

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

        # Log data versions and reproducibility metadata if requested
        data_versioner = None
        if log_data_versions or log_reproducibility:
            try:
                from mlops.data_versioner import DataVersioner

                data_versioner = DataVersioner()
            except ImportError:
                pass

        if log_data_versions:
            try:
                self.log_data_versions(data_versioner)
            except Exception as e:
                self.logger.warning(f"Failed to log data versions: {e}")

        if log_reproducibility:
            try:
                self.log_reproducibility_metadata(data_versioner)
            except Exception as e:
                self.logger.warning(f"Failed to log reproducibility metadata: {e}")

        self.logger.info(f"Started MLflow run: {run_name} (ID: {self._run_id})")

        return self._run_id if self._run_id is not None else ""

    def _log_system_info(self) -> None:
        """Log system information for reproducibility"""
        mlflow.log_param("python_version", sys.version.split()[0])
        mlflow.log_param("platform", sys.platform)

        # Log git commit if available (short version for backward compatibility)
        git_commit_short = self._get_git_commit(short=True)
        git_commit_full = self._get_git_commit(short=False)
        if git_commit_short:
            mlflow.log_param("git_commit", git_commit_short)
            # Also log as tags for easy filtering
            mlflow.set_tag("git_commit_short", git_commit_short)
        if git_commit_full:
            mlflow.set_tag("git_commit", git_commit_full)

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

    def _compute_config_hash(self, config_path: str = "params.yaml") -> Optional[str]:
        """Compute hash of params.yaml for reproducibility"""
        try:
            from pathlib import Path

            config_file = Path(config_path)
            if not config_file.exists():
                self.logger.warning(f"Config file not found: {config_path}")
                return None

            hasher = hashlib.sha256()
            with open(config_file, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()[:16]
        except Exception as e:
            self.logger.warning(f"Failed to compute config hash: {e}")
            return None

    def _compute_experiment_config_hash(
        self, experiment_config: Dict[str, Any]
    ) -> Optional[str]:
        """
        Compute deterministic hash of experiment config dictionary.

        Args:
            experiment_config: Experiment configuration dictionary

        Returns:
            SHA256 hash (first 16 chars) or None if computation fails
        """
        try:
            # Serialize config dict to JSON with sorted keys for determinism
            config_json = json.dumps(experiment_config, sort_keys=True, default=str)
            # Compute SHA256 hash
            hasher = hashlib.sha256()
            hasher.update(config_json.encode("utf-8"))
            return hasher.hexdigest()[:16]
        except Exception as e:
            self.logger.warning(f"Failed to compute experiment config hash: {e}")
            return None

    def _compute_requirements_hash(self) -> Optional[Dict[str, str]]:
        """
        Compute hash of requirements.txt for reproducibility.

        Returns:
            Dictionary with 'hash' and 'path' keys, or None if file not found
        """
        try:
            from pathlib import Path

            # Try multiple possible locations
            possible_paths = [
                Path("requirements.txt"),  # Project root
                Path("src/backend/trading_server/requirements.txt"),  # Server-specific
                Path(__file__).parent.parent.parent.parent
                / "requirements.txt",  # Relative to this file
            ]

            requirements_file = None
            for path in possible_paths:
                if path.exists():
                    requirements_file = path
                    break

            if not requirements_file:
                self.logger.debug("requirements.txt not found in any expected location")
                return None

            hasher = hashlib.sha256()
            with open(requirements_file, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)

            return {"hash": hasher.hexdigest(), "path": str(requirements_file)}
        except Exception as e:
            self.logger.warning(f"Failed to compute requirements hash: {e}")
            return None

    def _get_environment_id(self) -> Optional[str]:
        """Get environment identifier (Docker image or conda env)"""
        # Check for Docker
        docker_image = os.getenv("DOCKER_IMAGE_TAG")
        if docker_image:
            return f"docker:{docker_image}"

        # Check for conda
        conda_env = os.getenv("CONDA_DEFAULT_ENV")
        if conda_env:
            return f"conda:{conda_env}"

        # Check for virtualenv
        venv = os.getenv("VIRTUAL_ENV")
        if venv:
            from pathlib import Path

            venv_name = Path(venv).name
            return f"venv:{venv_name}"

        # Fallback to Python executable path hash
        try:
            python_path = sys.executable
            hasher = hashlib.sha256(python_path.encode())
            return f"python:{hasher.hexdigest()[:8]}"
        except Exception:
            return None

    def log_reproducibility_metadata(
        self,
        data_versioner: Optional[Any] = None,
        random_seed: Optional[int] = None,
        experiment_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log complete reproducibility checklist.

        Args:
            data_versioner: Optional DataVersioner instance for data version information.
            random_seed: Optional random seed value used for training.
            experiment_config: Optional experiment configuration dictionary for config hash.
        """
        if not self.is_run_active:
            raise RuntimeError("No active run. Call start_run() first.")

        # Compute requirements hash
        requirements_info = self._compute_requirements_hash()

        # Get git commit hash
        git_commit_full = self._get_git_commit(short=False)
        git_commit_short = self._get_git_commit(short=True)

        # Compute config hash - prefer experiment config if provided, otherwise params.yaml
        config_hash = None
        config_path = None
        if experiment_config is not None:
            config_hash = self._compute_experiment_config_hash(experiment_config)
            config_path = "experiment_config"
        else:
            config_hash = self._compute_config_hash()
            config_path = "params.yaml"

        reproducibility = {
            "code_commit_hash": git_commit_full,
            "code_commit_short": git_commit_short,
            "config_hash": config_hash,
            "config_path": config_path,
            "environment_id": self._get_environment_id(),
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
            "timestamp": datetime.now().isoformat(),
        }

        # Add random seed if provided
        if random_seed is not None:
            reproducibility["random_seed"] = random_seed

        # Add requirements hash if available
        if requirements_info:
            reproducibility["requirements_hash"] = requirements_info["hash"]
            reproducibility["requirements_path"] = requirements_info["path"]

        # Add data versions if available
        if data_versioner:
            try:
                summary = data_versioner.get_data_version_summary()
                reproducibility["data_versions"] = summary.get("data_versions", {})
                reproducibility["dvc_repo_root"] = summary.get("dvc_repo_root")
            except Exception as e:
                self.logger.warning(f"Failed to get data versions: {e}")

        # Log required tags for Gate C: git_commit, random_seed, config_hash
        mlflow.set_tag("git_commit", git_commit_full or "unknown")
        if random_seed is not None:
            mlflow.set_tag("random_seed", str(random_seed))
        mlflow.set_tag("config_hash", config_hash or "unknown")

        # Log as tags for easy filtering (backward compatibility)
        mlflow.set_tag(
            "reproducibility_code_commit",
            git_commit_full or "unknown",
        )
        mlflow.set_tag(
            "reproducibility_config_hash", config_hash or "unknown"
        )
        mlflow.set_tag(
            "reproducibility_environment",
            reproducibility["environment_id"] or "unknown",
        )
        if requirements_info:
            mlflow.set_tag(
                "reproducibility_requirements_hash", requirements_info["hash"]
            )

        # Log as parameters (for querying)
        mlflow.log_param("git_commit", git_commit_full or "unknown")
        if random_seed is not None:
            mlflow.log_param("random_seed", random_seed)
        mlflow.log_param("config_hash", config_hash or "unknown")

        # Log as parameters (backward compatibility)
        mlflow.log_param(
            "reproducibility_code_commit",
            git_commit_full or "unknown",
        )
        mlflow.log_param(
            "reproducibility_config_hash", config_hash or "unknown"
        )
        mlflow.log_param(
            "reproducibility_environment",
            reproducibility["environment_id"] or "unknown",
        )
        if requirements_info:
            mlflow.log_param("requirements_hash", requirements_info["hash"])

        # Store complete metadata as JSON artifact
        mlflow.log_dict(reproducibility, "reproducibility_metadata.json")

        self.logger.info("Logged reproducibility metadata")

    def enforce_random_seeds(self, seed: int) -> None:
        """
        Enforce random seeds for numpy, TensorFlow, and Python's random module.

        This ensures reproducibility by setting seeds for all random number generators
        used in the training process.

        Args:
            seed: Random seed value to use
        """
        import random

        # Seed Python's random module
        random.seed(seed)

        # Seed numpy
        try:
            import numpy as np

            np.random.seed(seed)
        except ImportError:
            self.logger.warning("NumPy not available - skipping numpy seed")

        # Seed TensorFlow if available
        try:
            import tensorflow as tf

            tf.random.set_seed(seed)
        except ImportError:
            self.logger.debug("TensorFlow not available - skipping TensorFlow seed")

        self.logger.info(
            f"Enforced random seeds: numpy, tensorflow, python.random = {seed}"
        )

    def _get_git_commit(self, short: bool = False) -> Optional[str]:
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
                commit_hash = result.stdout.strip()
                return commit_hash[:8] if short else commit_hash
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

    def log_metrics(
        self, metrics: Dict[str, float], step: Optional[int] = None
    ) -> None:
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

    def log_metric(self, key: str, value: float, step: Optional[int] = None) -> None:
        """Log a single metric"""
        self.log_metrics({key: value}, step=step)

    def log_model(
        self,
        model,
        artifact_path: str = "model",
        registered_model_name: Optional[str] = None,
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

    def log_artifact(
        self, local_path: str, artifact_path: Optional[str] = None
    ) -> None:
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
        data_hash: Optional[str] = None,
        row_count: Optional[int] = None,
        date_range: Optional[Dict[str, str]] = None,
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
        if self.client is None:
            self.logger.warning("MLflow client not initialized")
            return None
        try:
            return self.client.get_run(run_id)
        except Exception as e:
            self.logger.error(f"Failed to get run {run_id}: {e}")
            return None

    def search_runs(
        self,
        filter_string: str = "",
        max_results: int = 100,
        order_by: Optional[List[str]] = None,
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
            return runs[0]  # Use list indexing instead of .iloc
        return None

    def get_reproducibility_report(
        self, run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get reproducibility report for a run.

        Args:
            run_id: Run ID to get report for. If None, uses current run.

        Returns:
            Dictionary with reproducibility information
        """
        if run_id is None:
            run_id = self._run_id

        if run_id is None:
            raise ValueError("No run ID provided")

        run = self.get_run(run_id)
        if run is None:
            return {"error": "Run not found"}

        # Extract reproducibility information from run
        tags = run.data.tags
        params = run.data.params

        report = {
            "run_id": run_id,
            "code_commit": tags.get("reproducibility_code_commit")
            or params.get("reproducibility_code_commit"),
            "config_hash": tags.get("reproducibility_config_hash")
            or params.get("reproducibility_config_hash"),
            "environment": tags.get("reproducibility_environment")
            or params.get("reproducibility_environment"),
            "python_version": params.get("python_version"),
            "platform": params.get("platform"),
            "start_time": params.get("start_time"),
        }

        # Try to get data versions from artifact
        if self.client is not None:
            try:
                artifacts = self.client.list_artifacts(run_id)
                for artifact in artifacts:
                    if artifact.path == "reproducibility_metadata.json":
                        artifact_data = self.client.download_artifacts(
                            run_id, artifact.path
                        )
                        with open(artifact_data, "r") as f:
                            report["full_metadata"] = json.load(f)
                        break
            except Exception as e:
                self.logger.warning(
                    f"Failed to load full reproducibility metadata: {e}"
                )

        return report

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

    def log_data_versions(self, data_versioner: Optional[Any] = None) -> None:
        """
        Log DVC data versions to MLflow tags.

        Args:
            data_versioner: Optional DataVersioner instance. If None, creates a new one.
        """
        if not self.is_run_active:
            raise RuntimeError("No active run. Call start_run() first.")

        if data_versioner is None:
            try:
                from mlops.data_versioner import DataVersioner

                data_versioner = DataVersioner()
            except ImportError:
                self.logger.warning(
                    "DataVersioner not available - skipping data version logging"
                )
                mlflow.set_tag("dvc_available", "false")
                return

        if not data_versioner._dvc_available:
            mlflow.set_tag("dvc_available", "false")
            self.logger.warning("DVC not available - skipping data version logging")
            return

        # Get data version summary
        summary = data_versioner.get_data_version_summary()

        # Store as tags
        mlflow.set_tag("dvc_available", "true")
        mlflow.set_tag("dvc_repo_root", summary["dvc_repo_root"])

        # Store individual data file versions
        for file_path, version in summary["data_versions"].items():
            tag_key = f"data_version_{file_path.replace('/', '_').replace('.', '_')}"
            mlflow.set_tag(tag_key, version)

        # Store summary as JSON artifact
        mlflow.log_dict(summary, "data_versions.json")

    def log_feature_pipeline(
        self,
        pipeline_version: str,
        feature_list: List[str],
        feature_metadata: Dict[str, Any],
    ) -> None:
        """
        Log feature pipeline version and metadata to MLflow.

        Args:
            pipeline_version: Feature pipeline version string
            feature_list: List of feature names
            feature_metadata: Dictionary with feature definitions and metadata
        """
        if not self.is_run_active:
            raise RuntimeError("No active run. Call start_run() first.")

        # Set feature pipeline version as tag
        mlflow.set_tag("feature_pipeline_version", pipeline_version)

        # Log feature pipeline metadata as artifact
        pipeline_data = {
            "pipeline_version": pipeline_version,
            "features": feature_list,
            "metadata": feature_metadata,
        }
        mlflow.log_dict(pipeline_data, "feature_pipeline.json")

        # Also log as parameters for easy querying
        mlflow.log_param("feature_pipeline_version", pipeline_version)
        mlflow.log_param("num_pipeline_features", len(feature_list))

        self.logger.info(
            f"Logged feature pipeline version {pipeline_version} with {len(feature_list)} features"
        )

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

    def log_metrics(self, metrics: Dict, step: Optional[int] = None) -> None:
        pass

    def log_metric(self, key: str, value: float, step: Optional[int] = None) -> None:
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
    tracking_uri: Optional[str] = None,
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
            tracker = ExperimentTracker(
                tracking_uri=tracking_uri, experiment_name=experiment_name
            )
            return tracker
        except Exception as e:
            # Log a concise error message (connection errors are expected if MLflow is not running)
            error_msg = str(e)
            if "Connection" in error_msg or "refused" in error_msg.lower():
                logger = logging.getLogger(__name__)
                logger.debug(f"MLflow server not available: {error_msg}")
            else:
                logging.warning(f"Failed to create MLflow tracker: {error_msg}")
            if allow_dummy:
                return DummyExperimentTracker()
            raise
    else:
        if allow_dummy:
            return DummyExperimentTracker()
        raise ImportError("MLflow is not installed")
