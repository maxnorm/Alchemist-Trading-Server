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
    """Basic health check"""
    return {"status": "healthy", "service": "api"}


@router.get("/health/db")
async def health_check_db():
    """Database health check with detailed diagnostics"""
    from services.database import _engine
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
            if _engine is None:
                error_details["error"] = "Database engine not initialized"
            else:
                try:
                    with _engine.connect() as conn:
                        conn.execute(text("SELECT 1"))
                except Exception as conn_error:
                    error_details["error"] = f"Connection error: {str(conn_error)}"
                    error_details["error_type"] = type(conn_error).__name__
            
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


@router.get("/health/mlflow")
async def health_check_mlflow():
    """MLflow health check"""
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
