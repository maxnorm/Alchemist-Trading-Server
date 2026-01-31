"""
Integration tests for experiment management API endpoints with real database
"""
import pytest
import json
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text


@pytest.mark.integration
class TestExperimentLifecycle:
    """Test experiment CRUD operations with real database"""
    
    def test_create_experiment(self, api_client_integration, db_session):
        """Test creating experiment via API and verify database record"""
        response = api_client_integration.post(
            "/api/v1/experiments",
            json={
                "name": "test_experiment",
                "description": "Test experiment description",
                "features": ["price_bid_EURUSD", "price_ask_EURUSD"],
                "currency_pairs": ["EURUSD", "GBPUSD"],
                "training_mode": "historical",
                "hyperparameters": {"learning_rate": 0.001, "batch_size": 32}
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        experiment_id = data["id"]
        
        # Verify in database
        result = db_session.execute(
            text("SELECT * FROM experiments WHERE id = :id"),
            {"id": experiment_id}
        )
        row = result.fetchone()
        assert row is not None
        
        row_dict = dict(row._mapping)
        
        # Verify fields
        assert row_dict["name"] == "test_experiment"
        assert row_dict["description"] == "Test experiment description"
        assert row_dict["status"] == "created"
        assert row_dict["training_mode"] == "historical"
        assert row_dict["created_at"] is not None
        assert row_dict["started_at"] is None
        assert row_dict["completed_at"] is None
        
        # Verify JSONB fields
        features = json.loads(row_dict["features"]) if isinstance(row_dict["features"], str) else row_dict["features"]
        currency_pairs = json.loads(row_dict["currency_pairs"]) if isinstance(row_dict["currency_pairs"], str) else row_dict["currency_pairs"]
        hyperparameters = json.loads(row_dict["hyperparameters"]) if isinstance(row_dict["hyperparameters"], str) else row_dict["hyperparameters"]
        
        assert features == ["price_bid_EURUSD", "price_ask_EURUSD"]
        assert currency_pairs == ["EURUSD", "GBPUSD"]
        assert hyperparameters == {"learning_rate": 0.001, "batch_size": 32}
    
    def test_get_experiment(self, api_client_integration, db_session):
        """Test getting experiment and verify JSONB fields parsed correctly"""
        # Create experiment via SQL
        from tests.api.integration.conftest import create_test_experiment_via_sql
        experiment_id = create_test_experiment_via_sql(
            db_session,
            name="get_test_experiment",
            features=["feature1", "feature2"],
            currency_pairs=["EURUSD"],
            hyperparameters={"lr": 0.01}
        )
        
        # Get via API
        response = api_client_integration.get(f"/api/v1/experiments/{experiment_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == experiment_id
        assert data["name"] == "get_test_experiment"
        assert data["features"] == ["feature1", "feature2"]
        assert data["currency_pairs"] == ["EURUSD"]
        assert data["hyperparameters"] == {"lr": 0.01}
        assert data["status"] == "created"
    
    def test_list_experiments(self, api_client_integration, db_session):
        """Test listing experiments with filters"""
        # Create multiple experiments
        from tests.api.integration.conftest import create_test_experiment_via_sql
        
        exp1_id = create_test_experiment_via_sql(db_session, name="exp1", status="created")
        exp2_id = create_test_experiment_via_sql(db_session, name="exp2", status="training")
        exp3_id = create_test_experiment_via_sql(db_session, name="exp3", status="created")
        
        # List all
        response = api_client_integration.get("/api/v1/experiments")
        assert response.status_code == 200
        data = response.json()
        assert len(data["experiments"]) >= 3
        assert data["total"] >= 3
        
        # Filter by status
        response = api_client_integration.get("/api/v1/experiments?status=created")
        assert response.status_code == 200
        data = response.json()
        assert all(exp["status"] == "created" for exp in data["experiments"])


@pytest.mark.integration
class TestExperimentStatusTransitions:
    """Test experiment status transitions and timestamps"""
    
    def test_start_experiment(self, api_client_integration, db_session):
        """Test starting experiment and verify status and timestamp updates"""
        # Create experiment
        response = api_client_integration.post(
            "/api/v1/experiments",
            json={
                "name": "start_test",
                "features": ["price_bid_EURUSD"],
                "currency_pairs": ["EURUSD"],
                "training_mode": "historical",
                "hyperparameters": {}
            }
        )
        experiment_id = response.json()["id"]
        
        # Start experiment
        response = api_client_integration.post(
            f"/api/v1/experiments/{experiment_id}/start",
            json={"confirm": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "training"
        assert data["started_at"] is not None
        
        # Verify in database
        result = db_session.execute(
            text("SELECT status, started_at FROM experiments WHERE id = :id"),
            {"id": experiment_id}
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "training"
        assert row[1] is not None
    
    def test_cannot_start_already_training_experiment(self, api_client_integration, db_session):
        """Test that starting an already-training experiment fails"""
        from tests.api.integration.conftest import create_test_experiment_via_sql
        
        experiment_id = create_test_experiment_via_sql(
            db_session,
            name="already_training",
            status="training"
        )
        
        response = api_client_integration.post(
            f"/api/v1/experiments/{experiment_id}/start",
            json={"confirm": True}
        )
        
        assert response.status_code == 400
        assert "already training" in response.json()["detail"].lower()
    
    def test_stop_experiment(self, api_client_integration, db_session):
        """Test stopping experiment and verify status and timestamp updates"""
        from tests.api.integration.conftest import create_test_experiment_via_sql
        
        experiment_id = create_test_experiment_via_sql(
            db_session,
            name="stop_test",
            status="training"
        )
        
        # Stop experiment
        response = api_client_integration.post(f"/api/v1/experiments/{experiment_id}/stop")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["completed_at"] is not None
        
        # Verify in database
        result = db_session.execute(
            text("SELECT status, completed_at FROM experiments WHERE id = :id"),
            {"id": experiment_id}
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "completed"
        assert row[1] is not None
    
    def test_cannot_stop_non_training_experiment(self, api_client_integration, db_session):
        """Test that stopping a non-training experiment fails"""
        from tests.api.integration.conftest import create_test_experiment_via_sql
        
        experiment_id = create_test_experiment_via_sql(
            db_session,
            name="not_training",
            status="created"
        )
        
        response = api_client_integration.post(f"/api/v1/experiments/{experiment_id}/stop")
        
        assert response.status_code == 400
        assert "not currently training" in response.json()["detail"].lower()
    
    def test_delete_experiment(self, api_client_integration, db_session):
        """Test deleting experiment"""
        from tests.api.integration.conftest import create_test_experiment_via_sql
        
        experiment_id = create_test_experiment_via_sql(
            db_session,
            name="delete_test"
        )
        
        # Delete experiment
        response = api_client_integration.delete(f"/api/v1/experiments/{experiment_id}")
        
        assert response.status_code == 204
        
        # Verify deleted from database
        result = db_session.execute(
            text("SELECT COUNT(*) FROM experiments WHERE id = :id"),
            {"id": experiment_id}
        )
        count = result.scalar()
        assert count == 0


@pytest.mark.integration
class TestExperimentCascadeBehavior:
    """Test foreign key relationships and cascade behaviors"""
    
    def test_delete_experiment_sets_model_experiment_id_to_null(self, api_client_integration, db_session):
        """Test that deleting experiment sets model.experiment_id to NULL (ON DELETE SET NULL)"""
        from tests.api.integration.conftest import create_test_experiment_via_sql, create_test_model_via_sql
        
        # Create experiment
        experiment_id = create_test_experiment_via_sql(db_session, name="cascade_test")
        
        # Create model with experiment_id FK
        model_id = create_test_model_via_sql(
            db_session,
            experiment_id=experiment_id,
            version="1.0.0"
        )
        
        # Verify model has experiment_id
        result = db_session.execute(
            text("SELECT experiment_id FROM models WHERE id = :id"),
            {"id": model_id}
        )
        row = result.fetchone()
        assert row[0] == experiment_id
        
        # Delete experiment
        response = api_client_integration.delete(f"/api/v1/experiments/{experiment_id}")
        assert response.status_code == 204
        
        # Verify model.experiment_id is NULL
        result = db_session.execute(
            text("SELECT experiment_id FROM models WHERE id = :id"),
            {"id": model_id}
        )
        row = result.fetchone()
        assert row[0] is None, "Model experiment_id should be NULL after experiment deletion"
    
    def test_experiment_foreign_key_in_models(self, api_client_integration, db_session):
        """Test that models can reference experiments via FK"""
        from tests.api.integration.conftest import create_test_experiment_via_sql, create_test_model_via_sql
        
        # Create experiment via API
        response = api_client_integration.post(
            "/api/v1/experiments",
            json={
                "name": "fk_test",
                "features": ["price_bid_EURUSD"],
                "currency_pairs": ["EURUSD"],
                "training_mode": "historical",
                "hyperparameters": {}
            }
        )
        experiment_id = response.json()["id"]
        
        # Create model with FK
        model_id = create_test_model_via_sql(
            db_session,
            experiment_id=experiment_id,
            version="1.0.1"
        )
        
        # Query models by experiment_id
        response = api_client_integration.get(f"/api/v1/models?experiment_id={experiment_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["models"]) >= 1
        assert any(m["id"] == model_id for m in data["models"])
