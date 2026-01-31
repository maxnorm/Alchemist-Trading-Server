"""
Integration tests for model-to-account assignments with real database
"""
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import text


@pytest.mark.integration
class TestModelAssignments:
    """Test model-to-account assignment operations"""
    
    def test_assign_model_to_account(self, api_client_integration, db_session):
        """Test assigning model to account and verify assignment record"""
        from tests.api.integration.conftest import (
            create_test_account_via_sql,
            create_test_model_via_sql
        )
        
        # Create account via API
        response = api_client_integration.post(
            "/api/v1/accounts/mt5/register",
            json={
                "account_login": 12345678,
                "account_type": "demo",
                "broker_name": "Test Broker",
                "broker_server": "Test-Server",
                "account_currency": "USD",
                "account_leverage": 100,
                "account_name": "Test Account"
            }
        )
        assert response.status_code == 201
        account_id = response.json()["id"]
        
        # Create model in production stage
        model_id = create_test_model_via_sql(
            db_session,
            version="1.0.0",
            stage="production"
        )
        
        # Assign model to account
        response = api_client_integration.post(
            f"/api/v1/accounts/mt5/{account_id}/assign-model",
            json={
                "model_id": model_id,
                "trading_mode": "live",
                "notes": "Test assignment"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["account_id"] == account_id
        assert data["model_id"] == model_id
        assert data["trading_mode"] == "live"
        assert data["is_active"] is True
        assert data["assigned_at"] is not None
        
        # Verify in database
        result = db_session.execute(
            text("""
                SELECT account_id, model_id, trading_mode, is_active, assigned_at
                FROM account_model_assignments
                WHERE account_id = :account_id AND is_active = TRUE
            """),
            {"account_id": account_id}
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == account_id
        assert row[1] == model_id
        assert row[2] == "live"
        assert row[3] is True
        assert row[4] is not None
    
    def test_replace_assignment_unique_constraint(self, api_client_integration, db_session):
        """Test that assigning second model deactivates previous assignment"""
        from tests.api.integration.conftest import (
            create_test_account_via_sql,
            create_test_model_via_sql
        )
        
        # Create account
        account_id = create_test_account_via_sql(db_session, account_login=11111111)
        
        # Create two models
        model1_id = create_test_model_via_sql(
            db_session,
            version="1.0.1",
            stage="production"
        )
        model2_id = create_test_model_via_sql(
            db_session,
            version="1.0.2",
            stage="production"
        )
        
        # Assign model1
        response = api_client_integration.post(
            f"/api/v1/accounts/mt5/{account_id}/assign-model",
            json={"model_id": model1_id, "trading_mode": "live"}
        )
        assert response.status_code == 200
        
        # Assign model2 (should deactivate model1)
        response = api_client_integration.post(
            f"/api/v1/accounts/mt5/{account_id}/assign-model",
            json={"model_id": model2_id, "trading_mode": "live"}
        )
        assert response.status_code == 200
        
        # Verify model1 assignment is deactivated
        result = db_session.execute(
            text("""
                SELECT is_active, deactivated_at
                FROM account_model_assignments
                WHERE account_id = :account_id AND model_id = :model_id
            """),
            {"account_id": account_id, "model_id": model1_id}
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] is False, "Previous assignment should be deactivated"
        assert row[1] is not None, "Deactivated timestamp should be set"
        
        # Verify model2 assignment is active
        result = db_session.execute(
            text("""
                SELECT is_active
                FROM account_model_assignments
                WHERE account_id = :account_id AND model_id = :model_id
            """),
            {"account_id": account_id, "model_id": model2_id}
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] is True, "New assignment should be active"
    
    def test_get_current_assignment(self, api_client_integration, db_session):
        """Test getting current model assignment for account"""
        from tests.api.integration.conftest import (
            create_test_account_via_sql,
            create_test_model_via_sql
        )
        
        # Create account and model
        account_id = create_test_account_via_sql(db_session, account_login=22222222)
        model_id = create_test_model_via_sql(
            db_session,
            version="1.0.3",
            stage="production"
        )
        
        # Assign model
        response = api_client_integration.post(
            f"/api/v1/accounts/mt5/{account_id}/assign-model",
            json={"model_id": model_id, "trading_mode": "live"}
        )
        assert response.status_code == 200
        
        # Get current assignment
        response = api_client_integration.get(f"/api/v1/accounts/mt5/{account_id}/assignment")
        
        assert response.status_code == 200
        data = response.json()
        assert data["account_id"] == account_id
        assert data["model_id"] == model_id
        assert data["is_active"] is True
    
    def test_unassign_model(self, api_client_integration, db_session):
        """Test unassigning model from account"""
        from tests.api.integration.conftest import (
            create_test_account_via_sql,
            create_test_model_via_sql
        )
        
        # Create account and model
        account_id = create_test_account_via_sql(db_session, account_login=33333333)
        model_id = create_test_model_via_sql(
            db_session,
            version="1.0.4",
            stage="production"
        )
        
        # Assign model
        response = api_client_integration.post(
            f"/api/v1/accounts/mt5/{account_id}/assign-model",
            json={"model_id": model_id, "trading_mode": "live"}
        )
        assert response.status_code == 200
        
        # Unassign model
        response = api_client_integration.delete(
            f"/api/v1/accounts/mt5/{account_id}/assignment?confirm=true"
        )
        assert response.status_code == 204
        
        # Verify assignment is deactivated
        result = db_session.execute(
            text("""
                SELECT is_active, deactivated_at
                FROM account_model_assignments
                WHERE account_id = :account_id AND model_id = :model_id
            """),
            {"account_id": account_id, "model_id": model_id}
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] is False
        assert row[1] is not None


@pytest.mark.integration
class TestAssignmentConstraints:
    """Test assignment validation and constraints"""
    
    def test_cannot_assign_non_production_model_to_live_account(self, api_client_integration, db_session):
        """Test that assigning non-production model to live account fails"""
        from tests.api.integration.conftest import (
            create_test_account_via_sql,
            create_test_model_via_sql
        )
        
        # Create live account
        account_id = create_test_account_via_sql(
            db_session,
            account_login=44444444,
            account_type="live"
        )
        
        # Create model in staging (not production)
        model_id = create_test_model_via_sql(
            db_session,
            version="1.0.5",
            stage="staging"
        )
        
        # Try to assign (should fail)
        response = api_client_integration.post(
            f"/api/v1/accounts/mt5/{account_id}/assign-model",
            json={"model_id": model_id, "trading_mode": "live"}
        )
        
        assert response.status_code == 500  # Service raises ValueError which becomes 500
        # The error message should indicate the model must be in production
    
    def test_cannot_assign_to_nonexistent_account(self, api_client_integration, db_session):
        """Test that assigning to non-existent account returns 404"""
        from tests.api.integration.conftest import create_test_model_via_sql
        
        model_id = create_test_model_via_sql(
            db_session,
            version="1.0.6",
            stage="production"
        )
        
        # Try to assign to non-existent account
        response = api_client_integration.post(
            "/api/v1/accounts/mt5/99999/assign-model",
            json={"model_id": model_id, "trading_mode": "live"}
        )
        
        assert response.status_code == 404
    
    def test_cannot_assign_nonexistent_model(self, api_client_integration, db_session):
        """Test that assigning non-existent model returns 404"""
        from tests.api.integration.conftest import create_test_account_via_sql
        
        account_id = create_test_account_via_sql(db_session, account_login=55555555)
        
        # Try to assign non-existent model
        response = api_client_integration.post(
            f"/api/v1/accounts/mt5/{account_id}/assign-model",
            json={"model_id": 99999, "trading_mode": "live"}
        )
        
        assert response.status_code == 404


@pytest.mark.integration
class TestAssignmentCascadeBehavior:
    """Test cascade deletion behaviors for assignments"""
    
    def test_delete_account_cascades_to_assignments(self, api_client_integration, db_session):
        """Test that deleting account cascades to assignments (ON DELETE CASCADE)"""
        from tests.api.integration.conftest import (
            create_test_account_via_sql,
            create_test_model_via_sql
        )
        
        # Create account and model
        account_id = create_test_account_via_sql(db_session, account_login=66666666)
        model_id = create_test_model_via_sql(
            db_session,
            version="1.0.7",
            stage="production"
        )
        
        # Assign model
        response = api_client_integration.post(
            f"/api/v1/accounts/mt5/{account_id}/assign-model",
            json={"model_id": model_id, "trading_mode": "live"}
        )
        assert response.status_code == 200
        
        # Verify assignment exists
        result = db_session.execute(
            text("SELECT COUNT(*) FROM account_model_assignments WHERE account_id = :id"),
            {"id": account_id}
        )
        assert result.scalar() == 1
        
        # Delete account (soft delete via API)
        response = api_client_integration.delete(
            f"/api/v1/accounts/mt5/{account_id}?confirm=true"
        )
        assert response.status_code == 204
        
        # Verify assignment is deleted (hard delete, CASCADE)
        # Note: The API does soft delete (sets is_active=False), but if we hard delete,
        # assignments should cascade. Let's test hard delete directly.
        db_session.execute(
            text("DELETE FROM mt5_accounts WHERE id = :id"),
            {"id": account_id}
        )
        db_session.commit()
        
        # Verify assignment is deleted
        result = db_session.execute(
            text("SELECT COUNT(*) FROM account_model_assignments WHERE account_id = :id"),
            {"id": account_id}
        )
        assert result.scalar() == 0, "Assignment should be deleted when account is deleted"
    
    def test_delete_model_cascades_to_assignments(self, api_client_integration, db_session):
        """Test that deleting model cascades to assignments (ON DELETE CASCADE)"""
        from tests.api.integration.conftest import (
            create_test_account_via_sql,
            create_test_model_via_sql
        )
        
        # Create account and model
        account_id = create_test_account_via_sql(db_session, account_login=77777777)
        model_id = create_test_model_via_sql(
            db_session,
            version="1.0.8",
            stage="production"
        )
        
        # Assign model
        response = api_client_integration.post(
            f"/api/v1/accounts/mt5/{account_id}/assign-model",
            json={"model_id": model_id, "trading_mode": "live"}
        )
        assert response.status_code == 200
        
        # Verify assignment exists
        result = db_session.execute(
            text("SELECT COUNT(*) FROM account_model_assignments WHERE model_id = :id"),
            {"id": model_id}
        )
        assert result.scalar() == 1
        
        # Delete model (models are deleted by trading server, not API)
        db_session.execute(
            text("DELETE FROM models WHERE id = :id"),
            {"id": model_id}
        )
        db_session.commit()
        
        # Verify assignment is deleted (CASCADE)
        result = db_session.execute(
            text("SELECT COUNT(*) FROM account_model_assignments WHERE model_id = :id"),
            {"id": model_id}
        )
        assert result.scalar() == 0, "Assignment should be deleted when model is deleted"
