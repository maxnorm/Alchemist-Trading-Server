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
        with patch('services.experiment_service.create_experiment') as mock_create:
            mock_create.return_value = {
                "id": 1,
                "name": "test_experiment",
                "description": "Test",
                "features": ["price_bid_EURUSD"],
                "currency_pairs": ["EURUSD"],
                "training_mode": "live",
                "hyperparameters": {"learning_rate": 0.001},
                "status": "created",
                "created_at": datetime.utcnow().isoformat()
            }
            
            response = api_client.post(
                "/api/v1/experiments",
                json={
                    "name": "test_experiment",
                    "description": "Test",
                    "features": ["price_bid_EURUSD"],
                    "currency_pairs": ["EURUSD"],
                    "training_mode": "live",
                    "hyperparameters": {"learning_rate": 0.001}
                }
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["id"] == 1
            assert data["name"] == "test_experiment"
    
    def test_create_experiment_validation_error(self, api_client):
        """Test validation errors"""
        with patch('services.experiment_service.create_experiment') as mock_create:
            mock_create.side_effect = ValueError("Invalid feature: invalid_feature")
            
            response = api_client.post(
                "/api/v1/experiments",
                json={
                    "name": "test",
                    "features": ["invalid_feature"],
                    "currency_pairs": ["EURUSD"],
                    "training_mode": "live",
                    "hyperparameters": {}
                }
            )
            
            assert response.status_code == 400


class TestListExperiments:
    """GET /api/experiments - List experiments"""
    
    def test_list_experiments(self, api_client):
        """Test listing all experiments"""
        with patch('services.experiment_service.get_all_experiments') as mock_get:
            mock_get.return_value = [
                {
                    "id": 1,
                    "name": "experiment_1",
                    "status": "created"
                },
                {
                    "id": 2,
                    "name": "experiment_2",
                    "status": "training"
                }
            ]
            
            response = api_client.get("/api/v1/experiments")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["experiments"]) == 2
    
    def test_list_experiments_filter_by_status(self, api_client):
        """Test filtering by status"""
        with patch('services.experiment_service.get_all_experiments') as mock_get:
            mock_get.return_value = [
                {
                    "id": 1,
                    "name": "experiment_1",
                    "status": "created"
                }
            ]
            
            response = api_client.get("/api/experiments?status=created")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["experiments"]) == 1
            assert data["experiments"][0]["status"] == "created"


class TestStartStopExperiment:
    """POST /api/v1/experiments/{id}/start and /stop"""
    
    def test_start_experiment(self, api_client):
        """Test starting experiment"""
        with patch('services.experiment_service.start_experiment') as mock_start:
            mock_start.return_value = {"success": True, "message": "Experiment started"}
            
            response = api_client.post("/api/experiments/1/start")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
    
    def test_stop_experiment(self, api_client):
        """Test stopping experiment"""
        with patch('services.experiment_service.stop_experiment') as mock_stop:
            mock_stop.return_value = {"success": True, "message": "Experiment stopped"}
            
            response = api_client.post("/api/experiments/1/stop")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
    
    def test_start_experiment_already_running(self, api_client):
        """Test error case: already running"""
        with patch('services.experiment_service.start_experiment') as mock_start:
            mock_start.side_effect = ValueError("Experiment is already running")
            
            response = api_client.post("/api/experiments/1/start")
            
            assert response.status_code in [400, 409]  # Bad Request or Conflict
    
    def test_start_experiment_invalid_id(self, api_client):
        """Test error case: invalid ID"""
        with patch('services.experiment_service.start_experiment') as mock_start:
            mock_start.side_effect = ValueError("Experiment not found")
            
            response = api_client.post("/api/experiments/999/start")
            
            assert response.status_code in [400, 404]
