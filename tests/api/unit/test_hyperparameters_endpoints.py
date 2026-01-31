"""
Tests for hyperparameter search API endpoints
"""
import pytest
from unittest.mock import Mock, patch


class TestStartOptunaSearch:
    """POST /api/v1/hyperparameters/search"""
    
    def test_start_optuna_search(self, api_client):
        """Test study creation"""
        from schemas.hyperparameters import OptunaStudyResponse
        from schemas.experiments import ExperimentResponse
        from datetime import datetime
        
        from services import optuna_service, experiment_service
        with patch.object(optuna_service, 'create_optuna_study') as mock_create, \
             patch.object(experiment_service, 'get_experiment_by_id') as mock_get_exp:
            mock_get_exp.return_value = ExperimentResponse(
                id=1, name="test", features=[], currency_pairs=[],
                training_mode="paper", hyperparameters={}, status="created",
                created_at=datetime.utcnow()
            )
            mock_create.return_value = OptunaStudyResponse(
                id=1,
                experiment_id=1,
                study_name="test_study",
                n_trials=50,
                optimize_metric="sharpe_ratio",
                direction="maximize",
                status="running",
                created_at=datetime.utcnow()
            )
            
            response = api_client.post(
                "/api/v1/hyperparameters/search",
                json={
                    "experiment_id": 1,
                    "study_name": "test_study",
                    "n_trials": 50,
                    "optimize_metric": "sharpe_ratio",
                    "direction": "maximize"
                }
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["id"] == 1
            assert data["status"] == "running"
    
    def test_start_optuna_search_validation(self, api_client):
        """Test search space validation - experiment not found"""
        from services import experiment_service
        with patch.object(experiment_service, 'get_experiment_by_id') as mock_get_exp:
            mock_get_exp.return_value = None
            
            response = api_client.post(
                "/api/v1/hyperparameters/search",
                json={
                    "experiment_id": 999,
                    "study_name": "test_study",
                    "n_trials": 50,
                    "optimize_metric": "sharpe_ratio",
                    "direction": "maximize"
                }
            )
            
            # Should return 404 when experiment not found
            assert response.status_code == 404


class TestGetOptunaStatus:
    """GET /api/v1/experiments/{experiment_id}/optuna/status"""
    
    def test_get_optuna_status(self, api_client):
        """Test status retrieval"""
        from schemas.hyperparameters import OptunaStudyResponse
        from datetime import datetime
        
        from services import optuna_service
        with patch.object(optuna_service, 'get_study_by_experiment_id') as mock_get:
            mock_get.return_value = OptunaStudyResponse(
                id=1,
                experiment_id=1,
                study_name="test_study",
                n_trials=10,
                optimize_metric="sharpe_ratio",
                direction="maximize",
                status="running",
                best_value=1.5,
                best_params={"learning_rate": 0.001},
                created_at=datetime.utcnow()
            )
            
            response = api_client.get("/api/v1/experiments/1/optuna/status")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
    
    def test_get_optuna_status_not_found(self, api_client):
        """Test 404 when study not found"""
        from services import optuna_service
        with patch.object(optuna_service, 'get_study_by_experiment_id') as mock_get:
            mock_get.return_value = None
            
            response = api_client.get("/api/v1/experiments/1/optuna/status")
            
            assert response.status_code == 404


class TestGetOptunaTrials:
    """GET /api/v1/experiments/{experiment_id}/optuna/trials"""
    
    def test_get_optuna_trials(self, api_client):
        """Test trial listing"""
        from schemas.hyperparameters import OptunaStudyResponse, TrialResponse
        from datetime import datetime
        
        from services import optuna_service
        with patch.object(optuna_service, 'get_study_by_experiment_id') as mock_get_study, \
             patch.object(optuna_service, 'get_trials_by_study_id') as mock_get_trials:
            mock_get_study.return_value = OptunaStudyResponse(
                id=1, experiment_id=1, study_name="test", n_trials=10,
                optimize_metric="sharpe_ratio", direction="maximize",
                status="running", created_at=datetime.utcnow()
            )
            mock_get_trials.return_value = [
                TrialResponse(
                    id=1, study_id=1, trial_number=0,
                    params={"learning_rate": 0.001}, value=1.2,
                    state="complete", created_at=datetime.utcnow()
                ),
                TrialResponse(
                    id=2, study_id=1, trial_number=1,
                    params={"learning_rate": 0.002}, value=1.5,
                    state="complete", created_at=datetime.utcnow()
                )
            ]
            
            response = api_client.get("/api/v1/experiments/1/optuna/trials")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["trial_number"] == 0
    
    def test_get_optuna_trials_not_found(self, api_client):
        """Test 404 when study not found"""
        from services import optuna_service
        with patch.object(optuna_service, 'get_study_by_experiment_id') as mock_get:
            mock_get.return_value = None
            
            response = api_client.get("/api/v1/experiments/1/optuna/trials")
            
            assert response.status_code == 404
