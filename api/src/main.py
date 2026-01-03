"""
FastAPI application entry point
"""
from fastapi import FastAPI, Request, WebSocket, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import sys

from config import settings
from routers import (
    features,
    experiments,
    hyperparameters,
    models,
    trading,
    performance,
    health
)
from websocket.manager import websocket_manager
from websocket import channels
from services.database import init_db, close_db

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting FastAPI service...")
   
    try:
        init_db()
        logger.info("Database connection initialized")
    except Exception as e:
        logger.warning(f"Database connection not available at startup: {e}")
        logger.info("API will start without database connection. Health checks will indicate status.")
    
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI service...")
    close_db()
    await websocket_manager.disconnect_all()


# Create FastAPI app
app = FastAPI(
    title="Alchemist Trading Platform API",
    description="REST API and WebSocket service for the Alchemist AI Forex Experimentation Platform",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation error",
            "detail": exc.errors()
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.log_level == "DEBUG" else "An unexpected error occurred"
        }
    )


# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(features.router, prefix="/api/v1", tags=["Features"])
app.include_router(experiments.router, prefix="/api/v1", tags=["Experiments"])
app.include_router(hyperparameters.router, prefix="/api/v1", tags=["Hyperparameters"])
app.include_router(models.router, prefix="/api/v1", tags=["Models"])
app.include_router(trading.router, prefix="/api/v1", tags=["Trading"])
app.include_router(performance.router, prefix="/api/v1", tags=["Performance"])


# WebSocket endpoints
@app.websocket("/ws/ticks")
async def websocket_ticks(websocket: WebSocket):
    await channels.handle_websocket(websocket, "ticks")


@app.websocket("/ws/training")
async def websocket_training(websocket: WebSocket):
    await channels.handle_websocket(websocket, "training")


@app.websocket("/ws/optuna")
async def websocket_optuna(websocket: WebSocket):
    await channels.handle_websocket(websocket, "optuna")


@app.websocket("/ws/positions")
async def websocket_positions(websocket: WebSocket):
    await channels.handle_websocket(websocket, "positions")


@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    await channels.handle_websocket(websocket, "metrics")


@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    await channels.handle_websocket(websocket, "alerts")


@app.websocket("/ws/performance")
async def websocket_performance(websocket: WebSocket):
    await channels.handle_websocket(websocket, "performance")


@app.websocket("/ws/trades")
async def websocket_trades(websocket: WebSocket):
    await channels.handle_websocket(websocket, "trades")


@app.websocket("/ws/models")
async def websocket_models(websocket: WebSocket):
    """WebSocket for all model lifecycle updates"""
    await channels.handle_websocket(websocket, "models")


@app.websocket("/ws/models/{model_id}/status")
async def websocket_model_status(websocket: WebSocket, model_id: int):
    """WebSocket for specific model status updates"""
    await channels.handle_websocket(websocket, f"models/{model_id}/status")


@app.websocket("/ws/models/{model_id}/paper-session")
async def websocket_paper_session(websocket: WebSocket, model_id: int):
    """WebSocket for paper trading session updates"""
    await channels.handle_websocket(websocket, f"models/{model_id}/paper-session")


@app.websocket("/ws/models/{model_id}/validation")
async def websocket_validation(websocket: WebSocket, model_id: int):
    """WebSocket for model validation status updates"""
    await channels.handle_websocket(websocket, f"models/{model_id}/validation")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Alchemist Trading Platform API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }
