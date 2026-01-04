-- Phase 6: Live Performance Tracking Tables
-- Run this migration after Phase 7 (Models) is complete
-- Requires: models table (from Phase 7 - 10_models.sql)

USE db_forex;

-- Live trading sessions (tracks when a model is deployed to production)
CREATE TABLE IF NOT EXISTS live_trading_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active, paused, stopped
    start_balance DECIMAL(15, 2) NOT NULL,
    current_balance DECIMAL(15, 2) NOT NULL,
    high_water_mark DECIMAL(15, 2) NOT NULL,  -- For drawdown calculation
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP NULL,
    ended_reason VARCHAR(100),  -- 'user_stopped', 'kill_switch', 'replaced', etc.
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE,
    INDEX idx_model (model_id),
    INDEX idx_status (status),
    INDEX idx_started_at (started_at)
);

-- Individual trades executed by models
CREATE TABLE IF NOT EXISTS model_trades (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    model_id INT NOT NULL,
    order_uuid VARCHAR(36) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    action VARCHAR(10) NOT NULL,  -- 'BUY', 'SELL'
    entry_price DECIMAL(15, 5) NOT NULL,
    exit_price DECIMAL(15, 5),
    volume DECIMAL(10, 4) NOT NULL,
    pnl DECIMAL(15, 2),
    pnl_pips DECIMAL(10, 2),
    commission DECIMAL(10, 2) DEFAULT 0,
    swap DECIMAL(10, 2) DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'open',  -- 'open', 'closed', 'cancelled'
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP NULL,
    duration_seconds INT,
    FOREIGN KEY (session_id) REFERENCES live_trading_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE,
    INDEX idx_session (session_id),
    INDEX idx_model (model_id),
    INDEX idx_status (status),
    INDEX idx_opened_at (opened_at),
    INDEX idx_order_uuid (order_uuid)
);

-- Daily performance snapshots (for charts and historical analysis)
CREATE TABLE IF NOT EXISTS daily_performance (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT,  -- NULL for portfolio-level
    session_id INT,
    date DATE NOT NULL,
    starting_balance DECIMAL(15, 2) NOT NULL,
    ending_balance DECIMAL(15, 2) NOT NULL,
    pnl DECIMAL(15, 2) NOT NULL,
    pnl_pct DECIMAL(10, 4) NOT NULL,
    total_trades INT DEFAULT 0,
    winning_trades INT DEFAULT 0,
    losing_trades INT DEFAULT 0,
    gross_profit DECIMAL(15, 2) DEFAULT 0,
    gross_loss DECIMAL(15, 2) DEFAULT 0,
    max_drawdown DECIMAL(10, 4),
    sharpe_ratio DECIMAL(10, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_model_date (model_id, date),
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES live_trading_sessions(id) ON DELETE CASCADE,
    INDEX idx_model_date (model_id, date),
    INDEX idx_session (session_id),
    INDEX idx_date (date)
);

-- Real-time performance metrics (updated frequently)
CREATE TABLE IF NOT EXISTS performance_metrics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT,  -- NULL for portfolio-level
    session_id INT,
    metric_type VARCHAR(50) NOT NULL,  -- 'sharpe', 'sortino', 'win_rate', 'profit_factor', etc.
    value DECIMAL(15, 6) NOT NULL,
    period VARCHAR(20) NOT NULL,  -- 'realtime', 'daily', 'weekly', 'monthly', 'yearly', 'all_time'
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_metric (model_id, metric_type, period),
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES live_trading_sessions(id) ON DELETE CASCADE,
    INDEX idx_model_metric (model_id, metric_type),
    INDEX idx_period (period),
    INDEX idx_calculated_at (calculated_at)
);

-- Equity curve data points (for chart rendering)
CREATE TABLE IF NOT EXISTS equity_curve (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT,  -- NULL for portfolio-level
    session_id INT,
    timestamp TIMESTAMP NOT NULL,
    equity DECIMAL(15, 2) NOT NULL,
    balance DECIMAL(15, 2) NOT NULL,
    drawdown_pct DECIMAL(10, 4) NOT NULL,
    unrealized_pnl DECIMAL(15, 2) DEFAULT 0,
    INDEX idx_model_timestamp (model_id, timestamp),
    INDEX idx_session_timestamp (session_id, timestamp),
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES live_trading_sessions(id) ON DELETE CASCADE
);

-- Portfolio allocation tracking
CREATE TABLE IF NOT EXISTS portfolio_allocation (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model_id INT NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    position_value DECIMAL(15, 2) NOT NULL,
    allocation_pct DECIMAL(10, 4) NOT NULL,
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE,
    INDEX idx_model (model_id),
    INDEX idx_timestamp (timestamp),
    INDEX idx_symbol (symbol)
);
