-- Lineage Tracking Tables
-- Phase 4: Observability & Lineage
-- Stores OpenLineage events for data provenance tracking

-- Lineage jobs - Track job definitions
CREATE TABLE IF NOT EXISTS lineage_jobs (
    id SERIAL PRIMARY KEY,
    job_name VARCHAR(255) NOT NULL,
    namespace VARCHAR(100) NOT NULL,
    description TEXT,
    latest_run_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (job_name, namespace)
);

CREATE INDEX IF NOT EXISTS idx_lineage_jobs_namespace ON lineage_jobs(namespace);
CREATE INDEX IF NOT EXISTS idx_lineage_jobs_name ON lineage_jobs(job_name);

-- Lineage datasets - Track datasets
CREATE TABLE IF NOT EXISTS lineage_datasets (
    id SERIAL PRIMARY KEY,
    dataset_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    namespace VARCHAR(100) NOT NULL,
    schema_version VARCHAR(50),
    schema_json JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (dataset_id, namespace)
);

CREATE INDEX IF NOT EXISTS idx_lineage_datasets_namespace ON lineage_datasets(namespace);
CREATE INDEX IF NOT EXISTS idx_lineage_datasets_name ON lineage_datasets(name);

-- Lineage runs - Track data collection runs (TimescaleDB hypertable)
CREATE TABLE IF NOT EXISTS lineage_runs (
    id SERIAL NOT NULL,
    run_id VARCHAR(255) NOT NULL,
    job_name VARCHAR(255) NOT NULL,
    namespace VARCHAR(100) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status VARCHAR(50) NOT NULL,  -- 'RUNNING', 'COMPLETE', 'FAILED', 'ABORTED'
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, start_time),  -- Composite primary key required for hypertable
    FOREIGN KEY (job_name, namespace) REFERENCES lineage_jobs(job_name, namespace) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_lineage_runs_job ON lineage_runs(job_name, namespace);
CREATE INDEX IF NOT EXISTS idx_lineage_runs_status ON lineage_runs(status);
CREATE INDEX IF NOT EXISTS idx_lineage_runs_start_time ON lineage_runs(start_time);
CREATE INDEX IF NOT EXISTS idx_lineage_runs_run_id ON lineage_runs(run_id);  -- Regular index for lookups

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('lineage_runs', 'start_time', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Create composite unique index (run_id, start_time) for TimescaleDB compatibility
-- Note: This allows duplicate run_id at different times, but is required for hypertables
-- Application code should enforce global run_id uniqueness if needed
CREATE UNIQUE INDEX IF NOT EXISTS lineage_runs_id_start_time_unique 
    ON lineage_runs(id, start_time);
CREATE UNIQUE INDEX IF NOT EXISTS lineage_runs_run_id_start_time_unique 
    ON lineage_runs(run_id, start_time);

-- Lineage run datasets - Link runs to input/output datasets
CREATE TABLE IF NOT EXISTS lineage_run_datasets (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) NOT NULL,
    dataset_id VARCHAR(255) NOT NULL,
    io_type VARCHAR(20) NOT NULL,  -- 'input' or 'output'
    namespace VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Note: Foreign key on run_id removed due to TimescaleDB hypertable constraints
    -- Referential integrity should be enforced in application code
    FOREIGN KEY (dataset_id, namespace) REFERENCES lineage_datasets(dataset_id, namespace) ON DELETE CASCADE,
    UNIQUE (run_id, dataset_id, io_type)
);

CREATE INDEX IF NOT EXISTS idx_lineage_run_datasets_run ON lineage_run_datasets(run_id);
CREATE INDEX IF NOT EXISTS idx_lineage_run_datasets_dataset ON lineage_run_datasets(dataset_id);
CREATE INDEX IF NOT EXISTS idx_lineage_run_datasets_io_type ON lineage_run_datasets(io_type);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_lineage_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_lineage_jobs_updated_at
    BEFORE UPDATE ON lineage_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_lineage_updated_at();

CREATE TRIGGER update_lineage_datasets_updated_at
    BEFORE UPDATE ON lineage_datasets
    FOR EACH ROW
    EXECUTE FUNCTION update_lineage_updated_at();
