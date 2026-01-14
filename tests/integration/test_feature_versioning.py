"""
Integration tests for Feature Versioning

Tests feature pipeline versioning, feature registry, MLflow integration,
DVC integration, and feature catalog versioning.
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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/trading_server/src'))


class TestFeatureRegistry:
    """Tests for FeatureRegistry"""
    
    @pytest.fixture
    def mock_database(self):
        """Mock database connection"""
        db = MagicMock()
        conn = MagicMock()
        cursor = MagicMock()
        
        conn.cursor.return_value = cursor
        conn.commit = MagicMock()
        conn.rollback = MagicMock()
        conn.close = MagicMock()
        
        db.get_connection.return_value = conn
        
        return db
    
    def test_register_pipeline(self, mock_database):
        """Test pipeline version registration"""
        from mlops.feature_registry import FeatureRegistry
        
        registry = FeatureRegistry(mock_database)
        
        # Mock database response
        cursor = mock_database.get_connection().cursor()
        cursor.fetchone.return_value = None  # Version doesn't exist
        cursor.lastrowid = 1
        
        version = registry.register_pipeline(
            version="v1.0.0",
            pipeline_hash="abc123",
            feature_list=["price", "sma_20", "rsi"],
            feature_definitions={"window_size": 50},
            code_commit="commit123",
        )
        
        assert version is not None
        assert cursor.execute.call_count > 0
    
    def test_get_pipeline_version(self, mock_database):
        """Test retrieving pipeline version"""
        from mlops.feature_registry import FeatureRegistry
        
        registry = FeatureRegistry(mock_database)
        
        # Mock database response
        cursor = mock_database.get_connection().cursor()
        cursor.fetchone.return_value = (
            1,  # id
            "v1.0.0",  # version
            "abc123",  # pipeline_hash
            '["price", "sma_20"]',  # feature_list JSON
            '{"window_size": 50}',  # feature_definitions JSON
            "commit123",  # code_commit
            datetime.now(),  # created_at
        )
        
        version = registry.get_pipeline_version("v1.0.0")
        
        assert version is not None
        assert version.version == "v1.0.0"
        assert version.pipeline_hash == "abc123"
        assert len(version.feature_list) == 2
    
    def test_get_latest_version(self, mock_database):
        """Test getting latest pipeline version"""
        from mlops.feature_registry import FeatureRegistry
        
        registry = FeatureRegistry(mock_database)
        
        # Mock database response
        cursor = mock_database.get_connection().cursor()
        cursor.fetchone.return_value = (
            1,
            "v1.2.0",
            "hash456",
            '["price"]',
            '{}',
            None,
            datetime.now(),
        )
        
        latest = registry.get_latest_version()
        
        assert latest is not None
        assert latest.version == "v1.2.0"
    
    def test_list_versions(self, mock_database):
        """Test listing all versions"""
        from mlops.feature_registry import FeatureRegistry
        
        registry = FeatureRegistry(mock_database)
        
        # Mock database response
        cursor = mock_database.get_connection().cursor()
        cursor.fetchall.return_value = [
            (1, "v1.0.0", "hash1", '["price"]', '{}', None, datetime.now()),
            (2, "v1.1.0", "hash2", '["price", "rsi"]', '{}', None, datetime.now()),
        ]
        
        versions = registry.list_versions()
        
        assert len(versions) == 2
        assert versions[0].version == "v1.0.0"
        assert versions[1].version == "v1.1.0"
    
    def test_compute_pipeline_hash(self):
        """Test computing pipeline hash from files"""
        from mlops.feature_registry import FeatureRegistry
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            file1 = Path(tmpdir) / "feature1.py"
            file2 = Path(tmpdir) / "feature2.py"
            
            file1.write_text("def compute_feature(): pass")
            file2.write_text("def compute_other(): pass")
            
            hash1 = FeatureRegistry.compute_pipeline_hash([str(file1), str(file2)])
            hash2 = FeatureRegistry.compute_pipeline_hash([str(file1), str(file2)])
            
            # Same files should produce same hash
            assert hash1 == hash2
            
            # Different content should produce different hash
            file1.write_text("def compute_feature_different(): pass")
            hash3 = FeatureRegistry.compute_pipeline_hash([str(file1), str(file2)])
            assert hash1 != hash3


class TestFeatureEngineVersioning:
    """Tests for FeatureEngine versioning"""
    
    @pytest.fixture
    def feature_engineer(self):
        """Create a feature engineer instance"""
        from utils.feature_engineering import FeatureEngineer
        return FeatureEngineer(normalization_method="robust")
    
    @pytest.fixture
    def mock_database(self):
        """Mock database"""
        return MagicMock()
    
    @pytest.fixture
    def mock_registry(self):
        """Mock feature registry"""
        registry = MagicMock()
        registry.get_pipeline_by_hash.return_value = None
        registry.get_latest_version.return_value = None
        registry.compute_pipeline_hash.return_value = "test_hash"
        registry.get_git_commit.return_value = "commit123"
        
        # Mock registered version
        from mlops.feature_registry import FeaturePipelineVersion
        registered = FeaturePipelineVersion(
            version="v1.0.0",
            pipeline_hash="test_hash",
            feature_list=["price", "sma_20"],
            feature_definitions={},
            created_at=datetime.now(),
        )
        registry.register_pipeline.return_value = registered
        
        return registry
    
    def test_feature_engine_initializes_versioning(self, feature_engineer, mock_registry):
        """Test that FeatureEngine initializes versioning"""
        from application.environment.feature_engine import FeatureEngine
        
        engine = FeatureEngine(
            feature_engineer=feature_engineer,
            window_size=50,
            features_per_pair=10,
            feature_registry=mock_registry,
        )
        
        assert engine.pipeline_version is not None
        assert len(engine.feature_list) > 0
    
    def test_get_pipeline_metadata(self, feature_engineer, mock_registry):
        """Test exporting pipeline metadata"""
        from application.environment.feature_engine import FeatureEngine
        
        engine = FeatureEngine(
            feature_engineer=feature_engineer,
            window_size=50,
            features_per_pair=10,
            feature_registry=mock_registry,
        )
        
        metadata = engine.get_pipeline_metadata()
        
        assert "version" in metadata
        assert "features" in metadata
        assert "parameters" in metadata
        assert "feature_definitions" in metadata
        assert metadata["parameters"]["window_size"] == 50


class TestMLflowIntegration:
    """Tests for MLflow feature pipeline integration"""
    
    @pytest.fixture
    def mock_mlflow(self):
        """Mock MLflow module"""
        with patch.dict(sys.modules, {'mlflow': MagicMock()}):
            yield sys.modules['mlflow']
    
    def test_log_feature_pipeline(self, mock_mlflow):
        """Test logging feature pipeline to MLflow"""
        from mlops.experiment_tracker import ExperimentTracker
        
        # Setup mocks
        mock_mlflow.set_tracking_uri = MagicMock()
        mock_mlflow.set_experiment = MagicMock()
        mock_mlflow.get_experiment_by_name = MagicMock(return_value=MagicMock(experiment_id="1"))
        mock_mlflow.start_run = MagicMock(return_value=MagicMock(info=MagicMock(run_id="test-run-id")))
        mock_mlflow.set_tag = MagicMock()
        mock_mlflow.log_dict = MagicMock()
        mock_mlflow.log_param = MagicMock()
        
        tracker = ExperimentTracker()
        tracker.start_run("test")
        
        tracker.log_feature_pipeline(
            pipeline_version="v1.0.0",
            feature_list=["price", "sma_20", "rsi"],
            feature_metadata={"window_size": 50},
        )
        
        # Verify tag was set
        mock_mlflow.set_tag.assert_any_call("feature_pipeline_version", "v1.0.0")
        
        # Verify dict was logged
        assert mock_mlflow.log_dict.called
        call_args = mock_mlflow.log_dict.call_args
        assert call_args[0][1] == "feature_pipeline.json"


class TestDVCIntegration:
    """Tests for DVC feature code versioning"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @patch('subprocess.run')
    def test_version_feature_code(self, mock_subprocess, temp_dir):
        """Test versioning feature code with DVC"""
        from mlops.data_versioner import DataVersioner
        
        # Mock DVC commands
        def mock_run(cmd, **kwargs):
            result = MagicMock()
            if cmd[0] == "dvc" and cmd[1] == "version":
                result.returncode = 0
            elif cmd[0] == "dvc" and cmd[1] == "add":
                result.returncode = 0
            elif cmd[0] == "git" and cmd[1] == "rev-parse":
                result.returncode = 0
                result.stdout = "abc123\n"
            else:
                result.returncode = 0
            return result
        
        mock_subprocess.side_effect = mock_run
        
        versioner = DataVersioner(repo_root=str(temp_dir))
        
        # Create test feature files
        feature_file = temp_dir / "feature.py"
        feature_file.write_text("def compute(): pass")
        
        commit_hash = versioner.version_feature_code(
            feature_files=[str(feature_file)],
            version="v1.0.0",
        )
        
        # Should return commit hash if successful
        # In this mock, it should work
        assert mock_subprocess.called


class TestFeatureCatalogVersioning:
    """Tests for Feature Catalog versioning"""
    
    @pytest.fixture
    def mock_database(self):
        """Mock database"""
        db = MagicMock()
        conn = MagicMock()
        cursor = MagicMock()
        
        conn.cursor.return_value = cursor
        conn.commit = MagicMock()
        conn.rollback = MagicMock()
        conn.close = MagicMock()
        
        db.get_connection.return_value = conn
        
        return db
    
    def test_get_features_by_pipeline_version(self, mock_database):
        """Test getting features by pipeline version"""
        from features.catalog import FeatureCatalog
        
        catalog = FeatureCatalog(mock_database)
        
        # Mock database response
        cursor = mock_database.get_connection().cursor()
        cursor.fetchall.return_value = [
            ("price", "float", "feature_engine", "Price feature", "price", True),
            ("sma_20", "float", "feature_engine", "SMA 20", "technical", True),
        ]
        
        features = catalog.get_features_by_pipeline_version("v1.0.0")
        
        assert len(features) == 2
        assert features[0].name == "price"
    
    def test_get_feature_history(self, mock_database):
        """Test getting feature history"""
        from features.catalog import FeatureCatalog
        
        catalog = FeatureCatalog(mock_database)
        
        # Mock database response
        cursor = mock_database.get_connection().cursor()
        cursor.fetchall.return_value = [
            ("v1.0.0", "v1.0.0", datetime.now(), datetime.now()),
            ("v1.1.0", "v1.0.0", datetime.now(), datetime.now()),
        ]
        
        history = catalog.get_feature_history("price")
        
        assert len(history) == 2
        assert history[0]["pipeline_version"] == "v1.0.0"
    
    def test_compare_versions(self, mock_database):
        """Test comparing feature sets between versions"""
        from features.catalog import FeatureCatalog
        
        catalog = FeatureCatalog(mock_database)
        
        # Mock get_features_by_pipeline_version calls
        def mock_get_features(version):
            if version == "v1.0.0":
                from domain.models.feature import Feature
                return [
                    Feature("price", float, "source", "Price", "price"),
                    Feature("sma_20", float, "source", "SMA", "technical"),
                ]
            else:  # v1.1.0
                from domain.models.feature import Feature
                return [
                    Feature("price", float, "source", "Price", "price"),
                    Feature("rsi", float, "source", "RSI", "technical"),
                ]
        
        catalog.get_features_by_pipeline_version = mock_get_features
        
        comparison = catalog.compare_versions("v1.0.0", "v1.1.0")
        
        assert comparison["version1"] == "v1.0.0"
        assert comparison["version2"] == "v1.1.0"
        assert "rsi" in comparison["added_features"]
        assert "sma_20" in comparison["removed_features"]
        assert "price" in comparison["common_features"]


class TestEndToEndWorkflow:
    """End-to-end tests for feature versioning workflow"""
    
    @pytest.fixture
    def mock_database(self):
        """Mock database"""
        db = MagicMock()
        conn = MagicMock()
        cursor = MagicMock()
        
        conn.cursor.return_value = cursor
        conn.commit = MagicMock()
        conn.rollback = MagicMock()
        conn.close = MagicMock()
        
        db.get_connection.return_value = conn
        
        return db
    
    @pytest.fixture
    def mock_mlflow(self):
        """Mock MLflow"""
        with patch.dict(sys.modules, {'mlflow': MagicMock()}):
            mlflow = sys.modules['mlflow']
            mlflow.set_tracking_uri = MagicMock()
            mlflow.set_experiment = MagicMock()
            mlflow.get_experiment_by_name = MagicMock(return_value=MagicMock(experiment_id="1"))
            mlflow.start_run = MagicMock(return_value=MagicMock(info=MagicMock(run_id="test-run-id")))
            mlflow.set_tag = MagicMock()
            mlflow.log_dict = MagicMock()
            mlflow.log_param = MagicMock()
            yield mlflow
    
    def test_complete_workflow(self, mock_database, mock_mlflow):
        """Test complete workflow: feature computation -> versioning -> MLflow logging"""
        from mlops.feature_registry import FeatureRegistry
        from mlops.experiment_tracker import ExperimentTracker
        from utils.feature_engineering import FeatureEngineer
        from application.environment.feature_engine import FeatureEngine
        
        # Setup registry
        registry = FeatureRegistry(mock_database)
        cursor = mock_database.get_connection().cursor()
        cursor.fetchone.return_value = None  # New version
        cursor.lastrowid = 1
        
        # Create feature engine
        feature_engineer = FeatureEngineer()
        engine = FeatureEngine(
            feature_engineer=feature_engineer,
            window_size=50,
            features_per_pair=10,
            feature_registry=registry,
        )
        
        # Get metadata
        metadata = engine.get_pipeline_metadata()
        assert metadata["version"] is not None
        
        # Log to MLflow
        tracker = ExperimentTracker()
        tracker.start_run("test")
        
        tracker.log_feature_pipeline(
            pipeline_version=metadata["version"],
            feature_list=metadata["features"],
            feature_metadata=metadata["feature_definitions"],
        )
        
        # Verify MLflow was called
        assert mock_mlflow.set_tag.called
        assert mock_mlflow.log_dict.called
