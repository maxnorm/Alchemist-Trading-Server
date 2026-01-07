-- PostgreSQL migration: Indexes
-- Time-series queries on ticks_forex
CREATE INDEX IF NOT EXISTS idx_ticks_datetime ON ticks_forex(datetime);

-- Pair-specific time queries (most common for ML training)
CREATE INDEX IF NOT EXISTS idx_ticks_pair_datetime ON ticks_forex(forex_pairs_id, datetime);

-- Economic calendar queries
CREATE INDEX IF NOT EXISTS idx_economic_datetime ON economic_calendar(datetime);

-- Additional index for trade table if it exists
CREATE INDEX IF NOT EXISTS idx_trade_created_at ON trade(created_at);
