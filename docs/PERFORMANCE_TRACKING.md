# Performance Tracking Documentation

## Overview

Phase 6 implements comprehensive live performance tracking for trading models, enabling users to monitor portfolio-level and model-specific performance metrics in real-time.

## Architecture

### Backend Components

1. **SessionManager** (`src/mt5-python_server/src/performance/session_manager.py`)
   - Manages trading session lifecycle
   - Tracks session start/end balances
   - Links models to trading sessions

2. **TradeLogger** (`src/mt5-python_server/src/performance/trade_logger.py`)
   - Logs trade entries when positions are opened
   - Logs trade exits when positions are closed
   - Tracks open positions per model/session

3. **EquityTracker** (`src/mt5-python_server/src/performance/equity_tracker.py`)
   - Records periodic equity snapshots (every 5 minutes by default)
   - Tracks balance, equity, and unrealized P&L
   - Calculates drawdown percentage

4. **PerformanceMetricsCalculator** (`src/mt5-python_server/src/performance/metrics_calculator.py`)
   - Calculates all performance metrics from trade data
   - Supports multiple time periods
   - Metrics include: Sharpe ratio, Sortino ratio, win rate, drawdown, profit factor, expectancy, etc.

### Database Schema

All performance tracking tables are defined in `src/database/scripts/06_performance_tracking.sql`:

- `live_trading_sessions` - Tracks active trading sessions per model
- `model_trades` - Individual trade records
- `daily_performance` - Daily snapshots for historical analysis
- `performance_metrics` - Real-time calculated metrics
- `equity_curve` - Time-series equity data for charts
- `portfolio_allocation` - Asset allocation tracking

### API Endpoints

All performance endpoints are available under `/api/v1/performance`:

**Portfolio Endpoints:**
- `GET /api/v1/performance/portfolio` - Portfolio summary
- `GET /api/v1/performance/portfolio/equity-curve` - Portfolio equity curve data
- `GET /api/v1/performance/portfolio/breakdown` - P&L breakdown by period
- `GET /api/v1/performance/portfolio/allocation` - Asset allocation

**Model Endpoints:**
- `GET /api/v1/performance/models` - List all model performance summaries
- `GET /api/v1/performance/models/{model_id}` - Detailed model performance
- `GET /api/v1/performance/models/{model_id}/equity-curve` - Model equity curve
- `GET /api/v1/performance/models/{model_id}/trades` - Trade history with pagination
- `GET /api/v1/performance/models/{model_id}/statistics` - Detailed statistics
- `GET /api/v1/performance/models/{model_id}/comparison` - Paper vs live comparison

**Real-time Endpoints:**
- `GET /api/v1/performance/metrics/realtime` - Real-time metrics for all active models

### WebSocket Updates

Performance updates are broadcast via WebSocket on the `/ws/performance` channel:

**Message Types:**
- `portfolio_update` - Portfolio-level performance updates
- `model_update` - Model-level performance updates
- `trade_executed` - Trade execution notifications

### Frontend Components

1. **PortfolioPerformance Page** (`src/dashboard/src/pages/PortfolioPerformance.tsx`)
   - Portfolio equity curve chart
   - Key metrics cards (Total P&L, Sharpe Ratio, Max Drawdown, Win Rate, etc.)
   - Model contributions table
   - P&L breakdown by period
   - Currency pair and model allocation

2. **ModelPerformance Page** (`src/dashboard/src/pages/ModelPerformance.tsx`)
   - Model equity curve chart with drawdown overlay
   - Performance summary section
   - Risk metrics section
   - Trade statistics section
   - Timing analysis
   - Recent trades table with pagination
   - Paper vs Live comparison

3. **EquityCurveChart Component** (`src/dashboard/src/components/charts/EquityCurveChart.tsx`)
   - Uses Lightweight Charts for visualization
   - Supports equity and drawdown overlay
   - Responsive design

## Integration Points

### Trade Logging

Trade logging should be integrated when:
- A model is assigned to an account (Phase 7)
- Trades are executed via ActionExecutor/TradeExecutor
- Positions are closed

**Example Integration:**
```python
from performance import TradeLogger, SessionManager

# When model starts trading
session_manager = SessionManager(db)
session_id = session_manager.create_session(model_id, start_balance)

# When trade is executed
trade_logger = TradeLogger(db)
trade_id = trade_logger.log_trade_entry(
    session_id=session_id,
    model_id=model_id,
    order_uuid=order_uuid,
    symbol=symbol,
    action=action,
    entry_price=entry_price,
    volume=volume
)

# When position is closed
trade_logger.log_trade_exit(
    trade_id=trade_id,
    exit_price=exit_price,
    pnl=pnl,
    pnl_pips=pnl_pips,
    duration_seconds=duration_seconds
)
```

### Equity Tracking

Equity tracking should be integrated in the training loop or TradingController:

```python
from performance import EquityTracker

equity_tracker = EquityTracker(snapshot_interval_minutes=5, db=db)
equity_tracker.start_tracking(model_id, session_id)

# In training loop or periodic task
if equity_tracker.should_record_snapshot(session_id):
    equity_tracker.record_snapshot(
        model_id=model_id,
        session_id=session_id,
        balance=current_balance,
        equity=current_equity,
        unrealized_pnl=unrealized_pnl
    )
```

### Metrics Calculation

Metrics are calculated on-demand via the API or can be pre-calculated:

```python
from performance import PerformanceMetricsCalculator

calculator = PerformanceMetricsCalculator(db=db)
metrics = calculator.calculate_all_metrics(
    model_id=model_id,
    session_id=session_id,
    period='all_time'
)
calculator.update_metrics_in_db(model_id, session_id, 'all_time', metrics)
```

## Performance Metrics

### Calculated Metrics

- **Win Rate**: Winning trades / Total trades × 100
- **Sharpe Ratio**: (Mean return - Risk-free) / Std deviation (annualized)
- **Sortino Ratio**: (Mean return - Risk-free) / Downside deviation (annualized)
- **Max Drawdown**: Largest peak-to-trough decline
- **Profit Factor**: Gross profit / Gross loss
- **Expectancy**: Expected value per trade
- **Average Win / Average Loss**: Mean of winning/losing trades
- **Longest Win/Loss Streaks**: Maximum consecutive wins/losses
- **Recovery Factor**: Net profit / Max drawdown

## Usage

### Running Database Migration

```bash
mysql -u forex_user -p db_forex < src/database/scripts/06_performance_tracking.sql
```

### Accessing Performance Data

1. **Via API:**
   ```bash
   curl http://localhost:8000/api/v1/performance/portfolio?period=all_time
   ```

2. **Via Dashboard:**
   - Navigate to "Portfolio Performance" page for aggregate metrics
   - Navigate to "Model Performance" page for model-specific metrics
   - Click on a model in the Model Registry to view detailed performance

3. **Via WebSocket:**
   ```javascript
   const ws = new WebSocket('ws://localhost:8000/ws/performance')
   ws.onmessage = (event) => {
     const message = JSON.parse(event.data)
     if (message.type === 'portfolio_update') {
       // Handle portfolio update
     }
   }
   ```

## Notes

- Performance calculations are cached in the `performance_metrics` table to avoid database load
- Equity curve snapshots are configurable (default: 5 minutes)
- Trade history pagination supports large datasets
- Export functionality (PDF/CSV) is implemented as placeholder and can be enhanced later
- Paper vs live comparison requires linking paper trading sessions to models (Phase 7)
