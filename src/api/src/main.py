"""
FastAPI application entry point
"""

from fastapi import FastAPI, Request, WebSocket, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from contextlib import asynccontextmanager
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
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
    health,
    data,
    mt5_accounts,
    schema,
    lineage,
)
from websocket.manager import websocket_manager
from websocket import channels  # type: ignore[attr-defined]
from services.database import init_db, close_db
from services.clerk_seed import seed_clerk_user
from middleware.metrics import MetricsMiddleware
from infrastructure.messaging.alert_consumer import AlertConsumer

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
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
        logger.info(
            "API will start without database connection. Health checks will indicate status."
        )

    # Start alert consumer
    alert_consumer = None
    try:
        alert_consumer = AlertConsumer()
        await alert_consumer.start()
        logger.info("Alert consumer started")
    except Exception as e:
        logger.warning(f"Failed to start alert consumer: {e}")
        logger.info("API will continue without alert consumer. Alerts will not be broadcast.")

    # Seed Clerk user if enabled
    if settings.clerk_seed_enabled:
        try:
            logger.info("Clerk user seeding enabled, attempting to seed user...")
            success = seed_clerk_user()
            if success:
                logger.info("Clerk user seeded successfully")
            else:
                logger.warning("Failed to seed Clerk user, but API will continue")
        except Exception as e:
            logger.warning(f"Error during Clerk user seeding: {e}")
            logger.info("API will continue without seeded user")

    yield

    # Shutdown
    logger.info("Shutting down FastAPI service...")
    
    # Stop alert consumer
    if alert_consumer is not None:
        try:
            await alert_consumer.stop()
        except Exception as e:
            logger.warning(f"Error stopping alert consumer: {e}")
    
    close_db()
    await websocket_manager.disconnect_all()


# Create FastAPI app
app = FastAPI(
    title="Alchemist Trading Platform API",
    description="REST API and WebSocket service for the Alchemist AI Forex Experimentation Platform",
    version="1.0.0",
    lifespan=lifespan,
    # Configure docs to use /api/openapi.json
    docs_url="/docs",
    openapi_url="/api/openapi.json",
)

# Override openapi method to ensure it uses /api/openapi.json
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Add metrics middleware (before CORS)
app.add_middleware(MetricsMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost",  # Gateway
        # Add production domain: "https://yourdomain.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    return JSONResponse(
        status_code=422, content={"error": "Validation error", "detail": exc.errors()}
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": (
                str(exc)
                if settings.log_level == "DEBUG"
                else "An unexpected error occurred"
            ),
        },
    )


# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(features.router, prefix=settings.api_prefix, tags=["Features"])
app.include_router(experiments.router, prefix=settings.api_prefix, tags=["Experiments"])
app.include_router(hyperparameters.router, prefix=settings.api_prefix, tags=["Hyperparameters"])
app.include_router(models.router, prefix=settings.api_prefix, tags=["Models"])
app.include_router(trading.router, prefix=settings.api_prefix, tags=["Trading"])
app.include_router(performance.router, prefix=settings.api_prefix, tags=["Performance"])
app.include_router(data.router, prefix=settings.api_prefix, tags=["Data"])
app.include_router(mt5_accounts.router, prefix=settings.api_prefix, tags=["MT5 Accounts"])
app.include_router(schema.router, prefix=settings.api_prefix, tags=["Schema Registry"])
app.include_router(lineage.router, prefix=settings.api_prefix, tags=["Lineage"])


# WebSocket endpoints
@app.websocket("/ws")
async def websocket_generic(websocket: WebSocket):
    """Generic WebSocket endpoint that accepts channel subscriptions"""
    await channels.handle_generic_websocket(websocket)


@app.websocket("/ws/ticks")
async def websocket_ticks(websocket: WebSocket):
    await channels.handle_websocket(websocket, "ticks")


@app.websocket("/ws/accounts/mt5")
async def websocket_mt5_accounts(websocket: WebSocket):
    """WebSocket for MT5 account connection status updates"""
    await channels.handle_websocket(websocket, "mt5_accounts")


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
        "api_version": settings.api_version,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
