"""
Unit tests for experiment management components
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/mt5-python_server/src'))

from experiments.models import Experiment, ExperimentStatus, ExperimentRepository
from experiments.builder import ExperimentBuilder
from experiments.runner import ExperimentRunner
from experiments.optuna_tuner import OptunaHyperparameterTuner


class TestExperimentModel(unittest.TestCase):
    """Test Experiment model"""
    
    def test_experiment_to_dict(self):
        """Test experiment serialization"""
        experiment = Experiment(
            id=1,
            name="Test Experiment",
            description="Test",
            features=["price_mid", "rsi_14"],
            currency_pairs=["EURUSD"],
            training_mode="live",
            hyperparameters={"learning_rate": 0.001},
            status=ExperimentStatus.CREATED,
            mlflow_run_id=None,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None
        )
        
        data = experiment.to_dict()
        self.assertEqual(data['id'], 1)
        self.assertEqual(data['name'], "Test Experiment")
        self.assertEqual(data['status'], 'created')
    
    def test_experiment_from_dict(self):
        """Test experiment deserialization"""
        data = {
            'id': 1,
            'name': 'Test',
            'description': 'Test desc',
            'features': ['price_mid'],
            'currency_pairs': ['EURUSD'],
            'training_mode': 'live',
            'hyperparameters': {'learning_rate': 0.001},
            'status': 'created',
            'mlflow_run_id': None,
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'completed_at': None
        }
        
        experiment = Experiment.from_dict(data)
        self.assertEqual(experiment.id, 1)
        self.assertEqual(experiment.status, ExperimentStatus.CREATED)


class TestExperimentBuilder(unittest.TestCase):
    """Test ExperimentBuilder"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        self.mock_catalog = Mock()
        
        # Mock feature catalog
        from data_providers.base_provider import Feature
        mock_features = [
            Feature(name="price_mid", data_type=float, source="MT5", description="Mid price"),
            Feature(name="rsi_14", data_type=float, source="Indicators", description="RSI 14")
        ]
        self.mock_catalog.get_all_features.return_value = mock_features
        
        self.builder = ExperimentBuilder(self.mock_db, self.mock_catalog)
    
    def test_validate_experiment_valid(self):
        """Test validation of valid experiment"""
        features = ["price_mid", "rsi_14"]
        currency_pairs = ["EURUSD"]
        training_mode = "live"
        hyperparameters = {
            'learning_rate': 0.001,
            'gamma': 0.99,
            'batch_size': 64,
            'hidden_layers': [256, 128],
            'window_size': 50,
            'replay_buffer_size': 100000,
            'epsilon_start': 1.0,
            'epsilon_end': 0.01,
            'epsilon_decay': 10000,
            'target_update_freq': 1000
        }
        
        is_valid, errors = self.builder.validate_experiment_config(
            features, currency_pairs, training_mode, hyperparameters
        )
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_experiment_invalid_feature(self):
        """Test validation fails for invalid feature"""
        features = ["invalid_feature"]
        currency_pairs = ["EURUSD"]
        training_mode = "live"
        hyperparameters = {
            'learning_rate': 0.001,
            'gamma': 0.99,
            'batch_size': 64,
            'hidden_layers': [256, 128],
            'window_size': 50,
            'replay_buffer_size': 100000,
            'epsilon_start': 1.0,
            'epsilon_end': 0.01,
            'epsilon_decay': 10000,
            'target_update_freq': 1000
        }
        
        is_valid, errors = self.builder.validate_experiment_config(
            features, currency_pairs, training_mode, hyperparameters
        )
        
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)


class TestExperimentRunner(unittest.TestCase):
    """Test ExperimentRunner"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        self.mock_tracker = Mock()
        self.mock_agent_factory = Mock()
        self.mock_env_factory = Mock()
        self.mock_get_account = Mock(return_value=Mock())
        self.mock_get_risk_manager = Mock(return_value=Mock())
        
        self.runner = ExperimentRunner(
            database=self.mock_db,
            experiment_tracker=self.mock_tracker,
            agent_factory=self.mock_agent_factory,
            environment_factory=self.mock_env_factory,
            get_account_func=self.mock_get_account,
            get_risk_manager_func=self.mock_get_risk_manager
        )
    
    def test_create_agent_config(self):
        """Test agent config creation from hyperparameters"""
        hyperparameters = {
            'learning_rate': 0.001,
            'gamma': 0.99,
            'epsilon_start': 1.0,
            'epsilon_end': 0.01,
            'epsilon_decay': 0.999,
            'replay_buffer_size': 100000,
            'batch_size': 64,
            'target_update_freq': 1000
        }
        
        config = self.runner._create_agent_config(hyperparameters)
        self.assertEqual(config.learning_rate, 0.001)
        self.assertEqual(config.discount_factor, 0.99)
        self.assertEqual(config.batch_size, 64)


class TestOptunaTuner(unittest.TestCase):
    """Test OptunaHyperparameterTuner"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        self.mock_runner = Mock()
        
        self.tuner = OptunaHyperparameterTuner(
            database=self.mock_db,
            experiment_runner=self.mock_runner
        )
    
    def test_suggest_hyperparameters(self):
        """Test hyperparameter suggestion"""
        import optuna
        
        study = optuna.create_study()
        trial = study.ask()
        
        params = self.tuner._suggest_hyperparameters(trial)
        
        # Check all required parameters are present
        required = [
            'learning_rate', 'gamma', 'batch_size', 'hidden_layers',
            'window_size', 'replay_buffer_size', 'epsilon_start',
            'epsilon_end', 'epsilon_decay', 'target_update_freq'
        ]
        
        for param in required:
            self.assertIn(param, params)
        
        # Check ranges
        self.assertGreaterEqual(params['learning_rate'], 0.00001)
        self.assertLessEqual(params['learning_rate'], 0.01)
        self.assertGreaterEqual(params['gamma'], 0.9)
        self.assertLessEqual(params['gamma'], 0.999)
        self.assertIn(params['batch_size'], [32, 64, 128, 256])


if __name__ == '__main__':
    unittest.main()
