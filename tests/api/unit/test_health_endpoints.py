"""
Tests for health check API endpoints
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.exc import SQLAlchemyError
import httpx


class TestBasicHealthCheck:
    """GET /health - Basic health check"""

    def test_health_check(self, api_client):
        """Test basic health check returns healthy"""
        response = api_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "api"


class TestDatabaseHealthCheck:
    """GET /health/db - Database health check"""

    def test_database_health_check_healthy(self, api_client):
        """Test database healthy"""
        with patch("routers.health.check_db_health") as mock_check:
            mock_check.return_value = True

            response = api_client.get("/health/db")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "database"

    def test_database_health_check_unhealthy(self, api_client):
        """Test database unhealthy (503)"""
        with patch("routers.health.check_db_health") as mock_check, patch(
            "database.core.get_engine"
        ) as mock_get_engine:
            mock_check.return_value = False
            mock_engine = Mock()
            mock_conn = Mock()
            # Create a context manager mock
            mock_context = Mock()
            mock_context.__enter__ = Mock(return_value=mock_conn)
            mock_context.__exit__ = Mock(return_value=None)
            mock_engine.connect.return_value = mock_context
            mock_conn.execute.side_effect = Exception("Connection failed")
            mock_get_engine.return_value = mock_engine

            response = api_client.get("/health/db")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"

    def test_database_health_check_engine_not_initialized(self, api_client):
        """Test engine not initialized (503)"""
        with patch("routers.health.check_db_health") as mock_check, patch(
            "database.core.get_engine"
        ) as mock_get_engine:
            mock_check.return_value = False
            mock_get_engine.return_value = None

            response = api_client.get("/health/db")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "engine not initialized" in data["error"].lower()

    def test_database_health_check_connection_error(self, api_client):
        """Test connection error (503)"""
        with patch("routers.health.check_db_health") as mock_check, patch(
            "database.core.get_engine"
        ) as mock_get_engine:
            mock_check.return_value = False
            mock_engine = Mock()
            mock_engine.connect.side_effect = SQLAlchemyError("Connection error")
            mock_get_engine.return_value = mock_engine

            response = api_client.get("/health/db")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"

    def test_database_health_check_exception(self, api_client):
        """Test general exception (503)"""
        with patch("routers.health.check_db_health") as mock_check:
            mock_check.side_effect = Exception("Unexpected error")

            response = api_client.get("/health/db")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"


class TestClockSyncHealthCheck:
    """GET /health/clock-sync - Clock sync health check"""

    def test_clock_sync_health_check_healthy(self, api_client):
        """Test trading server healthy (200)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy", "service": "clock_sync"}

        with patch("routers.health.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            response = api_client.get("/health/clock-sync")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"

    def test_clock_sync_health_check_unhealthy(self, api_client):
        """Test trading server unhealthy (503)"""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.json.return_value = {
            "status": "unhealthy",
            "service": "clock_sync",
        }

        with patch("routers.health.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            response = api_client.get("/health/clock-sync")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"

    def test_clock_sync_health_check_timeout(self, api_client):
        """Test timeout (503)"""
        with patch("routers.health.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            response = api_client.get("/health/clock-sync")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "error"
            assert "timeout" in data["error"].lower() or "timed out" in data["error"].lower()

    def test_clock_sync_health_check_connection_error(self, api_client):
        """Test connection error (503)"""
        with patch("routers.health.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            response = api_client.get("/health/clock-sync")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unknown"
            assert "not available" in data["message"].lower()

    def test_clock_sync_health_check_unexpected_status(self, api_client):
        """Test unexpected status code (503)"""
        mock_response = AsyncMock()
        mock_response.status_code = 500

        with patch("routers.health.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_async_client

            response = api_client.get("/health/clock-sync")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "error"


class TestDataQualityHealthCheck:
    """GET /health/data-quality - Data quality health check"""

    def test_data_quality_health_check_healthy(self, api_client):
        """Test trading server healthy (200)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "service": "data_quality",
        }

        with patch("routers.health.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            response = api_client.get("/health/data-quality")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"

    def test_data_quality_health_check_unhealthy(self, api_client):
        """Test trading server unhealthy (503)"""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.json.return_value = {
            "status": "unhealthy",
            "service": "data_quality",
        }

        with patch("routers.health.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            response = api_client.get("/health/data-quality")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"

    def test_data_quality_health_check_timeout(self, api_client):
        """Test timeout (503)"""
        with patch("routers.health.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            response = api_client.get("/health/data-quality")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "error"
            assert "timeout" in data["error"].lower() or "timed out" in data["error"].lower()

    def test_data_quality_health_check_connection_error(self, api_client):
        """Test connection error (503)"""
        with patch("routers.health.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            response = api_client.get("/health/data-quality")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unknown"
            assert "not available" in data["message"].lower()

    def test_data_quality_health_check_unexpected_status(self, api_client):
        """Test unexpected status code (503)"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {}

        with patch("routers.health.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            response = api_client.get("/health/data-quality")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "error"


class TestMLflowHealthCheck:
    """GET /health/mlflow - MLflow health check"""

    def test_mlflow_health_check_healthy(self, api_client):
        """Test MLflow healthy (200)"""
        mock_response = Mock()
        mock_response.status_code = 200

        with patch("routers.health.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            response = api_client.get("/health/mlflow")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "mlflow"

    def test_mlflow_health_check_unhealthy(self, api_client):
        """Test MLflow unhealthy (503)"""
        mock_response = Mock()
        mock_response.status_code = 503

        with patch("routers.health.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            response = api_client.get("/health/mlflow")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"

    def test_mlflow_health_check_connection_error(self, api_client):
        """Test connection error (503)"""
        with patch("routers.health.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(side_effect=Exception("Connection failed"))
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            response = api_client.get("/health/mlflow")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
