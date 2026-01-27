-- Add fields for Python API connection (simplified - no connection_method needed)
-- Phase 19: MT5 Python API Migration

-- Add encrypted password and server fields for Python API connection
ALTER TABLE mt5_accounts 
ADD COLUMN IF NOT EXISTS mt5_password_encrypted BYTEA,
ADD COLUMN IF NOT EXISTS mt5_server VARCHAR(100);

-- Index for server filtering
CREATE INDEX IF NOT EXISTS idx_mt5_accounts_server 
    ON mt5_accounts(mt5_server) WHERE mt5_server IS NOT NULL;

-- Note: auth_token field remains for backward compatibility but is not used for new Python API accounts
