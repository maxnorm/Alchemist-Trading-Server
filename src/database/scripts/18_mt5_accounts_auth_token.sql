-- MT5 Accounts - Auth Token Support
-- Phase 18: Add per-account auth token for EA authentication

ALTER TABLE mt5_accounts
ADD COLUMN IF NOT EXISTS auth_token VARCHAR(128);

CREATE INDEX IF NOT EXISTS idx_mt5_accounts_auth_token ON mt5_accounts(auth_token);

