# Runtime Scenario: Model Promotion Flow

## Purpose
This diagram answers: **How does a model progress through the lifecycle stages from training to production?**

## Scope
- **Includes**: Model stages, promotion workflow, paper trading validation, production deployment
- **Excludes**: Training details (separate diagram)

## Source of Truth References
| Step | Evidence Path |
|------|---------------|
| Model API | `src/api/src/routers/models.py` |
| Model Service | `src/api/src/services/model_service.py` |
| Model Schema | `src/database/scripts/10_models.sql` |
| Paper Session Schema | `src/database/scripts/10_models.sql:27-44` |
| Dashboard Pages | `src/dashboard/src/pages/ModelRegistry.tsx` |

## Model Lifecycle Stages

```mermaid
stateDiagram-v2
    [*] --> training: Experiment completes
    training --> staging: Auto-register
    staging --> paper: Promote to Paper
    paper --> production: Promote to Production
    production --> archived: Archive
    staging --> archived: Archive
    paper --> staging: Rollback
    production --> paper: Rollback
    archived --> [*]
    
    note right of training: Model being trained
    note right of staging: Ready for validation
    note right of paper: Paper trading validation
    note right of production: Live trading
    note right of archived: No longer active
```

## Promotion Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant Dashboard
    participant API as FastAPI
    participant DB as PostgreSQL
    participant MLflow as MLflow
    participant Server as Trading Server
    participant Account as MT5 Account

    %% View Models
    User->>Dashboard: Navigate to Model Registry
    Dashboard->>API: GET /api/models
    API->>DB: SELECT * FROM models
    DB-->>API: Model list
    API-->>Dashboard: Models with stages
    Dashboard-->>User: Display model registry

    %% Promote to Paper Trading
    User->>Dashboard: Select model (staging)<br/>Click "Promote to Paper"
    Dashboard->>Dashboard: Prompt for TOTP code
    User->>Dashboard: Enter TOTP code
    
    Dashboard->>API: POST /api/models/{id}/promote/paper<br/>{confirm: true, totp_token: "123456"}
    
    API->>API: Verify TOTP token
    API->>DB: Get model details
    DB-->>API: Model (stage: staging)
    
    API->>DB: UPDATE models SET stage='paper'
    API->>DB: INSERT INTO paper_trading_sessions<br/>{model_id, status: 'running', start_balance}
    
    API-->>Dashboard: Model updated
    Dashboard-->>User: Promoted to Paper Trading

    %% Paper Trading Execution
    Note over Server,Account: Paper trading session runs...
    
    loop Paper Trading
        Server->>Server: Model generates signals
        Server->>Server: Execute paper trades (simulated)
        Server->>DB: Log paper trades
        Server->>API: WebSocket update
        API->>Dashboard: /ws/models/{id}/paper-session
        Dashboard-->>User: Real-time paper results
    end

    %% View Paper Results
    User->>Dashboard: Check paper trading results
    Dashboard->>API: GET /api/models/{id}/paper-sessions
    API->>DB: SELECT FROM paper_trading_sessions
    DB-->>API: Session results
    API-->>Dashboard: Sessions with metrics
    Dashboard-->>User: Display P&L, win rate, Sharpe

    %% Stop Paper Session
    User->>Dashboard: Click "Stop Paper Session"
    Dashboard->>API: POST /api/models/{id}/paper-sessions/{sid}/stop
    API->>DB: UPDATE paper_trading_sessions SET status='completed'
    API-->>Dashboard: Session stopped
    
    %% Promote to Production
    User->>Dashboard: Click "Promote to Production"
    Dashboard->>Dashboard: Show validation checklist
    
    Note over Dashboard: Validation Requirements:<br/>- Minimum paper trades<br/>- Positive returns<br/>- Risk metrics within bounds

    Dashboard->>API: GET /api/models/{id}/validation
    API->>DB: Calculate validation metrics
    DB-->>API: Validation result
    API-->>Dashboard: {passed: true, metrics: {...}}
    
    alt Validation Passed
        Dashboard->>Dashboard: Prompt for TOTP
        User->>Dashboard: Enter TOTP code
        
        Dashboard->>API: POST /api/models/{id}/promote/production<br/>{confirm: true, totp_token: "654321"}
        
        API->>API: Verify TOTP token
        API->>DB: UPDATE models SET stage='production'
        API->>DB: UPDATE models SET promoted_at=NOW()
        
        %% Notify connected accounts
        API->>Server: Notify model promotion
        Server->>Account: Update active model
        
        API-->>Dashboard: Model in production
        Dashboard-->>User: 🎉 Model deployed!
    else Validation Failed
        Dashboard-->>User: Validation failed - show issues
    end

    %% Assign to Account
    User->>Dashboard: Navigate to MT5 Accounts
    Dashboard->>API: GET /api/mt5-accounts
    API-->>Dashboard: Account list
    
    User->>Dashboard: Select account, assign model
    Dashboard->>API: POST /api/mt5-accounts/{id}/assign-model<br/>{model_id, totp_code}
    
    API->>DB: Deactivate previous assignment
    API->>DB: INSERT INTO account_model_assignments
    API-->>Dashboard: Model assigned
    Dashboard-->>User: Model now trading on account
```

## Stage Transitions

| From | To | Requirements | API Endpoint |
|------|----|--------------|--------------|
| staging | paper | TOTP verification | `POST /models/{id}/promote/paper` |
| paper | production | TOTP + validation passed | `POST /models/{id}/promote/production` |
| production | paper | TOTP verification | `POST /models/{id}/rollback` |
| paper | staging | TOTP verification | `POST /models/{id}/rollback` |
| any | archived | TOTP verification | `POST /models/{id}/archive` |

## Validation Requirements (Production Promotion)

| Metric | Requirement |
|--------|-------------|
| Paper trades | Minimum number executed |
| Total P&L | Must be positive |
| Win rate | Above threshold |
| Max drawdown | Below threshold |
| Sharpe ratio | Above threshold |

## Paper Trading Session

| Field | Description |
|-------|-------------|
| `model_id` | Associated model |
| `status` | running/completed/stopped |
| `start_balance` | Initial simulated balance |
| `current_balance` | Current balance |
| `total_trades` | Number of trades |
| `winning_trades` | Profitable trades |
| `pnl` | Profit/Loss |
| `sharpe_ratio` | Risk-adjusted return |
| `max_drawdown` | Maximum drawdown |

## WebSocket Channels

| Channel | Purpose |
|---------|---------|
| `/ws/models` | All model lifecycle updates |
| `/ws/models/{id}/status` | Specific model status changes |
| `/ws/models/{id}/paper-session` | Paper trading updates |
| `/ws/models/{id}/validation` | Validation status |

## Security Controls

1. **TOTP Required**: All promotion/rollback actions require 2FA
2. **Confirmation**: Explicit `confirm: true` flag required
3. **Audit Trail**: `promoted_at` and `promoted_by` tracked
4. **Ownership**: Only account owners can assign models

## Assumptions
- **None** - All promotion flows verified in codebase
