-- Add balance, equity, and profit fields to MT5 accounts
-- Phase 18: MT5 Account Financial Data

-- Add balance, equity, and profit columns to mt5_accounts table
ALTER TABLE mt5_accounts
ADD COLUMN IF NOT EXISTS balance NUMERIC(15, 2),
ADD COLUMN IF NOT EXISTS equity NUMERIC(15, 2),
ADD COLUMN IF NOT EXISTS profit NUMERIC(15, 2);

-- Add index on balance for performance queries
CREATE INDEX IF NOT EXISTS idx_mt5_accounts_balance ON mt5_accounts(balance) WHERE balance IS NOT NULL;
