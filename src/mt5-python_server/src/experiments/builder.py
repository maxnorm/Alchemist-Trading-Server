"""
Experiment Builder

Creates and validates experiment configurations.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from .models import Experiment, ExperimentStatus, ExperimentRepository
from features.catalog import FeatureCatalog

logger = logging.getLogger(__name__)


class ExperimentBuilder:
    """
    Builder for creating and validating experiments.
    """
    
    # Required hyperparameter fields
    REQUIRED_HYPERPARAMETERS = [
        'learning_rate',
        'gamma',
        'batch_size',
        'hidden_layers',
        'window_size',
        'replay_buffer_size',
        'epsilon_start',
        'epsilon_end',
        'epsilon_decay',
        'target_update_freq',
    ]
    
    def __init__(self, database, feature_catalog: FeatureCatalog):
        """
        Initialize experiment builder
        
        :param database: Database instance
        :param feature_catalog: FeatureCatalog instance to validate features
        """
        self.db = database
        self.feature_catalog = feature_catalog
        self.repository = ExperimentRepository(database)
    
    def create_experiment(
        self,
        name: str,
        description: str,
        features: List[str],
        currency_pairs: List[str],
        training_mode: str,
        hyperparameters: Dict[str, Any]
    ) -> Experiment:
        """
        Create and validate a new experiment
        
        Validates:
        - Feature names exist in catalog
        - Currency pairs are valid
        - Hyperparameters match expected schema
        - Training mode is valid
        
        :param name: Experiment name
        :param description: Experiment description
        :param features: List of feature names
        :param currency_pairs: List of currency pair symbols
        :param training_mode: 'live' or 'historical'
        :param hyperparameters: Hyperparameter dictionary
        :return: Created Experiment instance
        """
        # Validate inputs
        is_valid, errors = self.validate_experiment_config(
            features, currency_pairs, training_mode, hyperparameters
        )
        
        if not is_valid:
            raise ValueError(f"Invalid experiment configuration: {', '.join(errors)}")
        
        # Create experiment object
        experiment = Experiment(
            id=None,
            name=name,
            description=description,
            features=features,
            currency_pairs=currency_pairs,
            training_mode=training_mode,
            hyperparameters=hyperparameters,
            status=ExperimentStatus.CREATED,
            mlflow_run_id=None,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
        )
        
        # Save to database
        experiment_id = self.repository.create_experiment(experiment)
        experiment.id = experiment_id
        
        logger.info(f"Created experiment {experiment_id}: {name}")
        return experiment
    
    def validate_experiment(self, experiment: Experiment) -> Tuple[bool, List[str]]:
        """
        Validate experiment configuration
        
        :param experiment: Experiment instance
        :return: (is_valid, list_of_errors)
        """
        return self.validate_experiment_config(
            experiment.features,
            experiment.currency_pairs,
            experiment.training_mode,
            experiment.hyperparameters
        )
    
    def validate_experiment_config(
        self,
        features: List[str],
        currency_pairs: List[str],
        training_mode: str,
        hyperparameters: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate experiment configuration components
        
        :param features: List of feature names
        :param currency_pairs: List of currency pair symbols
        :param training_mode: Training mode string
        :param hyperparameters: Hyperparameter dictionary
        :return: (is_valid, list_of_errors)
        """
        errors = []
        
        # Validate features
        if not features:
            errors.append("At least one feature must be selected")
        else:
            # Check all features exist in catalog
            available_features = self.feature_catalog.get_all_features()
            available_feature_names = {f.name for f in available_features}
            
            for feature_name in features:
                if feature_name not in available_feature_names:
                    errors.append(f"Feature '{feature_name}' not found in catalog")
        
        # Validate currency pairs
        if not currency_pairs:
            errors.append("At least one currency pair must be selected")
        else:
            # Basic validation: check format (should be 6 characters like EURUSD)
            for pair in currency_pairs:
                if not isinstance(pair, str) or len(pair) != 6:
                    errors.append(f"Invalid currency pair format: {pair} (expected 6 characters)")
        
        # Validate training mode
        if training_mode not in ['live', 'historical']:
            errors.append(f"Invalid training mode: {training_mode} (must be 'live' or 'historical')")
        
        # Validate hyperparameters
        if not hyperparameters:
            errors.append("Hyperparameters dictionary cannot be empty")
        else:
            # Check required fields
            for required_field in self.REQUIRED_HYPERPARAMETERS:
                if required_field not in hyperparameters:
                    errors.append(f"Missing required hyperparameter: {required_field}")
            
            # Validate hyperparameter types and ranges
            if 'learning_rate' in hyperparameters:
                lr = hyperparameters['learning_rate']
                if not isinstance(lr, (int, float)) or lr <= 0 or lr > 1:
                    errors.append("learning_rate must be a positive number <= 1")
            
            if 'gamma' in hyperparameters:
                gamma = hyperparameters['gamma']
                if not isinstance(gamma, (int, float)) or gamma < 0 or gamma > 1:
                    errors.append("gamma must be a number between 0 and 1")
            
            if 'batch_size' in hyperparameters:
                batch_size = hyperparameters['batch_size']
                if not isinstance(batch_size, int) or batch_size <= 0:
                    errors.append("batch_size must be a positive integer")
            
            if 'window_size' in hyperparameters:
                window_size = hyperparameters['window_size']
                if not isinstance(window_size, int) or window_size <= 0:
                    errors.append("window_size must be a positive integer")
            
            if 'hidden_layers' in hyperparameters:
                hidden_layers = hyperparameters['hidden_layers']
                if not isinstance(hidden_layers, list) or not all(isinstance(x, int) and x > 0 for x in hidden_layers):
                    errors.append("hidden_layers must be a list of positive integers")
        
        return len(errors) == 0, errors
    
    def clone_experiment(
        self,
        experiment_id: int,
        new_name: str,
        modifications: Optional[Dict[str, Any]] = None
    ) -> Experiment:
        """
        Clone an existing experiment with optional modifications
        
        :param experiment_id: ID of experiment to clone
        :param new_name: Name for the new experiment
        :param modifications: Optional dictionary of modifications:
            - features: List[str]
            - currency_pairs: List[str]
            - training_mode: str
            - hyperparameters: Dict[str, Any]
        :return: New Experiment instance
        """
        # Get original experiment
        original = self.repository.get_experiment(experiment_id)
        if not original:
            raise ValueError(f"Experiment {experiment_id} not found")
        
        # Apply modifications
        features = modifications.get('features', original.features) if modifications else original.features
        currency_pairs = modifications.get('currency_pairs', original.currency_pairs) if modifications else original.currency_pairs
        training_mode = modifications.get('training_mode', original.training_mode) if modifications else original.training_mode
        hyperparameters = modifications.get('hyperparameters', original.hyperparameters.copy()) if modifications else original.hyperparameters.copy()
        
        # Validate modified configuration
        is_valid, errors = self.validate_experiment_config(
            features, currency_pairs, training_mode, hyperparameters
        )
        
        if not is_valid:
            raise ValueError(f"Invalid modifications: {', '.join(errors)}")
        
        # Create new experiment
        return self.create_experiment(
            name=new_name,
            description=f"Cloned from: {original.name}\n{original.description}",
            features=features,
            currency_pairs=currency_pairs,
            training_mode=training_mode,
            hyperparameters=hyperparameters
        )
