"""
Tests for trading control API endpoints
"""
import pytest
from unittest.mock import Mock, patch


class TestKillSwitchTrigger:
    """POST /api/trading/kill-switch/trigger"""
    
    def test_kill_switch_trigger(self, api_client):
        """Test kill switch activation"""
        with patch('services.trading_service.trigger_kill_switch') as mock_trigger:
            mock_trigger.return_value = {
                "success": True,
                "message": "Kill switch activated",
                "timestamp": "2024-01-01T00:00:00"
            }
            
            response = api_client.post("/api/v1/trading/kill-switch/trigger")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "Kill switch activated" in data["message"]
    
    def test_kill_switch_reset(self, api_client):
        """Test kill switch reset"""
        with patch('services.trading_service.reset_kill_switch') as mock_reset:
            mock_reset.return_value = {
                "success": True,
                "message": "Kill switch reset"
            }
            
            response = api_client.post("/api/v1/trading/kill-switch/reset")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


class TestCircuitBreakerStatus:
    """GET /api/trading/circuit-breaker/status"""
    
    def test_get_circuit_breaker_status(self, api_client):
        """Test status retrieval"""
        with patch('services.trading_service.get_circuit_breaker_status') as mock_get:
            mock_get.return_value = {
                "state": "closed",
                "loss_per_hour_pct": 2.5,
                "loss_per_day_pct": 4.0,
                "consecutive_losses": 2,
                "last_reset": "2024-01-01T00:00:00"
            }
            
            response = api_client.get("/api/v1/trading/circuit-breaker/status")
            
            assert response.status_code == 200
            data = response.json()
            assert data["state"] == "closed"
            assert "loss_per_hour_pct" in data
    
    def test_reset_circuit_breaker(self, api_client):
        """Test reset functionality"""
        with patch('services.trading_service.reset_circuit_breaker') as mock_reset:
            mock_reset.return_value = {
                "success": True,
                "message": "Circuit breaker reset"
            }
            
            response = api_client.post("/api/v1/trading/circuit-breaker/reset")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
