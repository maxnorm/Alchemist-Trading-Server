-- Feature Distributions Table
-- Phase 4: Observability & Lineage
-- Stores feature distribution statistics for drift detection

CREATE TABLE IF NOT EXISTS feature_distributions (
    id SERIAL NOT NULL,
    feature_name VARCHAR(255) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    mean DECIMAL(20, 10),
    std DECIMAL(20, 10),
    min_value DECIMAL(20, 10),
    max_value DECIMAL(20, 10),
    percentiles JSONB,  -- Stores percentiles: [10, 25, 50, 75, 90, 95, 99]
    sample_size INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, timestamp)  -- Composite primary key required for TimescaleDB hypertable
);

CREATE INDEX IF NOT EXISTS idx_feature_distributions_feature_symbol_time 
    ON feature_distributions(feature_name, symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_feature_distributions_symbol_time 
    ON feature_distributions(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_feature_distributions_timestamp 
    ON feature_distributions(timestamp);

-- Convert to TimescaleDB hypertable for time-series queries
SELECT create_hypertable('feature_distributions', 'timestamp', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Create composite unique index (id, timestamp) for TimescaleDB compatibility
CREATE UNIQUE INDEX IF NOT EXISTS feature_distributions_id_timestamp_unique 
    ON feature_distributions(id, timestamp);
