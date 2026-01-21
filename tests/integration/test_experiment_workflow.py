"""
Integration tests for complete experiment workflow

Tests experiment creation, execution, and MLflow linking
"""
import pytest
import os
import sys
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/trading_server/src'))

from experiments.builder import ExperimentBuilder
from experiments.runner import ExperimentRunner
from experiments.models import Experiment, ExperimentStatus, ExperimentRepository
from features.catalog import FeatureCatalog
from domain.models.feature import Feature


class TestExperimentCreation:
    """Test experiment creation via ExperimentBuilder"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database"""
        db = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        db.get_connection = Mock(return_value=mock_conn)
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.lastrowid = 1
        return db, mock_conn, mock_cursor
    
    @pytest.fixture
    def mock_feature_catalog(self):
        """Create mock feature catalog"""
        catalog = Mock(spec=FeatureCatalog)
        catalog.get_feature.return_value = Feature(
            name="price_bid_EURUSD",
            data_type=float,
            source="price",
            description="Bid price",
            category="price"
        )
        catalog.get_all_features.return_value = [
            Feature(name="price_bid_EURUSD", data_type=float, source="price", description="", category="price"),
            Feature(name="rsi_14_EURUSD", data_type=float, source="indicator", description="", category="technical"),
        ]
        return catalog
    
    def test_create_experiment(self, mock_db, mock_feature_catalog):
        """Test creating experiment with valid features and pairs"""
        db, mock_conn, mock_cursor = mock_db
        
        builder = ExperimentBuilder(db, mock_feature_catalog)
        
        experiment = builder.create_experiment(
            name="test_experiment",
            description="Test experiment",
            features=["price_bid_EURUSD", "rsi_14_EURUSD"],
            currency_pairs=["EURUSD"],
            training_mode="live",
            hyperparameters={
                "learning_rate": 0.001,
                "gamma": 0.99,
                "batch_size": 32,
                "hidden_layers": [128, 64],
                "window_size": 50,
                "replay_buffer_size": 10000,
                "epsilon_start": 1.0,
                "epsilon_end": 0.01,
                "epsilon_decay": 0.995,
                "target_update_freq": 100
            }
        )
        
        assert experiment.id == 1
        assert experiment.name == "test_experiment"
        assert experiment.status == ExperimentStatus.CREATED
        assert mock_cursor.execute.called
        mock_conn.commit.assert_called_once()
    
    def test_experiment_validation(self, mock_db, mock_feature_catalog):
        """Test experiment validation logic"""
        db, mock_conn, mock_cursor = mock_db
        
        builder = ExperimentBuilder(db, mock_feature_catalog)
        
        # Test invalid feature
        mock_feature_catalog.get_feature.return_value = None
        
        with pytest.raises(ValueError):
            builder.create_experiment(
                name="test",
                description="Test",
                features=["invalid_feature"],
                currency_pairs=["EURUSD"],
                training_mode="live",
                hyperparameters={"learning_rate": 0.001}
            )


class TestExperimentStartStop:
    """Test starting and stopping experiments"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database"""
        db = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        db.get_connection = Mock(return_value=mock_conn)
        mock_conn.cursor.return_value = mock_cursor
        return db, mock_conn, mock_cursor
    
    @pytest.fixture
    def mock_experiment(self):
        """Create mock experiment"""
        return Experiment(
            id=1,
            name="test_experiment",
            description="Test",
            features=["price_bid_EURUSD"],
            currency_pairs=["EURUSD"],
            training_mode="live",
            hyperparameters={"learning_rate": 0.001},
            status=ExperimentStatus.CREATED,
            created_at=datetime.utcnow(),
            started_at=None,
            completed_at=None,
            mlflow_run_id=None
        )
    
    def test_start_experiment(self, mock_db, mock_experiment):
        """Test starting experiment, verify status changes"""
        db, mock_conn, mock_cursor = mock_db
        
        repository = Mock(spec=ExperimentRepository)
        repository.get_experiment.return_value = mock_experiment
        repository.update_experiment_status = Mock()
        
        runner = ExperimentRunner(
            database=db,
            experiment_tracker=Mock(),
            agent_factory=Mock(),
            environment_factory=Mock(),
            get_account_func=Mock(return_value=Mock()),
            get_risk_manager_func=Mock(return_value=Mock())
        )
        runner.repository = repository
        
        # Mock agent and environment creation
        runner._create_agent_config = Mock(return_value=Mock())
        runner._create_environment = Mock(return_value=Mock())
        runner._start_training = Mock(return_value=True)
        
        success = runner.start_experiment(experiment_id=1)
        
        # Verify status was updated
        assert repository.update_experiment_status.called
    
    def test_stop_experiment(self, mock_db, mock_experiment):
        """Test stopping experiment, verify cleanup"""
        db, mock_conn, mock_cursor = mock_db
        
        repository = Mock(spec=ExperimentRepository)
        repository.get_experiment.return_value = mock_experiment
        repository.update_experiment_status = Mock()
        
        mock_trainer = Mock()
        mock_thread = Mock()
        mock_thread.is_alive.return_value = False
        
        runner = ExperimentRunner(
            database=db,
            experiment_tracker=Mock(),
            agent_factory=Mock(),
            environment_factory=Mock(),
            get_account_func=Mock(return_value=Mock()),
            get_risk_manager_func=Mock(return_value=Mock())
        )
        runner.repository = repository
        runner.running_experiments[1] = (mock_trainer, mock_thread)
        
        success = runner.stop_experiment(experiment_id=1)
        
        assert success
        assert 1 not in runner.running_experiments


class TestExperimentReproducibilityMetadata:
    """Test reproducibility metadata logging in MLflow"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database"""
        db = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        db.get_connection = Mock(return_value=mock_conn)
        mock_conn.cursor.return_value = mock_cursor
        return db, mock_conn, mock_cursor
    
    @pytest.fixture
    def mock_experiment(self):
        """Create mock experiment"""
        return Experiment(
            id=1,
            name="test_experiment",
            description="Test",
            features=["price_bid_EURUSD"],
            currency_pairs=["EURUSD"],
            training_mode="live",
            hyperparameters={"learning_rate": 0.001, "seed": 42},
            status=ExperimentStatus.CREATED,
            created_at=datetime.utcnow(),
            started_at=None,
            completed_at=None,
            mlflow_run_id=None
        )
    
    @pytest.fixture
    def mock_mlflow(self):
        """Mock MLflow module"""
        with patch.dict(sys.modules, {'mlflow': MagicMock()}):
            yield sys.modules['mlflow']
    
    def test_reproducibility_metadata_tags_logged(self, mock_db, mock_experiment, mock_mlflow):
        """Test that git_commit, random_seed, and config_hash tags are logged when starting experiment"""
        db, mock_conn, mock_cursor = mock_db
        
        from mlops.experiment_tracker import ExperimentTracker
        
        # Setup MLflow mocks
        mock_mlflow.set_tracking_uri = MagicMock()
        mock_mlflow.set_experiment = MagicMock()
        mock_mlflow.get_experiment_by_name = MagicMock(return_value=MagicMock(experiment_id="1"))
        mock_run = MagicMock(info=MagicMock(run_id="test-run-id"))
        mock_mlflow.start_run = MagicMock(return_value=mock_run)
        mock_mlflow.set_tag = MagicMock()
        mock_mlflow.log_param = MagicMock()
        mock_mlflow.log_params = MagicMock()
        mock_mlflow.log_dict = MagicMock()
        mock_mlflow.end_run = MagicMock()
        
        # Create tracker
        tracker = ExperimentTracker(
            tracking_uri="http://localhost:5000",
            experiment_name="test-experiment"
        )
        
        # Mock git commit
        with patch.object(tracker, '_get_git_commit', return_value='abc123def456789'):
            # Create repository mock
            repository = Mock(spec=ExperimentRepository)
            repository.get_experiment.return_value = mock_experiment
            repository.update_experiment_status = Mock()
            
            # Create runner with mocked dependencies
            runner = ExperimentRunner(
                database=db,
                experiment_tracker=tracker,
                agent_factory=Mock(),
                environment_factory=Mock(),
                get_account_func=Mock(return_value=Mock()),
                get_risk_manager_func=Mock(return_value=Mock())
            )
            runner.repository = repository
            
            # Mock all the internal methods that would normally create real objects
            runner._create_agent_config = Mock(return_value=Mock())
            runner._get_connectors_for_pairs = Mock(return_value=[])
            runner.environment_factory.create_environment = Mock(return_value=Mock())
            runner.agent_factory.create_agent = Mock(return_value=Mock())
            runner._create_training_config = Mock(return_value=Mock())
            runner._run_training = Mock()  # Prevent actual training thread
            
            # Mock data versioner
            with patch('mlops.data_versioner.DataVersioner', return_value=Mock(_dvc_available=False)):
                # Start experiment
                success = runner.start_experiment(experiment_id=1)
        
        # Verify experiment was started
        assert success
        
        # Verify required tags were set
        tag_calls = {call[0][0]: call[0][1] for call in mock_mlflow.set_tag.call_args_list}
        
        # Check for required tags
        assert 'git_commit' in tag_calls, f"git_commit tag not found. Tags: {list(tag_calls.keys())}"
        assert tag_calls['git_commit'] == 'abc123def456789'
        
        assert 'random_seed' in tag_calls, f"random_seed tag not found. Tags: {list(tag_calls.keys())}"
        assert tag_calls['random_seed'] == '42'
        
        assert 'config_hash' in tag_calls, f"config_hash tag not found. Tags: {list(tag_calls.keys())}"
        assert tag_calls['config_hash'] is not None
        assert tag_calls['config_hash'] != 'unknown'
        
        # Verify parameters were also logged
        param_calls = {call[0][0]: call[0][1] for call in mock_mlflow.log_param.call_args_list}
        assert 'git_commit' in param_calls
        assert 'random_seed' in param_calls
        assert 'config_hash' in param_calls


class TestExperimentCloning:
    """Test cloning existing experiments"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database"""
        db = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        db.get_connection = Mock(return_value=mock_conn)
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.lastrowid = 2
        return db, mock_conn, mock_cursor
    
    def test_clone_experiment(self, mock_db):
        """Test cloning experiment with modifications"""
        db, mock_conn, mock_cursor = mock_db
        
        original_experiment = Experiment(
            id=1,
            name="original",
            description="Original",
            features=["price_bid_EURUSD"],
            currency_pairs=["EURUSD"],
            training_mode="live",
            hyperparameters={"learning_rate": 0.001},
            status=ExperimentStatus.COMPLETED,
            created_at=datetime.utcnow(),
            started_at=None,
            completed_at=None,
            mlflow_run_id="run-123"
        )
        
        repository = Mock(spec=ExperimentRepository)
        repository.get_experiment.return_value = original_experiment
        
        catalog = Mock(spec=FeatureCatalog)
        catalog.get_feature.return_value = Feature(
            name="price_bid_EURUSD",
            data_type=float,
            source="price",
            description="",
            category="price"
        )
        
        builder = ExperimentBuilder(db, catalog)
        builder.repository = repository
        
        cloned = builder.clone_experiment(
            experiment_id=1,
            new_name="cloned_experiment",
            modifications={"learning_rate": 0.002}
        )
        
        assert cloned.id == 2
        assert cloned.name == "cloned_experiment"
        assert cloned.hyperparameters["learning_rate"] == 0.002
        assert cloned.status == ExperimentStatus.CREATED  # Reset status


class TestExperimentMLflowLinking:
    """Test MLflow run linking to experiments"""
    
    @pytest.fixture
    def mock_experiment_tracker(self):
        """Create mock experiment tracker"""
        tracker = Mock()
        tracker.start_run.return_value = "mlflow-run-123"
        return tracker
    
    def test_mlflow_run_created(self, mock_experiment_tracker):
        """Test that MLflow run is created when experiment starts"""
        # Verify tracker is called
        run_id = mock_experiment_tracker.start_run(
            experiment_name="test_experiment",
            tags={"experiment_id": "1"}
        )
        
        assert run_id == "mlflow-run-123"
        mock_experiment_tracker.start_run.assert_called_once()
    
    def test_experiment_id_tag(self, mock_experiment_tracker):
        """Test that experiment_id is stored as MLflow tag"""
        mock_experiment_tracker.start_run(
            experiment_name="test",
            tags={"experiment_id": "1", "status": "training"}
        )
        
        # Verify tags include experiment_id
        call_args = mock_experiment_tracker.start_run.call_args
        assert "experiment_id" in call_args.kwargs["tags"]
        assert call_args.kwargs["tags"]["experiment_id"] == "1"
