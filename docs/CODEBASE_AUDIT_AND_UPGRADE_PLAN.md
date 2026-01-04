# Codebase Audit & Upgrade Plan
## AI Forex Trading System - Deep Technical Review

**Date:** 2025-01-27  
**Auditor Role:** Senior Software + Infrastructure Engineer (AI Trading Systems, DRL/RL, MLOps)  
**Scope:** Complete codebase audit with research-backed recommendations for modular, production-ready architecture

---

## Executive Summary

1. **Data Architecture**: Tick ingestion works but lacks unified event bus; timezone normalization exists but needs validation; no systematic data quality gates
2. **Feature Engineering**: Feature catalog exists but no explicit look-ahead bias prevention; feature versioning not implemented
3. **RL/DRL Core**: Environments implement Gym API but reward functions need friction modeling improvements; action masking present but constraints incomplete
4. **Backtesting**: Historical environment exists with slippage models, but no walk-forward validation or PBO/CSCV overfitting defenses
5. **MLOps**: MLflow integration present but dataset versioning missing; model registry exists but promotion workflow needs automation
6. **Live Trading Safety**: Kill switch and circuit breaker well-implemented; OMS present but reconciliation gaps exist
7. **Data Versioning**: DVC pipeline defined but not fully implemented; raw data snapshots not versioned
8. **Evaluation Realism**: Transaction cost models exist but need stress testing; no regime shift simulation
9. **Modularity**: High coupling between data providers and environments; adding new data sources requires touching multiple files
10. **Reproducibility**: Seeds used but no comprehensive reproducibility checklist (code commit + config hash + data version + env)

---

## 1. Repository Map & Data/Control Flow

### 1.1 Top-Level Structure

```
1.1/
├── api/                    # FastAPI REST + WebSocket service
│   ├── src/
│   │   ├── routers/       # API endpoints
│   │   ├── services/      # Business logic
│   │   ├── schemas/        # Pydantic models
│   │   └── websocket/      # WebSocket channels
│   └── Dockerfile
├── dashboard/              # React frontend
│   └── src/
│       ├── pages/         # UI pages
│       ├── components/     # React components
│       ├── stores/         # Zustand state
│       └── services/       # API clients
├── database/              # MariaDB schema + migrations
│   └── scripts/           # SQL migration files
├── src/mt5-python_server/  # Core trading server
│   └── src/
│       ├── server.py       # Main server entrypoint
│       ├── trading_controller.py  # Live trading loop
│       ├── mt5_connection/       # MT5 socket handlers
│       ├── data_providers/        # Price + indicator providers
│       ├── environments/          # RL environments (live/historical/paper)
│       ├── agents/                # DQN agent
│       ├── experiments/           # Experiment builder/runner
│       ├── mlops/                 # MLflow integration
│       ├── risk/                  # Kill switch, circuit breaker, OMS
│       └── utils/                 # Time, features, transaction costs
├── tests/                 # Test suite
├── scripts/              # Utility scripts
└── docs/                 # Documentation

```

### 1.2 Data Flow Diagram

```
┌─────────────────┐
│  MT5 Terminal  │ (Tick Streamer EA)
└────────┬────────┘
         │ Socket (JSON ticks)
         ▼
┌─────────────────┐
│  Server.py     │ (Socket listener)
│  - Auth        │
│  - Route to    │
│    streamer    │
└────────┬────────┘
         │
    ┌────┴────┐
    │        │
    ▼        ▼
┌─────────┐ ┌──────────────┐
│Tick     │ │MT5Terminal   │
│Streamer │ │(Trading Ops) │
└────┬────┘ └──────┬───────┘
     │             │
     ▼             ▼
┌─────────────────────────┐
│   Database (MariaDB)    │
│   - ticks_forex         │
│   - economic_calendar    │
│   - experiments         │
│   - models              │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Data Providers         │
│  - PriceDataProvider    │
│  - IndicatorProvider    │
│  - Registry             │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Feature Catalog        │
│  - FeatureEngine         │
│  - FeatureEngineer      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Trading Environment     │
│  - LiveTradingEnv        │
│  - HistoricalTradingEnv │
│  - PaperTradingEnv       │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  DQN Agent              │
│  - act()                │
│  - remember()           │
│  - replay()             │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Trading Controller     │
│  - Risk Manager         │
│  - Kill Switch          │
│  - Circuit Breaker      │
│  - OMS                  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  MT5 Terminal           │
│  (Order Execution)      │
└─────────────────────────┘
```

### 1.3 Entry Points

- **Server**: `src/mt5-python_server/src/server.py` - Main socket server
- **API**: `src/api/src/main.py` - FastAPI application
- **Dashboard**: `src/dashboard/src/main.tsx` - React app
- **Training**: `src/mt5-python_server/src/training/train_agent.py`
- **Backtest**: `scripts/run-backtest.py`

### 1.4 High Coupling Areas

**Adding a new data source requires changes to:**
1. `server.py` - Register provider in `__auth_streamer()`
2. `data_providers/registry.py` - Register with registry
3. `features/catalog.py` - Sync catalog
4. `environments/live_env.py` - Pass to environment
5. `experiments/builder.py` - Feature selection UI
6. Database schema - If new data type needs storage

**This violates Single Responsibility Principle and makes the system brittle.**

---

## 2. Critical Issues (Prioritized)

| Issue | File(s) | Symptom | Root Cause | Impact | Fix | Effort | Risk |
|-------|---------|---------|------------|--------|-----|--------|------|
| **P0: No walk-forward validation** | `scripts/run-backtest.py`, `environments/historical_env.py` | Backtests may overfit to specific time periods | No temporal cross-validation; single train/test split | High false confidence, poor generalization | Implement walk-forward with expanding/rolling windows | Medium | High |
| **P0: Feature look-ahead bias risk** | `application/environment/feature_engine.py`, `data_providers/indicator_provider.py` | Features may use future information | No explicit timestamp validation in feature computation | Model learns from future, fails in production | Add timestamp checks; ensure features only use data ≤ current time | Low | High |
| **P0: No dataset versioning** | `dvc.yaml`, `scripts/export-data.py` | Cannot reproduce experiments with exact data | DVC pipeline defined but not executed; no raw data snapshots | Experiments not reproducible | Implement DVC pipeline; snapshot raw data; link to MLflow runs | Medium | High |
| **P1: No PBO/CSCV overfitting defense** | `experiments/runner.py`, `scripts/run-backtest.py` | Cannot estimate probability of backtest overfitting | No CSCV implementation | May select overfitted models | Implement CSCV method per Bailey & López de Prado | High | Medium |
| **P1: Incomplete transaction cost modeling** | `environments/slippage_models.py`, `utils/transaction_costs.py` | Costs may be underestimated | No market impact modeling; slippage models not stress-tested | Backtest vs live performance gap | Add market impact; stress test with widened spreads | Medium | Medium |
| **P1: No data quality gates** | `mt5_connection/tick_streamer.py` | Invalid ticks may enter system | Basic validation exists but no systematic quality checks | Garbage in, garbage out | Add data quality pipeline: outliers, duplicates, staleness | Low | Medium |
| **P1: High coupling for data sources** | `server.py`, `data_providers/`, `environments/` | Adding source touches 6+ files | No unified connector interface | Slow iteration, brittle | Implement `IDataSourceConnector` interface | High | Low |
| **P2: No time alignment validation** | `utils/time_utils.py`, `database.py` | Ticks and news may be misaligned | Timezone normalization exists but no cross-source validation | Features use wrong timestamps | Add alignment validation between sources | Low | Medium |
| **P2: Model registry promotion not automated** | `mlops/model_promoter.py` | Manual promotion steps | No CI/CD integration | Human error risk | Add automated promotion gates with tests | Medium | Low |
| **P2: No feature versioning** | `features/catalog.py` | Cannot track feature changes | Features computed on-the-fly | Cannot reproduce feature sets | Add feature versioning with DVC | Medium | Low |

---

## 3. Best-Practice & Research Comparison Table

| Area | Current | Recommended | Why It Improves Robustness | Source(s) |
|------|---------|-------------|---------------------------|-----------|
| **Backtest Overfitting** | Single train/test split; no PBO estimation | Implement CSCV (Combinatorially Symmetric Cross-Validation) to estimate PBO | Quantifies probability that backtest success is due to overfitting rather than skill; prevents false confidence | [Bailey et al. (2014) - "The Probability of Backtest Overfitting"](https://scholarworks.wmich.edu/math_pubs/42/) |
| **Look-Ahead Bias** | Features computed without explicit timestamp checks | Enforce "point-in-time" constraints: features only use data ≤ decision timestamp | Prevents model from learning from future information; critical for news/sentiment features | [Glasserman & Lin (2023) - "Look-Ahead Bias in Financial ML"](https://arxiv.org/abs/2309.17322) |
| **Data Versioning** | DVC pipeline defined but not executed; no raw snapshots | Version raw data with DVC; link data versions to MLflow runs | Enables exact experiment reproduction; tracks data lineage | [DVC Documentation - Data Versioning](https://dvc.org/doc/use-cases/versioning-data-and-model-files) |
| **Transaction Costs** | Spread + commission + basic slippage | Add market impact modeling; volatility-based slippage; stress test with widened spreads | Realistic cost modeling prevents backtest vs live performance gap | [Algorithmic Trading Transaction Costs](https://gjle.in/2024/03/31/economic-implications-of-algorithmic-trading/) |
| **DRL Trading Pipeline** | Custom implementation | Align with FinRL architecture: modular env/agent/app layers | Proven framework reduces bugs; better separation of concerns | [FinRL Paper (2021) - "FinRL: A Deep RL Library"](https://arxiv.org/abs/2111.09395) |
| **Model Registry** | Manual promotion; no automated gates | Implement staged promotion (Training → Staging → Paper → Production) with automated tests | Reduces human error; ensures models meet criteria before promotion | [MLflow Model Registry Best Practices](https://mlflow.org/docs/latest/ml/model-registry/workflow) |
| **Walk-Forward Validation** | Not implemented | Use expanding or rolling windows; never use future data for training | Prevents temporal leakage; more realistic evaluation | Standard practice in quantitative finance |
| **Feature Versioning** | Features computed on-the-fly | Version feature pipelines; store feature metadata with models | Enables feature rollback; tracks feature evolution | [Feature Store Best Practices](https://www.featurestore.org/) |
| **Data Quality** | Basic tick validation | Systematic quality gates: outliers, duplicates, staleness, missing data | Prevents garbage-in-garbage-out; improves model reliability | Industry standard for production ML systems |
| **Time Alignment** | Timezone normalization exists | Validate alignment between tick/news/macro sources | Ensures features use correct timestamps; prevents temporal misalignment | Critical for multi-source systems |

---

## 4. Target Modular Architecture

### 4.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA INGESTION LAYER                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │TickSource     │  │NewsSource    │  │MacroSource    │        │
│  │(MT5)         │  │(Scraper)     │  │(API)         │        │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘        │
│         │                  │                  │                 │
│         └──────────────────┴──────────────────┘                 │
│                            │                                     │
│                            ▼                                     │
│              ┌─────────────────────────┐                        │
│              │  IDataSourceConnector   │                        │
│              │  - stream()            │                        │
│              │  - batch()             │                        │
│              │  - get_schema()       │                        │
│              └─────────────┬───────────┘                        │
└────────────────────────────┼────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EVENT NORMALIZATION LAYER                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Event Bus / Message Queue                             │    │
│  │  - Normalized event schema                            │    │
│  │  - Timestamp alignment                                │    │
│  │  - Quality gates                                      │    │
│  └───────────────────────┬──────────────────────────────┘    │
│                          │                                       │
│                          ▼                                       │
│              ┌─────────────────────────┐                       │
│              │  IEventNormalizer       │                       │
│              │  - normalize()          │                       │
│              │  - validate()           │                       │
│              │  - align_timestamps()   │                       │
│              └─────────────┬───────────┘                       │
└────────────────────────────┼───────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FEATURE PIPELINE LAYER                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Feature Store / Registry                             │    │
│  │  - Versioned feature pipelines                        │    │
│  │  - Feature metadata                                   │    │
│  │  - Point-in-time constraints                          │    │
│  └───────────────────────┬──────────────────────────────┘    │
│                          │                                       │
│                          ▼                                       │
│              ┌─────────────────────────┐                       │
│              │  IFeaturePipeline       │                       │
│              │  - fit()                 │                       │
│              │  - transform()           │                       │
│              │  - get_version()         │                       │
│              └─────────────┬───────────┘                       │
└────────────────────────────┼───────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TRAINING LAYER (OFFLINE)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Training Pipeline                                    │    │
│  │  - Walk-forward splits                                │    │
│  │  - CSCV for overfitting detection                     │    │
│  │  - Experiment tracking (MLflow)                        │    │
│  └───────────────────────┬──────────────────────────────┘    │
│                          │                                       │
│                          ▼                                       │
│              ┌─────────────────────────┐                       │
│              │  ITradingEnv             │                       │
│              │  (Gym-like)               │                       │
│              │  - reset(seed)           │                       │
│              │  - step(action)           │                       │
│              │  - deterministic replay  │                       │
│              └─────────────┬───────────┘                       │
│                          │                                       │
│                          ▼                                       │
│              ┌─────────────────────────┐                       │
│              │  IPolicy/IAgent          │                       │
│              │  - act(state)            │                       │
│              │  - train()               │                       │
│              └─────────────┬───────────┘                       │
└────────────────────────────┼───────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MLOPS LAYER                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │Dataset       │  │Feature       │  │Model         │        │
│  │Registry      │  │Registry      │  │Registry      │        │
│  │(DVC)         │  │(DVC)         │  │(MLflow)      │        │
│  └──────────────┘  └──────────────┘  └──────┬───────┘        │
│                                               │                 │
│                                               ▼                 │
│                                  ┌───────────────────┐         │
│                                  │ Promotion Workflow│         │
│                                  │ Training→Staging→ │         │
│                                  │ Paper→Production   │         │
│                                  └───────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LIVE TRADING LAYER                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Paper Trading Service                                │    │
│  │  - Real execution on demo account                      │    │
│  │  - Performance tracking                               │    │
│  └───────────────────────┬──────────────────────────────┘    │
│                          │                                       │
│                          ▼                                       │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Live Trading Service                                 │    │
│  │  - Execution engine                                   │    │
│  │  - Risk manager (pre-trade checks)                    │    │
│  │  - Kill switch                                        │    │
│  │  - Circuit breaker                                    │    │
│  │  - OMS (reconciliation)                               │    │
│  │  - Monitoring & alerting                              │    │
│  └───────────────────────┬──────────────────────────────┘    │
│                          │                                       │
│                          ▼                                       │
│              ┌─────────────────────────┐                       │
│              │  IBrokerAdapter        │                       │
│              │  - submit_order()       │                       │
│              │  - get_positions()      │                       │
│              │  - reconcile()          │                       │
│              │  - idempotency          │                       │
│              └─────────────┬───────────┘                       │
└────────────────────────────┼───────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  MT5 / Broker   │
                    └─────────────────┘
```

### 4.2 Interface Contracts

#### IDataSourceConnector
```python
from abc import ABC, abstractmethod
from typing import Iterator, Optional, Dict, Any
from datetime import datetime

class IDataSourceConnector(ABC):
    """Unified interface for all data sources"""
    
    @abstractmethod
    def stream(self, start_time: Optional[datetime] = None) -> Iterator[Dict[str, Any]]:
        """Stream events in real-time"""
        pass
    
    @abstractmethod
    def batch(self, start_time: datetime, end_time: datetime) -> Iterator[Dict[str, Any]]:
        """Fetch historical data in batches"""
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Return schema definition"""
        pass
    
    @abstractmethod
    def get_latest_timestamp(self) -> Optional[datetime]:
        """Get timestamp of most recent data"""
        pass
```

#### IEventNormalizer
```python
class IEventNormalizer(ABC):
    """Normalize events from different sources to canonical format"""
    
    @abstractmethod
    def normalize(self, raw_event: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Convert raw event to canonical schema"""
        pass
    
    @abstractmethod
    def validate(self, event: Dict[str, Any]) -> bool:
        """Validate event quality"""
        pass
    
    @abstractmethod
    def align_timestamps(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Align timestamps across sources"""
        pass
```

#### IFeaturePipeline
```python
class IFeaturePipeline(ABC):
    """Versioned feature computation pipeline"""
    
    @abstractmethod
    def fit(self, data: pd.DataFrame, timestamp_col: str) -> None:
        """Fit feature pipeline (no look-ahead)"""
        pass
    
    @abstractmethod
    def transform(self, data: pd.DataFrame, current_time: datetime) -> np.ndarray:
        """Transform data to features (point-in-time)"""
        pass
    
    @abstractmethod
    def get_version(self) -> str:
        """Return feature pipeline version"""
        pass
    
    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return feature metadata"""
        pass
```

#### ITradingEnv (Enhanced)
```python
class ITradingEnv(gym.Env, ABC):
    """Enhanced trading environment with deterministic replay"""
    
    @abstractmethod
    def reset(self, seed: Optional[int] = None) -> Tuple[np.ndarray, Dict]:
        """Reset with seed for reproducibility"""
        pass
    
    @abstractmethod
    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """Step with transaction costs included in reward"""
        pass
    
    @abstractmethod
    def get_transaction_costs(self) -> TransactionCosts:
        """Get current transaction cost model"""
        pass
    
    @abstractmethod
    def set_slippage_model(self, model: SlippageModel) -> None:
        """Set slippage model for realism"""
        pass
```

#### IBrokerAdapter
```python
class IBrokerAdapter(ABC):
    """Broker execution adapter with idempotency"""
    
    @abstractmethod
    def submit_order(self, order: Order, idempotency_key: str) -> OrderStatus:
        """Submit order with idempotency"""
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """Get current positions"""
        pass
    
    @abstractmethod
    def reconcile(self, expected_positions: Dict[str, float]) -> List[Discrepancy]:
        """Reconcile positions"""
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderStatus:
        """Get order status"""
        pass
```

#### IRiskManager
```python
class IRiskManager(ABC):
    """Pre-trade risk checks"""
    
    @abstractmethod
    def can_trade(self, account: Account, order: Order) -> Tuple[bool, Optional[str]]:
        """Check if trade is allowed"""
        pass
    
    @abstractmethod
    def check_exposure_limits(self, account: Account) -> Tuple[bool, Optional[str]]:
        """Check exposure limits"""
        pass
    
    @abstractmethod
    def check_daily_loss_cap(self, account: Account) -> Tuple[bool, Optional[str]]:
        """Check daily loss cap"""
        pass
```

### 4.3 Recommended Folder Structure

```
src/mt5-python_server/src/
├── connectors/              # Data source connectors
│   ├── __init__.py
│   ├── base.py              # IDataSourceConnector
│   ├── mt5_tick_connector.py
│   ├── news_connector.py
│   └── macro_connector.py
├── events/                   # Event normalization
│   ├── __init__.py
│   ├── normalizer.py         # IEventNormalizer
│   ├── schema_registry.py
│   └── quality_gates.py
├── features/                 # Feature pipelines
│   ├── __init__.py
│   ├── base.py               # IFeaturePipeline
│   ├── pipelines/
│   │   ├── technical_indicators.py
│   │   └── news_sentiment.py
│   └── versioning.py
├── environments/             # RL environments (existing)
├── agents/                   # RL agents (existing)
├── training/                 # Training pipelines
│   ├── walk_forward.py
│   ├── cscv.py              # PBO/CSCV implementation
│   └── evaluation.py
├── mlops/                    # MLOps (existing + enhancements)
│   ├── dataset_registry.py   # NEW: DVC integration
│   ├── feature_registry.py   # NEW: Feature versioning
│   └── model_registry.py     # Existing
├── trading/                  # Live trading
│   ├── execution/            # Execution engine
│   ├── risk/                 # Risk manager (existing)
│   └── monitoring/           # Observability
└── utils/                    # Utilities (existing)
```

---

## 5. MLOps Plan

### 5.1 Dataset Versioning

**Current State:** DVC pipeline defined in `dvc.yaml` but not executed. No raw data snapshots.

**Target State:**
1. **Raw Data Snapshots**: Store raw ticks/calendar data with DVC
   ```bash
   dvc add data/raw/ticks_20250127.parquet
   dvc add data/raw/calendar_20250127.parquet
   ```
2. **Link to MLflow**: Store data version in MLflow run tags
   ```python
   mlflow.set_tag("data_version", "ticks_v1.2.3")
   mlflow.set_tag("dvc_repo", dvc.get_repo())
   ```
3. **Reproducibility Checklist**: Document in experiment metadata
   - Code commit hash
   - Config hash (params.yaml)
   - Data version (DVC)
   - Environment (Docker image hash)

**Implementation:**
- Create `mlops/dataset_registry.py` with DVC integration
- Update `experiments/runner.py` to record data versions
- Add data version to model registry schema

### 5.2 Feature Versioning

**Current State:** Features computed on-the-fly; no versioning.

**Target State:**
1. **Feature Pipeline Versioning**: Version feature computation code
   ```python
   class FeaturePipeline:
       def __init__(self, version: str):
           self.version = version  # e.g., "v1.2.0"
   ```
2. **Feature Metadata**: Store feature definitions with models
   ```json
   {
     "features": ["rsi_14", "macd_12_26"],
     "feature_pipeline_version": "v1.2.0",
     "computed_at": "2025-01-27T10:00:00Z"
   }
   ```
3. **DVC for Feature Artifacts**: Version computed features
   ```bash
   dvc add data/processed/features_v1.2.0.parquet
   ```

**Implementation:**
- Create `mlops/feature_registry.py`
- Update `features/catalog.py` to track versions
- Store feature metadata in MLflow model artifacts

### 5.3 Model Registry Promotion Workflow

**Current State:** Manual promotion via `model_promoter.py`.

**Target State:**
```
Training → Staging → Paper Trading → Production
   │          │            │              │
   │          │            │              │
   ▼          ▼            ▼              ▼
Auto      Manual      Automated      Manual
promote   review      tests          approval
```

**Promotion Gates:**

1. **Training → Staging:**
   - Model saved successfully
   - Basic metrics logged
   - Auto-promote

2. **Staging → Paper Trading:**
   - Validation metrics meet thresholds (Sharpe > 0.5, max drawdown < 20%)
   - No critical bugs in code review
   - Manual approval

3. **Paper Trading → Production:**
   - Paper trading results: Sharpe > 1.0, win rate > 50%, min 7 days
   - Automated tests pass (unit + integration)
   - Manual approval + 2FA

**Implementation:**
- Enhance `mlops/model_promoter.py` with automated gates
- Add CI/CD integration (GitHub Actions)
- Add promotion tests in `tests/integration/test_model_promotion.py`

---

## 6. Backtest Realism & Anti-Overfitting Plan

### 6.1 Walk-Forward Validation

**Implementation:**
```python
# scripts/walk_forward_validation.py

def walk_forward_validation(
    data: pd.DataFrame,
    train_window_days: int = 180,
    test_window_days: int = 30,
    step_days: int = 30
):
    """
    Walk-forward validation with expanding/rolling windows.
    Never use future data for training.
    """
    results = []
    start_date = data['timestamp'].min()
    end_date = data['timestamp'].max()
    
    current_date = start_date + timedelta(days=train_window_days)
    
    while current_date + timedelta(days=test_window_days) <= end_date:
        train_data = data[
            (data['timestamp'] >= start_date) &
            (data['timestamp'] < current_date)
        ]
        test_data = data[
            (data['timestamp'] >= current_date) &
            (data['timestamp'] < current_date + timedelta(days=test_window_days))
        ]
        
        # Train and evaluate
        metrics = train_and_evaluate(train_data, test_data)
        results.append(metrics)
        
        current_date += timedelta(days=step_days)
    
    return aggregate_results(results)
```

### 6.2 PBO/CSCV Implementation

**Reference:** Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2014). "The Probability of Backtest Overfitting."

**Implementation:**
```python
# training/cscv.py

def combinatorially_symmetric_cross_validation(
    data: pd.DataFrame,
    strategy_configs: List[Dict],
    n_splits: int = 4
) -> Dict[str, float]:
    """
    Estimate Probability of Backtest Overfitting (PBO) using CSCV.
    
    Returns:
        - pbo: Probability of backtest overfitting
        - performance_degradation: Expected performance drop
    """
    # Partition data into n_splits
    partitions = partition_data(data, n_splits)
    
    # For each combination of train/test splits
    results = []
    for train_indices, test_indices in generate_combinations(n_splits):
        train_data = data.iloc[train_indices]
        test_data = data.iloc[test_indices]
        
        # Evaluate all strategies
        strategy_performances = []
        for config in strategy_configs:
            metrics = evaluate_strategy(config, train_data, test_data)
            strategy_performances.append(metrics)
        
        results.append(strategy_performances)
    
    # Calculate PBO
    pbo = calculate_pbo(results)
    return {
        'pbo': pbo,
        'performance_degradation': calculate_degradation(results)
    }
```

### 6.3 Leakage Defenses

**Point-in-Time Constraints:**
```python
# features/base.py

class FeaturePipeline:
    def transform(self, data: pd.DataFrame, current_time: datetime) -> np.ndarray:
        """
        Transform with point-in-time constraint.
        Only use data <= current_time.
        """
        # Filter data to point-in-time
        historical_data = data[data['timestamp'] <= current_time]
        
        # Compute features
        features = self._compute_features(historical_data)
        
        return features
```

**News/Sentiment Look-Ahead Prevention:**
```python
# features/pipelines/news_sentiment.py

def extract_sentiment_features(news_data: pd.DataFrame, current_time: datetime):
    """
    Extract sentiment features with strict time constraints.
    """
    # Only use news published BEFORE current_time
    available_news = news_data[news_data['published_at'] < current_time]
    
    # Add latency buffer (e.g., 5 minutes for processing)
    available_news = available_news[
        available_news['published_at'] < current_time - timedelta(minutes=5)
    ]
    
    return compute_sentiment(available_news)
```

### 6.4 Cost/Slippage Modeling

**Enhanced Transaction Cost Model:**
```python
# environments/slippage_models.py (enhancements)

class MarketImpactSlippage(SlippageModel):
    """
    Market impact model based on order size and volatility.
    """
    def apply(self, price: float, quantity: float, is_buy: bool, 
              volatility: float, market_depth: float) -> float:
        """
        Calculate slippage with market impact.
        
        Impact = base_impact * (quantity / market_depth) * volatility_factor
        """
        base_impact = 0.0001  # 1 pip base
        size_factor = min(quantity / market_depth, 1.0)  # Cap at 1.0
        vol_factor = 1.0 + (volatility / 0.01)  # Scale with volatility
        
        impact = base_impact * size_factor * vol_factor
        
        if is_buy:
            return price * (1 + impact)
        else:
            return price * (1 - impact)
```

**Stress Testing:**
```python
# tests/stress/test_slippage_models.py

def test_slippage_under_stress():
    """Test slippage models with widened spreads and high volatility"""
    # Simulate market stress: 5x normal spread, 3x normal volatility
    stress_config = {
        'spread_multiplier': 5.0,
        'volatility_multiplier': 3.0
    }
    
    # Run backtest with stress config
    results = run_backtest_with_slippage(stress_config)
    
    # Verify performance degradation is realistic
    assert results['sharpe_ratio'] < baseline_sharpe * 0.7
```

---

## 7. Live Trading Safety & Operations

### 7.1 Pre-Trade Controls

**Current State:** Risk manager exists but needs enhancement.

**Enhancements:**
```python
# risk/pre_trade_controls.py

class PreTradeControls:
    def validate_order(self, account: Account, order: Order) -> Tuple[bool, Optional[str]]:
        """Comprehensive pre-trade validation"""
        checks = [
            self.check_exposure_limits(account, order),
            self.check_daily_loss_cap(account),
            self.check_position_limits(account, order),
            self.check_leverage_limits(account, order),
            self.check_market_hours(),
            self.check_feed_quality(),
        ]
        
        for passed, reason in checks:
            if not passed:
                return False, reason
        
        return True, None
```

### 7.2 Kill Switch

**Current State:** Well-implemented with multiple triggers.

**Status:** ✅ Good - No changes needed.

### 7.3 Circuit Breaker

**Current State:** Well-implemented with loss/volatility/error thresholds.

**Status:** ✅ Good - No changes needed.

### 7.4 Monitoring & Alerting

**Current State:** Basic logging exists.

**Enhancements Needed:**
1. **Structured Logging**: Already implemented ✅
2. **Metrics Collection**: Add Prometheus metrics
3. **Alerting**: Integrate with PagerDuty/Slack
4. **Drift Monitoring**: Monitor feature drift

**Implementation:**
```python
# trading/monitoring/metrics.py

from prometheus_client import Counter, Histogram, Gauge

trades_total = Counter('trading_trades_total', 'Total trades executed')
trade_latency = Histogram('trading_latency_seconds', 'Trade execution latency')
account_equity = Gauge('trading_account_equity', 'Current account equity')
```

### 7.5 Incident Runbooks

**Create:** `docs/runbooks/`

1. **Kill Switch Activation**
   - Steps to investigate
   - How to reset
   - Post-mortem template

2. **Circuit Breaker Trip**
   - Review metrics
   - Determine cause
   - Recovery steps

3. **Position Reconciliation Failure**
   - OMS vs broker mismatch
   - Resolution steps

---

## 8. "Next 14 Days" Implementation Plan

| Task | Owner Role | Acceptance Criteria | Tests | Dependencies |
|------|-----------|---------------------|-------|--------------|
| **Day 1-2: Data Quality Gates** | Backend Engineer | Data quality pipeline rejects invalid ticks (outliers, duplicates, staleness) | `test_data_quality_gates.py` | None |
| **Day 2-3: Feature Point-in-Time Constraints** | ML Engineer | Features only use data ≤ current timestamp; tests verify no look-ahead | `test_feature_timestamps.py` | None |
| **Day 3-5: Walk-Forward Validation** | ML Engineer | Walk-forward script produces expanding/rolling window results | `test_walk_forward.py` | Data quality gates |
| **Day 5-7: Dataset Versioning (DVC)** | MLOps Engineer | Raw data snapshots stored with DVC; linked to MLflow runs | `test_dataset_versioning.py` | DVC setup |
| **Day 7-9: IDataSourceConnector Interface** | Backend Engineer | New connector interface; MT5 connector refactored to use it | `test_connector_interface.py` | None |
| **Day 9-10: Enhanced Transaction Costs** | Quant Engineer | Market impact model added; stress tests pass | `test_market_impact.py` | None |
| **Day 10-12: Feature Versioning** | ML Engineer | Feature pipelines versioned; metadata stored with models | `test_feature_versioning.py` | Dataset versioning |
| **Day 12-13: Model Promotion Automation** | MLOps Engineer | Automated promotion gates (staging → paper) with tests | `test_model_promotion.py` | Feature versioning |
| **Day 13-14: Time Alignment Validation** | Backend Engineer | Cross-source timestamp validation; tests for misalignment detection | `test_time_alignment.py` | Data quality gates |
| **Day 14: Documentation & Runbooks** | Tech Writer | Runbooks created for kill switch, circuit breaker, reconciliation | N/A | All above |

**Priority Order:**
1. Data quality gates (foundation)
2. Feature point-in-time constraints (critical for correctness)
3. Walk-forward validation (evaluation realism)
4. Dataset versioning (reproducibility)
5. Connector interface (modularity)
6. Enhanced transaction costs (realism)
7. Feature versioning (MLOps)
8. Model promotion automation (safety)
9. Time alignment (data integrity)
10. Documentation (operational readiness)

---

## 9. Research Citations

### Backtest Overfitting
- **Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2014).** "The Probability of Backtest Overfitting." *Journal of Computational Finance*, 17(4). [Link](https://scholarworks.wmich.edu/math_pubs/42/)

### Look-Ahead Bias
- **Glasserman, P., & Lin, Y. (2023).** "Look-Ahead Bias in Financial Machine Learning." *arXiv preprint arXiv:2309.17322*. [Link](https://arxiv.org/abs/2309.17322)
- **Aisot Technologies (2024).** "Time-Boxed LLMs to Overcome Look-Ahead Bias." [Link](https://aisot.com/blog/aisot-technologies-launches-world-first-time-boxed-llms-to-overcome-look-ahead-bias-for-investment-strategy-optimization)

### DRL Trading Framework
- **Liu, X., et al. (2021).** "FinRL: A Deep Reinforcement Learning Library for Automated Trading in Quantitative Finance." *arXiv preprint arXiv:2111.09395*. [Link](https://arxiv.org/abs/2111.09395)

### Transaction Costs
- **Algorithmic Trading Transaction Costs Guide (2024).** [Link](https://gjle.in/2024/03/31/economic-implications-of-algorithmic-trading/)
- **Market Impact Research (2024).** *arXiv preprint arXiv:2505.15296*. [Link](https://arxiv.org/abs/2505.15296)

### MLOps & Model Registry
- **MLflow Model Registry Best Practices (2024).** [Link](https://mlflow.org/docs/latest/ml/model-registry/workflow)
- **MLOps Best Practices (2024).** [Link](https://www.mlopscrew.com/blog/mlops-best-practices)

### Data Versioning
- **DVC Documentation - Data Versioning (2024).** [Link](https://dvc.org/doc/use-cases/versioning-data-and-model-files)

---

## 10. Conclusion

This audit identifies **10 critical issues** (3 P0, 4 P1, 3 P2) and provides a **research-backed upgrade plan** to transform the codebase into a **modular, production-ready AI trading system**.

**Key Improvements:**
1. **Reduced False Confidence**: Walk-forward validation + PBO/CSCV prevent overfitting
2. **Improved Generalization**: Point-in-time constraints prevent look-ahead bias
3. **Enhanced Reproducibility**: Dataset + feature versioning enable exact reproduction
4. **Better Evaluation Realism**: Enhanced transaction costs + stress testing
5. **Modular Architecture**: Connector interfaces reduce coupling
6. **Operational Safety**: Automated promotion gates + comprehensive monitoring

**Expected Outcomes:**
- **Reduced backtest vs live performance gap** (realistic cost modeling)
- **Higher model reliability** (overfitting detection)
- **Faster iteration** (modular connectors)
- **Lower operational risk** (automated safety gates)

**Next Steps:**
1. Review and approve this plan
2. Assign owners to 14-day implementation tasks
3. Begin with data quality gates (foundation)
4. Iterate on architecture improvements

---

**Document Version:** 1.0  
**Last Updated:** 2025-01-27  
**Status:** Ready for Review
