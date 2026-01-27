-- Migration script for feature versioning
-- Week 7: Feature Versioning Implementation
-- Creates feature_pipelines table and adds version columns to features table

-- Create feature_pipelines table
CREATE TABLE IF NOT EXISTS feature_pipelines (
    id SERIAL PRIMARY KEY,
    version VARCHAR(50) UNIQUE NOT NULL,
    pipeline_hash VARCHAR(64) NOT NULL,
    feature_list JSONB NOT NULL,
    feature_definitions JSONB,
    code_commit VARCHAR(40),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_version ON feature_pipelines(version);
CREATE INDEX IF NOT EXISTS idx_hash ON feature_pipelines(pipeline_hash);

-- Add comment to table
COMMENT ON TABLE feature_pipelines IS 'Feature pipeline versions tracking feature computation code versions and metadata';

-- Add version columns to features table
ALTER TABLE features
ADD COLUMN IF NOT EXISTS pipeline_version VARCHAR(50),
ADD COLUMN IF NOT EXISTS first_seen_version VARCHAR(50);

-- Create index for pipeline_version
CREATE INDEX IF NOT EXISTS idx_pipeline_version ON features(pipeline_version);

-- Add comments to columns
COMMENT ON COLUMN features.pipeline_version IS 'Current pipeline version using this feature';
COMMENT ON COLUMN features.first_seen_version IS 'First pipeline version where this feature appeared';
