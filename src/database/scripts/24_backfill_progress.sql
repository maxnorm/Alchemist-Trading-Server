-- Migration: Create backfill_progress table for tracking historical data backfill progress
-- This enables resuming failed backfills and tracking statistics

CREATE TABLE IF NOT EXISTS backfill_progress(
    id BIGSERIAL PRIMARY KEY,
    connector_type VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    last_successful_time TIMESTAMP,
    records_collected BIGINT DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL,
    CONSTRAINT status_check CHECK (status IN ('pending', 'in_progress', 'completed', 'failed'))
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_backfill_progress_connector_symbol_status 
    ON backfill_progress(connector_type, symbol, status);
CREATE INDEX IF NOT EXISTS idx_backfill_progress_symbol_time 
    ON backfill_progress(symbol, start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_backfill_progress_status 
    ON backfill_progress(status);

-- Add updated_at trigger
CREATE TRIGGER update_backfill_progress_updated_at
    BEFORE UPDATE ON backfill_progress
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE backfill_progress IS 'Tracks progress of historical data backfill operations';
COMMENT ON COLUMN backfill_progress.connector_type IS 'Type of connector (e.g., mt5_tick)';
COMMENT ON COLUMN backfill_progress.symbol IS 'Trading symbol being backfilled';
COMMENT ON COLUMN backfill_progress.start_time IS 'Start time of backfill range';
COMMENT ON COLUMN backfill_progress.end_time IS 'End time of backfill range';
COMMENT ON COLUMN backfill_progress.last_successful_time IS 'Last successfully processed timestamp (for resume)';
COMMENT ON COLUMN backfill_progress.records_collected IS 'Number of records collected so far';
COMMENT ON COLUMN backfill_progress.status IS 'Status: pending, in_progress, completed, failed';
COMMENT ON COLUMN backfill_progress.error_message IS 'Error message if status is failed';
