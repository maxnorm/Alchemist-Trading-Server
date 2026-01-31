"""
Tests for experiment management API endpoints
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime


class TestCreateExperiment:
    """POST /api/v1/experiments - Create experiment"""
    
    def test_create_experiment(self, api_client):
        """Test valid experiment creation"""
        from schemas.experiments import ExperimentResponse
        
        from services import experiment_service
        with patch.object(experiment_service, 'create_experiment') as mock_create:
            mock_create.return_value = ExperimentResponse(
                id=1,
                name="test_experiment",
                description="Test",
                features=["price_bid_EURUSD"],
                currency_pairs=["EURUSD"],
                training_mode="paper",
                hyperparameters={"learning_rate": 0.001},
                status="created",
                created_at=datetime.utcnow()
            )
            
            response = api_client.post(
                "/api/v1/experiments",
                json={
                    "name": "test_experiment",
                    "description": "Test",
                    "features": ["price_bid_EURUSD"],
                    "currency_pairs": ["EURUSD"],
                    "training_mode": "paper",
                    "hyperparameters": {"learning_rate": 0.001}
                }
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["id"] == 1
            assert data["name"] == "test_experiment"
    
    def test_create_experiment_validation_error(self, api_client):
        """Test validation errors"""
        from services import experiment_service
        with patch.object(experiment_service, 'create_experiment') as mock_create:
            mock_create.side_effect = Exception("Invalid feature: invalid_feature")
            
            response = api_client.post(
                "/api/v1/experiments",
                json={
                    "name": "test",
                    "features": ["invalid_feature"],
                    "currency_pairs": ["EURUSD"],
                    "training_mode": "paper",
                    "hyperparameters": {}
                }
            )
            
            assert response.status_code == 400


class TestListExperiments:
    """GET /api/experiments - List experiments"""
    
    def test_list_experiments(self, api_client):
        """Test listing all experiments"""
        from schemas.experiments import ExperimentResponse
        
        from services import experiment_service
        with patch.object(experiment_service, 'get_all_experiments') as mock_get:
            mock_get.return_value = [
                ExperimentResponse(
                    id=1,
                    name="experiment_1",
                    features=[],
                    currency_pairs=[],
                    training_mode="paper",
                    hyperparameters={},
                    status="created",
                    created_at=datetime.utcnow()
                ),
                ExperimentResponse(
                    id=2,
                    name="experiment_2",
                    features=[],
                    currency_pairs=[],
                    training_mode="paper",
                    hyperparameters={},
                    status="training",
                    created_at=datetime.utcnow()
                )
            ]
            
            response = api_client.get("/api/v1/experiments")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["experiments"]) == 2
    
    def test_list_experiments_filter_by_status(self, api_client):
        """Test filtering by status"""
        from schemas.experiments import ExperimentResponse
        
        from services import experiment_service
        with patch.object(experiment_service, 'get_all_experiments') as mock_get:
            mock_get.return_value = [
                ExperimentResponse(
                    id=1,
                    name="experiment_1",
                    features=[],
                    currency_pairs=[],
                    training_mode="paper",
                    hyperparameters={},
                    status="created",
                    created_at=datetime.utcnow()
                )
            ]
            
            response = api_client.get("/api/v1/experiments?status=created")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["experiments"]) == 1
            assert data["experiments"][0]["status"] == "created"


class TestStartStopExperiment:
    """POST /api/v1/experiments/{id}/start and /stop"""
    
    def test_start_experiment(self, api_client):
        """Test starting experiment"""
        from schemas.experiments import ExperimentResponse
        
        from services import experiment_service
        with patch.object(experiment_service, 'get_experiment_by_id') as mock_get, \
             patch.object(experiment_service, 'update_experiment_status') as mock_update, \
             patch('infrastructure.messaging.experiment_publisher.ExperimentPublisher.get_instance') as mock_pub:
            mock_get.return_value = ExperimentResponse(
                id=1, name="test", features=[], currency_pairs=[], 
                training_mode="paper", hyperparameters={}, status="created",
                created_at=datetime.utcnow()
            )
            mock_update.return_value = ExperimentResponse(
                id=1, name="test", features=[], currency_pairs=[],
                training_mode="paper", hyperparameters={}, status="training",
                created_at=datetime.utcnow()
            )
            mock_publisher = Mock()
            mock_publisher.publish_experiment_start.return_value = True
            mock_pub.return_value = mock_publisher
            
            response = api_client.post(
                "/api/v1/experiments/1/start",
                json={"confirm": True}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "training"
    
    def test_stop_experiment(self, api_client):
        """Test stopping experiment"""
        from schemas.experiments import ExperimentResponse
        
        from services import experiment_service
        with patch.object(experiment_service, 'get_experiment_by_id') as mock_get, \
             patch.object(experiment_service, 'update_experiment_status') as mock_update:
            mock_get.return_value = ExperimentResponse(
                id=1, name="test", features=[], currency_pairs=[],
                training_mode="paper", hyperparameters={}, status="training",
                created_at=datetime.utcnow()
            )
            mock_update.return_value = ExperimentResponse(
                id=1, name="test", features=[], currency_pairs=[],
                training_mode="paper", hyperparameters={}, status="completed",
                created_at=datetime.utcnow()
            )
            
            response = api_client.post("/api/v1/experiments/1/stop")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
    
    def test_start_experiment_already_running(self, api_client):
        """Test error case: already running"""
        from schemas.experiments import ExperimentResponse
        
        from services import experiment_service
        with patch.object(experiment_service, 'get_experiment_by_id') as mock_get:
            mock_get.return_value = ExperimentResponse(
                id=1, name="test", features=[], currency_pairs=[],
                training_mode="paper", hyperparameters={}, status="training",
                created_at=datetime.utcnow()
            )
            
            response = api_client.post(
                "/api/v1/experiments/1/start",
                json={"confirm": True}
            )
            
            assert response.status_code == 400
            data = response.json()
            # Custom exception handler returns {"error": ..., "status_code": ...}
            assert "error" in data or "detail" in data
            error_msg = data.get("error") or data.get("detail", "")
            assert "already training" in error_msg.lower()
    
    def test_start_experiment_invalid_id(self, api_client):
        """Test error case: invalid ID"""
        from services import experiment_service
        with patch.object(experiment_service, 'get_experiment_by_id') as mock_get:
            mock_get.return_value = None
            
            response = api_client.post(
                "/api/v1/experiments/999/start",
                json={"confirm": True}
            )
            
            assert response.status_code == 404
