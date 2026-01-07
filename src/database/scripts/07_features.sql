-- Migration script for features table
-- Phase 2: Data Source Plugin System
-- Creates table to store feature metadata from data providers

CREATE TABLE IF NOT EXISTS features (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    data_type VARCHAR(20) NOT NULL,
    source VARCHAR(50) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    available BOOLEAN DEFAULT TRUE,
    min_value DOUBLE PRECISION,
    max_value DOUBLE PRECISION,
    mean_value DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_source ON features(source);
CREATE INDEX IF NOT EXISTS idx_category ON features(category);
CREATE INDEX IF NOT EXISTS idx_available ON features(available);
CREATE INDEX IF NOT EXISTS idx_name ON features(name);

-- Add trigger for updated_at column
CREATE TRIGGER update_features_updated_at
    BEFORE UPDATE ON features
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Add comment to table
COMMENT ON TABLE features IS 'Feature catalog storing metadata for all available features from data providers';
