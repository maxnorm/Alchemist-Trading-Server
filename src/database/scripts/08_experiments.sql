-- Phase 3: Experiments and Optuna Integration Tables
-- Run this migration after Phase 2 (Feature Catalog) is complete

USE db_forex;

-- Experiments table
CREATE TABLE IF NOT EXISTS experiments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    features JSON NOT NULL,  -- Array of feature names
    currency_pairs JSON NOT NULL,  -- Array of symbols
    training_mode ENUM('live', 'historical') NOT NULL,
    hyperparameters JSON NOT NULL,
    status ENUM('created', 'training', 'completed', 'failed', 'paused') DEFAULT 'created',
    mlflow_run_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
);

-- Optuna studies table
CREATE TABLE IF NOT EXISTS optuna_studies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    experiment_id INT NOT NULL,
    study_name VARCHAR(200) NOT NULL,
    direction ENUM('maximize', 'minimize') DEFAULT 'maximize',
    metric VARCHAR(50) NOT NULL,  -- 'sharpe_ratio', 'win_rate', 'total_pnl'
    n_trials INT NOT NULL,
    status ENUM('running', 'completed', 'failed', 'stopped') DEFAULT 'running',
    best_trial_number INT,
    best_value DECIMAL(10, 6),
    best_params JSON,
    param_importance JSON,  -- From Optuna's importance analysis
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
    INDEX idx_experiment (experiment_id),
    INDEX idx_status (status)
);

-- Optuna trials table
CREATE TABLE IF NOT EXISTS optuna_trials (
    id INT AUTO_INCREMENT PRIMARY KEY,
    study_id INT NOT NULL,
    trial_number INT NOT NULL,
    params JSON NOT NULL,
    value DECIMAL(10, 6),  -- Objective value
    state ENUM('running', 'complete', 'pruned', 'fail') DEFAULT 'running',
    metrics JSON,  -- Additional metrics: sharpe, win_rate, drawdown, etc.
    mlflow_run_id VARCHAR(100),  -- Link to MLflow run for this trial
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    FOREIGN KEY (study_id) REFERENCES optuna_studies(id) ON DELETE CASCADE,
    INDEX idx_study (study_id),
    INDEX idx_trial_number (study_id, trial_number),
    INDEX idx_state (state)
);
