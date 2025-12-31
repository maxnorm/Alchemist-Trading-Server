"""
Hyperparameter Tuning Framework
Automated hyperparameter optimization using Optuna
"""
import os
import json
import logging
from typing import Dict, Optional, Callable, Any
import optuna
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler


class HyperparameterTuner:
    """
    Hyperparameter tuning framework using Optuna
    Supports Bayesian optimization with TPE sampler
    """
    
    def __init__(
        self,
        study_name: str,
        storage: Optional[str] = None,
        direction: str = 'maximize',
        n_trials: int = 100,
        timeout: Optional[float] = None
    ):
        """
        Initialize hyperparameter tuner
        
        :param study_name: Name of the study
        :param storage: Optional database URL for persistent storage (e.g., 'sqlite:///optuna.db')
        :param direction: Optimization direction ('maximize' or 'minimize')
        :param n_trials: Number of trials to run
        :param timeout: Optional timeout in seconds
        """
        self.study_name = study_name
        self.n_trials = n_trials
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        
        # Create or load study
        if storage:
            self.study = optuna.create_study(
                study_name=study_name,
                storage=storage,
                direction=direction,
                sampler=TPESampler(seed=42),
                pruner=MedianPruner(n_startup_trials=5, n_warmup_steps=10),
                load_if_exists=True
            )
        else:
            self.study = optuna.create_study(
                study_name=study_name,
                direction=direction,
                sampler=TPESampler(seed=42),
                pruner=MedianPruner(n_startup_trials=5, n_warmup_steps=10)
            )
    
    def suggest_hyperparameters(self, trial: optuna.Trial) -> Dict[str, Any]:
        """
        Suggest hyperparameters for a trial
        
        :param trial: Optuna trial object
        :return: Dictionary of suggested hyperparameters
        """
        return {
            # Learning parameters
            'learning_rate': trial.suggest_loguniform('learning_rate', 1e-5, 1e-2),
            'discount_factor': trial.suggest_uniform('discount_factor', 0.9, 0.99),
            'epsilon_decay': trial.suggest_uniform('epsilon_decay', 0.99, 0.999),
            
            # Network architecture (basic - will be expanded in architecture search)
            'batch_size': trial.suggest_categorical('batch_size', [16, 32, 64, 128]),
            'target_update_freq': trial.suggest_categorical('target_update_freq', [50, 100, 200]),
            
            # PER parameters
            'per_alpha': trial.suggest_uniform('per_alpha', 0.4, 0.8),
            'per_beta': trial.suggest_uniform('per_beta', 0.2, 0.6),
            'per_beta_increment': trial.suggest_loguniform('per_beta_increment', 1e-4, 1e-2),
            
            # Memory size
            'memory_size': trial.suggest_categorical('memory_size', [5000, 10000, 20000])
        }
    
    def optimize(
        self,
        objective_func: Callable[[optuna.Trial], float],
        n_trials: Optional[int] = None,
        timeout: Optional[float] = None
    ) -> optuna.Study:
        """
        Run hyperparameter optimization
        
        :param objective_func: Objective function that takes a trial and returns a score
        :param n_trials: Number of trials (overrides initialization value)
        :param timeout: Timeout in seconds (overrides initialization value)
        :return: Optimized study
        """
        n_trials = n_trials or self.n_trials
        timeout = timeout or self.timeout
        
        self.logger.info(f"Starting hyperparameter optimization: {n_trials} trials")
        
        self.study.optimize(
            objective_func,
            n_trials=n_trials,
            timeout=timeout,
            show_progress_bar=True
        )
        
        self.logger.info(f"Optimization complete. Best value: {self.study.best_value:.4f}")
        self.logger.info(f"Best parameters: {self.study.best_params}")
        
        return self.study
    
    def get_best_hyperparameters(self) -> Dict[str, Any]:
        """
        Get best hyperparameters from study
        
        :return: Dictionary of best hyperparameters
        """
        if not self.study.best_params:
            raise ValueError("No trials completed yet. Run optimize() first.")
        return self.study.best_params.copy()
    
    def save_best_config(self, filepath: str):
        """
        Save best hyperparameters to config file
        
        :param filepath: Path to save config file
        """
        best_params = self.get_best_hyperparameters()
        
        config = {
            'study_name': self.study_name,
            'best_value': float(self.study.best_value),
            'best_trial': int(self.study.best_trial.number),
            'n_trials': len(self.study.trials),
            'hyperparameters': best_params
        }
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2)
        
        self.logger.info(f"Best hyperparameters saved to {filepath}")
    
    def load_best_config(self, filepath: str) -> Dict[str, Any]:
        """
        Load best hyperparameters from config file
        
        :param filepath: Path to config file
        :return: Dictionary of hyperparameters
        """
        with open(filepath, 'r') as f:
            config = json.load(f)
        return config['hyperparameters']
    
    def get_trial_history(self) -> list:
        """
        Get history of all trials
        
        :return: List of trial values
        """
        return [trial.value for trial in self.study.trials if trial.value is not None]
    
    def visualize_optimization(self, output_file: Optional[str] = None):
        """
        Visualize optimization history (requires plotly)
        
        :param output_file: Optional file to save plot
        """
        try:
            import optuna.visualization as vis
            
            fig = vis.plot_optimization_history(self.study)
            if output_file:
                fig.write_html(output_file)
            else:
                fig.show()
        except ImportError:
            self.logger.warning("plotly not installed. Install with: pip install plotly")
