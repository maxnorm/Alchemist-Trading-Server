---
name: Phase 6 Live Performance Tracking
overview: Implement comprehensive live performance tracking system including database tables, trade logging, metrics calculation, equity curve tracking, API endpoints, and React dashboard pages for portfolio and model performance visualization with real-time updates.
todos:
  - id: phase6-db-schema
    content: Create database migration script 06_performance_tracking.sql with all performance tables (live_trading_sessions, model_trades, daily_performance, performance_metrics, equity_curve, portfolio_allocation)
    status: completed
  - id: phase6-trade-logger
    content: Implement TradeLogger class in src/mt5-python_server/src/performance/trade_logger.py with log_trade_entry, log_trade_exit, get_open_trades, get_trade_history methods
    status: completed
  - id: phase6-equity-tracker
    content: Implement EquityTracker class in src/mt5-python_server/src/performance/equity_tracker.py with record_snapshot, get_equity_curve, start_tracking, stop_tracking methods
    status: completed
  - id: phase6-metrics-calculator
    content: Implement PerformanceMetricsCalculator class in src/mt5-python_server/src/performance/metrics_calculator.py with all metric calculations (Sharpe, Sortino, win rate, drawdown, profit factor, expectancy, etc.)
    status: completed
  - id: phase6-session-manager
    content: Implement SessionManager class in src/mt5-python_server/src/performance/session_manager.py for trading session lifecycle management
    status: completed
  - id: phase6-integrate-logging
    content: Integrate TradeLogger into ActionExecutor/TradeExecutor to log trades on execution
    status: completed
  - id: phase6-integrate-tracking
    content: Integrate EquityTracker into TradingController or training loop for periodic equity snapshots
    status: completed
  - id: phase6-performance-api
    content: Create FastAPI performance router api/src/routers/performance.py with portfolio and model endpoints
    status: completed
  - id: phase6-performance-schemas
    content: Create Pydantic schemas in api/src/schemas/performance.py for request/response models
    status: completed
  - id: phase6-performance-service
    content: Create service layer api/src/services/performance_service.py for business logic
    status: completed
  - id: phase6-websocket-performance
    content: Add performance WebSocket channel to api/src/websocket/manager.py for real-time updates
    status: completed
  - id: phase6-portfolio-page
    content: Implement Portfolio Performance page dashboard/src/pages/PortfolioPerformance.tsx with equity curve chart, metrics cards, model contributions, and P&L breakdown
    status: completed
  - id: phase6-model-page
    content: Implement Model Performance page dashboard/src/pages/ModelPerformance.tsx with all performance sections, charts, and trade history
    status: completed
  - id: phase6-chart-components
    content: Create EquityCurveChart component using Lightweight Charts for portfolio and model pages
    status: completed
  - id: phase6-realtime-updates
    content: Integrate WebSocket real-time updates into dashboard pages using Zustand
    status: completed
  - id: phase6-export-functionality
    content: Implement export functionality (PDF/CSV) for portfolio and model reports (P1, can defer)
    status: completed
  - id: phase6-paper-live-comparison
    content: Implement paper vs live comparison feature in Model Performance page
    status: completed
  - id: phase6-integration-tests
    content: Write integration tests for performance API endpoints and backend components
    status: completed
  - id: phase6-documentation
    content: Document performance metrics calculations and API endpoints
    status: completed
---

# Phase 6: Live Performance Tracking

## Overview

Phase 6 implements comprehensive live performance tracking for trading models, enabling users to monitor portfolio-level and model-specific performance metrics in real-time. This phase builds on the FastAPI service (Phase 4) and React dashboard (Phase 5) to provide complete performance analytics.

## Goals

- Track all trades executed by models with detailed P&L information
- Calculate and display key performance metrics (Sharpe ratio, win rate, drawdown, etc.)
- Provide portfolio-level aggregation across all active models
- Enable real-time performance updates via WebSocket
- Support historical analysis with time-based filtering
- Compare paper trading vs live trading performance

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TRADING EXECUTION LAYER                   │
│  (ActionExecutor, TradeExecutor)                            │
│                    │                                         │
│                    ▼                                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         TradeLogger (logs all trades)                 │  │
│  └──────────────────┬─────────────────────────────────────┘  │
│                     │                                         │
│                     ▼                                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │    EquityTracker (periodic balance snapshots)        │  │
│  └──────────────────┬─────────────────────────────────────┘  │
│                     │                                         │
│                     ▼                                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  PerformanceMetricsCalculator (calculates metrics)    │  │
│  └──────────────────┬─────────────────────────────────────┘  │
│                     │                                         │
│                     ▼                                         │
│              ┌──────────────┐                                │
│              │   Database    │                                │
│              │  (MariaDB)    │                                │
│              └──────┬────────┘                                │
│                     │                                         │
│                     ▼                                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         FastAPI Performance Endpoints                 │  │
│  └──────────────────┬─────────────────────────────────────┘  │
│                     │                                         │
│                     ▼                                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │      React Dashboard Performance Pages                │  │
│  │  (Portfolio Performance, Model Performance)           │  │
│  └──────────────────────────────────────────────────────┘  │
```

## Database Schema

### New Tables

All tables follow the PRD schema (Section 17) with model-based tracking:

**`live_trading_sessions`** - Tracks active trading sessions per model

- Links models to trading periods
- Tracks start/end balance, high water mark for drawdown
- Status: active, paused, stopped

**`model_trades`** - Individual trade records

- Links to session_id and model_id
- Stores entry/exit prices, P&L, duration
- Status: open, closed, cancelled

**`daily_performance`** - Daily snapshots for historical analysis

- Model-level or portfolio-level (model_id NULL)
- Aggregated daily metrics (P&L, win rate, Sharpe, etc.)

**`performance_metrics`** - Real-time calculated metrics

- Metric types: sharpe, sortino, win_rate, profit_factor, etc.
- Periods: realtime, daily, weekly, monthly, yearly, all_time
- Supports both model-level and portfolio-level

**`equity_curve`** - Time-series equity data for charts

- Timestamped balance and equity values
- Drawdown percentage per point
- Unrealized P&L tracking

**`portfolio_allocation`** - Asset allocation tracking

- Position values by model and symbol
- Allocation percentages

### Migration Script

Create `database/scripts/06_performance_tracking.sql` with all table definitions, indexes, and foreign keys as specified in PRD Section 17.

## Backend Implementation

### 1. Performance Module Structure

Create `src/mt5-python_server/src/performance/` directory:

```
performance/
├── __init__.py
├── trade_logger.py          # Trade entry/exit logging
├── equity_tracker.py        # Periodic equity snapshots
├── metrics_calculator.py    # Performance metrics calculation
└── session_manager.py      # Trading session lifecycle
```

### 2. TradeLogger (`trade_logger.py`)

**Responsibilities:**

- Log trade entries when positions are opened
- Log trade exits when positions are closed
- Track open positions per model/session
- Calculate P&L including commissions and swaps

**Key Methods:**

```python
class TradeLogger:
    def log_trade_entry(
        self, 
        session_id: int,
        model_id: int,
        order_uuid: str,
        symbol: str,
        action: str,  # 'BUY' or 'SELL'
        entry_price: float,
        volume: float,
        commission: float = 0.0,
        swap: float = 0.0
    ) -> int  # Returns trade_id
    
    def log_trade_exit(
        self,
        trade_id: int,
        exit_price: float,
        pnl: float,
        pnl_pips: float,
        duration_seconds: int
    ) -> None
    
    def get_open_trades(
        self,
        session_id: Optional[int] = None,
        model_id: Optional[int] = None
    ) -> List[Dict]
    
    def get_trade_history(
        self,
        model_id: Optional[int] = None,
        session_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict]
```

**Integration Points:**

- Hook into `ActionExecutor.execute_action()` to log entries
- Hook into position close logic to log exits
- Use OMS order_uuid for trade tracking

### 3. EquityTracker (`equity_tracker.py`)

**Responsibilities:**

- Record periodic equity snapshots (every N minutes)
- Track balance, equity, and unrealized P&L
- Calculate drawdown percentage
- Support both model-level and portfolio-level tracking

**Key Methods:**

```python
class EquityTracker:
    def __init__(
        self,
        snapshot_interval_minutes: int = 5,
        db: Optional[Database] = None
    )
    
    def record_snapshot(
        self,
        model_id: Optional[int],  # None for portfolio-level
        session_id: int,
        balance: float,
        equity: float,
        unrealized_pnl: float = 0.0
    ) -> None
    
    def get_equity_curve(
        self,
        model_id: Optional[int] = None,
        session_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]  # List of {timestamp, equity, balance, drawdown_pct}
    
    def start_tracking(
        self,
        model_id: Optional[int],
        session_id: int
    ) -> None
    
    def stop_tracking(
        self,
        session_id: int
    ) -> None
```

**Integration Points:**

- Initialize in `TradingController` when model starts trading
- Call `record_snapshot()` periodically (background task or in training loop)
- Stop tracking when session ends

### 4. PerformanceMetricsCalculator (`metrics_calculator.py`)

**Responsibilities:**

- Calculate all performance metrics from trade data
- Support multiple time periods (daily, weekly, monthly, etc.)
- Cache calculations for performance
- Update database with calculated metrics

**Key Methods:**

```python
class PerformanceMetricsCalculator:
    def calculate_win_rate(
        self,
        trades: List[Dict]
    ) -> float
    
    def calculate_sharpe_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.0,
        annualized: bool = True
    ) -> float
    
    def calculate_sortino_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.0
    ) -> float
    
    def calculate_max_drawdown(
        self,
        equity_curve: List[Dict]
    ) -> Tuple[float, float]  # (max_drawdown, max_drawdown_pct)
    
    def calculate_profit_factor(
        self,
        trades: List[Dict]
    ) -> float
    
    def calculate_expectancy(
        self,
        trades: List[Dict]
    ) -> float
    
    def calculate_all_metrics(
        self,
        model_id: Optional[int],
        session_id: Optional[int],
        period: str = 'all_time'
    ) -> Dict[str, float]
    
    def update_metrics_in_db(
        self,
        model_id: Optional[int],
        session_id: Optional[int],
        period: str,
        metrics: Dict[str, float]
    ) -> None
```

**Metrics Implemented:**

- Win Rate (winning trades / total trades)
- Sharpe Ratio (annualized risk-adjusted return)
- Sortino Ratio (downside deviation only)
- Max Drawdown (largest peak-to-trough decline)
- Profit Factor (gross profit / gross loss)
- Expectancy (expected value per trade)
- Average Win / Average Loss
- Longest Win/Loss Streaks
- Recovery Factor (net profit / max drawdown)

### 5. SessionManager (`session_manager.py`)

**Responsibilities:**

- Manage trading session lifecycle
- Track session start/end balances
- Link models to trading sessions
- Handle session status (active, paused, stopped)

**Key Methods:**

```python
class SessionManager:
    def create_session(
        self,
        model_id: int,
        start_balance: float
    ) -> int  # Returns session_id
    
    def end_session(
        self,
        session_id: int,
        reason: str,
        end_balance: float
    ) -> None
    
    def pause_session(
        self,
        session_id: int
    ) -> None
    
    def resume_session(
        self,
        session_id: int
    ) -> None
    
    def get_active_sessions(
        self,
        model_id: Optional[int] = None
    ) -> List[Dict]
```

**Integration Points:**

- Called when model is assigned to account (Phase 7)
- Called when model is unassigned or trading stops
- Used by TradeLogger and EquityTracker to link data

## FastAPI Endpoints

### Performance Router (`api/src/routers/performance.py`)

**Portfolio Endpoints:**

- `GET /api/performance/portfolio` - Portfolio summary (total P&L, Sharpe, drawdown, win rate)
- `GET /api/performance/portfolio/equity-curve` - Portfolio equity curve data
- `GET /api/performance/portfolio/breakdown` - P&L breakdown by period (daily/weekly/monthly)
- `GET /api/performance/portfolio/allocation` - Asset allocation by pair/model
- `GET /api/performance/portfolio/export` - Export portfolio report (PDF/CSV)

**Model Endpoints:**

- `GET /api/performance/models` - List all model performance summaries
- `GET /api/performance/models/{model_id}` - Detailed model performance
- `GET /api/performance/models/{model_id}/equity-curve` - Model equity curve
- `GET /api/performance/models/{model_id}/trades` - Trade history with pagination
- `GET /api/performance/models/{model_id}/statistics` - Detailed statistics (win streaks, avg duration, etc.)
- `GET /api/performance/models/{model_id}/comparison` - Paper vs live comparison
- `GET /api/performance/models/{model_id}/export` - Export model report

**Real-time Endpoints:**

- `GET /api/performance/metrics/realtime` - Real-time metrics for all active models

**Query Parameters:**

- `start_date`, `end_date` - Date range filtering
- `period` - Time period (daily, weekly, monthly, yearly, all_time)
- `limit`, `offset` - Pagination for trade history

### WebSocket Updates

Extend `api/src/websocket/manager.py` with performance channel:

**Channel:** `/ws/performance`

**Message Types:**

```json
{
  "type": "portfolio_update",
  "data": {
    "total_pnl": 2456.78,
    "sharpe_ratio": 1.87,
    "max_drawdown": -8.2,
    "win_rate": 58.3,
    "timestamp": "2025-01-15T14:30:00Z"
  }
}

{
  "type": "model_update",
  "data": {
    "model_id": 1,
    "model_version": "v3.2.1",
    "pnl": 1234.56,
    "sharpe_ratio": 2.14,
    "win_rate": 62.1,
    "timestamp": "2025-01-15T14:30:00Z"
  }
}

{
  "type": "trade_executed",
  "data": {
    "model_id": 1,
    "symbol": "EURUSD",
    "action": "BUY",
    "entry_price": 1.08234,
    "volume": 0.1,
    "pnl": null,
    "timestamp": "2025-01-15T14:32:15Z"
  }
}
```

**Integration:**

- Broadcast updates when trades are executed
- Broadcast periodic metric updates (every 30 seconds)
- Broadcast equity curve updates (every snapshot)

## React Dashboard Pages

### 1. Portfolio Performance Page

**File:** `dashboard/src/pages/PortfolioPerformance.tsx`

**Features:**

- Portfolio equity curve chart (Lightweight Charts)
- Key metrics cards (Total P&L, Sharpe Ratio, Max Drawdown, Win Rate, Profit Factor, Expectancy)
- Model contributions table (which models contribute most)
- P&L breakdown by period (Today, This Week, This Month, This Year, All Time)
- Currency pair allocation chart
- Export buttons (PDF/CSV)

**Components:**

- `EquityCurveChart` - Lightweight Charts line chart with drawdown overlay
- `MetricsCard` - Reusable card for displaying metric values
- `ModelContributionsTable` - Table showing model performance breakdown
- `PeriodBreakdownTable` - P&L breakdown by time period
- `AllocationChart` - Pie/bar chart for currency pair allocation

**State Management:**

- Use TanStack Query for data fetching
- Use Zustand for real-time WebSocket updates
- Auto-refresh every 30 seconds

**Time Range Filter:**

- Dropdown: Today, This Week, This Month, This Year, All Time
- Custom date range picker (optional)

### 2. Model Performance Page

**File:** `dashboard/src/pages/ModelPerformance.tsx`

**Route:** `/performance/models/:modelId`

**Features:**

- Model equity curve chart with drawdown overlay
- Performance summary section (Total P&L, Today, This Week, This Month)
- Risk metrics section (Sharpe, Sortino, Max Drawdown, Recovery Factor)
- Trade statistics section (Total Trades, Win Rate, Avg Win/Loss, Profit Factor, Expectancy)
- Timing analysis (Avg Duration, Time in Market, Best Hour/Day)
- Action distribution chart (BUY/SELL/HOLD percentages)
- P&L by currency pair table (for multi-pair models)
- Recent trades table with pagination
- Model configuration display
- Paper vs Live comparison section
- Export buttons (PDF/CSV)

**Components:**

- `ModelEquityCurveChart` - Chart with equity and drawdown lines
- `PerformanceSummary` - Key performance metrics
- `RiskMetrics` - Risk-related metrics
- `TradeStatistics` - Trade-level statistics
- `TimingAnalysis` - Time-based analysis
- `ActionDistributionChart` - Bar chart for action distribution
- `RecentTradesTable` - Paginated table of recent trades
- `PaperLiveComparison` - Comparison table between paper and live performance

**Navigation:**

- Breadcrumb: Portfolio Performance → Model Performance
- Link from Model Registry page
- Link from Training Monitor page

### 3. Integration with Existing Pages

**Model Registry Page:**

- Add performance summary column (P&L, Sharpe, Win Rate)
- Link to Model Performance page
- Show performance badges (🟢 Good, 🟡 Monitor, 🔴 Underperforming)

**Training Monitor Page:**

- Show real-time P&L for active experiments
- Link to Model Performance page when training completes

**Live Trading Page:**

- Show active positions with real-time P&L
- Link to Model Performance page for each active model

## Implementation Tasks

### Database Layer

1. Create migration script `database/scripts/06_performance_tracking.sql`
2. Add database methods in `src/mt5-python_server/src/database.py` for performance tables
3. Test database schema and indexes

### Backend Core

4. Create `performance/` module directory structure
5. Implement `TradeLogger` class with database integration
6. Implement `EquityTracker` class with periodic snapshot logic
7. Implement `PerformanceMetricsCalculator` with all metric calculations
8. Implement `SessionManager` for session lifecycle
9. Integrate TradeLogger into `ActionExecutor`/`TradeExecutor`
10. Integrate EquityTracker into `TradingController` or training loop
11. Add background task for periodic metric calculation (optional)

### FastAPI Layer

12. Create `api/src/routers/performance.py` with all endpoints
13. Create Pydantic schemas in `api/src/schemas/performance.py`
14. Implement service layer `api/src/services/performance_service.py`
15. Add WebSocket performance channel to `api/src/websocket/manager.py`
16. Add performance endpoints to main FastAPI app
17. Test all endpoints with sample data

### React Dashboard

18. Create `PortfolioPerformance.tsx` page with layout
19. Implement `EquityCurveChart` component using Lightweight Charts
20. Implement metrics cards and summary sections
21. Implement model contributions table
22. Implement P&L breakdown table
23. Implement allocation chart
24. Add export functionality (PDF/CSV)
25. Create `ModelPerformance.tsx` page with layout
26. Implement model equity curve chart
27. Implement all performance sections (summary, risk, statistics, timing)
28. Implement recent trades table with pagination
29. Implement paper vs live comparison
30. Add WebSocket integration for real-time updates
31. Add navigation links from other pages
32. Style and polish UI

### Testing

33. Write unit tests for TradeLogger
34. Write unit tests for EquityTracker
35. Write unit tests for PerformanceMetricsCalculator
36. Write integration tests for performance API endpoints
37. Write E2E tests for dashboard pages
38. Test WebSocket real-time updates

### Documentation

39. Document performance metrics calculations
40. Document API endpoints
41. Update user guide with performance tracking section

## Dependencies

**Backend:**

- Existing `Database` class for database operations
- `ActionExecutor`/`TradeExecutor` for trade execution hooks
- `TradingController` for session management
- FastAPI for API endpoints
- WebSocket manager for real-time updates

**Frontend:**

- Lightweight Charts for equity curve visualization
- TanStack Query for data fetching
- Zustand for WebSocket state management
- shadcn/ui components for UI
- Date-fns for date formatting

## Success Criteria

- All trades are logged with accurate P&L
- Equity curve updates in real-time (within 5 minutes)
- All performance metrics calculate correctly
- Portfolio and model pages load in < 2 seconds
- WebSocket updates arrive within 1 second
- Export functionality generates accurate reports
- Paper vs live comparison shows correctly
- All API endpoints return correct data
- Dashboard pages are responsive and accessible

## Notes

- Performance calculations should be cached to avoid database load
- Equity curve snapshots should be configurable (default: 5 minutes)
- Trade history pagination should support large datasets
- Export functionality can be implemented as P1 (defer if needed)
- Paper vs live comparison requires linking paper trading sessions to models
- Consider adding performance alerts (e.g., drawdown threshold exceeded)