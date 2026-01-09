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


@router.get("/health/clock-sync")
async def health_check_clock_sync():
    """Clock synchronization health check"""
    try:
        # Import clock sync monitor from trading server
        # Note: This requires the trading server to be running and accessible
        # For now, we'll create a simple check that can be enhanced later
        import sys
        import os
        
        # Try to import clock sync monitor
        try:
            # Add trading server src to path if needed
            trading_server_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "trading_server", "src"
            )
            if trading_server_path not in sys.path:
                sys.path.insert(0, trading_server_path)
            
            from monitoring.clock_sync_monitor import ClockSyncMonitor
            
            # Get singleton instance or create new one
            # In production, this should be a shared instance
            monitor = ClockSyncMonitor()
            status = monitor.get_status()
            
            is_healthy = monitor.is_healthy()
            
            if is_healthy:
                return {
                    "status": "healthy",
                    "service": "clock_sync",
                    "last_drift_seconds": status.get("last_drift_seconds"),
                    "last_status": status.get("last_status"),
                    "check_count": status.get("check_count"),
                }
            else:
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "unhealthy",
                        "service": "clock_sync",
                        "last_drift_seconds": status.get("last_drift_seconds"),
                        "last_status": status.get("last_status"),
                        "warning": "Clock synchronization issue detected",
                    },
                )
        except ImportError:
            # Clock sync monitor not available
            return {
                "status": "unknown",
                "service": "clock_sync",
                "message": "Clock sync monitor not available",
            }
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
