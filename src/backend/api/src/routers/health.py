"""
Health check endpoints
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from services.database import check_db_health
from config import settings
import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check (internal-only endpoint, not exposed through gateway)"""
    return {"status": "healthy", "service": "api"}


@router.get("/health/db")
async def health_check_db():
    """Database health check with detailed diagnostics (internal-only endpoint, not exposed through gateway)"""
    from database.core import get_engine
    from config import settings
    
    try:
        is_healthy = check_db_health()
        if is_healthy:
            return {
                "status": "healthy",
                "service": "database",
                "host": settings.db_host,
                "port": settings.db_port,
                "database": settings.db_name,
            }
        else:
            # Provide detailed error information
            error_details = {
                "status": "unhealthy",
                "service": "database",
                "error": "Database connection failed",
                "host": settings.db_host,
                "port": settings.db_port,
                "database": settings.db_name,
                "user": settings.db_user,
            }
            
            # Try to get more specific error
            try:
                engine = get_engine()
                if engine is None:
                    error_details["error"] = "Database engine not initialized"
                else:
                    try:
                        with engine.connect() as conn:
                            conn.execute(text("SELECT 1"))
                    except Exception as conn_error:
                        error_details["error"] = f"Connection error: {str(conn_error)}"
                        error_details["error_type"] = type(conn_error).__name__
            except RuntimeError as e:
                error_details["error"] = f"Database engine not initialized: {str(e)}"
            
            return JSONResponse(status_code=503, content=error_details)
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "database",
                "error": str(e),
                "error_type": type(e).__name__,
                "host": settings.db_host,
                "port": settings.db_port,
                "database": settings.db_name,
            },
        )


@router.get("/health/clock-sync")
async def health_check_clock_sync():
    """Clock synchronization health check - proxies to trading server (internal-only endpoint, not exposed through gateway)"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.trading_server_url}/health/clock-sync"
            )
            if response.status_code == 200:
                # Parse response and return
                data = response.json()
                return data
            elif response.status_code == 503:
                # Trading server returned unhealthy status
                data = response.json()
                return JSONResponse(
                    status_code=503,
                    content=data,
                )
            else:
                # Unexpected status code
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "error",
                        "service": "clock_sync",
                        "error": f"Trading server returned status {response.status_code}",
                    },
                )
    except httpx.TimeoutException:
        logger.error("Clock sync health check timed out")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "service": "clock_sync",
                "error": "Trading server health check timed out",
            },
        )
    except httpx.ConnectError:
        logger.error("Clock sync health check: could not connect to trading server")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unknown",
                "service": "clock_sync",
                "message": "Trading server not available",
            },
        )
    except Exception as e:
        logger.error(f"Clock sync health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "service": "clock_sync",
                "error": str(e),
            },
        )


@router.get("/health/data-quality")
async def health_check_data_quality():
    """Data quality health check - proxies to trading server (internal-only endpoint, not exposed through gateway)"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.trading_server_url}/health/data-quality"
            )
            if response.status_code == 200:
                # Parse response and return
                data = response.json()
                return data
            elif response.status_code == 503:
                # Trading server returned unhealthy status
                data = response.json()
                return JSONResponse(
                    status_code=503,
                    content=data,
                )
            else:
                # Unexpected status code
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "error",
                        "service": "data_quality",
                        "error": f"Trading server returned status {response.status_code}",
                    },
                )
    except httpx.TimeoutException:
        logger.error("Data quality health check timed out")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "service": "data_quality",
                "error": "Trading server health check timed out",
            },
        )
    except httpx.ConnectError:
        logger.error("Data quality health check: could not connect to trading server")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unknown",
                "service": "data_quality",
                "message": "Trading server not available",
            },
        )
    except Exception as e:
        logger.error(f"Data quality health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "service": "data_quality",
                "error": str(e),
            },
        )


@router.get("/health/mlflow")
async def health_check_mlflow():
    """MLflow health check (public endpoint)"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.mlflow_tracking_uri}/health")
            if response.status_code == 200:
                return {"status": "healthy", "service": "mlflow"}
            else:
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "unhealthy",
                        "service": "mlflow",
                        "error": f"MLflow returned status {response.status_code}",
                    },
                )
    except Exception as e:
        logger.error(f"MLflow health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "service": "mlflow", "error": str(e)},
        )
