"""
Experiment Runner

Executes experiments by creating agents, environments, and training loops.
"""

import logging
import threading
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from sqlalchemy import text

from .models import ExperimentStatus, ExperimentRepository
from domain.config.agent_config import AgentConfig
from domain.config.training_config import TrainingConfig
from domain.environment_type import EnvironmentType
from infrastructure.factories.agent_factory import AgentFactory
from infrastructure.factories.environment_factory import EnvironmentFactory
from training.live_trainer import LiveTrainer
from models.account import Account
from utils.risk_management import RiskManager

logger = logging.getLogger(__name__)

# Try to import CSCV
try:
    from training.cscv import combinatorially_symmetric_cross_validation, interpret_pbo

    CSCV_AVAILABLE = True
except ImportError:
    CSCV_AVAILABLE = False
    logger.warning("CSCV module not available. PBO calculation will be skipped.")


class ExperimentRunner:
    """
    Runner for executing experiments.
    """

    def __init__(
        self,
        database,
        experiment_tracker,
        agent_factory: AgentFactory,
        environment_factory: EnvironmentFactory,
        get_account_func: Callable[[int], Optional[Account]],
        get_risk_manager_func: Callable[[], RiskManager],
        training_loop_factory: Optional[Callable] = None,
        feature_catalog=None,
    ):
        """
        Initialize experiment runner

        :param database: Database instance
        :param experiment_tracker: ExperimentTracker (MLflow) instance
        :param agent_factory: AgentFactory instance
        :param environment_factory: EnvironmentFactory instance
        :param get_account_func: Function to get Account instance by account_login.
        :param get_risk_manager_func: Function to get RiskManager instance
        :param training_loop_factory: Optional factory for creating training loops
        :param feature_catalog: Optional FeatureCatalog instance for feature validation
        """
        self.db = database
        self.experiment_tracker = experiment_tracker
        self.agent_factory = agent_factory
        self.environment_factory = environment_factory
        self.get_account = get_account_func
        self.get_risk_manager = get_risk_manager_func
        self.training_loop_factory = training_loop_factory
        self.feature_catalog = feature_catalog

        self.repository = ExperimentRepository(database)

        # Track running experiments: experiment_id -> (trainer, thread)
        self.running_experiments: Dict[int, tuple] = {}
        self._lock = threading.Lock()

    def start_experiment(self, experiment_id: int) -> bool:
        """
        Start training for an experiment

        Steps:
        1. Load experiment from database
        2. Validate experiment is in 'created' status
        3. Create agent with experiment hyperparameters
        4. Create environment with experiment features
        5. Start MLflow run and link to experiment
        6. Update experiment status to 'training'
        7. Start training loop in background thread
        8. Store training thread reference for stop capability

        :param experiment_id: Experiment ID
        :return: True if started successfully
        """
        with self._lock:
            # Check if already running
            if experiment_id in self.running_experiments:
                logger.warning(f"Experiment {experiment_id} is already running")
                return False

            # Load experiment
            experiment = self.repository.get_experiment(experiment_id)
            if not experiment:
                logger.error(f"Experiment {experiment_id} not found")
                return False

            # Validate status - accept both CREATED and TRAINING
            # (API may update status to TRAINING before Redis message arrives)
            if experiment.status not in (
                ExperimentStatus.CREATED,
                ExperimentStatus.TRAINING,
            ):
                logger.error(
                    f"Experiment {experiment_id} is not in 'created' or 'training' status "
                    f"(current: {experiment.status.value})"
                )
                return False

            try:
                # Create agent config from experiment hyperparameters
                agent_config = self._create_agent_config(experiment.hyperparameters)

                # Get risk manager
                risk_manager = self.get_risk_manager()

                # Map training_mode to EnvironmentType
                # LIVE mode has been removed - use 'paper' for live training on demo accounts
                if experiment.training_mode == "live":
                    raise ValueError(
                        "LIVE training mode has been removed. "
                        "Use 'paper' mode for live training on demo accounts. "
                        "For live trading with trained models, assign a model to a live account."
                    )

                env_type_map = {
                    "paper": EnvironmentType.PAPER,
                    "historical": EnvironmentType.HISTORICAL,
                }
                env_type = env_type_map.get(experiment.training_mode)
                if env_type is None:
                    raise ValueError(
                        f"Invalid training_mode: {experiment.training_mode}. "
                        f"Must be one of: {list(env_type_map.keys())}"
                    )

                # Validate features exist in catalog if feature_catalog is available
                if experiment.features and self.feature_catalog:
                    self._validate_features_exist(experiment.features)

                connectors = self._get_connectors_for_pairs(experiment.currency_pairs)
                window_size = experiment.hyperparameters.get("window_size", 50)
                # Extract seed from hyperparameters (default: 42 for reproducibility)
                seed = experiment.hyperparameters.get("seed", 42)

                # Create environment based on type
                if env_type == EnvironmentType.HISTORICAL:
                    # Historical data must be provided in hyperparameters
                    # Data loading is NOT implemented per requirements
                    data = experiment.hyperparameters.get("historical_data")
                    if data is None:
                        raise ValueError(
                            "Historical data must be provided in hyperparameters. "
                            "Set 'historical_data' key with a pandas DataFrame."
                        )
                    environment = self.environment_factory.create_environment(
                        environment_type=env_type,
                        data=data,
                        window_size=window_size,
                        seed=seed,
                        initial_balance=experiment.hyperparameters.get(
                            "initial_balance", 10000.0
                        ),
                        transaction_cost=experiment.hyperparameters.get(
                            "transaction_cost", 0.0001
                        ),
                    )
                    # For historical, we don't have an account, use None
                    account = None
                elif env_type == EnvironmentType.PAPER:
                    demo_account = self._get_demo_account()
                    environment = self.environment_factory.create_environment(
                        environment_type=env_type,
                        account=demo_account,
                        connectors=connectors,
                        window_size=window_size,
                        seed=seed,
                        features=experiment.features,
                    )
                    account = demo_account
                else:
                    # This should never be reached due to validation above,
                    # but kept for safety
                    raise ValueError(
                        f"Unsupported environment type: {env_type}. "
                        "Only 'historical' and 'paper' modes are supported."
                    )

                # Create agent
                agent = self.agent_factory.create_agent(
                    env=environment, config=agent_config
                )

                # Create training config
                training_config = self._create_training_config(
                    experiment.hyperparameters
                )

                # Execute DVC pipeline to ensure data is up-to-date
                data_versioner = None
                try:
                    from mlops.data_versioner import DataVersioner

                    data_versioner = DataVersioner()
                    if data_versioner._dvc_available:
                        # Check if pipeline needs to be run
                        status = data_versioner.get_pipeline_status()
                        if not status.get("up_to_date", False):
                            logger.info(
                                "DVC pipeline not up-to-date, running pipeline..."
                            )
                            data_versioner.run_pipeline()
                        else:
                            logger.info("DVC pipeline is up-to-date")
                except Exception as e:
                    logger.warning(f"Failed to execute DVC pipeline: {e}")

                # Start MLflow run and link to experiment
                run_name = f"experiment_{experiment_id}_{experiment.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                mlflow_run_id = None
                if self.experiment_tracker:
                    try:
                        mlflow_run_id = self.experiment_tracker.start_run(
                            run_name=run_name,
                            experiment_id=experiment_id,
                            tags={
                                "experiment_name": experiment.name,
                                "experiment_id": str(experiment_id),
                                "training_mode": experiment.training_mode,
                                "currency_pairs": ",".join(experiment.currency_pairs),
                                "features": ",".join(experiment.features),
                            },
                            log_data_versions=False,  # Will log manually with data_versioner
                            log_reproducibility=False,  # Will log manually with seed and config
                        )

                        # Log data versions if available
                        if data_versioner:
                            try:
                                self.experiment_tracker.log_data_versions(
                                    data_versioner
                                )
                            except Exception as e:
                                logger.warning(f"Failed to log data versions: {e}")

                        # Log experiment configuration
                        self.experiment_tracker.log_experiment_config(experiment)

                        # Log feature pipeline metadata if available
                        try:
                            if (
                                hasattr(environment, "feature_engine")
                                and environment.feature_engine
                            ):
                                feature_metadata = (
                                    environment.feature_engine.get_pipeline_metadata()
                                )
                                if feature_metadata and feature_metadata.get("version"):
                                    self.experiment_tracker.log_feature_pipeline(
                                        pipeline_version=feature_metadata["version"],
                                        feature_list=feature_metadata.get(
                                            "features", []
                                        ),
                                        feature_metadata=feature_metadata.get(
                                            "feature_definitions", {}
                                        ),
                                    )
                        except Exception as e:
                            logger.warning(
                                f"Failed to log feature pipeline metadata: {e}"
                            )

                        # Log hyperparameters
                        self.experiment_tracker.log_params(experiment.hyperparameters)

                        # Save complete experiment configuration as artifact
                        experiment_config = {
                            "hyperparameters": experiment.hyperparameters,
                            "currency_pairs": experiment.currency_pairs,
                            "features": experiment.features,
                            "training_mode": experiment.training_mode,
                            "name": experiment.name,
                            "description": experiment.description,
                            "experiment_id": experiment_id,
                        }
                        try:
                            self.experiment_tracker.log_dict(
                                experiment_config, "experiment_config.json"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to save experiment config as artifact: {e}"
                            )

                        # Log seed and enforce random seeds
                        try:
                            self.experiment_tracker.log_param("seed", seed)
                            self.experiment_tracker.set_tag("seed", str(seed))
                            # Enforce random seeds for reproducibility
                            self.experiment_tracker.enforce_random_seeds(seed)
                        except Exception as e:
                            logger.warning(f"Failed to log/enforce random seeds: {e}")

                        # Log reproducibility metadata with seed and experiment config
                        try:
                            self.experiment_tracker.log_reproducibility_metadata(
                                data_versioner=data_versioner,
                                random_seed=seed,
                                experiment_config=experiment_config,
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to log reproducibility metadata: {e}"
                            )

                    except Exception as e:
                        logger.warning(f"Failed to start MLflow run: {e}")

                # Update experiment status
                self.repository.update_experiment_status(
                    experiment_id=experiment_id,
                    status=ExperimentStatus.TRAINING,
                    mlflow_run_id=mlflow_run_id,
                    started_at=datetime.now(),
                )

                # Create trainer
                # Type assertions: LiveTrainer requires LiveTradingEnv and non-None Account
                from typing import cast
                from environments.live_env import LiveTradingEnv
                from models.account import Account
                
                if not isinstance(environment, LiveTradingEnv):
                    raise ValueError(
                        f"LiveTrainer requires LiveTradingEnv, got {type(environment)}"
                    )
                if account is None:
                    raise ValueError("LiveTrainer requires a non-None Account")
                
                trainer = LiveTrainer(
                    agent=agent,
                    environment=cast(LiveTradingEnv, environment),
                    account=cast(Account, account),
                    risk_manager=risk_manager,
                    config=training_config,
                )

                # Set experiment tracker in training loop
                if self.experiment_tracker and hasattr(
                    trainer.training_loop, "tracker"
                ):
                    trainer.training_loop.tracker = self.experiment_tracker

                # Start training in background thread
                training_thread = threading.Thread(
                    target=self._run_training,
                    args=(trainer, experiment_id),
                    daemon=True,
                )
                training_thread.start()

                # Store reference
                self.running_experiments[experiment_id] = (trainer, training_thread)

                logger.info(f"Started experiment {experiment_id}: {experiment.name}")
                return True

            except Exception as e:
                logger.error(
                    f"Error starting experiment {experiment_id}: {e}", exc_info=True
                )
                # Update status to failed
                self.repository.update_experiment_status(
                    experiment_id=experiment_id, status=ExperimentStatus.FAILED
                )
                return False

    def stop_experiment(self, experiment_id: int) -> bool:
        """
        Stop a running experiment

        :param experiment_id: Experiment ID
        :return: True if stopped successfully
        """
        with self._lock:
            if experiment_id not in self.running_experiments:
                logger.warning(f"Experiment {experiment_id} is not running")
                return False

            try:
                trainer, thread = self.running_experiments[experiment_id]

                # Stop trainer
                trainer.stop()

                # Wait for thread to finish (with timeout)
                thread.join(timeout=10)

                # Remove from running experiments
                del self.running_experiments[experiment_id]

                # Update experiment status
                self.repository.update_experiment_status(
                    experiment_id=experiment_id, status=ExperimentStatus.PAUSED
                )

                logger.info(f"Stopped experiment {experiment_id}")
                return True

            except Exception as e:
                logger.error(
                    f"Error stopping experiment {experiment_id}: {e}", exc_info=True
                )
                return False

    def get_experiment_status(self, experiment_id: int) -> Dict[str, Any]:
        """
        Get current status and metrics for an experiment

        :param experiment_id: Experiment ID
        :return: Dictionary with status information
        """
        experiment = self.repository.get_experiment(experiment_id)
        if not experiment:
            return {"error": "Experiment not found"}

        status = {
            "id": experiment.id,
            "name": experiment.name,
            "status": experiment.status.value,
            "mlflow_run_id": experiment.mlflow_run_id,
            "created_at": (
                experiment.created_at.isoformat() if experiment.created_at else None
            ),
            "started_at": (
                experiment.started_at.isoformat() if experiment.started_at else None
            ),
            "completed_at": (
                experiment.completed_at.isoformat() if experiment.completed_at else None
            ),
            "is_running": experiment_id in self.running_experiments,
        }

        # Add training metrics if running
        if experiment_id in self.running_experiments:
            trainer, _ = self.running_experiments[experiment_id]
            if hasattr(trainer, "metrics_tracker"):
                metrics = trainer.metrics_tracker.get_metrics()
                status["metrics"] = metrics

        return status

    def _run_training(self, trainer: LiveTrainer, experiment_id: int):
        """
        Run training and update experiment status on completion

        :param trainer: LiveTrainer instance
        :param experiment_id: Experiment ID
        """
        try:
            trainer.start()

            # Wait for training to complete (or be stopped)
            if trainer.training_thread:
                trainer.training_thread.join()

            # Update experiment status
            with self._lock:
                if experiment_id in self.running_experiments:
                    del self.running_experiments[experiment_id]

                # Determine final status
                final_status = ExperimentStatus.COMPLETED
                if trainer.training_loop and hasattr(
                    trainer.training_loop, "is_running"
                ):
                    if not trainer.training_loop.is_running:
                        # Check if it was stopped or failed
                        final_status = ExperimentStatus.PAUSED

                self.repository.update_experiment_status(
                    experiment_id=experiment_id,
                    status=final_status,
                    completed_at=datetime.now(),
                )

                # End MLflow run
                mlflow_run_id = None
                if self.experiment_tracker:
                    try:
                        mlflow_run_id = self.experiment_tracker.get_current_run_id()
                        self.experiment_tracker.end_run()
                    except Exception as e:
                        logger.warning(f"Failed to end MLflow run: {e}")

                # Register model in database if training completed successfully
                if final_status == ExperimentStatus.COMPLETED:
                    try:
                        from mlops.model_registry import ModelRegistry
                        from experiments.models import ExperimentRepository

                        # Get experiment details
                        exp_repo = ExperimentRepository(self.db)
                        experiment = exp_repo.get_experiment(experiment_id)

                        if experiment:
                            # Get MLflow model URI if available
                            mlflow_model_uri = None
                            if mlflow_run_id and self.experiment_tracker:
                                try:
                                    mlflow_model_uri = (
                                        self.experiment_tracker.get_model_uri()
                                    )
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to get MLflow model URI: {e}"
                                    )

                            # Get training metrics if available
                            metrics = None
                            if trainer.training_loop and hasattr(
                                trainer.training_loop, "metrics_tracker"
                            ):
                                try:
                                    metrics = (
                                        trainer.training_loop.metrics_tracker.get_metrics()
                                    )
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to get training metrics: {e}"
                                    )

                            # Register model
                            run_id = mlflow_run_id or experiment.mlflow_run_id
                            if run_id:
                                model_registry = ModelRegistry(self.db)
                                model = model_registry.register_model(
                                    experiment_id=experiment_id,
                                    mlflow_run_id=run_id,
                                    features=experiment.features,
                                    hyperparameters=experiment.hyperparameters,
                                    mlflow_model_uri=mlflow_model_uri,
                                    metrics=metrics,
                                )

                                if model is not None:
                                    logger.info(
                                        f"Registered model {model.id} (v{model.version}) for experiment {experiment_id}"
                                    )
                                else:
                                    logger.warning(
                                        f"Failed to register model for experiment {experiment_id}: model is None"
                                    )
                            else:
                                logger.warning(
                                    f"Cannot register model for experiment {experiment_id}: no MLflow run ID"
                                )
                    except Exception as e:
                        logger.error(
                            f"Failed to register model for experiment {experiment_id}: {e}",
                            exc_info=True,
                        )

                    # Calculate and store PBO if CSCV is available and multiple experiments exist
                    if CSCV_AVAILABLE and self.experiment_tracker:
                        try:
                            self._calculate_and_store_pbo(experiment_id, mlflow_run_id)
                        except Exception as e:
                            logger.warning(
                                f"Failed to calculate PBO for experiment {experiment_id}: {e}"
                            )

                logger.info(
                    f"Experiment {experiment_id} completed with status: {final_status.value}"
                )

        except Exception as e:
            logger.error(
                f"Error in training for experiment {experiment_id}: {e}", exc_info=True
            )
            with self._lock:
                if experiment_id in self.running_experiments:
                    del self.running_experiments[experiment_id]

                self.repository.update_experiment_status(
                    experiment_id=experiment_id,
                    status=ExperimentStatus.FAILED,
                    completed_at=datetime.now(),
                )

    def _create_agent_config(self, hyperparameters: Dict[str, Any]) -> AgentConfig:
        """
        Create AgentConfig from experiment hyperparameters

        :param hyperparameters: Hyperparameter dictionary
        :return: AgentConfig instance
        """
        return AgentConfig(
            learning_rate=hyperparameters.get("learning_rate", 0.0001),
            discount_factor=hyperparameters.get("gamma", 0.99),
            epsilon=hyperparameters.get("epsilon_start", 1.0),
            epsilon_min=hyperparameters.get("epsilon_end", 0.01),
            epsilon_decay=hyperparameters.get("epsilon_decay", 0.999),
            memory_size=hyperparameters.get("replay_buffer_size", 100000),
            batch_size=hyperparameters.get("batch_size", 64),
            target_update_freq=hyperparameters.get("target_update_freq", 1000),
            use_double_dqn=True,
        )

    def _create_training_config(
        self, hyperparameters: Dict[str, Any]
    ) -> TrainingConfig:
        """
        Create TrainingConfig from experiment hyperparameters

        :param hyperparameters: Hyperparameter dictionary
        :return: TrainingConfig instance
        """
        return TrainingConfig(
            decision_interval=60,  # Default, can be overridden
            episode_duration_hours=24,  # Default
            min_experiences_before_training=100,  # Default
            save_freq_steps=1000,  # Default
            training_enabled=True,
            trading_enabled=False,  # Start with trading disabled for safety
        )

    def _validate_features_exist(self, feature_names: List[str]) -> None:
        """
        Validate that all specified features exist in the feature catalog.

        :param feature_names: List of feature names to validate
        :raises ValueError: If any feature doesn't exist
        """
        if not self.feature_catalog:
            logger.warning("Feature catalog not available, skipping feature validation")
            return

        try:
            available_features = self.feature_catalog.get_all_features()
            available_feature_names = {f.name for f in available_features}

            missing = [f for f in feature_names if f not in available_feature_names]
            if missing:
                available_sample = list(available_feature_names)[:10]
                raise ValueError(
                    f"Features not found in catalog: {missing}. "
                    f"Available features (sample): {available_sample}..."
                )
        except Exception as e:
            logger.warning(f"Error validating features: {e}")
            # Don't fail if validation has issues, just log warning

    def _get_connectors_for_pairs(self, currency_pairs: list):
        """
        Get data connectors for specified currency pairs

        :param currency_pairs: List of currency pair symbols
        :return: List of IDataSourceConnector instances
        """
        # This is a placeholder - in real implementation, this would query
        # the server's connector registry for connectors matching the pairs
        # For now, we'll create connectors directly
        # TODO: Enhance to support feature filtering
        from connectors.mt5_price_connector import MT5PriceConnector
        from connectors.base import ConnectorConfig
        from models.currency_pair import CurrencyPair

        connectors = []
        for symbol in currency_pairs:
            # Create a basic connector - in real implementation, get from registry
            # Default to 5 digits for most forex pairs
            pair = CurrencyPair(symbol=symbol, digits=5)
            connector_config = ConnectorConfig(
                source="mt5",
                symbol=symbol,
                extra_config={"digits": 5},
            )
            connector = MT5PriceConnector(
                currency_pair=pair,
                config=connector_config,
            )
            connector.connect()
            connectors.append(connector)

        return connectors

    def _get_demo_account(self) -> Account:
        """
        Get or retrieve demo account for paper trading

        :return: Account instance for demo account
        :raises ValueError: If no demo account is found or not connected
        """
        try:
            # Query database for demo account
            with self.db.execute_query() as conn:
                result = conn.execute(
                    text(
                        "SELECT account_login, auth_token FROM mt5_accounts "
                        "WHERE account_type = 'demo' AND is_active = TRUE "
                        "ORDER BY created_at DESC LIMIT 1"
                    )
                )
                row = result.fetchone()

                if not row:
                    raise ValueError(
                        "No active demo account found in database. "
                        "Please create and connect a demo account first."
                    )

                account_login = row[0]
                auth_token = row[1] if len(row) > 1 else None

                # Try to get account from server's account list by login
                # For paper trading, we need the demo account to be connected to the server
                # If it's not connected, we'll raise a clear error
                try:
                    account = self.get_account(account_login)
                    if account:
                        return account
                    else:
                        # Account not found in connected accounts
                        raise ValueError(
                            f"Demo account {account_login} found in database but not connected to server. "
                            "Please ensure the demo account is connected via Server.connect_account() "
                            "before starting a paper trading experiment."
                        )
                except Exception as e:
                    # If get_account() fails, raise error with helpful message
                    if isinstance(e, ValueError):
                        raise  # Re-raise ValueError as-is
                    if auth_token:
                        raise ValueError(
                            f"Demo account {account_login} found in database but not connected. "
                            f"Please connect it using: server.connect_account({account_login}, '{auth_token}')"
                        )
                    else:
                        raise ValueError(
                            f"Demo account {account_login} found in database but has no auth_token. "
                            "Please ensure the demo account is properly configured and connected."
                        )

        except ValueError:
            # Re-raise ValueError as-is
            raise
        except Exception as e:
            logger.error(f"Error querying for demo account: {e}", exc_info=True)
            raise ValueError(f"Failed to query for demo account: {e}")

    def _calculate_and_store_pbo(
        self, experiment_id: int, mlflow_run_id: Optional[str]
    ) -> None:
        """
        Calculate PBO using CSCV if multiple strategy configurations are available.

        This method attempts to find related experiments (e.g., from Optuna trials)
        and calculate PBO. If insufficient configurations are available, PBO is skipped.

        Args:
            experiment_id: Current experiment ID
            mlflow_run_id: MLflow run ID for storing PBO
        """
        if not CSCV_AVAILABLE:
            return

        try:
            # Try to get related experiments (e.g., from same Optuna study)
            # For now, we'll check if there are other experiments with similar names
            # In a full implementation, this would query Optuna studies or experiment groups
            experiment = self.repository.get_experiment(experiment_id)
            if not experiment:
                return

            # Check if this is part of an Optuna study
            # Look for experiments with similar names (trial experiments)
            if "_trial_" in experiment.name:
                # This is likely an Optuna trial - try to get all trials
                base_name = experiment.name.split("_trial_")[0]
                related_experiments = self._get_related_experiments(base_name)

                if len(related_experiments) >= 2:
                    # We have multiple configurations - can calculate PBO
                    # Note: This is a simplified version. In practice, you'd need:
                    # 1. Historical data for all experiments
                    # 2. Train/evaluate functions
                    # 3. Proper strategy configurations

                    # For now, we'll just log that PBO calculation would be possible
                    # A full implementation would require:
                    # - Access to historical data
                    # - Ability to re-run evaluations on different splits
                    # - Strategy configurations from all related experiments

                    logger.info(
                        f"Found {len(related_experiments)} related experiments for PBO calculation. "
                        "Full CSCV implementation requires historical data and evaluation functions."
                    )

                    # Store a placeholder PBO tag indicating that PBO calculation is available
                    # but requires additional setup
                    if mlflow_run_id and self.experiment_tracker:
                        try:
                            # Re-open the run to add tags
                            import mlflow

                            with mlflow.start_run(run_id=mlflow_run_id):
                                mlflow.set_tag("pbo_available", "true")
                                mlflow.set_tag(
                                    "pbo_n_strategies", str(len(related_experiments))
                                )
                                mlflow.set_tag(
                                    "pbo_note",
                                    "PBO calculation available but requires historical data and evaluation setup",
                                )
                        except Exception as e:
                            logger.warning(f"Failed to store PBO tags: {e}")
        except Exception as e:
            logger.debug(f"PBO calculation skipped: {e}")

    def _get_related_experiments(self, base_name: str) -> List[Any]:
        """
        Get related experiments (e.g., from same Optuna study).

        Args:
            base_name: Base experiment name to search for

        Returns:
            List of related experiment IDs or configurations
        """
        # This is a placeholder - in a full implementation, this would:
        # 1. Query database for experiments with similar names
        # 2. Or query Optuna studies for all trials
        # 3. Return experiment configurations or IDs

        # For now, return empty list
        return []

    def calculate_pbo_for_experiments(
        self,
        experiment_ids: List[int],
        historical_data,
        train_func,
        evaluate_func,
        evaluation_metric: str = "sharpe_ratio",
    ) -> Dict[str, Any]:
        """
        Calculate PBO for a set of experiments using CSCV.

        This method should be called when you have:
        - Multiple completed experiments (e.g., from Optuna trials)
        - Historical data for evaluation
        - Train and evaluate functions

        Args:
            experiment_ids: List of experiment IDs to evaluate
            historical_data: Historical data DataFrame with timestamp column
            train_func: Function to train strategy: train_func(data, config) -> model
            evaluate_func: Function to evaluate strategy: evaluate_func(data, model, config) -> metrics
            evaluation_metric: Metric to use for ranking (default: "sharpe_ratio")

        Returns:
            Dictionary with PBO results
        """
        if not CSCV_AVAILABLE:
            raise ImportError("CSCV module not available")

        if len(experiment_ids) < 2:
            raise ValueError("Need at least 2 experiments for PBO calculation")

        # Get strategy configurations from experiments
        strategy_configs = []
        for exp_id in experiment_ids:
            experiment = self.repository.get_experiment(exp_id)
            if experiment:
                strategy_configs.append(experiment.hyperparameters)

        if len(strategy_configs) < 2:
            raise ValueError("Insufficient strategy configurations for PBO")

        # Run CSCV
        cscv_result = combinatorially_symmetric_cross_validation(
            data=historical_data,
            strategy_configs=strategy_configs,
            n_splits=4,
            evaluation_metric=evaluation_metric,
            train_func=train_func,
            evaluate_func=evaluate_func,
        )

        # Store PBO in MLflow for each experiment
        pbo = cscv_result["pbo"]
        interpretation = interpret_pbo(pbo)

        for exp_id in experiment_ids:
            experiment = self.repository.get_experiment(exp_id)
            if experiment and experiment.mlflow_run_id:
                try:
                    import mlflow

                    with mlflow.start_run(run_id=experiment.mlflow_run_id):
                        mlflow.set_tag("pbo", str(pbo))
                        mlflow.set_tag("pbo_interpretation", interpretation)
                        mlflow.set_tag(
                            "pbo_performance_degradation",
                            str(cscv_result["performance_degradation"]),
                        )
                        mlflow.set_tag("pbo_logit", str(cscv_result["logit_pbo"]))
                        mlflow.set_tag(
                            "pbo_n_strategies", str(cscv_result["n_strategies"])
                        )
                except Exception as e:
                    logger.warning(f"Failed to store PBO for experiment {exp_id}: {e}")

        logger.info(
            f"Calculated PBO for {len(experiment_ids)} experiments: {pbo:.3f} ({interpretation})"
        )

        return cscv_result
