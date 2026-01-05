-- Migration script for feature versioning
-- Week 7: Feature Versioning Implementation
-- Creates feature_pipelines table and adds version columns to features table

-- Create feature_pipelines table
CREATE TABLE IF NOT EXISTS feature_pipelines (
    id INT PRIMARY KEY AUTO_INCREMENT,
    version VARCHAR(50) UNIQUE NOT NULL,
    pipeline_hash VARCHAR(64) NOT NULL,
    feature_list JSON NOT NULL,
    feature_definitions JSON,
    code_commit VARCHAR(40),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_version (version),
    INDEX idx_hash (pipeline_hash)
);

-- Add comment to table
ALTER TABLE feature_pipelines COMMENT = 'Feature pipeline versions tracking feature computation code versions and metadata';

-- Add version columns to features table
ALTER TABLE features
ADD COLUMN IF NOT EXISTS pipeline_version VARCHAR(50),
ADD COLUMN IF NOT EXISTS first_seen_version VARCHAR(50);

-- Create index for pipeline_version
CREATE INDEX IF NOT EXISTS idx_pipeline_version ON features(pipeline_version);

-- Add comment to columns
ALTER TABLE features MODIFY COLUMN pipeline_version VARCHAR(50) COMMENT 'Current pipeline version using this feature';
ALTER TABLE features MODIFY COLUMN first_seen_version VARCHAR(50) COMMENT 'First pipeline version where this feature appeared';
