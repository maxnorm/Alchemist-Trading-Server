USE db_forex;

-- Orders table for OMS
CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR(64) PRIMARY KEY,
    client_order_id VARCHAR(100),
    experiment_id INT NULL,
    account_login INT NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    side ENUM('BUY', 'SELL') NOT NULL,
    order_type ENUM('MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT') DEFAULT 'MARKET',
    quantity DECIMAL(15, 6) NOT NULL,
    price DECIMAL(15, 6) NULL,
    stop_loss DECIMAL(15, 6) NULL,
    take_profit DECIMAL(15, 6) NULL,
    state ENUM('PENDING_NEW', 'NEW', 'PARTIALLY_FILLED', 'FILLED', 
               'PENDING_CANCEL', 'CANCELLED', 'REJECTED', 'EXPIRED') DEFAULT 'PENDING_NEW',
    filled_quantity DECIMAL(15, 6) DEFAULT 0,
    average_fill_price DECIMAL(15, 6) DEFAULT 0,
    broker_order_id VARCHAR(100) NULL,
    reject_reason TEXT NULL,
    metadata JSON NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_experiment (experiment_id),
    INDEX idx_account (account_login),
    INDEX idx_client_order_id (client_order_id),
    INDEX idx_state (state),
    INDEX idx_symbol (symbol)
);

-- Kill switch events table
CREATE TABLE IF NOT EXISTS kill_switch_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trigger_source VARCHAR(50) NOT NULL,
    reason TEXT NOT NULL,
    positions_closed INT DEFAULT 0,
    approver VARCHAR(100) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    INDEX idx_created_at (created_at),
    INDEX idx_resolved_at (resolved_at)
);

-- Circuit breaker events table
CREATE TABLE IF NOT EXISTS circuit_breaker_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    breaker_type VARCHAR(50) NOT NULL,  -- 'loss', 'volatility', 'error', 'latency'
    trigger_value DECIMAL(10, 4) NOT NULL,
    threshold_value DECIMAL(10, 4) NOT NULL,
    trip_reason TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resumed_at TIMESTAMP NULL,
    INDEX idx_created_at (created_at),
    INDEX idx_resumed_at (resumed_at)
);
