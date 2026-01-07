-- MT5 Accounts and Connection Management
-- Phase 17: MT5 Account Management

-- MT5 Accounts registered in the system
CREATE TABLE IF NOT EXISTS mt5_accounts (
    id SERIAL PRIMARY KEY,
    account_login BIGINT UNIQUE NOT NULL,
    account_type VARCHAR(20) NOT NULL,  -- 'demo', 'live'
    broker_name VARCHAR(100),
    broker_server VARCHAR(100),
    account_currency VARCHAR(10),
    account_leverage INT,
    account_name VARCHAR(100),  -- User-friendly name (editable)
    is_active BOOLEAN DEFAULT TRUE,
    last_seen_at TIMESTAMP NULL,  -- Last time EA connected
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mt5_accounts_login ON mt5_accounts(account_login);
CREATE INDEX IF NOT EXISTS idx_mt5_accounts_active ON mt5_accounts(is_active);
CREATE INDEX IF NOT EXISTS idx_mt5_accounts_type ON mt5_accounts(account_type);

-- Model assignments to MT5 accounts
CREATE TABLE IF NOT EXISTS account_model_assignments (
    id SERIAL PRIMARY KEY,
    account_id INT NOT NULL,
    model_id INT NOT NULL,
    trading_mode VARCHAR(20) NOT NULL,  -- 'paper', 'live'
    is_active BOOLEAN DEFAULT TRUE,  -- Only one active assignment per account
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by INT,  -- dashboard_users.id (nullable for now, add FK later)
    deactivated_at TIMESTAMP NULL,
    deactivated_by INT NULL,
    notes TEXT,
    FOREIGN KEY (account_id) REFERENCES mt5_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE,
    CONSTRAINT unique_active_account UNIQUE (account_id, is_active) DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX IF NOT EXISTS idx_account_model_assignments_model ON account_model_assignments(model_id);
CREATE INDEX IF NOT EXISTS idx_account_model_assignments_active ON account_model_assignments(is_active);
CREATE INDEX IF NOT EXISTS idx_account_model_assignments_assigned_at ON account_model_assignments(assigned_at);

-- Connection status tracking
CREATE TABLE IF NOT EXISTS mt5_connections (
    id SERIAL PRIMARY KEY,
    account_id INT NOT NULL,
    terminal_id INT,  -- Terminal ID from MT5Terminal
    ea_version VARCHAR(50),
    connection_ip VARCHAR(45),
    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    disconnected_at TIMESTAMP NULL,
    disconnect_reason VARCHAR(100),
    is_connected BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (account_id) REFERENCES mt5_accounts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mt5_connections_account_connected ON mt5_connections(account_id, is_connected);
CREATE INDEX IF NOT EXISTS idx_mt5_connections_connected_at ON mt5_connections(connected_at);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_mt5_accounts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
CREATE TRIGGER trigger_update_mt5_accounts_updated_at
    BEFORE UPDATE ON mt5_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_mt5_accounts_updated_at();
