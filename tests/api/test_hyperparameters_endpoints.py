"""
Tests for hyperparameter search API endpoints
"""
import pytest
from unittest.mock import Mock, patch


class TestStartOptunaSearch:
    """POST /api/experiments/{id}/optuna/start"""
    
    def test_start_optuna_search(self, api_client):
        """Test study creation"""
        with patch('services.optuna_service.start_optuna_search') as mock_start:
            mock_start.return_value = {
                "study_id": 1,
                "status": "running",
                "message": "Optuna search started"
            }
            
            response = api_client.post(
                "/api/v1/experiments/1/optuna/start",
                json={
                    "metric": "sharpe_ratio",
                    "direction": "maximize",
                    "n_trials": 50
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["study_id"] == 1
            assert data["status"] == "running"
    
    def test_start_optuna_search_validation(self, api_client):
        """Test search space validation"""
        with patch('services.optuna_service.start_optuna_search') as mock_start:
            mock_start.side_effect = ValueError("Invalid metric: invalid_metric")
            
            response = api_client.post(
                "/api/v1/experiments/1/optuna/start",
                json={
                    "metric": "invalid_metric",
                    "direction": "maximize",
                    "n_trials": 50
                }
            )
            
            assert response.status_code == 400


class TestGetOptunaStatus:
    """GET /api/experiments/{id}/optuna/status"""
    
    def test_get_optuna_status(self, api_client):
        """Test status retrieval"""
        with patch('services.optuna_service.get_optuna_status') as mock_get:
            mock_get.return_value = {
                "study_id": 1,
                "status": "running",
                "n_trials": 10,
                "n_completed": 5,
                "best_value": 1.5,
                "best_params": {"learning_rate": 0.001}
            }
            
            response = api_client.get("/api/v1/experiments/1/optuna/status")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert data["n_trials"] == 10
            assert data["n_completed"] == 5
    
    def test_get_optuna_status_not_found(self, api_client):
        """Test 404 when study not found"""
        with patch('services.optuna_service.get_optuna_status') as mock_get:
            mock_get.return_value = None
            
            response = api_client.get("/api/v1/experiments/1/optuna/status")
            
            assert response.status_code == 404


class TestGetOptunaTrials:
    """GET /api/experiments/{id}/optuna/trials"""
    
    def test_get_optuna_trials(self, api_client):
        """Test trial listing"""
        with patch('services.optuna_service.get_optuna_trials') as mock_get:
            mock_get.return_value = [
                {
                    "trial_number": 0,
                    "params": {"learning_rate": 0.001},
                    "value": 1.2,
                    "state": "complete"
                },
                {
                    "trial_number": 1,
                    "params": {"learning_rate": 0.002},
                    "value": 1.5,
                    "state": "complete"
                }
            ]
            
            response = api_client.get("/api/v1/experiments/1/optuna/trials")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["trial_number"] == 0
    
    def test_get_optuna_trials_filtering(self, api_client):
        """Test filtering and sorting"""
        with patch('services.optuna_service.get_optuna_trials') as mock_get:
            mock_get.return_value = [
                {
                    "trial_number": 1,
                    "params": {"learning_rate": 0.002},
                    "value": 1.5,
                    "state": "complete"
                }
            ]
            
            response = api_client.get("/api/v1/experiments/1/optuna/trials?state=complete&sort=value&order=desc")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
