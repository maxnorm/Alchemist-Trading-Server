"""
Experiment Runner

Executes experiments by creating agents, environments, and training loops.
"""

import logging
import threading
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from .models import ExperimentStatus, ExperimentRepository
from domain.config.agent_config import AgentConfig
from domain.config.training_config import TrainingConfig
from infrastructure.factories.agent_factory import AgentFactory
from infrastructure.factories.environment_factory import EnvironmentFactory
from training.live_trainer import LiveTrainer
from models.account import Account
from utils.risk_management import RiskManager

logger = logging.getLogger(__name__)


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
        get_account_func: Callable[[], Account],
        get_risk_manager_func: Callable[[], RiskManager],
        training_loop_factory: Optional[Callable] = None,
    ):
        """
        Initialize experiment runner

        :param database: Database instance
        :param experiment_tracker: ExperimentTracker (MLflow) instance
        :param agent_factory: AgentFactory instance
        :param environment_factory: EnvironmentFactory instance
        :param get_account_func: Function to get Account instance
        :param get_risk_manager_func: Function to get RiskManager instance
        :param training_loop_factory: Optional factory for creating training loops
        """
        self.db = database
        self.experiment_tracker = experiment_tracker
        self.agent_factory = agent_factory
        self.environment_factory = environment_factory
        self.get_account = get_account_func
        self.get_risk_manager = get_risk_manager_func
        self.training_loop_factory = training_loop_factory

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

            # Validate status
            if experiment.status != ExperimentStatus.CREATED:
                logger.error(
                    f"Experiment {experiment_id} is not in 'created' status (current: {experiment.status.value})"
                )
                return False

            try:
                # Create agent config from experiment hyperparameters
                agent_config = self._create_agent_config(experiment.hyperparameters)

                # Get account and risk manager
                account = self.get_account()
                risk_manager = self.get_risk_manager()

                # Create environment with experiment features
                # Note: This assumes environment factory can filter by features
                # For now, we'll use all available providers and filter in the environment
                # TODO: Enhance environment factory to support feature selection
                data_providers = self._get_data_providers_for_pairs(
                    experiment.currency_pairs
                )
                window_size = experiment.hyperparameters.get("window_size", 50)

                environment = self.environment_factory.create_environment(
                    account=account,
                    data_providers=data_providers,
                    window_size=window_size,
                )

                # Create agent
                agent = self.agent_factory.create_agent(
                    env=environment, config=agent_config
                )

                # Create training config
                training_config = self._create_training_config(
                    experiment.hyperparameters
                )

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
                        )

                        # Log experiment configuration
                        self.experiment_tracker.log_experiment_config(experiment)

                        # Log hyperparameters
                        self.experiment_tracker.log_params(experiment.hyperparameters)

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
                trainer = LiveTrainer(
                    agent=agent,
                    environment=environment,
                    account=account,
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

    def _get_data_providers_for_pairs(self, currency_pairs: list):
        """
        Get data providers for specified currency pairs

        :param currency_pairs: List of currency pair symbols
        :return: List of PriceDataProvider instances
        """
        # This is a placeholder - in real implementation, this would query
        # the server's data provider registry for providers matching the pairs
        # For now, we'll need to get this from the server instance
        # TODO: Enhance to support feature filtering
        from data_providers.price_provider import PriceDataProvider
        from models.currency_pair import CurrencyPair

        providers = []
        for symbol in currency_pairs:
            # Create a basic provider - in real implementation, get from registry
            # Default to 5 digits for most forex pairs
            pair = CurrencyPair(symbol=symbol, digits=5)
            provider = PriceDataProvider(currency_pair=pair)
            providers.append(provider)

        return providers
