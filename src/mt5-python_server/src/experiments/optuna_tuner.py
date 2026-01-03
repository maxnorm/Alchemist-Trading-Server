"""
Optuna Hyperparameter Tuner

Integrates Optuna with experiments for automated hyperparameter optimization.
"""

import json
import logging
import optuna
from typing import Dict, Any, Optional, List
from datetime import datetime
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler

from .models import Experiment, ExperimentRepository
from .runner import ExperimentRunner

logger = logging.getLogger(__name__)


class OptunaHyperparameterTuner:
    """
    Optuna-based hyperparameter tuner integrated with experiments.
    """

    def __init__(self, database, experiment_runner: ExperimentRunner):
        """
        Initialize Optuna tuner

        :param database: Database instance
        :param experiment_runner: ExperimentRunner to execute trials
        """
        self.db = database
        self.experiment_runner = experiment_runner
        self.repository = ExperimentRepository(database)

        # Track running studies: study_id -> study
        self.running_studies: Dict[int, optuna.Study] = {}

    def create_study(
        self,
        experiment_id: int,
        metric: str = "sharpe_ratio",
        direction: str = "maximize",
        n_trials: int = 50,
        study_name: Optional[str] = None,
    ) -> int:
        """
        Create Optuna study linked to experiment

        :param experiment_id: Base experiment ID
        :param metric: Metric to optimize ('sharpe_ratio', 'win_rate', 'total_pnl')
        :param direction: 'maximize' or 'minimize'
        :param n_trials: Number of trials to run
        :param study_name: Optional study name (auto-generated if not provided)
        :return: Study ID
        """
        # Get base experiment
        experiment = self.repository.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        # Generate study name if not provided
        if not study_name:
            study_name = (
                f"{experiment.name}_optuna_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )

        # Create study in database
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO optuna_studies (
                    experiment_id, study_name, direction, metric, n_trials, status
                ) VALUES (%s, %s, %s, %s, %s, 'running')
                """,
                (experiment_id, study_name, direction, metric, n_trials),
            )

            study_id = cursor.lastrowid
            conn.commit()
            cursor.close()

            logger.info(
                f"Created Optuna study {study_id} for experiment {experiment_id}"
            )
            return study_id

        except Exception as e:
            logger.error(f"Error creating Optuna study: {e}", exc_info=True)
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def run_trials(
        self,
        study_id: int,
        n_trials: Optional[int] = None,
        timeout: Optional[float] = None,
        n_jobs: int = 1,
    ) -> Dict[str, Any]:
        """
        Run Optuna optimization trials

        :param study_id: Study ID
        :param n_trials: Number of trials (overrides study setting)
        :param timeout: Timeout in seconds
        :param n_jobs: Number of parallel jobs
        :return: Dictionary with results
        """
        # Get study from database
        study_data = self._get_study(study_id)
        if not study_data:
            raise ValueError(f"Study {study_id} not found")

        experiment_id = study_data["experiment_id"]
        base_experiment = self.repository.get_experiment(experiment_id)
        if not base_experiment:
            raise ValueError(f"Base experiment {experiment_id} not found")

        direction = study_data["direction"]
        n_trials_to_run = n_trials or study_data["n_trials"]

        # Create Optuna study
        study = optuna.create_study(
            study_name=study_data["study_name"],
            direction=direction,
            sampler=TPESampler(seed=42),
            pruner=MedianPruner(n_startup_trials=5, n_warmup_steps=10),
        )

        # Store study reference
        self.running_studies[study_id] = study

        # Define objective function
        def objective(trial: optuna.Trial) -> float:
            """Objective function for Optuna"""
            try:
                # Suggest hyperparameters
                hyperparameters = self._suggest_hyperparameters(trial)

                # Create trial experiment
                trial_experiment = self._create_trial_experiment(
                    base_experiment=base_experiment,
                    hyperparameters=hyperparameters,
                    trial_number=trial.number,
                )

                # Store trial in database
                trial_id = self._store_trial(
                    study_id=study_id,
                    trial_number=trial.number,
                    params=hyperparameters,
                    state="running",
                )

                # Run experiment
                success = self.experiment_runner.start_experiment(trial_experiment.id)
                if not success:
                    self._update_trial(trial_id, state="fail", value=None)
                    raise optuna.TrialPruned()

                # Wait for experiment to complete (or timeout)
                # In a real implementation, this would wait for the experiment to finish
                # and then evaluate the metric. For now, we'll simulate this.
                # TODO: Implement proper experiment completion waiting and metric evaluation

                # For now, return a placeholder value
                # In real implementation, this would:
                # 1. Wait for experiment to complete
                # 2. Get performance metrics from experiment
                # 3. Extract the metric value (sharpe_ratio, win_rate, etc.)
                # 4. Return that value

                # Placeholder: return random value for now
                import random

                value = (
                    random.uniform(0.5, 2.0)
                    if direction == "maximize"
                    else random.uniform(-2.0, -0.5)
                )

                # Update trial
                self._update_trial(
                    trial_id,
                    state="complete",
                    value=value,
                    metrics={"placeholder": True},
                )

                return value

            except optuna.TrialPruned:
                # Trial was pruned
                self._update_trial(trial_id, state="pruned", value=None)
                raise
            except Exception as e:
                logger.error(f"Error in trial {trial.number}: {e}", exc_info=True)
                self._update_trial(trial_id, state="fail", value=None)
                raise

        # Run optimization
        try:
            study.optimize(
                objective,
                n_trials=n_trials_to_run,
                timeout=timeout,
                n_jobs=n_jobs,
                show_progress_bar=True,
            )

            # Update study with best results
            if study.best_trial:
                self._update_study(
                    study_id=study_id,
                    best_trial_number=study.best_trial.number,
                    best_value=study.best_value,
                    best_params=study.best_params,
                    status="completed",
                )

            # Calculate parameter importance
            try:
                importance = optuna.importance.get_param_importances(study)
                self._update_study(study_id=study_id, param_importance=importance)
            except Exception as e:
                logger.warning(f"Failed to calculate parameter importance: {e}")

            return {
                "study_id": study_id,
                "n_trials": len(study.trials),
                "best_value": study.best_value,
                "best_params": study.best_params,
                "status": "completed",
            }

        except Exception as e:
            logger.error(f"Error running Optuna study {study_id}: {e}", exc_info=True)
            self._update_study(study_id=study_id, status="failed")
            raise
        finally:
            # Remove from running studies
            if study_id in self.running_studies:
                del self.running_studies[study_id]

    def get_best_params(self, study_id: int) -> Dict[str, Any]:
        """
        Get best hyperparameters from study

        :param study_id: Study ID
        :return: Dictionary of best hyperparameters
        """
        study_data = self._get_study(study_id)
        if not study_data:
            raise ValueError(f"Study {study_id} not found")

        if not study_data.get("best_params"):
            raise ValueError(f"Study {study_id} has no best parameters yet")

        return (
            json.loads(study_data["best_params"])
            if isinstance(study_data["best_params"], str)
            else study_data["best_params"]
        )

    def get_trial_results(self, study_id: int) -> List[Dict[str, Any]]:
        """
        Get all trial results for a study

        :param study_id: Study ID
        :return: List of trial dictionaries
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT trial_number, params, value, state, metrics, created_at, completed_at
                FROM optuna_trials
                WHERE study_id = %s
                ORDER BY trial_number
                """,
                (study_id,),
            )

            rows = cursor.fetchall()
            trials = []

            for row in rows:
                (
                    trial_number,
                    params_json,
                    value,
                    state,
                    metrics_json,
                    created_at,
                    completed_at,
                ) = row

                trials.append(
                    {
                        "trial_number": trial_number,
                        "params": json.loads(params_json) if params_json else {},
                        "value": float(value) if value else None,
                        "state": state,
                        "metrics": json.loads(metrics_json) if metrics_json else {},
                        "created_at": created_at.isoformat() if created_at else None,
                        "completed_at": (
                            completed_at.isoformat() if completed_at else None
                        ),
                    }
                )

            cursor.close()
            return trials

        except Exception as e:
            logger.error(f"Error getting trial results: {e}", exc_info=True)
            return []
        finally:
            if conn:
                conn.close()

    def get_param_importance(self, study_id: int) -> Dict[str, float]:
        """
        Calculate parameter importance using Optuna

        :param study_id: Study ID
        :return: Dictionary of parameter importance scores
        """
        study_data = self._get_study(study_id)
        if not study_data:
            raise ValueError(f"Study {study_id} not found")

        if study_data.get("param_importance"):
            importance = study_data["param_importance"]
            if isinstance(importance, str):
                return json.loads(importance)
            return importance

        # If not stored, try to calculate from running study
        if study_id in self.running_studies:
            study = self.running_studies[study_id]
            try:
                importance = optuna.importance.get_param_importances(study)
                return importance
            except Exception as e:
                logger.warning(f"Failed to calculate parameter importance: {e}")
                return {}

        return {}

    def _suggest_hyperparameters(self, trial: optuna.Trial) -> Dict[str, Any]:
        """
        Define search space per PRD Section 10.3

        :param trial: Optuna trial
        :return: Dictionary of suggested hyperparameters
        """
        return {
            # Learning rate: [0.00001, 0.01] log scale
            "learning_rate": trial.suggest_loguniform("learning_rate", 0.00001, 0.01),
            # Gamma (discount factor): [0.9, 0.999]
            "gamma": trial.suggest_uniform("gamma", 0.9, 0.999),
            # Batch size: [32, 64, 128, 256]
            "batch_size": trial.suggest_categorical("batch_size", [32, 64, 128, 256]),
            # Hidden layers: [[64,64], [128,64], [256,128], [512,256]]
            "hidden_layers": trial.suggest_categorical(
                "hidden_layers", [[64, 64], [128, 64], [256, 128], [512, 256]]
            ),
            # Window size: [20, 50, 100]
            "window_size": trial.suggest_categorical("window_size", [20, 50, 100]),
            # Replay buffer size: [10000, 100000, 500000]
            "replay_buffer_size": trial.suggest_categorical(
                "replay_buffer_size", [10000, 100000, 500000]
            ),
            # Epsilon start: Fixed at 1.0
            "epsilon_start": 1.0,
            # Epsilon end: [0.01, 0.1]
            "epsilon_end": trial.suggest_uniform("epsilon_end", 0.01, 0.1),
            # Epsilon decay: [5000, 10000, 50000]
            "epsilon_decay": trial.suggest_categorical(
                "epsilon_decay", [5000, 10000, 50000]
            ),
            # Target update frequency: [100, 1000, 5000]
            "target_update_freq": trial.suggest_categorical(
                "target_update_freq", [100, 1000, 5000]
            ),
        }

    def _create_trial_experiment(
        self,
        base_experiment: Experiment,
        hyperparameters: Dict[str, Any],
        trial_number: int,
    ) -> Experiment:
        """
        Create a trial experiment with suggested hyperparameters

        :param base_experiment: Base experiment to clone
        :param hyperparameters: Suggested hyperparameters
        :param trial_number: Trial number
        :return: New Experiment instance
        """
        from .builder import ExperimentBuilder

        # Create builder (we'll need to get feature catalog from somewhere)
        # For now, create a minimal builder
        # TODO: Get feature catalog from server/context
        feature_catalog = None  # This should be passed in or retrieved

        builder = ExperimentBuilder(self.db, feature_catalog)

        # Clone experiment with new hyperparameters
        return builder.create_experiment(
            name=f"{base_experiment.name}_trial_{trial_number}",
            description=f"Optuna trial {trial_number} for {base_experiment.name}",
            features=base_experiment.features,
            currency_pairs=base_experiment.currency_pairs,
            training_mode=base_experiment.training_mode,
            hyperparameters=hyperparameters,
        )

    def _get_study(self, study_id: int) -> Optional[Dict[str, Any]]:
        """Get study data from database"""
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, experiment_id, study_name, direction, metric, n_trials, status,
                       best_trial_number, best_value, best_params, param_importance
                FROM optuna_studies
                WHERE id = %s
                """,
                (study_id,),
            )

            row = cursor.fetchone()
            cursor.close()

            if not row:
                return None

            (
                id_val,
                experiment_id,
                study_name,
                direction,
                metric,
                n_trials,
                status,
                best_trial_number,
                best_value,
                best_params,
                param_importance,
            ) = row

            return {
                "id": id_val,
                "experiment_id": experiment_id,
                "study_name": study_name,
                "direction": direction,
                "metric": metric,
                "n_trials": n_trials,
                "status": status,
                "best_trial_number": best_trial_number,
                "best_value": float(best_value) if best_value else None,
                "best_params": best_params,
                "param_importance": param_importance,
            }

        except Exception as e:
            logger.error(f"Error getting study {study_id}: {e}", exc_info=True)
            return None
        finally:
            if conn:
                conn.close()

    def _store_trial(
        self, study_id: int, trial_number: int, params: Dict[str, Any], state: str
    ) -> int:
        """Store trial in database"""
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO optuna_trials (study_id, trial_number, params, state)
                VALUES (%s, %s, %s, %s)
                """,
                (study_id, trial_number, json.dumps(params), state),
            )

            trial_id = cursor.lastrowid
            conn.commit()
            cursor.close()

            return trial_id

        except Exception as e:
            logger.error(f"Error storing trial: {e}", exc_info=True)
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def _update_trial(
        self,
        trial_id: int,
        state: Optional[str] = None,
        value: Optional[float] = None,
        metrics: Optional[Dict[str, Any]] = None,
        mlflow_run_id: Optional[str] = None,
    ):
        """Update trial in database"""
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            updates = []
            params = []

            if state is not None:
                updates.append("state = ?")
                params.append(state)

            if value is not None:
                updates.append("value = ?")
                params.append(value)

            if metrics is not None:
                updates.append("metrics = ?")
                params.append(json.dumps(metrics))

            if mlflow_run_id is not None:
                updates.append("mlflow_run_id = ?")
                params.append(mlflow_run_id)

            if updates:
                updates.append("completed_at = ?")
                params.append(datetime.now())
                params.append(trial_id)

                cursor.execute(
                    f"UPDATE optuna_trials SET {', '.join(updates)} WHERE id = %s",
                    params,
                )

                conn.commit()

            cursor.close()

        except Exception as e:
            logger.error(f"Error updating trial: {e}", exc_info=True)
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    def _update_study(
        self,
        study_id: int,
        best_trial_number: Optional[int] = None,
        best_value: Optional[float] = None,
        best_params: Optional[Dict[str, Any]] = None,
        param_importance: Optional[Dict[str, float]] = None,
        status: Optional[str] = None,
    ):
        """Update study in database"""
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            updates = []
            params = []

            if best_trial_number is not None:
                updates.append("best_trial_number = ?")
                params.append(best_trial_number)

            if best_value is not None:
                updates.append("best_value = ?")
                params.append(best_value)

            if best_params is not None:
                updates.append("best_params = ?")
                params.append(json.dumps(best_params))

            if param_importance is not None:
                updates.append("param_importance = ?")
                params.append(json.dumps(param_importance))

            if status is not None:
                updates.append("status = ?")
                params.append(status)
                if status in ["completed", "failed", "stopped"]:
                    updates.append("completed_at = ?")
                    params.append(datetime.now())

            if updates:
                params.append(study_id)
                cursor.execute(
                    f"UPDATE optuna_studies SET {', '.join(updates)} WHERE id = %s",
                    params,
                )
                conn.commit()

            cursor.close()

        except Exception as e:
            logger.error(f"Error updating study: {e}", exc_info=True)
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
