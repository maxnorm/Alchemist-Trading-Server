-- Phase 3: Experiments and Optuna Integration Tables
-- Run this migration after Phase 2 (Feature Catalog) is complete

-- Create ENUM types for PostgreSQL
DO $$ BEGIN
    CREATE TYPE training_mode_enum AS ENUM ('live', 'historical');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE experiment_status_enum AS ENUM ('created', 'training', 'completed', 'failed', 'paused');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE direction_enum AS ENUM ('maximize', 'minimize');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE study_status_enum AS ENUM ('running', 'completed', 'failed', 'stopped');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE trial_state_enum AS ENUM ('running', 'complete', 'pruned', 'fail');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Experiments table
CREATE TABLE IF NOT EXISTS experiments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    features JSONB NOT NULL,  -- Array of feature names
    currency_pairs JSONB NOT NULL,  -- Array of symbols
    training_mode training_mode_enum NOT NULL,
    hyperparameters JSONB NOT NULL,
    status experiment_status_enum DEFAULT 'created',
    mlflow_run_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS idx_status ON experiments(status);
CREATE INDEX IF NOT EXISTS idx_created_at ON experiments(created_at);

-- Optuna studies table
CREATE TABLE IF NOT EXISTS optuna_studies (
    id SERIAL PRIMARY KEY,
    experiment_id INT NOT NULL,
    study_name VARCHAR(200) NOT NULL,
    direction direction_enum DEFAULT 'maximize',
    metric VARCHAR(50) NOT NULL,  -- 'sharpe_ratio', 'win_rate', 'total_pnl'
    n_trials INT NOT NULL,
    status study_status_enum DEFAULT 'running',
    best_trial_number INT,
    best_value DECIMAL(10, 6),
    best_params JSONB,
    param_importance JSONB,  -- From Optuna's importance analysis
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_experiment ON optuna_studies(experiment_id);
CREATE INDEX IF NOT EXISTS idx_status ON optuna_studies(status);

-- Optuna trials table
CREATE TABLE IF NOT EXISTS optuna_trials (
    id SERIAL PRIMARY KEY,
    study_id INT NOT NULL,
    trial_number INT NOT NULL,
    params JSONB NOT NULL,
    value DECIMAL(10, 6),  -- Objective value
    state trial_state_enum DEFAULT 'running',
    metrics JSONB,  -- Additional metrics: sharpe, win_rate, drawdown, etc.
    mlflow_run_id VARCHAR(100),  -- Link to MLflow run for this trial
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    FOREIGN KEY (study_id) REFERENCES optuna_studies(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_study ON optuna_trials(study_id);
CREATE INDEX IF NOT EXISTS idx_trial_number ON optuna_trials(study_id, trial_number);
CREATE INDEX IF NOT EXISTS idx_state ON optuna_trials(state);
