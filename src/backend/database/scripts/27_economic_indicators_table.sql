-- Migration: Create economic_indicators table for macroeconomic indicator data
-- This table stores economic indicators from multiple sources (FRED, World Bank, ECB)

CREATE TABLE IF NOT EXISTS economic_indicators(
    id BIGSERIAL NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    series_id VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    source VARCHAR(50) NOT NULL,
    country VARCHAR(3),
    frequency VARCHAR(20),
    receive_time TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL,
    CONSTRAINT source_check CHECK (source IN ('FRED', 'WORLD_BANK', 'ECB', 'OTHER')),
    CONSTRAINT frequency_check CHECK (frequency IN ('DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'ANNUAL', NULL))
);

-- Add bitemporal columns (for consistency with other tables)
ALTER TABLE economic_indicators
ADD COLUMN IF NOT EXISTS latency_seconds INT NULL,
ADD COLUMN IF NOT EXISTS is_stale BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS stale_age_seconds INT NULL,
ADD COLUMN IF NOT EXISTS timestamp_source VARCHAR(20) DEFAULT 'event';

-- Add schema versioning columns (for consistency with Phase 1)
ALTER TABLE economic_indicators
ADD COLUMN IF NOT EXISTS schema_version VARCHAR(20) DEFAULT '1.0.0',
ADD COLUMN IF NOT EXISTS schema_type VARCHAR(50) DEFAULT 'economic';

-- Add indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_economic_indicators_series_timestamp 
    ON economic_indicators(series_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_economic_indicators_source_timestamp 
    ON economic_indicators(source, timestamp);
CREATE INDEX IF NOT EXISTS idx_economic_indicators_country_timestamp 
    ON economic_indicators(country, timestamp) WHERE country IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_economic_indicators_timestamp 
    ON economic_indicators(timestamp);
CREATE INDEX IF NOT EXISTS idx_economic_indicators_receive_time 
    ON economic_indicators(receive_time);
CREATE INDEX IF NOT EXISTS idx_economic_indicators_schema_version 
    ON economic_indicators(schema_version, schema_type);

-- Add trigger for updated_at column
CREATE TRIGGER update_economic_indicators_updated_at
    BEFORE UPDATE ON economic_indicators
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments
COMMENT ON TABLE economic_indicators IS 'Macroeconomic indicators from multiple sources (FRED, World Bank, ECB)';
COMMENT ON COLUMN economic_indicators.timestamp IS 'Event time (indicator observation time)';
COMMENT ON COLUMN economic_indicators.series_id IS 'Source-specific series identifier (e.g., FEDFUNDS for FRED)';
COMMENT ON COLUMN economic_indicators.value IS 'Indicator value';
COMMENT ON COLUMN economic_indicators.source IS 'Data source: FRED, WORLD_BANK, ECB, OTHER';
COMMENT ON COLUMN economic_indicators.country IS 'ISO country code (2-3 characters)';
COMMENT ON COLUMN economic_indicators.frequency IS 'Data frequency: DAILY, WEEKLY, MONTHLY, QUARTERLY, ANNUAL';
COMMENT ON COLUMN economic_indicators.receive_time IS 'Transaction time (when received)';
COMMENT ON COLUMN economic_indicators.latency_seconds IS 'Delay: receive_time - timestamp';
COMMENT ON COLUMN economic_indicators.is_stale IS 'Flag if original timestamp was stale';
COMMENT ON COLUMN economic_indicators.stale_age_seconds IS 'Age of stale timestamp';
COMMENT ON COLUMN economic_indicators.timestamp_source IS 'event, receive, estimated';
COMMENT ON COLUMN economic_indicators.schema_version IS 'Schema contract version used when data was ingested';
COMMENT ON COLUMN economic_indicators.schema_type IS 'Data type identifier (economic)';

-- Convert to TimescaleDB hypertable (1-month chunk interval for economic data)
SELECT create_hypertable('economic_indicators', 'timestamp', 
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE);

-- Create composite unique index (id, timestamp) for TimescaleDB compatibility
CREATE UNIQUE INDEX IF NOT EXISTS economic_indicators_id_timestamp_unique 
    ON economic_indicators(id, timestamp);

-- Create unique index to prevent duplicate indicators (same series_id, timestamp)
CREATE UNIQUE INDEX IF NOT EXISTS economic_indicators_unique_indicator 
    ON economic_indicators(series_id, timestamp);
