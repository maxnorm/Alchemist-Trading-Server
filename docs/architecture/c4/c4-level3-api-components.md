# C4 Level 3 - API Container Components

## Purpose
This diagram answers: **What are the internal components of the FastAPI REST API service and how do they collaborate?**

## Scope
- **Includes**: Routers, services, middleware, WebSocket handlers, database access
- **Excludes**: Implementation details within individual components

## Source of Truth References
| Component | Evidence Path |
|-----------|---------------|
| Main Application | `src/api/src/main.py` |
| Routers | `src/api/src/routers/*.py` |
| Services | `src/api/src/services/*.py` |
| Middleware | `src/api/src/middleware/auth.py`, `src/api/src/middleware/metrics.py` |
| WebSocket | `src/api/src/websocket/manager.py`, `src/api/src/websocket/channels.py` |
| Schemas | `src/api/src/schemas/*.py` |
| Database | `src/api/src/database/*.py` |
| Config | `src/api/src/config.py` |

## Component Diagram

```mermaid
flowchart TB
    subgraph External["External Systems"]
        Client["Dashboard / API Client"]
        Clerk["Clerk Auth Service"]
        TradingServer["Trading Server"]
        Postgres[("PostgreSQL")]
        Redis[("Redis")]
        MLflow["MLflow"]
    end

    subgraph FastAPIContainer["⚙️ FastAPI API Container"]
        subgraph Middleware["🛡️ Middleware Layer"]
            CORS["CORS Middleware"]
            Metrics["Metrics Middleware<br/>(Prometheus)"]
            Auth["Auth Middleware<br/>(Clerk JWT)"]
        end

        subgraph Routers["🔀 REST Routers"]
            HealthRouter["health.py<br/>/health, /ready"]
            FeaturesRouter["features.py<br/>/api/features"]
            ExperimentsRouter["experiments.py<br/>/api/experiments"]
            HyperparamsRouter["hyperparameters.py<br/>/api/hyperparameters"]
            ModelsRouter["models.py<br/>/api/models"]
            TradingRouter["trading.py<br/>/api/trading"]
            PerformanceRouter["performance.py<br/>/api/performance"]
            MT5AccountsRouter["mt5_accounts.py<br/>/api/mt5-accounts"]
            DataRouter["data.py<br/>/api/data"]
            SchemaRouter["schema.py<br/>/api/schema"]
            LineageRouter["lineage.py<br/>/api/lineage"]
        end

        subgraph WebSocket["📡 WebSocket Layer"]
            WSManager["Connection Manager"]
            WSChannels["Channel Handlers"]
            
            subgraph Channels["WebSocket Channels"]
                WSTicks["/ws/ticks"]
                WSTraining["/ws/training"]
                WSOptuna["/ws/optuna"]
                WSPositions["/ws/positions"]
                WSAlerts["/ws/alerts"]
                WSModels["/ws/models"]
                WSMT5["/ws/accounts/mt5"]
            end
        end

        subgraph Services["🔧 Business Services"]
            ExperimentSvc["experiment_service.py"]
            FeatureSvc["feature_service.py"]
            ModelSvc["model_service.py"]
            TradingSvc["trading_service.py"]
            PerformanceSvc["performance_service.py"]
            MT5AccountsSvc["mt5_accounts_service.py"]
            ClerkSvc["clerk_service.py"]
            DatabaseSvc["database.py"]
        end

        subgraph Infra["🏗️ Infrastructure"]
            AlertConsumer["Alert Consumer<br/>(Redis Pub/Sub)"]
            DBSession["Database Session<br/>(SQLAlchemy)"]
        end

        subgraph Schemas["📋 Pydantic Schemas"]
            SchemaModels["experiments.py<br/>features.py<br/>models.py<br/>trading.py<br/>mt5_accounts.py"]
        end
    end

    %% External connections
    Client -->|"HTTP/WSS"| CORS
    Auth -->|"Verify JWT"| Clerk
    
    %% Middleware chain
    CORS --> Metrics --> Auth --> Routers
    CORS --> Metrics --> WebSocket

    %% Router to Service
    ExperimentsRouter --> ExperimentSvc
    FeaturesRouter --> FeatureSvc
    ModelsRouter --> ModelSvc
    TradingRouter --> TradingSvc
    PerformanceRouter --> PerformanceSvc
    MT5AccountsRouter --> MT5AccountsSvc

    %% WebSocket routing
    WSManager --> WSChannels
    WSChannels --> Channels
    AlertConsumer -->|"Broadcast"| WSManager

    %% Service to Infrastructure
    ExperimentSvc --> DBSession
    FeatureSvc --> DBSession
    ModelSvc --> DBSession
    TradingSvc --> DBSession
    ModelSvc --> TradingServer
    MT5AccountsSvc --> DBSession
    ClerkSvc --> Auth

    %% Infrastructure to External
    DBSession --> Postgres
    AlertConsumer --> Redis
    ModelSvc --> MLflow

    %% Schemas used throughout
    Routers -.->|"Validate"| SchemaModels
    Services -.->|"Return"| SchemaModels

    style FastAPIContainer fill:#f8f9fa,stroke:#dee2e6
    style Auth fill:#6c5ce7,stroke:#5649c0,color:#fff
    style WSManager fill:#00b894,stroke:#00997b,color:#fff
```

## Component Details

### Middleware Layer
| Component | File | Responsibility |
|-----------|------|----------------|
| CORS | `main.py` (inline) | Cross-origin request handling |
| Metrics | `middleware/metrics.py` | Prometheus metrics collection |
| Auth | `middleware/auth.py` | Clerk JWT token verification |

### REST Routers (all prefixed with `/api`)
| Router | File | Endpoints |
|--------|------|-----------|
| Health | `health.py` | `/health`, `/ready` |
| Features | `features.py` | GET/POST `/features`, feature catalog |
| Experiments | `experiments.py` | CRUD `/experiments`, start/stop/clone |
| Hyperparameters | `hyperparameters.py` | Optuna search management |
| Models | `models.py` | Model registry, promotion, paper sessions |
| Trading | `trading.py` | Trading status, kill switch, circuit breaker |
| Performance | `performance.py` | Portfolio/model metrics, equity curves |
| MT5 Accounts | `mt5_accounts.py` | Account registration, assignment |
| Data | `data.py` | Data access and queries |
| Schema | `schema.py` | Schema registry |
| Lineage | `lineage.py` | Data lineage tracking |

### WebSocket Channels
| Channel | Purpose |
|---------|---------|
| `/ws/ticks` | Real-time tick data streaming |
| `/ws/training` | Training metrics updates |
| `/ws/optuna` | Hyperparameter search progress |
| `/ws/positions` | Open positions updates |
| `/ws/alerts` | System alerts and notifications |
| `/ws/models` | Model lifecycle updates |
| `/ws/accounts/mt5` | MT5 connection status |
| `/ws/performance` | Performance metrics updates |

### Services
| Service | Responsibility |
|---------|----------------|
| `experiment_service` | Experiment CRUD, status management |
| `feature_service` | Feature catalog queries |
| `model_service` | Model registry, promotion workflow |
| `trading_service` | Kill switch, circuit breaker, positions |
| `performance_service` | Metrics calculation, equity curves |
| `mt5_accounts_service` | Account lifecycle, model assignments |
| `clerk_service` | Clerk API integration |
| `database` | Database session management |

## Data Flow
1. **Request arrives** → CORS → Metrics → Auth middleware
2. **Auth verifies** JWT with Clerk → extracts user_id and roles
3. **Router handles** request → calls appropriate service
4. **Service executes** business logic → queries database
5. **Response returned** via Pydantic schema validation

## Assumptions
- **None** - All components verified in source code
