"""
Integration tests for model registry API endpoints with real database
"""
import pytest
import json
from sqlalchemy.orm import Session
from sqlalchemy import text


@pytest.mark.integration
class TestModelPromotionWorkflow:
    """Test model promotion through stages"""
    
    def test_promote_to_staging(self, api_client_integration, db_session):
        """Test promoting model to staging stage"""
        from tests.api.integration.conftest import create_test_model_via_sql
        
        # Create model (default stage is 'staging' but let's start from 'training')
        model_id = create_test_model_via_sql(
            db_session,
            version="1.0.0",
            stage="training"
        )
        
        # Promote to staging
        response = api_client_integration.post(f"/api/v1/models/{model_id}/promote/staging")
        
        assert response.status_code == 200
        data = response.json()
        assert data["stage"] == "staging"
        assert data["promoted_at"] is not None
        
        # Verify in database
        result = db_session.execute(
            text("SELECT stage, promoted_at FROM models WHERE id = :id"),
            {"id": model_id}
        )
        row = result.fetchone()
        assert row[0] == "staging"
        assert row[1] is not None
    
    def test_promote_to_paper(self, api_client_integration, db_session):
        """Test promoting model from staging to paper"""
        from tests.api.integration.conftest import create_test_model_via_sql
        
        model_id = create_test_model_via_sql(
            db_session,
            version="1.0.1",
            stage="staging"
        )
        
        # Promote to paper
        response = api_client_integration.post(f"/api/v1/models/{model_id}/promote/paper")
        
        assert response.status_code == 200
        data = response.json()
        assert data["stage"] == "paper"
        
        # Verify in database
        result = db_session.execute(
            text("SELECT stage FROM models WHERE id = :id"),
            {"id": model_id}
        )
        row = result.fetchone()
        assert row[0] == "paper"
    
    def test_cannot_promote_from_wrong_stage(self, api_client_integration, db_session):
        """Test that promoting from wrong stage fails"""
        from tests.api.integration.conftest import create_test_model_via_sql
        
        # Try to promote to paper from training (should be from staging)
        model_id = create_test_model_via_sql(
            db_session,
            version="1.0.2",
            stage="training"
        )
        
        response = api_client_integration.post(f"/api/v1/models/{model_id}/promote/paper")
        
        assert response.status_code == 400
        assert "staging" in response.json()["detail"].lower()
    
    def test_promote_to_production_with_validation(self, api_client_integration, db_session):
        """Test promoting model to production with validation checks"""
        from tests.api.integration.conftest import create_test_model_via_sql, create_test_paper_session_via_sql
        
        # Create model in paper stage
        model_id = create_test_model_via_sql(
            db_session,
            version="1.0.3",
            stage="paper"
        )
        
        # Create paper session with good results
        session_id = create_test_paper_session_via_sql(
            db_session,
            model_id=model_id,
            start_balance=10000.0,
            status="completed"
        )
        
        # Update session with good metrics
        db_session.execute(
            text("""
                UPDATE paper_trading_sessions
                SET total_trades = 150,
                    winning_trades = 80,
                    pnl = 500.0,
                    sharpe_ratio = 1.5,
                    max_drawdown = 0.05,
                    ended_at = NOW()
                WHERE id = :id
            """),
            {"id": session_id}
        )
        db_session.commit()
        
        # Update model with paper trading results
        results = {
            "total_trades": 150,
            "winning_trades": 80,
            "win_rate": 80 / 150,
            "pnl": 500.0,
            "sharpe_ratio": 1.5,
            "max_drawdown": 0.05
        }
        db_session.execute(
            text("UPDATE models SET paper_trading_results = :results WHERE id = :id"),
            {"results": json.dumps(results), "id": model_id}
        )
        db_session.commit()
        
        # Promote to production with 2FA token
        response = api_client_integration.post(
            f"/api/v1/models/{model_id}/promote/production",
            json={
                "target_stage": "production",
                "confirm": True,
                "totp_token": "123456"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["stage"] == "production"
        
        # Verify in database
        result = db_session.execute(
            text("SELECT stage FROM models WHERE id = :id"),
            {"id": model_id}
        )
        row = result.fetchone()
        assert row[0] == "production"
    
    def test_promote_to_production_archives_previous_production(self, api_client_integration, db_session):
        """Test that promoting to production archives previous production models"""
        from tests.api.integration.conftest import create_test_model_via_sql
        
        # Create first production model
        model1_id = create_test_model_via_sql(
            db_session,
            version="1.0.4",
            stage="production"
        )
        
        # Create second model in paper with good results
        model2_id = create_test_model_via_sql(
            db_session,
            version="1.0.5",
            stage="paper"
        )
        
        # Add paper trading results
        results = {
            "total_trades": 200,
            "winning_trades": 110,
            "win_rate": 0.55,
            "pnl": 1000.0,
            "sharpe_ratio": 1.8,
            "max_drawdown": 0.08
        }
        db_session.execute(
            text("UPDATE models SET paper_trading_results = :results WHERE id = :id"),
            {"results": json.dumps(results), "id": model2_id}
        )
        db_session.commit()
        
        # Promote model2 to production
        response = api_client_integration.post(
            f"/api/v1/models/{model2_id}/promote/production",
            json={
                "target_stage": "production",
                "confirm": True,
                "totp_token": "123456"
            }
        )
        
        assert response.status_code == 200
        
        # Verify model1 is archived
        result = db_session.execute(
            text("SELECT stage FROM models WHERE id = :id"),
            {"id": model1_id}
        )
        row = result.fetchone()
        assert row[0] == "archived"
        
        # Verify model2 is production
        result = db_session.execute(
            text("SELECT stage FROM models WHERE id = :id"),
            {"id": model2_id}
        )
        row = result.fetchone()
        assert row[0] == "production"
    
    def test_model_experiment_relationship(self, api_client_integration, db_session):
        """Test model-experiment foreign key relationship"""
        from tests.api.integration.conftest import create_test_experiment_via_sql, create_test_model_via_sql
        
        # Create experiment via API
        response = api_client_integration.post(
            "/api/v1/experiments",
            json={
                "name": "model_fk_test",
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
            version="1.0.6"
        )
        
        # Query models by experiment_id
        response = api_client_integration.get(f"/api/v1/models?experiment_id={experiment_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["models"]) >= 1
        assert any(m["id"] == model_id and m["experiment_id"] == experiment_id for m in data["models"])


@pytest.mark.integration
class TestPaperSessionLifecycle:
    """Test paper trading session management"""
    
    def test_start_paper_session(self, api_client_integration, db_session):
        """Test starting paper trading session"""
        from tests.api.integration.conftest import create_test_model_via_sql
        
        model_id = create_test_model_via_sql(
            db_session,
            version="1.0.7",
            stage="paper"
        )
        
        # Start paper session
        response = api_client_integration.post(
            f"/api/v1/models/{model_id}/paper-sessions/start",
            json={"start_balance": 10000.0}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["model_id"] == model_id
        assert data["status"] == "running"
        assert data["start_balance"] == 10000.0
        assert data["current_balance"] == 10000.0
        assert data["started_at"] is not None
        
        # Verify in database
        result = db_session.execute(
            text("""
                SELECT status, start_balance, current_balance, started_at
                FROM paper_trading_sessions
                WHERE id = :id
            """),
            {"id": data["id"]}
        )
        row = result.fetchone()
        assert row[0] == "running"
        assert float(row[1]) == 10000.0
        assert float(row[2]) == 10000.0
        assert row[3] is not None
    
    def test_cannot_start_session_for_non_paper_model(self, api_client_integration, db_session):
        """Test that starting session for non-paper model fails"""
        from tests.api.integration.conftest import create_test_model_via_sql
        
        model_id = create_test_model_via_sql(
            db_session,
            version="1.0.8",
            stage="staging"
        )
        
        response = api_client_integration.post(
            f"/api/v1/models/{model_id}/paper-sessions/start",
            json={"start_balance": 10000.0}
        )
        
        assert response.status_code == 400
        assert "paper stage" in response.json()["detail"].lower()
    
    def test_stop_paper_session(self, api_client_integration, db_session):
        """Test stopping paper trading session and storing results"""
        from tests.api.integration.conftest import create_test_model_via_sql, create_test_paper_session_via_sql
        
        model_id = create_test_model_via_sql(
            db_session,
            version="1.0.9",
            stage="paper"
        )
        
        session_id = create_test_paper_session_via_sql(
            db_session,
            model_id=model_id,
            start_balance=10000.0,
            status="running"
        )
        
        # Update session with some metrics
        db_session.execute(
            text("""
                UPDATE paper_trading_sessions
                SET total_trades = 50,
                    winning_trades = 30,
                    pnl = 200.0,
                    current_balance = 10200.0
                WHERE id = :id
            """),
            {"id": session_id}
        )
        db_session.commit()
        
        # Stop session
        response = api_client_integration.post(
            f"/api/v1/models/{model_id}/paper-sessions/{session_id}/stop"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["ended_at"] is not None
        
        # Verify results stored in model
        result = db_session.execute(
            text("SELECT paper_trading_results FROM models WHERE id = :id"),
            {"id": model_id}
        )
        row = result.fetchone()
        assert row[0] is not None
        results = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        assert "total_trades" in results
        assert "win_rate" in results
    
    def test_cascade_delete_paper_sessions(self, api_client_integration, db_session):
        """Test that deleting model cascades to paper sessions (ON DELETE CASCADE)"""
        from tests.api.integration.conftest import create_test_model_via_sql, create_test_paper_session_via_sql
        
        model_id = create_test_model_via_sql(
            db_session,
            version="1.0.10",
            stage="paper"
        )
        
        session_id = create_test_paper_session_via_sql(
            db_session,
            model_id=model_id,
            status="running"
        )
        
        # Verify session exists
        result = db_session.execute(
            text("SELECT COUNT(*) FROM paper_trading_sessions WHERE id = :id"),
            {"id": session_id}
        )
        assert result.scalar() == 1
        
        # Delete model directly (models are deleted by trading server, not API)
        db_session.execute(
            text("DELETE FROM models WHERE id = :id"),
            {"id": model_id}
        )
        db_session.commit()
        
        # Verify session is deleted (CASCADE)
        result = db_session.execute(
            text("SELECT COUNT(*) FROM paper_trading_sessions WHERE id = :id"),
            {"id": session_id}
        )
        assert result.scalar() == 0, "Paper session should be deleted when model is deleted"
    
    def test_list_paper_sessions(self, api_client_integration, db_session):
        """Test listing paper sessions for a model"""
        from tests.api.integration.conftest import create_test_model_via_sql, create_test_paper_session_via_sql
        
        model_id = create_test_model_via_sql(
            db_session,
            version="1.0.11",
            stage="paper"
        )
        
        # Create multiple sessions
        session1_id = create_test_paper_session_via_sql(db_session, model_id=model_id, status="completed")
        session2_id = create_test_paper_session_via_sql(db_session, model_id=model_id, status="running")
        
        # List sessions
        response = api_client_integration.get(f"/api/v1/models/{model_id}/paper-sessions")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) >= 2
        assert data["total"] >= 2
        assert any(s["id"] == session1_id for s in data["sessions"])
        assert any(s["id"] == session2_id for s in data["sessions"])
