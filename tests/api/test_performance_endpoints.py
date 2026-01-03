"""
Tests for performance tracking API endpoints
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta


class TestGetPortfolioMetrics:
    """GET /api/performance/portfolio"""
    
    def test_get_portfolio_metrics(self, api_client):
        """Test aggregate metrics calculation"""
        with patch('services.performance_service.get_portfolio_metrics') as mock_get:
            mock_get.return_value = {
                "total_pnl": 1000.0,
                "win_rate": 55.5,
                "sharpe_ratio": 1.8,
                "max_drawdown_pct": 5.2,
                "total_trades": 100,
                "winning_trades": 55,
                "losing_trades": 45
            }
            
            response = api_client.get("/api/v1/performance/portfolio")
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_pnl"] == 1000.0
            assert data["win_rate"] == 55.5
    
    def test_get_portfolio_metrics_time_period(self, api_client):
        """Test time period filtering"""
        with patch('services.performance_service.get_portfolio_metrics') as mock_get:
            mock_get.return_value = {
                "total_pnl": 500.0,
                "win_rate": 60.0
            }
            
            response = api_client.get("/api/v1/performance/portfolio?period=daily")
            
            assert response.status_code == 200
            data = response.json()
            assert "total_pnl" in data


class TestGetExperimentTrades:
    """GET /api/performance/experiments/{id}/trades"""
    
    def test_get_experiment_trades(self, api_client):
        """Test trade history retrieval"""
        with patch('services.performance_service.get_experiment_trades') as mock_get:
            mock_get.return_value = [
                {
                    "id": 1,
                    "symbol": "EURUSD",
                    "action": "BUY",
                    "entry_price": 1.1000,
                    "exit_price": 1.1050,
                    "pnl": 50.0,
                    "status": "closed",
                    "opened_at": datetime.utcnow().isoformat()
                },
                {
                    "id": 2,
                    "symbol": "GBPUSD",
                    "action": "SELL",
                    "entry_price": 1.2500,
                    "exit_price": None,
                    "pnl": None,
                    "status": "open",
                    "opened_at": datetime.utcnow().isoformat()
                }
            ]
            
            response = api_client.get("/api/v1/performance/experiments/1/trades")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["symbol"] == "EURUSD"
    
    def test_get_experiment_trades_filtering(self, api_client):
        """Test filtering and pagination"""
        with patch('services.performance_service.get_experiment_trades') as mock_get:
            mock_get.return_value = [
                {
                    "id": 1,
                    "symbol": "EURUSD",
                    "status": "closed",
                    "pnl": 50.0
                }
            ]
            
            response = api_client.get("/api/v1/performance/experiments/1/trades?status=closed&limit=10&offset=0")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["status"] == "closed"
    
    def test_get_equity_curve(self, api_client):
        """Test equity curve retrieval"""
        with patch('services.performance_service.get_equity_curve') as mock_get:
            mock_get.return_value = [
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "equity": 10000.0,
                    "balance": 10000.0,
                    "drawdown_pct": 0.0
                },
                {
                    "timestamp": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                    "equity": 10100.0,
                    "balance": 10000.0,
                    "drawdown_pct": 0.0
                }
            ]
            
            response = api_client.get("/api/v1/performance/experiments/1/equity-curve")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["equity"] == 10000.0
