-- PostgreSQL migration: Safety infrastructure tables

-- Create ENUM types for PostgreSQL
DO $$ BEGIN
    CREATE TYPE order_side_enum AS ENUM ('BUY', 'SELL');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE order_type_enum AS ENUM ('MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE order_state_enum AS ENUM ('PENDING_NEW', 'NEW', 'PARTIALLY_FILLED', 'FILLED', 
                                          'PENDING_CANCEL', 'CANCELLED', 'REJECTED', 'EXPIRED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Orders table for OMS
CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR(64) PRIMARY KEY,
    client_order_id VARCHAR(100),
    experiment_id INT NULL,
    account_login INT NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    side order_side_enum NOT NULL,
    order_type order_type_enum DEFAULT 'MARKET',
    quantity DECIMAL(15, 6) NOT NULL,
    price DECIMAL(15, 6) NULL,
    stop_loss DECIMAL(15, 6) NULL,
    take_profit DECIMAL(15, 6) NULL,
    state order_state_enum DEFAULT 'PENDING_NEW',
    filled_quantity DECIMAL(15, 6) DEFAULT 0,
    average_fill_price DECIMAL(15, 6) DEFAULT 0,
    broker_order_id VARCHAR(100) NULL,
    reject_reason TEXT NULL,
    metadata JSONB NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_experiment ON orders(experiment_id);
CREATE INDEX IF NOT EXISTS idx_account ON orders(account_login);
CREATE INDEX IF NOT EXISTS idx_client_order_id ON orders(client_order_id);
CREATE INDEX IF NOT EXISTS idx_state ON orders(state);
CREATE INDEX IF NOT EXISTS idx_symbol ON orders(symbol);

-- Add trigger for updated_at column
CREATE TRIGGER update_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Kill switch events table
CREATE TABLE IF NOT EXISTS kill_switch_events (
    id SERIAL PRIMARY KEY,
    trigger_source VARCHAR(50) NOT NULL,
    reason TEXT NOT NULL,
    positions_closed INT DEFAULT 0,
    approver VARCHAR(100) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS idx_created_at ON kill_switch_events(created_at);
CREATE INDEX IF NOT EXISTS idx_resolved_at ON kill_switch_events(resolved_at);

-- Circuit breaker events table
CREATE TABLE IF NOT EXISTS circuit_breaker_events (
    id SERIAL PRIMARY KEY,
    breaker_type VARCHAR(50) NOT NULL,  -- 'loss', 'volatility', 'error', 'latency'
    trigger_value DECIMAL(10, 4) NOT NULL,
    threshold_value DECIMAL(10, 4) NOT NULL,
    trip_reason TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resumed_at TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS idx_created_at ON circuit_breaker_events(created_at);
CREATE INDEX IF NOT EXISTS idx_resumed_at ON circuit_breaker_events(resumed_at);
