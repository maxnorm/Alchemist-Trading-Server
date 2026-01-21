---
name: Alchemist Platform Development Plan
overview: Comprehensive development plan for The Alchemist AI Forex Experimentation Platform, organized into 8 phases covering safety infrastructure, data sources, experiments, API, dashboard, performance tracking, MLOps, and testing.
todos:
  - id: phase1-kill-switch-api
    content: Add API trigger to kill switch (defer to Phase 4 FastAPI integration)
    status: pending
  - id: phase1-kill-switch-integration
    content: Integrate kill switch with TradingController - check before each trade
    status: completed
  - id: phase1-circuit-breaker-integration
    content: Integrate circuit breaker with TradingController - check before trades, record after
    status: completed
  - id: phase1-oms-idempotency
    content: Implement OMS idempotency - unique order IDs, duplicate detection
    status: completed
  - id: phase1-oms-reconciliation
    content: Implement OMS position reconciliation - periodic sync with MT5
    status: completed
  - id: phase1-oms-state-machine
    content: Implement OMS order state machine - pending → submitted → filled/rejected
    status: completed
  - id: phase1-safety-tests
    content: Write integration tests for safety mechanisms
    status: completed
  - id: phase2-provider-registry
    content: Create DataProviderRegistry class with auto-discovery
    status: completed
  - id: phase2-enhance-base-provider
    content: Add get_features() method and Feature dataclass to base provider
    status: completed
  - id: phase2-indicator-provider
    content: Create IndicatorProvider wrapping technical indicators
    status: completed
  - id: phase2-feature-catalog
    content: Create FeatureCatalog class and database table
    status: completed
  - id: phase2-startup-discovery
    content: Implement auto-discovery on Server startup
    status: completed
  - id: phase2-provider-docs
    content: Write documentation for adding new data sources
    status: completed
  - id: phase3-experiment-model
    content: Create Experiment dataclass and database table
    status: completed
  - id: phase3-experiment-builder
    content: Create ExperimentBuilder class
    status: completed
  - id: phase3-experiment-runner
    content: Create ExperimentRunner class integrating with TrainingLoop
    status: completed
  - id: phase3-optuna-integration
    content: Create OptunaHyperparameterTuner with study and trial management
    status: completed
  - id: phase3-optuna-database
    content: Create Optuna database tables for studies and trials
    status: completed
  - id: phase3-mlflow-linking
    content: Link MLflow runs to experiments via tags
    status: completed
  - id: phase4-fastapi-structure
    content: Set up FastAPI project structure with routers and schemas
    status: completed
  - id: phase4-feature-endpoints
    content: Implement feature catalog REST endpoints
    status: completed
  - id: phase4-experiment-endpoints
    content: Implement experiment management REST endpoints
    status: completed
  - id: phase4-hyperparameter-endpoints
    content: Implement Optuna hyperparameter search REST endpoints
    status: completed
  - id: phase4-model-endpoints
    content: Implement model registry REST endpoints
    status: completed
  - id: phase4-trading-endpoints
    content: Implement trading control REST endpoints (kill switch, circuit breaker)
    status: completed
  - id: phase4-websocket-manager
    content: Implement WebSocket manager for real-time updates
    status: completed
  - id: phase4-docker-compose
    content: Add FastAPI service to docker-compose.yml
    status: completed
  - id: phase5-react-setup
    content: Initialize React project with Vite, TypeScript, Tailwind, shadcn/ui
    status: completed
  - id: phase5-dashboard-layout
    content: Implement dashboard layout with sidebar and header
    status: completed
  - id: phase5-experiment-builder-page
    content: Implement Experiment Builder page with feature selection
    status: completed
  - id: phase5-hyperparameter-page
    content: Implement Hyperparameter Search page with Optuna UI
    status: completed
  - id: phase5-training-monitor
    content: Implement Training Monitor page with real-time metrics
    status: completed
  - id: phase5-feature-catalog-page
    content: Implement Feature Catalog page
    status: completed
  - id: phase5-model-registry-page
    content: Implement Model Registry page
    status: completed
  - id: phase5-live-trading-page
    content: Implement Live Trading page with kill switch controls
    status: completed
  - id: phase5-api-client
    content: Set up API client service with Axios
    status: completed
  - id: phase5-websocket-client
    content: Set up WebSocket client service
    status: completed
  - id: phase6-performance-tables
    content: Create performance database tables (trades, equity_curve, performance_metrics)
    status: completed
  - id: phase6-trade-logger
    content: Implement TradeLogger for logging trade entries and exits
    status: completed
  - id: phase6-metrics-calculator
    content: Implement PerformanceMetricsCalculator for win rate, Sharpe, drawdown
    status: completed
  - id: phase6-equity-tracker
    content: Implement EquityTracker for periodic balance snapshots
    status: completed
  - id: phase6-performance-api
    content: Create performance API endpoints
    status: completed
  - id: phase6-portfolio-page
    content: Implement Portfolio Performance page with charts
    status: completed
  - id: phase6-model-performance-page
    content: Implement Model Performance page with trade history
    status: completed
  - id: phase6-realtime-updates
    content: Implement real-time performance updates via WebSocket
    status: completed
  - id: phase7-model-registry-enhance
    content: Enhance model registry with promotion workflow
    status: completed
  - id: phase7-paper-validator
    content: Implement PaperTradingValidator with validation criteria
    status: completed
  - id: phase7-promotion-workflow
    content: Implement promotion workflow (training → paper → live)
    status: completed
  - id: phase7-mlflow-verify
    content: Verify MLflow server connectivity and configuration
    status: completed
  - id: phase8-integration-tests
    content: Write comprehensive integration tests
    status: completed
  - id: phase8-e2e-tests
    content: Write end-to-end tests for complete workflows
    status: completed
  - id: phase8-performance-optimization
    content: Optimize feature extraction, queries, and WebSocket frequency
    status: completed
  - id: phase8-bug-fixes
    content: Fix bugs and polish UI/UX
    status: completed
  - id: phase8-documentation
    content: Write API docs, user guide, and developer guide
    status: completed
---

# The Alchemist Platform - Complete Development Plan

## Current State Analysis

### What Exists ✅

- **Core Infrastructure**: Socket server, MT5 connection, tick streaming
- **AI Components**: DQN agent (Attention-DQN), feature engineering, technical indicators
- **Training**: Live training loop with MLflow integration, checkpoint management
- **Risk Management**: Kill switch (partial), circuit breaker (partial), OMS (partial)
- **Data Providers**: Base provider interface, price provider implementation
- **Environments**: Live, paper, historical trading environments
- **Database**: MariaDB with basic schema (ticks, currency pairs, economic calendar)
- **MLOps**: Experiment tracker (MLflow), data versioner (DVC), model promoter (partial)

### What's Missing ❌

- **Data Source Registry**: Auto-discovery system for providers
- **Feature Catalog**: Database-backed feature metadata system
- **Experiment Builder**: Configuration and management system
- **Optuna Integration**: Hyperparameter search automation
- **FastAPI Service**: REST + WebSocket API layer
- **React Dashboard**: Complete experimentation UI
- **Performance Tracking**: Trade logging, metrics calculation, equity curves
- **Model Registry**: Complete lifecycle management
- **Database Schema**: New tables for experiments, features, models, performance

---

## Phase 1: Safety Infrastructure (Week 1)

**Goal**: Complete and integrate all safety mechanisms before any trading operations.

### Tasks

#### 1.1 Complete Kill Switch Implementation

**Files**: `src/mt5-python_server/src/risk/kill_switch.py`

- ✅ File trigger (exists)
- ✅ Environment trigger (exists)
- ✅ Network trigger (exists)
- ✅ Signal trigger (exists)
- ❌ **Add API trigger** - FastAPI endpoint integration (defer to Phase 4)
- ❌ **Integrate with TradingController** - Wire kill switch checks into trading loop
- ❌ **Add dashboard button trigger** - WebSocket command (defer to Phase 5)

**Integration Points**:

- Update `TradingController` to check `kill_switch.is_active()` before each trade
- Add kill switch status endpoint for monitoring

#### 1.2 Complete Circuit Breaker Implementation

**Files**: `src/mt5-python_server/src/risk/circuit_breaker.py`

- ✅ Core logic exists
- ❌ **Integrate with TradingController** - Check before trades, record after trades
- ❌ **Add volatility calculation** - Integrate with price history manager
- ❌ **Add daily/hourly reset hooks** - Call at appropriate times

**Integration Points**:

- `TradingController.execute_trade()` - Check circuit breaker before execution
- `TradingController.record_trade_result()` - Update circuit breaker metrics

#### 1.3 Complete Order Management System (OMS)

**Files**: `src/mt5-python_server/src/risk/oms.py`

- ✅ Basic structure exists
- ❌ **Implement idempotency** - Unique order IDs, duplicate detection
- ❌ **Position reconciliation** - Periodic sync with MT5 positions
- ❌ **Order state machine** - pending → submitted → filled/rejected
- ❌ **Alert system** - Notify on mismatches

**Database Changes**:

```sql
CREATE TABLE orders (
    id VARCHAR(64) PRIMARY KEY,
    experiment_id INT,
    account_login INT,
    symbol VARCHAR(10),
    order_type ENUM('BUY', 'SELL', 'CLOSE'),
    state ENUM('PENDING', 'SUBMITTED', 'FILLED', 'REJECTED', 'CANCELLED'),
    mt5_ticket BIGINT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    INDEX idx_experiment (experiment_id),
    INDEX idx_account (account_login)
);
```

#### 1.4 Integration Testing

**Files**: `tests/integration/test_safety_integration.py`

- Test kill switch triggers all mechanisms
- Test circuit breaker trips on thresholds
- Test OMS idempotency and reconciliation
- Test integration with TradingController

---

## Phase 2: Data Source Plugin System (Week 2)

**Goal**: Enable extensible data sources with auto-discovery and feature catalog.

### Tasks

#### 2.1 Create Data Provider Registry

**New File**: `src/mt5-python_server/src/data_providers/registry.py`

```python
class DataProviderRegistry:
    - register_provider(name, provider_instance)
    - discover_features() -> List[Feature]
    - get_provider(name) -> DataProvider
    - check_health() -> Dict[str, bool]
```

**Integration**: Update `Server.__init__()` to initialize registry and discover features on startup.

#### 2.2 Enhance Base Provider Interface

**File**: `src/mt5-python_server/src/data_providers/base_provider.py`

- Add `get_features() -> List[Feature]` abstract method
- Add `Feature` dataclass with metadata (name, type, description, source)
- Add optional `collect_historical()` method

#### 2.3 Create Indicator Provider

**New File**: `src/mt5-python_server/src/data_providers/indicator_provider.py`

- Wraps existing `technical_indicators.py` utilities
- Provides RSI, MACD, Bollinger Bands, ATR, EMA features
- Declares feature metadata

#### 2.4 Create Feature Catalog System

**New File**: `src/mt5-python_server/src/features/catalog.py`

```python
class FeatureCatalog:
    - store_features(features: List[Feature])
    - get_all_features() -> List[Feature]
    - get_features_by_source(source: str) -> List[Feature]
    - update_feature_availability(name: str, available: bool)
```

**Database Changes**:

```sql
CREATE TABLE features (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) UNIQUE NOT NULL,
    data_type VARCHAR(20) NOT NULL,
    source VARCHAR(50) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    available BOOLEAN DEFAULT TRUE,
    min_value DOUBLE,
    max_value DOUBLE,
    mean_value DOUBLE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    INDEX idx_source (source),
    INDEX idx_category (category)
);
```

#### 2.5 Auto-Discovery on Startup

**File**: `src/mt5-python_server/src/server.py`

- Initialize `DataProviderRegistry` in `Server.__init__()`
- Register existing `PriceDataProvider` instances
- Create and register `IndicatorProvider` for each currency pair
- Call `registry.discover_features()` and store in `FeatureCatalog`
- Populate database `features` table

#### 2.6 Provider Extension Documentation

**New File**: `docs/data-source-guide/ADDING_DATA_SOURCES.md`

- Step-by-step guide for adding new providers
- Code examples
- Feature declaration patterns

---

## Phase 3: Experiment & Optuna Integration (Week 3)

**Goal**: Enable experiment configuration and automated hyperparameter search.

### Tasks

#### 3.1 Create Experiment Model

**New File**: `src/mt5-python_server/src/experiments/models.py`

```python
@dataclass
class Experiment:
    id: int
    name: str
    description: str
    features: List[str]  # Feature names
    currency_pairs: List[str]
    training_mode: str  # 'live' or 'historical'
    hyperparameters: Dict[str, Any]
    status: str  # 'created', 'training', 'completed', 'failed'
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
```

**Database Changes**:

```sql
CREATE TABLE experiments (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    features JSON NOT NULL,  -- Array of feature names
    currency_pairs JSON NOT NULL,  -- Array of symbols
    training_mode ENUM('live', 'historical') NOT NULL,
    hyperparameters JSON NOT NULL,
    status ENUM('created', 'training', 'completed', 'failed', 'paused') DEFAULT 'created',
    mlflow_run_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    INDEX idx_status (status)
);
```

#### 3.2 Create Experiment Builder

**New File**: `src/mt5-python_server/src/experiments/builder.py`

```python
class ExperimentBuilder:
    - create_experiment(name, description, features, pairs, mode, hyperparams) -> Experiment
    - validate_experiment(experiment) -> bool
    - clone_experiment(experiment_id) -> Experiment
```

#### 3.3 Create Experiment Runner

**New File**: `src/mt5-python_server/src/experiments/runner.py`

```python
class ExperimentRunner:
    - start_experiment(experiment_id) -> bool
    - stop_experiment(experiment_id) -> bool
    - get_experiment_status(experiment_id) -> Dict
```

**Integration**:

- Use existing `TrainingLoop` and `LiveTrainer`
- Create agent with experiment's hyperparameters
- Create environment with experiment's features
- Start MLflow run and link to experiment

#### 3.4 Integrate Optuna

**New File**: `src/mt5-python_server/src/experiments/optuna_tuner.py`

```python
class OptunaHyperparameterTuner:
    - create_study(experiment_id, metric='sharpe_ratio') -> Study
    - run_trials(n_trials, experiment_template) -> Dict
    - get_best_params(study_id) -> Dict
    - get_trial_results(study_id) -> List[Dict]
```

**Database Changes**:

```sql
CREATE TABLE optuna_studies (
    id INT PRIMARY KEY AUTO_INCREMENT,
    experiment_id INT NOT NULL,
    study_name VARCHAR(200),
    direction ENUM('maximize', 'minimize') DEFAULT 'maximize',
    metric VARCHAR(50),
    n_trials INT,
    status ENUM('running', 'completed', 'failed') DEFAULT 'running',
    best_params JSON,
    best_value DOUBLE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id),
    INDEX idx_experiment (experiment_id)
);

CREATE TABLE optuna_trials (
    id INT PRIMARY KEY AUTO_INCREMENT,
    study_id INT NOT NULL,
    trial_number INT,
    params JSON,
    value DOUBLE,
    state ENUM('running', 'complete', 'pruned', 'fail') DEFAULT 'running',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (study_id) REFERENCES optuna_studies(id),
    INDEX idx_study (study_id)
);
```

**Optuna Integration Points**:

- Define search space for each hyperparameter (from PRD Section 10.3)
- Objective function: Train model, evaluate on validation, return metric
- Use pruning to stop bad trials early
- Store trial results in database

#### 3.5 Enhance MLflow Integration

**File**: `src/mt5-python_server/src/mlops/experiment_tracker.py`

- Link MLflow runs to experiments (store `experiment_id` as tag)
- Log experiment configuration
- Store model artifacts with experiment metadata

---

## Phase 4: FastAPI Service (Week 4)

**Goal**: Create REST API and WebSocket service for dashboard communication.

### Tasks

#### 4.1 Set Up FastAPI Project Structure

**New Directory**: `api/`

```
api/
├── Dockerfile
├── requirements.txt
├── src/
│   ├── main.py
│   ├── config.py
│   ├── dependencies.py
│   ├── routers/
│   │   ├── features.py
│   │   ├── experiments.py
│   │   ├── hyperparameters.py
│   │   ├── models.py
│   │   ├── trading.py
│   │   └── performance.py
│   ├── schemas/
│   │   └── (Pydantic models)
│   ├── services/
│   │   ├── experiment_service.py
│   │   └── feature_service.py
│   └── websocket/
│       └── manager.py
```

#### 4.2 Implement Feature Catalog Endpoints

**File**: `api/src/routers/features.py`

- `GET /api/features` - List all features
- `GET /api/features/{feature_id}` - Get feature details
- `GET /api/features?source={source}` - Filter by source
- `GET /api/features?category={category}` - Filter by category

#### 4.3 Implement Experiment Endpoints

**File**: `api/src/routers/experiments.py`

- `POST /api/experiments` - Create experiment
- `GET /api/experiments` - List experiments
- `GET /api/experiments/{id}` - Get experiment details
- `POST /api/experiments/{id}/start` - Start training
- `POST /api/experiments/{id}/stop` - Stop training
- `POST /api/experiments/{id}/clone` - Clone experiment
- `DELETE /api/experiments/{id}` - Delete experiment

#### 4.4 Implement Hyperparameter Endpoints

**File**: `api/src/routers/hyperparameters.py`

- `POST /api/experiments/{id}/optuna/start` - Start Optuna search
- `GET /api/experiments/{id}/optuna/status` - Get search status
- `GET /api/experiments/{id}/optuna/trials` - Get trial results
- `GET /api/experiments/{id}/optuna/best` - Get best parameters

#### 4.5 Implement Model Endpoints

**File**: `api/src/routers/models.py`

- `GET /api/models` - List all models
- `GET /api/models/{id}` - Get model details
- `POST /api/models/{id}/promote` - Promote to paper/live
- `POST /api/models/{id}/rollback` - Rollback model

#### 4.6 Implement Trading Endpoints

**File**: `api/src/routers/trading.py`

- `GET /api/trading/status` - Get trading status
- `POST /api/trading/kill-switch/trigger` - Trigger kill switch
- `POST /api/trading/kill-switch/reset` - Reset kill switch
- `GET /api/trading/circuit-breaker/status` - Get circuit breaker status
- `POST /api/trading/circuit-breaker/reset` - Reset circuit breaker

#### 4.7 Implement WebSocket Manager

**File**: `api/src/websocket/manager.py`

- Real-time experiment progress updates
- Training metrics streaming
- Trade execution notifications
- Performance updates

**Channels** (from PRD Section 15.9):

- `/ws/experiments/{id}/progress`
- `/ws/trading/status`
- `/ws/performance/updates`

#### 4.8 Update Docker Compose

**File**: `docker-compose.yml`

- Add `api` service
- Configure FastAPI on port 8080
- Set up dependencies (MariaDB, MLflow)

---

## Phase 5: React Dashboard (Week 5-6)

**Goal**: Build complete experimentation UI for creating and managing experiments.

**📋 Detailed Plan**: See `phase_5_react_dashboard_a1b2c3d4.plan.md` for comprehensive implementation details, including 2FA for sensitive operations, MT5 Accounts page, WebSocket integration, and all component specifications.

### Tasks

#### 5.1 Initialize React Project

**New Directory**: `dashboard/`

```
dashboard/
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── tsconfig.json
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── components/
    ├── pages/
    ├── hooks/
    ├── services/
    ├── stores/
    └── types/
```

**Dependencies**: Vite, React, TypeScript, Tailwind CSS, shadcn/ui, Zustand, TanStack Query, Lightweight Charts

#### 5.2 Implement Dashboard Layout

**File**: `dashboard/src/components/Layout.tsx`

- Sidebar navigation
- Header with status indicators
- Main content area
- Responsive design

#### 5.3 Implement Experiment Builder Page

**File**: `dashboard/src/pages/ExperimentBuilder.tsx`

- Feature selection (multi-select with filtering)
- Currency pair selection
- Training mode selection
- Hyperparameter configuration (manual/Optuna toggle)
- Form validation
- Save/start experiment actions

#### 5.4 Implement Hyperparameter Search Page

**File**: `dashboard/src/pages/HyperparameterSearch.tsx`

- Optuna search configuration
- Real-time trial progress (WebSocket)
- Parameter importance visualization
- Best parameters display
- Apply to experiment button

#### 5.5 Implement Training Monitor Page

**File**: `dashboard/src/pages/TrainingMonitor.tsx`

- List of active experiments
- Real-time metrics charts (WebSocket)
- Training progress indicators
- Stop/pause controls

#### 5.6 Implement Feature Catalog Page

**File**: `dashboard/src/pages/FeatureCatalog.tsx`

- Table of all features
- Filtering by source/category
- Feature details modal
- Availability status indicators

#### 5.7 Implement Model Registry Page

**File**: `dashboard/src/pages/ModelRegistry.tsx`

- List of trained models
- Lifecycle stages (training → paper → live)
- Promotion controls
- Model performance summary

#### 5.8 Implement Live Trading Page

**File**: `dashboard/src/pages/LiveTrading.tsx`

- Active positions display
- Kill switch controls
- Circuit breaker status
- Trade history

#### 5.9 Set Up API Client

**File**: `dashboard/src/services/api.ts`

- Axios instance with base URL
- Request interceptors
- Error handling

#### 5.10 Set Up WebSocket Client

**File**: `dashboard/src/services/websocket.ts`

- WebSocket connection management
- Channel subscriptions
- Message handling

---

## Phase 6: Live Performance Tracking (Week 6-7)

**Goal**: Track and display trading performance metrics.

### Tasks

#### 6.1 Create Performance Database Tables

**File**: `database/scripts/06_performance.sql`

```sql
CREATE TABLE trades (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    experiment_id INT NOT NULL,
    account_login INT NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    order_type ENUM('BUY', 'SELL') NOT NULL,
    entry_price DOUBLE NOT NULL,
    exit_price DOUBLE,
    volume DOUBLE NOT NULL,
    pnl DOUBLE,
    pnl_pct DOUBLE,
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    status ENUM('OPEN', 'CLOSED') DEFAULT 'OPEN',
    FOREIGN KEY (experiment_id) REFERENCES experiments(id),
    INDEX idx_experiment (experiment_id),
    INDEX idx_account (account_login),
    INDEX idx_status (status)
);

CREATE TABLE equity_curve (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    experiment_id INT NOT NULL,
    account_login INT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    balance DOUBLE NOT NULL,
    equity DOUBLE NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id),
    INDEX idx_experiment_timestamp (experiment_id, timestamp)
);

CREATE TABLE performance_metrics (
    id INT PRIMARY KEY AUTO_INCREMENT,
    experiment_id INT NOT NULL,
    account_login INT NOT NULL,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    total_trades INT,
    winning_trades INT,
    losing_trades INT,
    win_rate DOUBLE,
    total_pnl DOUBLE,
    sharpe_ratio DOUBLE,
    max_drawdown DOUBLE,
    max_drawdown_pct DOUBLE,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id),
    INDEX idx_experiment_period (experiment_id, period_start)
);
```

#### 6.2 Implement Trade Logging

**File**: `src/mt5-python_server/src/performance/trade_logger.py`

```python
class TradeLogger:
    - log_trade_entry(experiment_id, account, symbol, order_type, price, volume)
    - log_trade_exit(trade_id, exit_price, pnl)
    - get_open_trades(experiment_id) -> List[Trade]
```

**Integration**: Update `ActionExecutor` to log trades on execution.

#### 6.3 Implement Metrics Calculator

**File**: `src/mt5-python_server/src/performance/metrics_calculator.py`

```python
class PerformanceMetricsCalculator:
    - calculate_win_rate(trades) -> float
    - calculate_sharpe_ratio(returns, risk_free_rate=0) -> float
    - calculate_max_drawdown(equity_curve) -> Tuple[float, float]
    - calculate_total_pnl(trades) -> float
```

#### 6.4 Implement Equity Curve Collection

**File**: `src/mt5-python_server/src/performance/equity_tracker.py`

```python
class EquityTracker:
    - record_snapshot(experiment_id, account, balance, equity)
    - get_equity_curve(experiment_id, start_date, end_date) -> List[Dict]
```

**Integration**: Periodic snapshot collection (every N minutes) in training loop.

#### 6.5 Create Performance API Endpoints

**File**: `api/src/routers/performance.py`

- `GET /api/performance/portfolio` - Portfolio-level metrics
- `GET /api/performance/experiments/{id}` - Experiment-specific metrics
- `GET /api/performance/experiments/{id}/trades` - Trade history
- `GET /api/performance/experiments/{id}/equity-curve` - Equity curve data

#### 6.6 Implement Portfolio Performance Page

**File**: `dashboard/src/pages/PortfolioPerformance.tsx`

- Aggregate metrics across all experiments
- Equity curve chart (Lightweight Charts)
- Performance comparison table
- Time period filters

#### 6.7 Implement Model Performance Page

**File**: `dashboard/src/pages/ModelPerformance.tsx`

- Individual model metrics
- Trade history table
- Win/loss distribution
- Drawdown visualization

#### 6.8 Real-Time Performance Updates

- WebSocket channel for performance updates
- Auto-refresh metrics every N seconds
- Live equity curve updates

---

## Phase 7: MLOps & Model Lifecycle (Week 8)

**Goal**: Complete model registry and promotion workflow.

### Tasks

#### 7.1 Enhance Model Registry

**File**: `src/mt5-python_server/src/mlops/model_promoter.py`

- Complete promotion workflow (training → paper → live)
- Validation gates before promotion
- Rollback functionality

**Database Changes**:

```sql
CREATE TABLE models (
    id INT PRIMARY KEY AUTO_INCREMENT,
    experiment_id INT NOT NULL,
    name VARCHAR(200) NOT NULL,
    version INT NOT NULL,
    mlflow_run_id VARCHAR(100),
    model_path VARCHAR(500),
    stage ENUM('training', 'paper', 'live', 'archived') DEFAULT 'training',
    promoted_at TIMESTAMP NULL,
    promoted_by VARCHAR(100),
    performance_metrics JSON,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id),
    UNIQUE KEY unique_experiment_version (experiment_id, version),
    INDEX idx_stage (stage)
);
```

#### 7.2 Implement Paper Trading Validation

**File**: `src/mt5-python_server/src/mlops/paper_validator.py`

```python
class PaperTradingValidator:
    - validate_model(model_id, min_trades=100, min_win_rate=0.5) -> bool
    - get_validation_report(model_id) -> Dict
```

**Validation Criteria** (from PRD):

- Minimum number of trades
- Minimum win rate
- Maximum drawdown
- Positive Sharpe ratio

#### 7.3 Implement Promotion Workflow

**File**: `src/mt5-python_server/src/mlops/promotion_workflow.py`

```python
class PromotionWorkflow:
    - promote_to_paper(model_id) -> bool
    - promote_to_live(model_id, approver) -> bool
    - rollback_model(model_id) -> bool
```

#### 7.4 Set Up MLflow Server

**File**: `docker-compose.yml`

- MLflow service already configured (port 5000)
- Verify connectivity from API and training services

---

## Phase 8: Testing & Polish (Week 9)

**Goal**: Comprehensive testing and bug fixes.

### Tasks

#### 8.1 Integration Tests

**Files**: `tests/integration/`

- Test data provider registry and feature discovery
- Test experiment creation and execution
- Test Optuna search completion
- Test model promotion workflow
- Test performance metrics calculation

#### 8.2 End-to-End Tests

**Files**: `tests/e2e/`

- Test complete experiment lifecycle (create → train → paper → live)
- Test dashboard workflows
- Test API endpoints with real data

#### 8.3 Performance Optimization

- Optimize feature extraction (caching)
- Optimize database queries (indexes)
- Optimize WebSocket message frequency

#### 8.4 Bug Fixes and Polish

- Fix any issues found during testing
- Improve error messages
- Add loading states to UI
- Enhance logging

#### 8.5 Documentation

**Files**: `docs/`

- API documentation (OpenAPI/Swagger)
- User guide for dashboard
- Developer guide for adding data sources
- Deployment guide

---

## Database Migration Strategy

All new tables should be added via migration scripts in `database/scripts/`:

- `06_features.sql` - Feature catalog tables
- `07_experiments.sql` - Experiment and Optuna tables
- `08_performance.sql` - Performance tracking tables
- `09_models.sql` - Model registry tables

Run migrations in order before starting each phase.

---

## Dependencies Between Phases

```
Phase 1 (Safety) → Required for all trading operations
Phase 2 (Data Sources) → Required for Phase 3 (Experiments)
Phase 3 (Experiments) → Required for Phase 4 (API) and Phase 5 (Dashboard)
Phase 4 (API) → Required for Phase 5 (Dashboard)
Phase 5 (Dashboard) → Can start in parallel with Phase 6
Phase 6 (Performance) → Depends on Phase 3 (Experiments)
Phase 7 (MLOps) → Depends on Phase 3 (Experiments)
Phase 8 (Testing) → Depends on all previous phases
```

---

## Key Integration Points

1. **Server Initialization** (`server.py`): Initialize registry, catalog, experiments on startup
2. **Trading Controller** (`trading_controller.py`): Integrate kill switch, circuit breaker, OMS
3. **Training Loop** (`training_loop.py`): Link to experiments, log to MLflow, track performance
4. **Action Executor** (`action_executor.py`): Log trades, update OMS, check safety mechanisms

---

## Success Criteria

- ✅ All safety mechanisms operational and tested
- ✅ Data providers auto-discover and features appear in catalog
- ✅ Experiments can be created and trained via dashboard
- ✅ Optuna search finds optimal hyperparameters
- ✅ Models progress through lifecycle (training → paper → live)
- ✅ Performance metrics accurately tracked and displayed
- ✅ Dashboard provides complete experimentation workflow
- ✅ All critical paths tested and documented