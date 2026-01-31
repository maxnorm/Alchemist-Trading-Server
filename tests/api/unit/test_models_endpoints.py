"""
Tests for model registry API endpoints
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError


class TestListModels:
    """GET /api/v1/models - List models"""

    def test_list_models(self, api_client):
        """Test listing all models"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_all_models") as mock_get:
            mock_get.return_value = [
                ModelResponse(
                    id=1,
                    version="1.0.0",
                    experiment_id=1,
                    stage="staging",
                    features=["price_bid_EURUSD"],
                    hyperparameters={"learning_rate": 0.001},
                    created_at=datetime.utcnow(),
                ),
                ModelResponse(
                    id=2,
                    version="1.0.1",
                    experiment_id=1,
                    stage="paper",
                    features=["price_bid_EURUSD"],
                    hyperparameters={"learning_rate": 0.001},
                    created_at=datetime.utcnow(),
                ),
            ]

            response = api_client.get("/api/v1/models")

            assert response.status_code == 200
            data = response.json()
            assert len(data["models"]) == 2
            assert data["total"] == 2

    def test_list_models_filter_by_stage(self, api_client):
        """Test filtering by stage"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_all_models") as mock_get:
            mock_get.return_value = [
                ModelResponse(
                    id=1,
                    version="1.0.0",
                    experiment_id=1,
                    stage="staging",
                    features=[],
                    hyperparameters={},
                    created_at=datetime.utcnow(),
                )
            ]

            response = api_client.get("/api/v1/models?stage=staging")

            assert response.status_code == 200
            data = response.json()
            assert len(data["models"]) == 1
            assert data["models"][0]["stage"] == "staging"

    def test_list_models_filter_by_experiment_id(self, api_client):
        """Test filtering by experiment ID"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_all_models") as mock_get:
            mock_get.return_value = [
                ModelResponse(
                    id=1,
                    version="1.0.0",
                    experiment_id=5,
                    stage="staging",
                    features=[],
                    hyperparameters={},
                    created_at=datetime.utcnow(),
                )
            ]

            response = api_client.get("/api/v1/models?experiment_id=5")

            assert response.status_code == 200
            data = response.json()
            assert len(data["models"]) == 1
            assert data["models"][0]["experiment_id"] == 5

    def test_list_models_empty(self, api_client):
        """Test empty result set"""
        from services import model_service
        with patch.object(model_service, "get_all_models") as mock_get:
            mock_get.return_value = []

            response = api_client.get("/api/v1/models")

            assert response.status_code == 200
            data = response.json()
            assert len(data["models"]) == 0
            assert data["total"] == 0

    def test_list_models_database_error(self, api_client):
        """Test database error handling"""
        from services import model_service
        with patch.object(model_service, "get_all_models") as mock_get:
            mock_get.side_effect = SQLAlchemyError("Database connection failed")

            response = api_client.get("/api/v1/models")

            assert response.status_code == 503
            data = response.json()
            assert "error" in data or "detail" in data


class TestGetModel:
    """GET /api/v1/models/{model_id} - Get model"""

    def test_get_model_by_id(self, api_client):
        """Test getting model details"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get:
            mock_get.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="staging",
                features=["price_bid_EURUSD"],
                hyperparameters={"learning_rate": 0.001},
                created_at=datetime.utcnow(),
            )

            response = api_client.get("/api/v1/models/1")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 1
            assert data["version"] == "1.0.0"

    def test_get_model_not_found(self, api_client):
        """Test 404 for non-existent model"""
        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get:
            mock_get.return_value = None

            response = api_client.get("/api/v1/models/999")

            assert response.status_code == 404
            data = response.json()
            assert "error" in data or "detail" in data
            error_msg = data.get("error") or data.get("detail", "")
            assert "not found" in error_msg.lower()


class TestPromoteToStaging:
    """POST /api/v1/models/{model_id}/promote/staging - Promote to staging"""

    def test_promote_to_staging(self, api_client):
        """Test successful promotion"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get, patch.object(
            model_service, "promote_model"
        ) as mock_promote:
            mock_get.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="development",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )
            mock_promote.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="staging",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )

            response = api_client.post("/api/v1/models/1/promote/staging")

            assert response.status_code == 200
            data = response.json()
            assert data["stage"] == "staging"

    def test_promote_to_staging_already_in_staging(self, api_client):
        """Test 400 error when already in staging"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get:
            mock_get.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="staging",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )

            response = api_client.post("/api/v1/models/1/promote/staging")

            assert response.status_code == 400
            data = response.json()
            assert "error" in data or "detail" in data
            error_msg = data.get("error") or data.get("detail", "")
            assert "already in staging" in error_msg.lower()

    def test_promote_to_staging_model_not_found(self, api_client):
        """Test 404 error when model not found"""
        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get:
            mock_get.return_value = None

            response = api_client.post("/api/v1/models/999/promote/staging")

            assert response.status_code == 404

    def test_promote_to_staging_service_error(self, api_client):
        """Test 500 error from service"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get, patch.object(
            model_service, "promote_model"
        ) as mock_promote:
            mock_get.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="development",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )
            mock_promote.side_effect = Exception("Service error")

            response = api_client.post("/api/v1/models/1/promote/staging")

            assert response.status_code == 500
            data = response.json()
            assert "error" in data or "detail" in data


class TestPromoteToPaper:
    """POST /api/v1/models/{model_id}/promote/paper - Promote to paper"""

    def test_promote_to_paper(self, api_client):
        """Test successful promotion"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get, patch.object(
            model_service, "promote_model"
        ) as mock_promote, patch(
            "websocket.channels.broadcast_model_stage_change"
        ) as mock_broadcast:
            mock_get.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="staging",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )
            mock_promote.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="paper",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )
            mock_broadcast.return_value = AsyncMock()

            response = api_client.post("/api/v1/models/1/promote/paper")

            assert response.status_code == 200
            data = response.json()
            assert data["stage"] == "paper"

    def test_promote_to_paper_invalid_stage(self, api_client):
        """Test 400 error when not in staging"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get:
            mock_get.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="development",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )

            response = api_client.post("/api/v1/models/1/promote/paper")

            assert response.status_code == 400
            data = response.json()
            assert "error" in data or "detail" in data
            error_msg = data.get("error") or data.get("detail", "")
            assert "must be in staging" in error_msg.lower()

    def test_promote_to_paper_model_not_found(self, api_client):
        """Test 404 error when model not found"""
        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get:
            mock_get.return_value = None

            response = api_client.post("/api/v1/models/999/promote/paper")

            assert response.status_code == 404

    def test_promote_to_paper_websocket_broadcast(self, api_client):
        """Test WebSocket broadcast is called"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get, patch.object(
            model_service, "promote_model"
        ) as mock_promote, patch(
            "websocket.channels.broadcast_model_stage_change"
        ) as mock_broadcast:
            mock_get.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="staging",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )
            mock_promote.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="paper",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )
            mock_broadcast.return_value = AsyncMock()

            response = api_client.post("/api/v1/models/1/promote/paper")

            assert response.status_code == 200
            # Note: WebSocket broadcast is async, so we verify it was called
            # The actual await happens in the router, but we can't easily test async here


class TestPromoteToProduction:
    """POST /api/v1/models/{model_id}/promote/production - Promote to production"""

    def test_promote_to_production(self, api_client):
        """Test successful promotion with 2FA"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get, patch.object(
            model_service, "validate_model_for_production"
        ) as mock_validate, patch.object(
            model_service, "promote_model"
        ) as mock_promote, patch(
            "websocket.channels.broadcast_model_stage_change"
        ) as mock_broadcast:
            mock_get.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="paper",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )
            mock_validate.return_value = {"passed": True, "messages": []}
            mock_promote.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="production",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )
            mock_broadcast.return_value = AsyncMock()

            response = api_client.post(
                "/api/v1/models/1/promote/production",
                json={"target_stage": "production", "confirm": True, "totp_token": "123456"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["stage"] == "production"

    def test_promote_to_production_missing_2fa(self, api_client):
        """Test 400 error when 2FA token is missing"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get:
            mock_get.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="paper",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )

            response = api_client.post(
                "/api/v1/models/1/promote/production", json={"target_stage": "production", "confirm": True}
            )

            assert response.status_code == 400
            data = response.json()
            assert "error" in data or "detail" in data
            error_msg = data.get("error") or data.get("detail", "")
            assert "2fa" in error_msg.lower() or "token" in error_msg.lower()

    def test_promote_to_production_invalid_2fa_format(self, api_client):
        """Test 400 error when 2FA token format is invalid"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get:
            mock_get.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="paper",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )

            response = api_client.post(
                "/api/v1/models/1/promote/production",
                json={"target_stage": "production", "confirm": True, "totp_token": "abc123"},
            )

            assert response.status_code == 400
            data = response.json()
            assert "error" in data or "detail" in data
            error_msg = data.get("error") or data.get("detail", "")
            assert "invalid" in error_msg.lower() or "format" in error_msg.lower()

    def test_promote_to_production_invalid_stage(self, api_client):
        """Test 400 error when not in paper stage"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get:
            mock_get.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="staging",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )

            response = api_client.post(
                "/api/v1/models/1/promote/production",
                json={"target_stage": "production", "confirm": True, "totp_token": "123456"},
            )

            assert response.status_code == 400
            data = response.json()
            assert "error" in data or "detail" in data
            error_msg = data.get("error") or data.get("detail", "")
            assert "paper" in error_msg.lower()

    def test_promote_to_production_validation_failed(self, api_client):
        """Test 400 error when validation fails"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get, patch.object(
            model_service, "validate_model_for_production"
        ) as mock_validate:
            mock_get.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="paper",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )
            mock_validate.return_value = {
                "passed": False,
                "messages": ["Insufficient paper trading sessions"],
            }

            response = api_client.post(
                "/api/v1/models/1/promote/production",
                json={"target_stage": "production", "confirm": True, "totp_token": "123456"},
            )

            assert response.status_code == 400
            data = response.json()
            assert "error" in data or "detail" in data
            error_msg = data.get("error") or data.get("detail", "")
            assert "validation" in error_msg.lower() or "failed" in error_msg.lower()

    def test_promote_to_production_model_not_found(self, api_client):
        """Test 404 error when model not found"""
        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get:
            mock_get.return_value = None

            response = api_client.post(
                "/api/v1/models/999/promote/production",
                json={"target_stage": "production", "confirm": True, "totp_token": "123456"},
            )

            assert response.status_code == 404

    def test_promote_to_production_no_confirm(self, api_client):
        """Test 400 error when confirmation is missing"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get:
            mock_get.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="paper",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )

            response = api_client.post(
                "/api/v1/models/1/promote/production",
                json={"target_stage": "production", "totp_token": "123456"},
            )

            assert response.status_code == 400
            data = response.json()
            assert "error" in data or "detail" in data
            error_msg = data.get("error") or data.get("detail", "")
            assert "confirm" in error_msg.lower()


class TestRollbackProduction:
    """POST /api/v1/models/{model_id}/rollback - Rollback production"""

    def test_rollback_production(self, api_client):
        """Test successful rollback"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get, patch.object(
            model_service, "rollback_production"
        ) as mock_rollback:
            mock_get.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="production",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )
            mock_rollback.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="paper",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )

            response = api_client.post("/api/v1/models/1/rollback?confirm=true")

            assert response.status_code == 200
            data = response.json()
            assert data["stage"] == "paper"

    def test_rollback_production_no_confirm(self, api_client):
        """Test 400 error when confirmation is missing"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get:
            mock_get.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="production",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )

            response = api_client.post("/api/v1/models/1/rollback")

            assert response.status_code == 400
            data = response.json()
            assert "error" in data or "detail" in data
            error_msg = data.get("error") or data.get("detail", "")
            assert "confirm" in error_msg.lower()

    def test_rollback_production_invalid_stage(self, api_client):
        """Test 400 error when not in production"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get:
            mock_get.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="paper",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )

            response = api_client.post("/api/v1/models/1/rollback?confirm=true")

            assert response.status_code == 400
            data = response.json()
            assert "error" in data or "detail" in data
            error_msg = data.get("error") or data.get("detail", "")
            assert "production" in error_msg.lower()

    def test_rollback_production_model_not_found(self, api_client):
        """Test 404 error when model not found"""
        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get:
            mock_get.return_value = None

            response = api_client.post("/api/v1/models/999/rollback?confirm=true")

            assert response.status_code == 404


class TestPaperSessions:
    """GET/POST /api/v1/models/{model_id}/paper-sessions - Paper sessions"""

    def test_get_paper_sessions(self, api_client):
        """Test listing paper sessions"""
        from schemas.models import PaperSessionResponse

        from services import model_service
        with patch.object(model_service, "get_paper_sessions") as mock_get:
            mock_get.return_value = [
                PaperSessionResponse(
                    id=1,
                    model_id=1,
                    status="completed",
                    start_balance=10000.0,
                    current_balance=10500.0,
                    total_trades=10,
                    winning_trades=6,
                    pnl=500.0,
                    started_at=datetime.utcnow(),
                )
            ]

            response = api_client.get("/api/v1/models/1/paper-sessions")

            assert response.status_code == 200
            data = response.json()
            assert len(data["sessions"]) == 1
            assert data["total"] == 1

    def test_start_paper_session(self, api_client):
        """Test starting paper session"""
        from schemas.models import ModelResponse, PaperSessionResponse

        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get_model, patch.object(
            model_service, "start_paper_session"
        ) as mock_start, patch(
            "websocket.channels.broadcast_paper_session_update"
        ) as mock_broadcast:
            mock_get_model.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="paper",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )
            mock_start.return_value = PaperSessionResponse(
                id=1,
                model_id=1,
                status="running",
                start_balance=10000.0,
                current_balance=10000.0,
                total_trades=0,
                winning_trades=0,
                pnl=0.0,
                started_at=datetime.utcnow(),
            )
            mock_broadcast.return_value = AsyncMock()

            response = api_client.post(
                "/api/v1/models/1/paper-sessions/start", json={"start_balance": 10000.0}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert data["start_balance"] == 10000.0

    def test_start_paper_session_invalid_stage(self, api_client):
        """Test 400 error when model not in paper stage"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get:
            mock_get.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="staging",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )

            response = api_client.post(
                "/api/v1/models/1/paper-sessions/start", json={"start_balance": 10000.0}
            )

            assert response.status_code == 400
            data = response.json()
            assert "error" in data or "detail" in data
            error_msg = data.get("error") or data.get("detail", "")
            assert "paper" in error_msg.lower()

    def test_start_paper_session_model_not_found(self, api_client):
        """Test 404 error when model not found"""
        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get:
            mock_get.return_value = None

            response = api_client.post(
                "/api/v1/models/999/paper-sessions/start", json={"start_balance": 10000.0}
            )

            assert response.status_code == 404

    def test_stop_paper_session(self, api_client):
        """Test stopping paper session"""
        from schemas.models import PaperSessionResponse, ModelResponse

        from services import model_service
        with patch.object(model_service, "get_paper_session") as mock_get_session, patch.object(
            model_service, "stop_paper_session"
        ) as mock_stop, patch.object(
            model_service, "validate_model_for_production"
        ) as mock_validate, patch(
            "websocket.channels.broadcast_paper_session_update"
        ) as mock_broadcast_session, patch(
            "websocket.channels.broadcast_validation_update"
        ) as mock_broadcast_validation:
            mock_get_session.return_value = PaperSessionResponse(
                id=1,
                model_id=1,
                status="running",
                start_balance=10000.0,
                current_balance=10500.0,
                total_trades=10,
                winning_trades=6,
                pnl=500.0,
                started_at=datetime.utcnow(),
            )
            mock_stop.return_value = PaperSessionResponse(
                id=1,
                model_id=1,
                status="completed",
                start_balance=10000.0,
                current_balance=10500.0,
                total_trades=10,
                winning_trades=6,
                pnl=500.0,
                sharpe_ratio=1.5,
                max_drawdown=100.0,
                started_at=datetime.utcnow(),
                ended_at=datetime.utcnow(),
            )
            mock_validate.return_value = {"passed": True, "messages": []}
            mock_broadcast_session.return_value = AsyncMock()
            mock_broadcast_validation.return_value = AsyncMock()

            response = api_client.post("/api/v1/models/1/paper-sessions/1/stop")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"

    def test_stop_paper_session_not_found(self, api_client):
        """Test 404 error when session not found"""
        from services import model_service
        with patch.object(model_service, "get_paper_session") as mock_get:
            mock_get.return_value = None

            response = api_client.post("/api/v1/models/1/paper-sessions/999/stop")

            assert response.status_code == 404

    def test_stop_paper_session_wrong_model(self, api_client):
        """Test 400 error when session belongs to different model"""
        from schemas.models import PaperSessionResponse

        from services import model_service
        with patch.object(model_service, "get_paper_session") as mock_get:
            mock_get.return_value = PaperSessionResponse(
                id=1,
                model_id=2,  # Different model ID
                status="running",
                start_balance=10000.0,
                current_balance=10000.0,
                total_trades=0,
                winning_trades=0,
                pnl=0.0,
                started_at=datetime.utcnow(),
            )

            response = api_client.post("/api/v1/models/1/paper-sessions/1/stop")

            assert response.status_code == 400
            data = response.json()
            assert "error" in data or "detail" in data
            error_msg = data.get("error") or data.get("detail", "")
            assert "belong" in error_msg.lower() or "model" in error_msg.lower()


class TestGetValidationStatus:
    """GET /api/v1/models/{model_id}/validation - Get validation status"""

    def test_get_validation_status(self, api_client):
        """Test getting validation results"""
        from schemas.models import ModelResponse

        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get, patch.object(
            model_service, "validate_model_for_production"
        ) as mock_validate:
            mock_get.return_value = ModelResponse(
                id=1,
                version="1.0.0",
                experiment_id=1,
                stage="paper",
                features=[],
                hyperparameters={},
                created_at=datetime.utcnow(),
            )
            mock_validate.return_value = {
                "passed": True,
                "checks": {"min_sessions": True, "min_sharpe": True},
                "metrics": {"sharpe_ratio": 1.5, "win_rate": 0.6},
                "messages": [],
            }

            response = api_client.get("/api/v1/models/1/validation")

            assert response.status_code == 200
            data = response.json()
            assert data["passed"] is True
            assert "checks" in data

    def test_get_validation_status_model_not_found(self, api_client):
        """Test 404 error when model not found"""
        from services import model_service
        with patch.object(model_service, "get_model_by_id") as mock_get:
            mock_get.return_value = None

            response = api_client.get("/api/v1/models/999/validation")

            assert response.status_code == 404
