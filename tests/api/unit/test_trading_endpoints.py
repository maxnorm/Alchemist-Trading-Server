"""
Tests for trading control API endpoints
"""
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.exc import SQLAlchemyError


class TestGetTradingStatus:
    """GET /api/v1/trading/status - Get trading status"""

    def test_get_trading_status(self, api_client):
        """Test getting trading status"""
        from schemas.trading import TradingStatusResponse

        from services import trading_service
        with patch.object(trading_service, "get_trading_status") as mock_get:
            mock_get.return_value = TradingStatusResponse(
                is_active=True,
                active_experiments=[1, 2],
                open_positions=5,
                active_positions=5,
                total_pnl=1000.0,
                total_equity=50000.0,
                total_balance=49000.0,
                kill_switch_active=False,
                circuit_breaker_active=False,
            )

            response = api_client.get("/api/v1/trading/status")

            assert response.status_code == 200
            data = response.json()
            assert data["is_active"] is True
            assert len(data["active_experiments"]) == 2

    def test_get_trading_status_database_error(self, api_client):
        """Test database error (503)"""
        from services import trading_service
        with patch.object(trading_service, "get_trading_status") as mock_get:
            mock_get.side_effect = SQLAlchemyError("Database connection failed")

            response = api_client.get("/api/v1/trading/status")

            assert response.status_code == 503
            data = response.json()
            assert "error" in data or "detail" in data

    def test_get_trading_status_service_error(self, api_client):
        """Test service error (500)"""
        from services import trading_service
        with patch.object(trading_service, "get_trading_status") as mock_get:
            mock_get.side_effect = Exception("Service error")

            response = api_client.get("/api/v1/trading/status")

            assert response.status_code == 500
            data = response.json()
            assert "error" in data or "detail" in data


class TestStartTrading:
    """POST /api/v1/trading/start - Start trading"""

    def test_start_trading(self, api_client):
        """Test starting trading with confirmation"""
        from services import trading_service
        from services.trading_service import check_kill_switch_status

        with patch("routers.trading.check_kill_switch_status") as mock_check:
            mock_check.return_value = False

            response = api_client.post("/api/v1/trading/start?confirm=true")

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "started" in data["message"].lower()

    def test_start_trading_no_confirm(self, api_client):
        """Test 400 error when confirmation is missing"""
        response = api_client.post("/api/v1/trading/start")

        assert response.status_code == 400
        data = response.json()
        assert "error" in data or "detail" in data
        error_msg = data.get("error") or data.get("detail", "")
        assert "confirm" in error_msg.lower()

    def test_start_trading_kill_switch_active(self, api_client):
        """Test 400 error when kill switch is active"""
        from services import trading_service
        from services.trading_service import check_kill_switch_status

        with patch("routers.trading.check_kill_switch_status") as mock_check:
            mock_check.return_value = True

            response = api_client.post("/api/v1/trading/start?confirm=true")

            assert response.status_code == 400
            data = response.json()
            assert "error" in data or "detail" in data
            error_msg = data.get("error") or data.get("detail", "")
            assert "kill switch" in error_msg.lower()


class TestStopTrading:
    """POST /api/v1/trading/stop - Stop trading"""

    def test_stop_trading(self, api_client):
        """Test stopping trading"""
        response = api_client.post("/api/v1/trading/stop")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "stopped" in data["message"].lower()


class TestKillSwitchTrigger:
    """POST /api/trading/kill-switch/trigger"""
    
    def test_kill_switch_trigger(self, api_client):
        """Test kill switch activation"""
        from services import trading_service
        with patch.object(trading_service, 'trigger_kill_switch') as mock_trigger:
            mock_trigger.return_value = True
            
            response = api_client.post("/api/v1/trading/kill-switch/trigger?reason=Test")
            
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "Kill switch activated" in data["message"]
    
    def test_kill_switch_reset(self, api_client):
        """Test kill switch reset"""
        from services import trading_service
        with patch.object(trading_service, 'reset_kill_switch') as mock_reset:
            mock_reset.return_value = True
            
            response = api_client.post("/api/v1/trading/kill-switch/reset")
            
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "reset" in data["message"].lower()


class TestCircuitBreakerStatus:
    """GET /api/trading/circuit-breaker/status"""
    
    def test_get_circuit_breaker_status(self, api_client):
        """Test status retrieval"""
        from schemas.trading import CircuitBreakerStatusResponse
        
        from services import trading_service
        with patch.object(trading_service, 'get_circuit_breaker_status') as mock_get:
            mock_get.return_value = CircuitBreakerStatusResponse(
                is_active=False,
                reason=None,
                loss_threshold=2.5,
                current_loss=1.0
            )
            
            response = api_client.get("/api/v1/trading/circuit-breaker/status")
            
            assert response.status_code == 200
            data = response.json()
            assert data["is_active"] is False
            assert "loss_threshold" in data
    
    def test_reset_circuit_breaker(self, api_client):
        """Test reset functionality"""
        from services import trading_service
        with patch.object(trading_service, 'reset_circuit_breaker') as mock_reset:
            mock_reset.return_value = True
            
            response = api_client.post("/api/v1/trading/circuit-breaker/reset")
            
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "reset" in data["message"].lower()
