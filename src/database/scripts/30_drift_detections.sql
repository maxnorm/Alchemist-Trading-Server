-- Drift Detection Results Storage
-- Phase 4: Observability & Lineage
-- Stores drift detection results

-- Drift detections table - Store drift detection results
CREATE TABLE IF NOT EXISTS drift_detections (
    id SERIAL NOT NULL,
    feature_name VARCHAR(255) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    detection_time TIMESTAMP NOT NULL,
    psi_score DECIMAL(10, 6),
    ks_statistic DECIMAL(10, 6),
    ks_pvalue DECIMAL(10, 6),
    drift_severity VARCHAR(20) NOT NULL,  -- 'none', 'minor', 'major'
    drift_detected BOOLEAN NOT NULL,
    baseline_window_start TIMESTAMP NOT NULL,
    baseline_window_end TIMESTAMP NOT NULL,
    current_window_start TIMESTAMP NOT NULL,
    current_window_end TIMESTAMP NOT NULL,
    baseline_size INTEGER,
    current_size INTEGER,
    baseline_mean DECIMAL(20, 10),
    baseline_std DECIMAL(20, 10),
    current_mean DECIMAL(20, 10),
    current_std DECIMAL(20, 10),
    mean_change_pct DECIMAL(10, 4),
    std_change_pct DECIMAL(10, 4),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, detection_time)  -- Composite primary key required for TimescaleDB hypertable
);

CREATE INDEX IF NOT EXISTS idx_drift_detections_feature_symbol ON drift_detections(feature_name, symbol);
CREATE INDEX IF NOT EXISTS idx_drift_detections_detection_time ON drift_detections(detection_time);
CREATE INDEX IF NOT EXISTS idx_drift_detections_severity ON drift_detections(drift_severity);
CREATE INDEX IF NOT EXISTS idx_drift_detections_detected ON drift_detections(drift_detected);
CREATE INDEX IF NOT EXISTS idx_drift_detections_symbol_time ON drift_detections(symbol, detection_time);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('drift_detections', 'detection_time', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Create composite unique index (id, detection_time) for TimescaleDB compatibility
CREATE UNIQUE INDEX IF NOT EXISTS drift_detections_id_detection_time_unique 
    ON drift_detections(id, detection_time);

-- Add comments
COMMENT ON TABLE drift_detections IS 'Drift detection results for features';
COMMENT ON COLUMN drift_detections.feature_name IS 'Name of the feature';
COMMENT ON COLUMN drift_detections.symbol IS 'Trading symbol';
COMMENT ON COLUMN drift_detections.detection_time IS 'When drift detection was performed';
COMMENT ON COLUMN drift_detections.psi_score IS 'Population Stability Index score';
COMMENT ON COLUMN drift_detections.ks_statistic IS 'Kolmogorov-Smirnov test statistic';
COMMENT ON COLUMN drift_detections.ks_pvalue IS 'Kolmogorov-Smirnov test p-value';
COMMENT ON COLUMN drift_detections.drift_severity IS 'Drift severity: none, minor, or major';
COMMENT ON COLUMN drift_detections.drift_detected IS 'Whether drift was detected';
