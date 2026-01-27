---
name: Phase 7 MLOps Model Lifecycle
overview: Complete the MLOps model lifecycle system with database-backed registry, paper trading stage, validation gates, 2FA for production promotions, and full API/dashboard integration.
todos:
  - id: phase7-database-schema
    content: Create database schema for models and paper_trading_sessions tables
    status: completed
  - id: phase7-model-registry
    content: Implement ModelRegistry class for database-backed model tracking
    status: completed
  - id: phase7-paper-stage
    content: Add Paper stage to ModelPromoter lifecycle
    status: completed
  - id: phase7-paper-session-manager
    content: Create PaperTradingSessionManager for session tracking
    status: completed
  - id: phase7-2fa-support
    content: Add 2FA support for production promotions
    status: completed
  - id: phase7-model-api
    content: Create API endpoints for model lifecycle management
    status: completed
  - id: phase7-training-integration
    content: Integrate model registration with ExperimentRunner
    status: completed
  - id: phase7-dashboard-page
    content: Create Model Registry dashboard page with promotion workflow
    status: completed
  - id: phase7-websocket-updates
    content: Add WebSocket channels for model lifecycle updates
    status: completed
  - id: phase7-testing
    content: Write integration tests for model lifecycle
    status: completed
---

# Phase 7: MLOps & Model Lifecycle Completion

## Overview

Phase 7 completes the model lifecycle management system by implementing a database-backed model registry, adding the Paper trading stage, integrating paper trading validation, adding 2FA for production promotions, and providing full API and dashboard support for model management.

## Current State Analysis

### What Exists

- `ModelPromoter` class with MLflow integration (stages: None, Staging, Production, Archived)
- Paper trading validation logic in `ModelPromoter.validate_for_production()`
- Rollback functionality in `ModelPromoter`
- `PaperTradingEnv` for paper trading execution
- MLflow experiment tracking

### What's Missing

- Database-backed model registry (PRD requires `models` table)
- Paper stage in lifecycle (PRD: Training → Staging → Paper → Production)
- Paper trading session tracking (`paper_trading_sessions` table)
- Integration between paper trading results and model validation
- 2FA support for production promotions
- API endpoints for model lifecycle management
- Dashboard UI for model registry and promotion workflow
- Synchronization between MLflow and database model registry

## Implementation Plan

### 7.1 Database Schema for Model Registry

**File**: `database/scripts/09_models.sql`

Create database tables matching PRD schema:

```sql
-- Model registry (matches PRD Section 17.4)
CREATE TABLE models (
    id INT AUTO_INCREMENT PRIMARY KEY,
    version VARCHAR(50) UNIQUE NOT NULL,
    experiment_id INT,
    stage VARCHAR(20) NOT NULL DEFAULT 'staging',  -- staging, paper, production, archived
    features JSON NOT NULL,
    hyperparameters JSON NOT NULL,
    metrics JSON,
    mlflow_model_uri VARCHAR(500),
    mlflow_run_id VARCHAR(100),
    paper_trading_results JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    promoted_at TIMESTAMP NULL,
    promoted_by INT,  -- dashboard_users.id (for audit)
    FOREIGN KEY (experiment_id) REFERENCES experiments(id),
    INDEX idx_stage (stage),
    INDEX idx_experiment (experiment_id)
);

-- Paper trading sessions
CREATE TABLE paper_trading_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'running',  -- running, completed, stopped
    start_balance DECIMAL(15, 2),
    current_balance DECIMAL(15, 2),
    total_trades INT DEFAULT 0,
    winning_trades INT DEFAULT 0,
    pnl DECIMAL(15, 2) DEFAULT 0,
    sharpe_ratio DECIMAL(10, 4),
    max_drawdown DECIMAL(10, 4),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP NULL,
    FOREIGN KEY (model_id) REFERENCES models(id),
    INDEX idx_model_status (model_id, status)
);
```

### 7.2 Enhance ModelPromoter with Paper Stage

**File**: `src/mt5-python_server/src/mlops/model_promoter.py`

Update `ModelStage` enum to include Paper:

```python
class ModelStage(Enum):
    TRAINING = "Training"
    STAGING = "Staging"
    PAPER = "Paper"
    PRODUCTION = "Production"
    ARCHIVED = "Archived"
```

Add methods:

- `promote_to_paper(version, approver)` - Promote from Staging to Paper
- `get_paper_model()` - Get current paper trading model
- `start_paper_trading_session(model_id)` - Initialize paper trading session
- `end_paper_trading_session(session_id)` - End session and collect metrics

### 7.3 Create Database Model Registry Service

**New File**: `src/mt5-python_server/src/mlops/model_registry.py`

```python
class ModelRegistry:
    """
    Database-backed model registry that syncs with MLflow.
    
    Responsibilities:
  - Register models after training completes
  - Track model lifecycle stages in database
  - Sync with MLflow model registry
  - Link models to experiments
  - Store paper trading results
    """
    
    Methods:
  - register_model(experiment_id, mlflow_run_id, features, hyperparams) -> Model
  - get_model(model_id) -> Model
  - get_models_by_stage(stage) -> List[Model]
  - update_model_stage(model_id, new_stage, promoted_by)
  - store_paper_trading_results(model_id, results)
  - sync_with_mlflow() - Ensure database and MLflow are in sync
```

**Integration Points**:

- Called from `ExperimentRunner` when training completes
- Called from `ModelPromoter` when stages change
- Called from paper trading environment when session ends

### 7.4 Implement Paper Trading Session Manager

**New File**: `src/mt5-python_server/src/mlops/paper_session_manager.py`

```python
class PaperTradingSessionManager:
    """
    Manages paper trading sessions for model validation.
    
    Responsibilities:
  - Create paper trading sessions
  - Track session metrics in real-time
  - Calculate validation metrics
  - Link sessions to models
    """
    
    Methods:
  - create_session(model_id, start_balance) -> Session
  - update_session_metrics(session_id, balance, trades)
  - end_session(session_id) -> Dict[metrics]
  - get_session_metrics(session_id) -> Dict
  - validate_session(session_id, criteria) -> ValidationResult
```

**Integration Points**:

- Called from `PaperTradingEnv` when session starts/ends
- Called from `ModelPromoter` for validation
- Updates `paper_trading_sessions` table

### 7.5 Add 2FA Support for Production Promotions

**New File**: `src/mt5-python_server/src/mlops/two_factor_auth.py`

```python
class TwoFactorAuth:
    """
    TOTP-based 2FA for sensitive operations.
    
    Uses same TOTP implementation as dashboard authentication.
    """
    
    Methods:
  - verify_totp(user_id, token) -> bool
  - require_2fa_for_promotion() -> bool
```

**Integration Points**:

- `ModelPromoter.promote_to_production()` requires 2FA token
- API endpoint validates 2FA before promotion
- Dashboard prompts for 2FA code

### 7.6 Create Model Lifecycle API Endpoints

**File**: `api/src/routers/models.py` (create if doesn't exist)

Endpoints:

- `GET /api/models` - List all models with filters (stage, experiment_id)
- `GET /api/models/{id}` - Get model details
- `POST /api/models/{id}/promote/staging` - Promote to staging
- `POST /api/models/{id}/promote/paper` - Promote to paper
- `POST /api/models/{id}/promote/production` - Promote to production (requires 2FA)
- `POST /api/models/{id}/rollback` - Rollback production model
- `GET /api/models/{id}/paper-sessions` - Get paper trading sessions
- `POST /api/models/{id}/paper-sessions/start` - Start paper trading session
- `POST /api/models/{id}/paper-sessions/{session_id}/stop` - Stop session
- `GET /api/models/{id}/validation` - Get validation status

**Schemas**: `api/src/schemas/models.py`

- `ModelResponse`, `ModelPromoteRequest`, `PaperSessionResponse`, `ValidationResultResponse`

### 7.7 Integrate Model Registration with Training

**File**: `src/mt5-python_server/src/experiments/runner.py`

Update `ExperimentRunner` to:

- Register model in database when training completes
- Link model to experiment and MLflow run
- Set initial stage to "Training" → auto-promote to "Staging" on completion
- Store model metadata (features, hyperparameters, metrics)

### 7.8 Create Model Registry Dashboard Page

**File**: `dashboard/src/pages/ModelRegistry.tsx`

Features:

- Table of all models with stage badges
- Filter by stage (Training, Staging, Paper, Production, Archived)
- Model details modal (features, hyperparameters, metrics)
- Promotion workflow UI:
                - Promote to Paper button (for Staging models)
                - Start Paper Trading button
                - View Paper Results button
                - Promote to Production button (with 2FA prompt)
                - Rollback button (for Production models)
- Paper trading session status display
- Validation status indicators

### 7.9 Enhance Model Promoter with Database Integration

**File**: `src/mt5-python_server/src/mlops/model_promoter.py`

Update to:

- Use `ModelRegistry` for database operations
- Sync stage changes with both MLflow and database
- Store promotion audit trail (who, when, why)
- Link paper trading sessions to models
- Validate using `PaperTradingSessionManager`

### 7.10 WebSocket Updates for Model Lifecycle

**File**: `api/src/websocket/manager.py`

Add channels:

- `/ws/models/{id}/status` - Model stage changes
- `/ws/models/{id}/paper-session` - Paper trading session updates
- `/ws/models/{id}/validation` - Validation status updates

### 7.11 Testing

**Files**: `tests/integration/test_model_lifecycle.py`

Test cases:

- Model registration after training
- Stage transitions (Training → Staging → Paper → Production)
- Paper trading session creation and metrics collection
- Validation criteria checking
- 2FA requirement for production promotion
- Rollback functionality
- Database-MLflow synchronization

## Database Migration

Run migration script before starting:

```bash
mysql -u root -p < database/scripts/09_models.sql
```

## Integration Flow

```
Training Complete
    ↓
ExperimentRunner registers model (stage: Training)
    ↓
Auto-promote to Staging
    ↓
User promotes to Paper via dashboard
    ↓
Start Paper Trading Session
    ↓
PaperTradingEnv executes trades, updates session metrics
    ↓
End Paper Trading Session
    ↓
ModelPromoter validates against criteria
    ↓
If passed: User promotes to Production (with 2FA)
    ↓
Model in Production, previous Production → Archived
```

## Success Criteria

- ✅ Models automatically registered after training
- ✅ Database and MLflow stay synchronized
- ✅ Paper trading sessions tracked and validated
- ✅ Production promotion requires 2FA
- ✅ Complete audit trail for all promotions
- ✅ Dashboard shows full model lifecycle
- ✅ Rollback works correctly
- ✅ All API endpoints functional

## Dependencies

- Phase 3: Experiments (for model registration)
- Phase 4: FastAPI (for API endpoints)
- Phase 5: Dashboard (for UI)
- Phase 6: Performance tracking (for paper trading metrics)

## Files to Create/Modify

**New Files**:

- `database/scripts/09_models.sql`
- `src/mt5-python_server/src/mlops/model_registry.py`
- `src/mt5-python_server/src/mlops/paper_session_manager.py`
- `src/mt5-python_server/src/mlops/two_factor_auth.py`
- `api/src/routers/models.py`
- `api/src/schemas/models.py`
- `dashboard/src/pages/ModelRegistry.tsx`
- `tests/integration/test_model_lifecycle.py`

**Modified Files**:

- `src/mt5-python_server/src/mlops/model_promoter.py` (add Paper stage, database integration)
- `src/mt5-python_server/src/experiments/runner.py` (register models)
- `api/src/websocket/manager.py` (add model channels)
- `src/mt5-python_server/src/environments/paper_env.py` (integrate with session manager)