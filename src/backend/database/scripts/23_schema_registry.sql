-- Migration script for Schema Registry
-- Phase 1: Foundation - Schema Registry Implementation
-- Creates schema_registry table to store JSON schema definitions with versioning support

-- Create schema_registry table to store schema definitions
CREATE TABLE IF NOT EXISTS schema_registry (
    id SERIAL PRIMARY KEY,
    data_type VARCHAR(50) NOT NULL,
    version VARCHAR(20) NOT NULL,
    schema_json JSONB NOT NULL,  -- JSON Schema definition (Draft 7 format)
    compatibility_mode VARCHAR(20) NOT NULL DEFAULT 'NONE',  -- 'BACKWARD', 'FORWARD', 'FULL', 'NONE'
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- 'active', 'deprecated', 'archived'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL,
    UNIQUE (data_type, version)
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_schema_registry_data_type_version ON schema_registry(data_type, version);
CREATE INDEX IF NOT EXISTS idx_schema_registry_data_type_status ON schema_registry(data_type, status);

-- Add trigger for updated_at column
CREATE TRIGGER update_schema_registry_updated_at
    BEFORE UPDATE ON schema_registry
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Add comments
COMMENT ON TABLE schema_registry IS 'Schema Registry - Stores JSON schema definitions with versioning and compatibility tracking';
COMMENT ON COLUMN schema_registry.data_type IS 'Data type identifier (e.g., tick, bar, news, economic)';
COMMENT ON COLUMN schema_registry.version IS 'Semantic version (MAJOR.MINOR.PATCH format)';
COMMENT ON COLUMN schema_registry.schema_json IS 'JSON Schema definition in Draft 7 format';
COMMENT ON COLUMN schema_registry.compatibility_mode IS 'Compatibility mode: BACKWARD, FORWARD, FULL, or NONE';
COMMENT ON COLUMN schema_registry.status IS 'Schema status: active, deprecated, or archived';
