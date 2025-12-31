"""
Neural Architecture Search (NAS)
Finds optimal model architecture for trading agent
"""
import os
import json
import logging
from typing import Dict, Optional, Callable, Any, List
import optuna
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler


class ArchitectureSearch:
    """
    Neural Architecture Search for DQN agent
    Searches for optimal architecture configuration
    """
    
    def __init__(
        self,
        study_name: str = 'architecture_search',
        storage: Optional[str] = None,
        direction: str = 'maximize',
        n_trials: int = 50
    ):
        """
        Initialize architecture search
        
        :param study_name: Name of the study
        :param storage: Optional database URL for persistent storage
        :param direction: Optimization direction
        :param n_trials: Number of trials to run
        """
        self.study_name = study_name
        self.n_trials = n_trials
        self.logger = logging.getLogger(__name__)
        
        # Create or load study
        if storage:
            self.study = optuna.create_study(
                study_name=study_name,
                storage=storage,
                direction=direction,
                sampler=TPESampler(seed=42),
                pruner=MedianPruner(n_startup_trials=3, n_warmup_steps=5),
                load_if_exists=True
            )
        else:
            self.study = optuna.create_study(
                study_name=study_name,
                direction=direction,
                sampler=TPESampler(seed=42),
                pruner=MedianPruner(n_startup_trials=3, n_warmup_steps=5)
            )
    
    def suggest_architecture(self, trial: optuna.Trial) -> Dict[str, Any]:
        """
        Suggest architecture configuration for a trial
        
        :param trial: Optuna trial object
        :return: Dictionary of architecture parameters
        """
        # Number of LSTM layers
        n_lstm_layers = trial.suggest_int('n_lstm_layers', 1, 3)
        
        # LSTM units per layer
        lstm_units = []
        for i in range(n_lstm_layers):
            units = trial.suggest_categorical(
                f'lstm_units_{i}',
                [64, 128, 256, 512]
            )
            lstm_units.append(units)
        
        # Number of dense layers
        n_dense_layers = trial.suggest_int('n_dense_layers', 1, 3)
        
        # Dense layer units
        dense_units = []
        for i in range(n_dense_layers):
            units = trial.suggest_categorical(
                f'dense_units_{i}',
                [32, 64, 128, 256]
            )
            dense_units.append(units)
        
        # Dropout rate
        dropout_rate = trial.suggest_categorical(
            'dropout_rate',
            [0.1, 0.2, 0.3, 0.4]
        )
        
        # Activation function
        activation = trial.suggest_categorical(
            'activation',
            ['relu', 'tanh', 'elu']
        )
        
        return {
            'n_lstm_layers': n_lstm_layers,
            'lstm_units': lstm_units,
            'n_dense_layers': n_dense_layers,
            'dense_units': dense_units,
            'dropout_rate': dropout_rate,
            'activation': activation
        }
    
    def optimize(
        self,
        objective_func: Callable[[optuna.Trial], float],
        n_trials: Optional[int] = None
    ) -> optuna.Study:
        """
        Run architecture search optimization
        
        :param objective_func: Objective function that takes a trial and returns a score
        :param n_trials: Number of trials (overrides initialization value)
        :return: Optimized study
        """
        n_trials = n_trials or self.n_trials
        
        self.logger.info(f"Starting architecture search: {n_trials} trials")
        
        self.study.optimize(
            objective_func,
            n_trials=n_trials,
            show_progress_bar=True
        )
        
        self.logger.info(f"Architecture search complete. Best value: {self.study.best_value:.4f}")
        self.logger.info(f"Best architecture: {self.study.best_params}")
        
        return self.study
    
    def get_best_architecture(self) -> Dict[str, Any]:
        """
        Get best architecture configuration
        
        :return: Dictionary of best architecture parameters
        """
        if not self.study.best_params:
            raise ValueError("No trials completed yet. Run optimize() first.")
        
        # Reconstruct architecture config from best params
        best_params = self.study.best_params
        
        # Extract LSTM layers
        n_lstm_layers = best_params['n_lstm_layers']
        lstm_units = [best_params[f'lstm_units_{i}'] for i in range(n_lstm_layers)]
        
        # Extract dense layers
        n_dense_layers = best_params['n_dense_layers']
        dense_units = [best_params[f'dense_units_{i}'] for i in range(n_dense_layers)]
        
        return {
            'n_lstm_layers': n_lstm_layers,
            'lstm_units': lstm_units,
            'n_dense_layers': n_dense_layers,
            'dense_units': dense_units,
            'dropout_rate': best_params['dropout_rate'],
            'activation': best_params['activation']
        }
    
    def save_best_architecture(self, filepath: str):
        """
        Save best architecture to config file
        
        :param filepath: Path to save config file
        """
        best_arch = self.get_best_architecture()
        
        config = {
            'study_name': self.study_name,
            'best_value': float(self.study.best_value),
            'best_trial': int(self.study.best_trial.number),
            'n_trials': len(self.study.trials),
            'architecture': best_arch
        }
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2)
        
        self.logger.info(f"Best architecture saved to {filepath}")
    
    def load_architecture(self, filepath: str) -> Dict[str, Any]:
        """
        Load architecture configuration from file
        
        :param filepath: Path to config file
        :return: Dictionary of architecture parameters
        """
        with open(filepath, 'r') as f:
            config = json.load(f)
        return config['architecture']
