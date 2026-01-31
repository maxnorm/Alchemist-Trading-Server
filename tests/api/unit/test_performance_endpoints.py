"""
Tests for performance tracking API endpoints
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta


class TestGetPortfolioMetrics:
    """GET /api/v1/performance/portfolio"""
    
    def test_get_portfolio_metrics(self, api_client):
        """Test aggregate metrics calculation"""
        from schemas.performance import PortfolioPerformanceResponse
        
        from services import performance_service
        with patch.object(performance_service, 'get_portfolio_performance') as mock_get:
            mock_get.return_value = PortfolioPerformanceResponse(
                total_trades=100,
                winning_trades=55,
                losing_trades=45,
                win_rate=55.5,
                total_pnl=1000.0,
                sharpe_ratio=1.8,
                max_drawdown_pct=5.2
            )
            
            response = api_client.get("/api/v1/performance/portfolio")
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_pnl"] == 1000.0
            assert data["win_rate"] == 55.5
            assert data["total_trades"] == 100
    
    def test_get_portfolio_metrics_time_period(self, api_client):
        """Test time period filtering"""
        from schemas.performance import PortfolioPerformanceResponse
        
        from services import performance_service
        with patch.object(performance_service, 'get_portfolio_performance') as mock_get:
            mock_get.return_value = PortfolioPerformanceResponse(
                total_trades=50,
                winning_trades=30,
                losing_trades=20,
                win_rate=60.0,
                total_pnl=500.0
            )
            
            response = api_client.get("/api/v1/performance/portfolio?period=daily")
            
            assert response.status_code == 200
            data = response.json()
            assert "total_pnl" in data
            assert data["total_trades"] == 50


class TestGetModelTrades:
    """GET /api/v1/performance/models/{model_id}/trades"""
    
    def test_get_model_trades(self, api_client):
        """Test trade history retrieval"""
        from services import performance_service
        with patch.object(performance_service, 'get_model_trades') as mock_get:
            mock_get.return_value = ([
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
            ], 2)
            
            response = api_client.get("/api/v1/performance/models/1/trades")
            
            assert response.status_code == 200
            data = response.json()
            assert "trades" in data
            assert len(data["trades"]) == 2
            assert data["trades"][0]["symbol"] == "EURUSD"
    
    def test_get_model_trades_filtering(self, api_client):
        """Test filtering and pagination"""
        from services import performance_service
        with patch.object(performance_service, 'get_model_trades') as mock_get:
            mock_get.return_value = ([
                {
                    "id": 1,
                    "symbol": "EURUSD",
                    "status": "closed",
                    "pnl": 50.0
                }
            ], 1)
            
            response = api_client.get("/api/v1/performance/models/1/trades?limit=10&offset=0")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["trades"]) == 1
            assert data["trades"][0]["status"] == "closed"
    
    def test_get_model_equity_curve(self, api_client):
        """Test equity curve retrieval"""
        from schemas.performance import EquityCurveResponse, EquityCurvePoint
        
        from services import performance_service
        with patch.object(performance_service, 'get_model_equity_curve') as mock_get:
            points = [
                EquityCurvePoint(
                    timestamp=datetime.utcnow(),
                    equity=10000.0,
                    balance=10000.0
                ),
                EquityCurvePoint(
                    timestamp=datetime.utcnow() + timedelta(hours=1),
                    equity=10100.0,
                    balance=10000.0
                )
            ]
            mock_get.return_value = EquityCurveResponse(
                data=points,
                total_points=2
            )
            
            response = api_client.get("/api/v1/performance/models/1/equity-curve")
            
            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert "total_points" in data
            assert len(data["data"]) == 2
            assert data["data"][0]["equity"] == 10000.0
            assert data["total_points"] == 2
