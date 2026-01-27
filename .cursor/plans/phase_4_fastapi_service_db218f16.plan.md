---
name: Phase 4 FastAPI Service
overview: Implement the FastAPI REST API and WebSocket service to enable dashboard communication with the trading backend. This includes all REST endpoints for features, experiments, hyperparameters, models, trading controls, and performance, plus real-time WebSocket channels for live updates.
todos:
  - id: phase4-project-setup
    content: Set up FastAPI project structure with Dockerfile, requirements.txt, and basic configuration
    status: completed
  - id: phase4-database-service
    content: Create database service layer with SQLAlchemy connection pool and session management
    status: completed
  - id: phase4-feature-endpoints
    content: Implement feature catalog REST endpoints (list, get, filter by source)
    status: completed
  - id: phase4-experiment-endpoints
    content: Implement experiment management REST endpoints (CRUD, start/stop, clone)
    status: completed
  - id: phase4-hyperparameter-endpoints
    content: Implement Optuna hyperparameter search REST endpoints
    status: completed
  - id: phase4-model-endpoints
    content: Implement model registry REST endpoints (list, promote, archive, rollback)
    status: completed
  - id: phase4-trading-endpoints
    content: Implement trading control REST endpoints (status, kill switch, circuit breaker)
    status: completed
  - id: phase4-performance-endpoints
    content: Implement performance metrics REST endpoints (portfolio, model performance, equity curves)
    status: completed
  - id: phase4-websocket-manager
    content: Implement WebSocket manager with connection handling and channel support
    status: completed
  - id: phase4-websocket-channels
    content: Implement WebSocket channels (ticks, training, optuna, positions, metrics, alerts, trades)
    status: completed
  - id: phase4-docker-compose
    content: Add API service to docker-compose.yml with proper dependencies and health checks
    status: completed
  - id: phase4-error-handling
    content: Implement global error handling, validation, and consistent error responses
    status: completed
  - id: phase4-health-checks
    content: Implement health check endpoints for API, database, and MLflow connectivity
    status: completed
  - id: phase4-api-docs
    content: Verify FastAPI auto-generated API documentation (Swagger UI) is accessible
    status: completed
---

# Phase 4: FastAPI Service Implementation

## Overview

Phase 4 implements the FastAPI service layer that bridges the React dashboard with the Python trading backend. This service provides REST endpoints for all platform operations and WebSocket channels for real-time updates.

## Architecture

The FastAPI service will:

- Run as a separate Docker container on port 8000
- Connect to MariaDB for data persistence
- Communicate with the trading server via shared database and potentially gRPC/HTTP (future)
- Provide REST API at `/api/v1` and WebSocket at `/ws`
- Support local deployment without authentication (structure ready for future OAuth2)

## Project Structure

```
api/
├── Dockerfile
├── requirements.txt
├── .env.example
├── src/
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Configuration management
│   ├── dependencies.py         # Dependency injection (DB, services)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── features.py         # Feature catalog endpoints
│   │   ├── experiments.py      # Experiment management endpoints
│   │   ├── hyperparameters.py  # Optuna search endpoints
│   │   ├── models.py           # Model registry endpoints
│   │   ├── trading.py         # Trading control endpoints (kill switch, etc.)
│   │   └── performance.py      # Performance metrics endpoints
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── features.py         # Feature Pydantic models
│   │   ├── experiments.py      # Experiment Pydantic models
│   │   ├── hyperparameters.py  # Optuna Pydantic models
│   │   ├── models.py           # Model Pydantic models
│   │   ├── trading.py          # Trading Pydantic models
│   │   └── performance.py      # Performance Pydantic models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── database.py         # Database connection service
│   │   ├── feature_service.py  # Feature catalog business logic
│   │   ├── experiment_service.py # Experiment business logic
│   │   ├── optuna_service.py   # Optuna search business logic
│   │   ├── model_service.py    # Model registry business logic
│   │   ├── trading_service.py  # Trading control business logic
│   │   └── performance_service.py # Performance metrics business logic
│   └── websocket/
│       ├── __init__.py
│       ├── manager.py          # WebSocket connection manager
│       └── channels.py          # WebSocket channel handlers
```

## Implementation Tasks

### 4.1 Project Setup

**Files**: `api/Dockerfile`, `api/requirements.txt`, `api/src/main.py`, `api/src/config.py`

- Create FastAPI project structure
- Set up Dockerfile with Python 3.11+ base image
- Install dependencies: fastapi, uvicorn, websockets, pydantic, sqlalchemy, mariadb-connector, python-dotenv
- Configure environment variables (database connection, MLflow URL)
- Set up CORS for local development
- Configure logging

**Key Dependencies**:

- `fastapi>=0.104.0`
- `uvicorn[standard]>=0.24.0`
- `websockets>=12.0`
- `pydantic>=2.5.0`
- `sqlalchemy>=2.0.0`
- `mariadb>=1.1.0`
- `python-dotenv>=1.0.0`

### 4.2 Database Service Layer

**File**: `api/src/services/database.py`

- Create SQLAlchemy connection pool to MariaDB
- Implement connection health checks
- Create database session dependency for FastAPI
- Handle connection retries and error recovery
- Support async database operations

**Integration**: Use same database credentials as trading server (`forex_user`/`forex_password`)

### 4.3 Feature Catalog Endpoints

**Files**: `api/src/routers/features.py`, `api/src/schemas/features.py`, `api/src/services/feature_service.py`

**Endpoints** (from PRD Section 16.2):

- `GET /api/v1/features` - List all features with filtering (source, category)
- `GET /api/v1/features/{name}` - Get feature details
- `GET /api/v1/features/sources` - List all data sources
- `GET /api/v1/features/sources/{id}/health` - Get source health status

**Implementation**:

- Query `features` table from database
- Query `data_providers` table for source information
- Return feature metadata (name, type, description, statistics)
- Support filtering by query parameters

**Schemas**:

- `FeatureResponse` - Feature details
- `FeatureListResponse` - List of features
- `DataSourceResponse` - Data source information

### 4.4 Experiment Endpoints

**Files**: `api/src/routers/experiments.py`, `api/src/schemas/experiments.py`, `api/src/services/experiment_service.py`

**Endpoints** (from PRD Section 16.3):

- `GET /api/v1/experiments` - List all experiments (with status filtering)
- `POST /api/v1/experiments` - Create new experiment
- `GET /api/v1/experiments/{id}` - Get experiment details
- `POST /api/v1/experiments/{id}/start` - Start training
- `POST /api/v1/experiments/{id}/stop` - Stop training
- `POST /api/v1/experiments/{id}/clone` - Clone experiment
- `DELETE /api/v1/experiments/{id}` - Delete experiment

**Implementation**:

- CRUD operations on `experiments` table
- Integration with experiment runner (if exists) or create service layer
- Validate experiment configuration before creation
- Handle experiment lifecycle (created → training → completed/failed)

**Schemas**:

- `ExperimentCreate` - Experiment creation request
- `ExperimentResponse` - Experiment details
- `ExperimentListResponse` - List of experiments
- `ExperimentStartRequest` - Start training request

**Integration Points**:

- If experiment runner exists: call `ExperimentRunner.start_experiment()`
- Otherwise: create service that interfaces with training loop

### 4.5 Hyperparameter Search Endpoints

**Files**: `api/src/routers/hyperparameters.py`, `api/src/schemas/hyperparameters.py`, `api/src/services/optuna_service.py`

**Endpoints** (from PRD Section 16.4):

- `POST /api/v1/hyperparameters/search` - Start Optuna search
- `GET /api/v1/hyperparameters/search/{id}` - Get search status
- `GET /api/v1/hyperparameters/search/{id}/trials` - Get all trials
- `GET /api/v1/hyperparameters/search/{id}/best` - Get best trial
- `POST /api/v1/hyperparameters/search/{id}/stop` - Stop search
- `GET /api/v1/hyperparameters/search/{id}/importance` - Get parameter importance

**Implementation**:

- Query `optuna_studies` and `optuna_trials` tables
- Create Optuna study via service layer
- Stream trial results via WebSocket
- Calculate parameter importance using Optuna's built-in methods

**Schemas**:

- `OptunaSearchCreate` - Search configuration
- `OptunaStudyResponse` - Study status and details
- `TrialResponse` - Individual trial results
- `ParameterImportanceResponse` - Parameter importance scores

**Integration Points**:

- If Optuna integration exists: use `OptunaHyperparameterTuner`
- Otherwise: create service that initializes Optuna studies

### 4.6 Model Registry Endpoints

**Files**: `api/src/routers/models.py`, `api/src/schemas/models.py`, `api/src/services/model_service.py`

**Endpoints** (from PRD Section 16.5):

- `GET /api/v1/models` - List registered models
- `GET /api/v1/models/{version}` - Get model details
- `POST /api/v1/models/{version}/promote` - Promote model stage (training → paper → live)
- `POST /api/v1/models/{version}/archive` - Archive model
- `POST /api/v1/models/{version}/rollback` - Rollback to previous model

**Implementation**:

- Query `models` table
- Integrate with MLflow for model artifacts
- Handle model promotion workflow
- Validate promotion criteria (paper trading results, etc.)

**Schemas**:

- `ModelResponse` - Model details
- `ModelListResponse` - List of models
- `ModelPromoteRequest` - Promotion request

**Integration Points**:

- MLflow client for model artifacts
- Model promoter service (if exists)

### 4.7 Trading Control Endpoints

**Files**: `api/src/routers/trading.py`, `api/src/schemas/trading.py`, `api/src/services/trading_service.py`

**Endpoints** (from PRD Section 16.6):

- `GET /api/v1/trading/status` - Get trading status (active experiments, positions)
- `POST /api/v1/trading/start` - Start live trading (with confirmation)
- `POST /api/v1/trading/stop` - Stop trading
- `POST /api/v1/trading/kill` - Emergency kill switch (with confirmation)
- `GET /api/v1/trading/positions` - Get open positions
- `GET /api/v1/trading/history` - Get trade history

**Kill Switch Integration**:

- `POST /api/v1/trading/kill-switch/trigger` - Trigger kill switch
- `POST /api/v1/trading/kill-switch/reset` - Reset kill switch
- `GET /api/v1/trading/kill-switch/status` - Get kill switch status

**Circuit Breaker Integration**:

- `GET /api/v1/trading/circuit-breaker/status` - Get circuit breaker status
- `POST /api/v1/trading/circuit-breaker/reset` - Reset circuit breaker

**Implementation**:

- Interface with kill switch and circuit breaker (file-based or database)
- Query trading status from database (experiments, positions)
- Provide confirmation mechanism for sensitive operations
- Log all trading control actions

**Integration Points**:

- Kill switch file trigger: Write to kill switch file
- Circuit breaker: Query status from database or service
- OMS: Query positions from `orders` table

**Note**: Since kill switch and circuit breaker are in the trading server process, we may need:

- File-based communication (kill switch file)
- Database status tables
- Or future gRPC/HTTP communication

### 4.8 Performance Endpoints

**Files**: `api/src/routers/performance.py`, `api/src/schemas/performance.py`, `api/src/services/performance_service.py`

**Endpoints** (from PRD Section 16.8):

- `GET /api/v1/performance/portfolio` - Portfolio performance summary
- `GET /api/v1/performance/portfolio/equity-curve` - Portfolio equity curve data
- `GET /api/v1/performance/portfolio/breakdown` - P&L breakdown by period
- `GET /api/v1/performance/portfolio/allocation` - Allocation by pair/model
- `GET /api/v1/performance/models` - List all model performance summaries
- `GET /api/v1/performance/models/{version}` - Detailed model performance
- `GET /api/v1/performance/models/{version}/equity-curve` - Model equity curve
- `GET /api/v1/performance/models/{version}/trades` - Model trade history
- `GET /api/v1/performance/models/{version}/statistics` - Model statistics
- `GET /api/v1/performance/metrics/realtime` - Real-time performance metrics

**Implementation**:

- Query `trades`, `equity_curve`, `performance_metrics` tables
- Calculate aggregate metrics (Sharpe ratio, win rate, drawdown)
- Support time period filtering
- Return formatted data for charts

**Schemas**:

- `PortfolioPerformanceResponse` - Portfolio summary
- `EquityCurveResponse` - Equity curve data points
- `ModelPerformanceResponse` - Model performance details
- `TradeHistoryResponse` - Trade history list

**Note**: Performance tables may be created in Phase 6, but endpoints structure should be ready.

### 4.9 WebSocket Manager

**Files**: `api/src/websocket/manager.py`, `api/src/websocket/channels.py`

**WebSocket Endpoints** (from PRD Section 16.9):

- `/ws/ticks` - Real-time tick data
- `/ws/training` - Training progress updates
- `/ws/optuna` - Optuna search progress
- `/ws/positions` - Position updates
- `/ws/metrics` - P&L, balance updates
- `/ws/alerts` - Alert notifications
- `/ws/performance` - Real-time performance updates
- `/ws/trades` - Real-time trade notifications

**Implementation**:

- WebSocket connection manager with room/channel support
- Broadcast messages to subscribed clients
- Handle connection lifecycle (connect, disconnect, reconnect)
- Support multiple clients per channel
- Message format: JSON with type and payload

**Channel Handlers**:

- `TickChannel` - Stream tick data from price providers
- `TrainingChannel` - Stream training metrics from experiments
- `OptunaChannel` - Stream Optuna trial results
- `PositionChannel` - Stream position updates from OMS
- `MetricsChannel` - Stream performance metrics
- `AlertChannel` - Stream system alerts
- `TradeChannel` - Stream trade execution notifications

**Integration Points**:

- Subscribe to price provider updates (via database polling or future event system)
- Poll experiment status from database
- Poll Optuna trial results from database
- Poll position updates from OMS database tables

### 4.10 Docker Compose Integration

**File**: `docker-compose.yml`

Add API service:

```yaml
api:
  container_name: "api"
  build:
    context: ./api
    dockerfile: Dockerfile
  ports:
    - "8000:8000"
  depends_on:
    mariadb:
      condition: service_healthy
    mlflow:
      condition: service_healthy
  environment:
    DATABASE_URL: mysql://forex_user:forex_password@mariadb:3306/db_forex
    MLFLOW_TRACKING_URI: http://mlflow:5000
    API_HOST: 0.0.0.0
    API_PORT: 8000
  volumes:
    - "./logs:/app/logs"
  restart: unless-stopped
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
```

### 4.11 Error Handling & Validation

**Files**: `api/src/main.py`, `api/src/dependencies.py`

- Global exception handlers for common errors
- Pydantic validation for all request bodies
- Database error handling (connection failures, query errors)
- HTTP status codes (200, 201, 400, 404, 500)
- Error response schema with consistent format

### 4.12 Health Check & Monitoring

**File**: `api/src/routers/health.py` (or in main.py)

- `GET /health` - Health check endpoint
- `GET /health/db` - Database connection check
- `GET /health/mlflow` - MLflow connectivity check
- Return service status for monitoring

## Integration Strategy

### Database Communication

- FastAPI service connects directly to MariaDB
- Shares same database as trading server
- Use database as communication layer (status tables, event logs)

### Trading Server Communication

- **Current**: File-based (kill switch file) + Database (status tables)
- **Future**: gRPC or HTTP for direct service communication

### Real-time Updates

- WebSocket channels poll database for updates
- Future: Event-driven system with message queue (Redis/RabbitMQ)

## Testing Strategy

- Unit tests for service layer (mock database)
- Integration tests for endpoints (test database)
- WebSocket connection tests
- End-to-end API tests with real database

## Performance Requirements

- API response time (p95) < 200ms (from PRD NFR-3)
- WebSocket latency < 100ms (from PRD NFR-2)
- Support 10+ concurrent WebSocket connections
- Database connection pooling (10-20 connections)

## Security Considerations

- No authentication for local deployment (as per PRD)
- CORS configured for localhost only
- Input validation on all endpoints
- SQL injection prevention (parameterized queries)
- Rate limiting on sensitive endpoints (optional)

## Dependencies on Previous Phases

- **Phase 1**: Kill switch and circuit breaker must be implemented
- **Phase 2**: Feature catalog and data providers must exist
- **Phase 3**: Experiments and Optuna integration must exist
- Database tables from previous phases must be created

## Success Criteria

- All REST endpoints implemented and tested
- WebSocket channels functional for real-time updates
- API service runs in Docker container
- Health checks pass
- Integration with trading server via database
- API documentation auto-generated (FastAPI Swagger UI)