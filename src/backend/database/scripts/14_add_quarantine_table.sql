-- Migration: Add quarantine_ticks table for storing rejected ticks
-- This migration creates a table to capture all ticks rejected by quality gates
-- for review and analysis, enabling data quality monitoring and improvement.

-- Create quarantine_ticks table
CREATE TABLE IF NOT EXISTS quarantine_ticks (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(6) NOT NULL,
    datetime TIMESTAMP(6) NOT NULL,
    receive_time TIMESTAMP(6) NULL,
    bid DOUBLE PRECISION NOT NULL,
    ask DOUBLE PRECISION NOT NULL,
    rejection_reason TEXT NOT NULL,
    rejection_category VARCHAR(50) NOT NULL,
    quarantined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_symbol ON quarantine_ticks(symbol);
CREATE INDEX IF NOT EXISTS idx_datetime ON quarantine_ticks(datetime);
CREATE INDEX IF NOT EXISTS idx_rejection_category ON quarantine_ticks(rejection_category);
CREATE INDEX IF NOT EXISTS idx_quarantined_at ON quarantine_ticks(quarantined_at);
CREATE INDEX IF NOT EXISTS idx_symbol_datetime ON quarantine_ticks(symbol, datetime);

-- Add comments
COMMENT ON TABLE quarantine_ticks IS 'Quarantine table for ticks rejected by quality gates';
COMMENT ON COLUMN quarantine_ticks.symbol IS 'Currency pair symbol (e.g., EURUSD)';
COMMENT ON COLUMN quarantine_ticks.datetime IS 'Event time with microsecond precision';
COMMENT ON COLUMN quarantine_ticks.receive_time IS 'When tick was received (transaction time)';
COMMENT ON COLUMN quarantine_ticks.bid IS 'Bid price';
COMMENT ON COLUMN quarantine_ticks.ask IS 'Ask price';
COMMENT ON COLUMN quarantine_ticks.rejection_reason IS 'Detailed reason for rejection';
COMMENT ON COLUMN quarantine_ticks.rejection_category IS 'Categorized reason: outlier, duplicate, stale, missing_data, invalid_spread';
COMMENT ON COLUMN quarantine_ticks.quarantined_at IS 'When tick was quarantined';
