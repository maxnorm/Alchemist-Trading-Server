-- Migration: Create bars_forex table for OHLCV bar data
-- This table stores aggregated price bars (OHLCV) for multiple timeframes

CREATE TABLE IF NOT EXISTS bars_forex(
    id BIGSERIAL NOT NULL,
    datetime TIMESTAMP NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION,
    timeframe VARCHAR(10) NOT NULL,
    forex_pairs_id INT NOT NULL,
    CONSTRAINT forex_pairs_id_bars
        FOREIGN KEY (forex_pairs_id)
        REFERENCES forex_pairs(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT timeframe_check CHECK (timeframe IN ('M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1')),
    CONSTRAINT ohlcv_check CHECK (high >= low AND high >= open AND high >= close AND low <= open AND low <= close),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL
);

-- Add bitemporal columns (for consistency with ticks_forex)
ALTER TABLE bars_forex
ADD COLUMN IF NOT EXISTS receive_time TIMESTAMP NULL,
ADD COLUMN IF NOT EXISTS latency_seconds INT NULL,
ADD COLUMN IF NOT EXISTS is_stale BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS stale_age_seconds INT NULL,
ADD COLUMN IF NOT EXISTS timestamp_source VARCHAR(20) DEFAULT 'event';

-- Add schema versioning columns (for consistency with Phase 1)
ALTER TABLE bars_forex
ADD COLUMN IF NOT EXISTS schema_version VARCHAR(20) DEFAULT '1.0.0',
ADD COLUMN IF NOT EXISTS schema_type VARCHAR(50) DEFAULT 'bar';

-- Add indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_bars_pair_timeframe_datetime 
    ON bars_forex(forex_pairs_id, timeframe, datetime);
CREATE INDEX IF NOT EXISTS idx_bars_datetime 
    ON bars_forex(datetime);
CREATE INDEX IF NOT EXISTS idx_bars_timeframe_datetime 
    ON bars_forex(timeframe, datetime);
CREATE INDEX IF NOT EXISTS idx_bars_receive_time 
    ON bars_forex(receive_time);
CREATE INDEX IF NOT EXISTS idx_bars_schema_version 
    ON bars_forex(schema_version, schema_type);

-- Add trigger for updated_at column
CREATE TRIGGER update_bars_forex_updated_at
    BEFORE UPDATE ON bars_forex
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments
COMMENT ON TABLE bars_forex IS 'OHLCV bar data for forex pairs across multiple timeframes';
COMMENT ON COLUMN bars_forex.datetime IS 'Event time (bar start time) with microsecond precision';
COMMENT ON COLUMN bars_forex.timeframe IS 'Bar timeframe: M1, M5, M15, M30, H1, H4, D1';
COMMENT ON COLUMN bars_forex.receive_time IS 'Transaction time (when received) with microsecond precision';
COMMENT ON COLUMN bars_forex.latency_seconds IS 'Delay: receive_time - datetime';
COMMENT ON COLUMN bars_forex.is_stale IS 'Flag if original timestamp was stale';
COMMENT ON COLUMN bars_forex.stale_age_seconds IS 'Age of stale timestamp';
COMMENT ON COLUMN bars_forex.timestamp_source IS 'event, receive, estimated';
COMMENT ON COLUMN bars_forex.schema_version IS 'Schema contract version used when data was ingested';
COMMENT ON COLUMN bars_forex.schema_type IS 'Data type identifier (bar)';

-- Convert to TimescaleDB hypertable (1-day chunk interval)
SELECT create_hypertable('bars_forex', 'datetime', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Create composite unique index (id, datetime) for TimescaleDB compatibility
CREATE UNIQUE INDEX IF NOT EXISTS bars_forex_id_datetime_unique 
    ON bars_forex(id, datetime);

-- Create unique index to prevent duplicate bars (same symbol, timeframe, datetime)
CREATE UNIQUE INDEX IF NOT EXISTS bars_forex_unique_bar 
    ON bars_forex(forex_pairs_id, timeframe, datetime);
