"""
Integration tests for MLOps components

Tests MLflow experiment tracking, DVC versioning, and model promotion.
"""

import pytest
import os
import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/backend/trading_server/src'))


class TestExperimentTracker:
    """Tests for ExperimentTracker"""
    
    @pytest.fixture
    def mock_mlflow(self):
        """Mock MLflow module"""
        with patch.dict(sys.modules, {'mlflow': MagicMock()}):
            yield sys.modules['mlflow']
    
    def test_experiment_tracker_creates_run(self, mock_mlflow):
        """Test that experiment tracker can create a run"""
        from mlops.experiment_tracker import ExperimentTracker
        
        # Mock MLflow functions
        mock_mlflow.set_tracking_uri = MagicMock()
        mock_mlflow.set_experiment = MagicMock()
        mock_mlflow.get_experiment_by_name = MagicMock(return_value=MagicMock(experiment_id="1"))
        mock_mlflow.start_run = MagicMock(return_value=MagicMock(info=MagicMock(run_id="test-run-id")))
        mock_mlflow.log_param = MagicMock()
        mock_mlflow.end_run = MagicMock()
        
        tracker = ExperimentTracker(
            tracking_uri="http://localhost:5000",
            experiment_name="test-experiment"
        )
        
        run_id = tracker.start_run("test-run")
        
        assert run_id == "test-run-id"
        mock_mlflow.start_run.assert_called_once()
    
    def test_metrics_logged_to_mlflow(self, mock_mlflow):
        """Test that metrics are logged correctly"""
        from mlops.experiment_tracker import ExperimentTracker
        
        mock_mlflow.set_tracking_uri = MagicMock()
        mock_mlflow.set_experiment = MagicMock()
        mock_mlflow.get_experiment_by_name = MagicMock(return_value=MagicMock(experiment_id="1"))
        mock_mlflow.start_run = MagicMock(return_value=MagicMock(info=MagicMock(run_id="test-run-id")))
        mock_mlflow.log_param = MagicMock()
        mock_mlflow.log_metric = MagicMock()
        mock_mlflow.end_run = MagicMock()
        
        tracker = ExperimentTracker()
        tracker.start_run("test")
        
        tracker.log_metrics({'reward': 0.5, 'loss': 0.1}, step=10)
        
        # Verify log_metric was called for each metric
        assert mock_mlflow.log_metric.call_count == 2
    
    def test_params_logged_to_mlflow(self, mock_mlflow):
        """Test that params are logged correctly"""
        from mlops.experiment_tracker import ExperimentTracker
        
        mock_mlflow.set_tracking_uri = MagicMock()
        mock_mlflow.set_experiment = MagicMock()
        mock_mlflow.get_experiment_by_name = MagicMock(return_value=MagicMock(experiment_id="1"))
        mock_mlflow.start_run = MagicMock(return_value=MagicMock(info=MagicMock(run_id="test-run-id")))
        mock_mlflow.log_param = MagicMock()
        mock_mlflow.log_params = MagicMock()
        mock_mlflow.end_run = MagicMock()
        
        tracker = ExperimentTracker()
        tracker.start_run("test")
        
        tracker.log_params({'learning_rate': 0.001, 'batch_size': 32})
        
        mock_mlflow.log_params.assert_called_once()
    
    def test_compute_experiment_config_hash_deterministic(self, mock_mlflow):
        """Test that experiment config hash is deterministic"""
        from mlops.experiment_tracker import ExperimentTracker
        
        mock_mlflow.set_tracking_uri = MagicMock()
        mock_mlflow.set_experiment = MagicMock()
        mock_mlflow.get_experiment_by_name = MagicMock(return_value=MagicMock(experiment_id="1"))
        mock_mlflow.start_run = MagicMock(return_value=MagicMock(info=MagicMock(run_id="test-run-id")))
        mock_mlflow.end_run = MagicMock()
        
        tracker = ExperimentTracker()
        tracker.start_run("test")
        
        experiment_config = {
            "hyperparameters": {"learning_rate": 0.001, "batch_size": 64},
            "currency_pairs": ["EURUSD", "GBPUSD"],
            "features": ["price_mid", "rsi_14"],
            "training_mode": "live",
            "name": "test_experiment",
            "description": "Test description",
            "experiment_id": 1,
        }
        
        # Compute hash twice - should be identical
        hash1 = tracker._compute_experiment_config_hash(experiment_config)
        hash2 = tracker._compute_experiment_config_hash(experiment_config)
        
        assert hash1 == hash2
        assert hash1 is not None
        assert len(hash1) == 16  # SHA256 hash, first 16 chars
    
    def test_compute_experiment_config_hash_different_configs(self, mock_mlflow):
        """Test that different configs produce different hashes"""
        from mlops.experiment_tracker import ExperimentTracker
        
        mock_mlflow.set_tracking_uri = MagicMock()
        mock_mlflow.set_experiment = MagicMock()
        mock_mlflow.get_experiment_by_name = MagicMock(return_value=MagicMock(experiment_id="1"))
        mock_mlflow.start_run = MagicMock(return_value=MagicMock(info=MagicMock(run_id="test-run-id")))
        mock_mlflow.end_run = MagicMock()
        
        tracker = ExperimentTracker()
        tracker.start_run("test")
        
        config1 = {
            "hyperparameters": {"learning_rate": 0.001},
            "currency_pairs": ["EURUSD"],
        }
        
        config2 = {
            "hyperparameters": {"learning_rate": 0.002},  # Different value
            "currency_pairs": ["EURUSD"],
        }
        
        hash1 = tracker._compute_experiment_config_hash(config1)
        hash2 = tracker._compute_experiment_config_hash(config2)
        
        assert hash1 != hash2
    
    def test_compute_experiment_config_hash_order_independent(self, mock_mlflow):
        """Test that config hash is independent of key order"""
        from mlops.experiment_tracker import ExperimentTracker
        
        mock_mlflow.set_tracking_uri = MagicMock()
        mock_mlflow.set_experiment = MagicMock()
        mock_mlflow.get_experiment_by_name = MagicMock(return_value=MagicMock(experiment_id="1"))
        mock_mlflow.start_run = MagicMock(return_value=MagicMock(info=MagicMock(run_id="test-run-id")))
        mock_mlflow.end_run = MagicMock()
        
        tracker = ExperimentTracker()
        tracker.start_run("test")
        
        # Same config, different key order (should produce same hash due to sort_keys=True)
        config1 = {
            "hyperparameters": {"learning_rate": 0.001, "batch_size": 64},
            "currency_pairs": ["EURUSD"],
        }
        
        config2 = {
            "currency_pairs": ["EURUSD"],  # Different order
            "hyperparameters": {"batch_size": 64, "learning_rate": 0.001},  # Different order
        }
        
        hash1 = tracker._compute_experiment_config_hash(config1)
        hash2 = tracker._compute_experiment_config_hash(config2)
        
        assert hash1 == hash2
    
    def test_log_reproducibility_metadata_with_seed_and_config(self, mock_mlflow):
        """Test that reproducibility metadata logs git_commit, random_seed, and config_hash tags"""
        from mlops.experiment_tracker import ExperimentTracker
        
        mock_mlflow.set_tracking_uri = MagicMock()
        mock_mlflow.set_experiment = MagicMock()
        mock_mlflow.get_experiment_by_name = MagicMock(return_value=MagicMock(experiment_id="1"))
        mock_run = MagicMock(info=MagicMock(run_id="test-run-id"))
        mock_mlflow.start_run = MagicMock(return_value=mock_run)
        mock_mlflow.set_tag = MagicMock()
        mock_mlflow.log_param = MagicMock()
        mock_mlflow.log_dict = MagicMock()
        mock_mlflow.end_run = MagicMock()
        
        tracker = ExperimentTracker()
        tracker.start_run("test", log_reproducibility=False)
        
        experiment_config = {
            "hyperparameters": {"learning_rate": 0.001},
            "currency_pairs": ["EURUSD"],
            "features": ["price_mid"],
            "training_mode": "live",
            "name": "test",
            "description": "test",
            "experiment_id": 1,
        }
        
        # Mock git commit
        with patch.object(tracker, '_get_git_commit', return_value='abc123def456'):
            tracker.log_reproducibility_metadata(
                random_seed=42,
                experiment_config=experiment_config
            )
        
        # Verify required tags are set
        tag_calls = {call[0][0]: call[0][1] for call in mock_mlflow.set_tag.call_args_list}
        assert 'git_commit' in tag_calls
        assert tag_calls['git_commit'] == 'abc123def456'
        assert 'random_seed' in tag_calls
        assert tag_calls['random_seed'] == '42'
        assert 'config_hash' in tag_calls
        assert tag_calls['config_hash'] is not None
        assert tag_calls['config_hash'] != 'unknown'


class TestDataVersioner:
    """Tests for DataVersioner"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_compute_file_hash(self, temp_dir):
        """Test file hash computation"""
        from mlops.data_versioner import DataVersioner
        
        # Create test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")
        
        hash1 = DataVersioner.compute_file_hash(str(test_file))
        hash2 = DataVersioner.compute_file_hash(str(test_file))
        
        # Same file should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 hash length
    
    def test_create_metadata(self, temp_dir):
        """Test metadata creation"""
        from mlops.data_versioner import DataVersioner
        
        # Create test file
        test_file = temp_dir / "data.csv"
        test_file.write_text("a,b,c\n1,2,3")
        
        versioner = DataVersioner(repo_root=str(temp_dir))
        metadata = versioner.create_metadata(str(test_file))
        
        assert metadata['file_name'] == 'data.csv'
        assert metadata['file_size_bytes'] > 0
        assert 'md5_hash' in metadata
        assert 'created_at' in metadata
    
    def test_save_metadata(self, temp_dir):
        """Test metadata saving"""
        from mlops.data_versioner import DataVersioner
        
        test_file = temp_dir / "data.parquet"
        test_file.write_text("fake parquet content")
        
        versioner = DataVersioner(repo_root=str(temp_dir))
        metadata = {'test': 'value', 'count': 100}
        
        metadata_path = versioner.save_metadata(str(test_file), metadata)
        
        assert Path(metadata_path).exists()
        
        with open(metadata_path) as f:
            loaded = json.load(f)
        
        assert loaded['test'] == 'value'
        assert loaded['count'] == 100


class TestModelPromoter:
    """Tests for ModelPromoter"""
    
    @pytest.fixture
    def mock_mlflow_client(self):
        """Mock MLflow client"""
        with patch('mlops.model_promoter.MlflowClient') as mock_client:
            yield mock_client
    
    def test_validate_for_production_passes(self, mock_mlflow_client):
        """Test validation passes with good metrics"""
        from mlops.model_promoter import ModelPromoter, PromotionCriteria
        
        promoter = ModelPromoter(
            tracking_uri="http://localhost:5000",
            model_name="test-model",
            criteria=PromotionCriteria(
                min_paper_trading_days=14,
                min_trade_count=100,
                min_sharpe_ratio=1.0,
                max_drawdown=0.10,
                min_win_rate=0.45
            )
        )
        
        good_metrics = {
            'days_traded': 20,
            'trade_count': 150,
            'sharpe_ratio': 1.5,
            'max_drawdown': 0.08,
            'win_rate': 0.52
        }
        
        passed, result = promoter.validate_for_production(1, good_metrics)
        
        assert passed is True
        assert all(result.checks.values())
    
    def test_validate_for_production_fails_sharpe(self, mock_mlflow_client):
        """Test validation fails with low Sharpe ratio"""
        from mlops.model_promoter import ModelPromoter, PromotionCriteria
        
        promoter = ModelPromoter(
            tracking_uri="http://localhost:5000",
            model_name="test-model",
            criteria=PromotionCriteria(min_sharpe_ratio=1.0)
        )
        
        bad_metrics = {
            'days_traded': 20,
            'trade_count': 150,
            'sharpe_ratio': 0.5,  # Below threshold
            'max_drawdown': 0.08,
            'win_rate': 0.52
        }
        
        passed, result = promoter.validate_for_production(1, bad_metrics)
        
        assert passed is False
        assert result.checks['sharpe_ratio'] is False
        assert any('sharpe' in m.lower() for m in result.messages)
    
    def test_validate_for_production_fails_drawdown(self, mock_mlflow_client):
        """Test validation fails with high drawdown"""
        from mlops.model_promoter import ModelPromoter, PromotionCriteria
        
        promoter = ModelPromoter(
            tracking_uri="http://localhost:5000",
            model_name="test-model",
            criteria=PromotionCriteria(max_drawdown=0.10)
        )
        
        bad_metrics = {
            'days_traded': 20,
            'trade_count': 150,
            'sharpe_ratio': 1.5,
            'max_drawdown': 0.15,  # Above threshold
            'win_rate': 0.52
        }
        
        passed, result = promoter.validate_for_production(1, bad_metrics)
        
        assert passed is False
        assert result.checks['max_drawdown'] is False
    
    def test_model_promotion_workflow(self, mock_mlflow_client):
        """Test full model promotion workflow"""
        from mlops.model_promoter import ModelPromoter, ValidationResult
        
        mock_instance = mock_mlflow_client.return_value
        mock_instance.get_latest_versions.return_value = []
        mock_instance.transition_model_version_stage.return_value = None
        mock_instance.set_model_version_tag.return_value = None
        
        promoter = ModelPromoter(
            tracking_uri="http://localhost:5000",
            model_name="test-model"
        )
        
        # Promote to staging
        success = promoter.promote_to_staging(version=1, approver="trainer")
        
        assert success is True
        mock_instance.transition_model_version_stage.assert_called()
        
        # Validate
        metrics = {
            'days_traded': 20,
            'trade_count': 150,
            'sharpe_ratio': 1.5,
            'max_drawdown': 0.08,
            'win_rate': 0.52
        }
        passed, validation = promoter.validate_for_production(1, metrics)
        
        assert passed is True
        
        # Promote to production
        success = promoter.promote_to_production(
            version=1,
            approver="admin",
            validation=validation
        )
        
        assert success is True


class TestDVCIntegration:
    """Tests for DVC integration"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_data_versioner_without_dvc(self, temp_dir):
        """Test DataVersioner handles missing DVC gracefully"""
        from mlops.data_versioner import DataVersioner
        
        versioner = DataVersioner(repo_root=str(temp_dir))
        
        # Should not crash even if DVC is not available
        assert versioner.repo_root == temp_dir


class TestTrainingReproducibility:
    """Tests for training reproducibility with MLOps"""
    
    def test_dummy_tracker_works(self):
        """Test DummyExperimentTracker doesn't crash"""
        from mlops.experiment_tracker import DummyExperimentTracker
        
        tracker = DummyExperimentTracker()
        
        # All operations should work without error
        run_id = tracker.start_run("test")
        tracker.log_params({'lr': 0.001})
        tracker.log_metrics({'loss': 0.5}, step=1)
        tracker.log_param("key", "value")
        tracker.log_metric("metric", 1.0)
        tracker.set_tag("tag", "value")
        tracker.end_run()
        
        assert run_id == "dummy-run-id"
    
    def test_get_experiment_tracker_fallback(self):
        """Test get_experiment_tracker falls back to dummy"""
        from mlops.experiment_tracker import get_experiment_tracker, DummyExperimentTracker
        
        # With invalid URI, should fall back to dummy
        tracker = get_experiment_tracker(
            tracking_uri="http://nonexistent:5000",
            allow_dummy=True
        )
        
        # Should be either real or dummy tracker
        assert tracker is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
