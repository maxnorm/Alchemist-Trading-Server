-- Model Registry and Paper Trading Sessions
-- Phase 7: MLOps & Model Lifecycle

-- Model registry (matches PRD Section 17.4)
CREATE TABLE IF NOT EXISTS models (
    id INT AUTO_INCREMENT PRIMARY KEY,
    version VARCHAR(50) UNIQUE NOT NULL,
    experiment_id INT,
    stage VARCHAR(20) NOT NULL DEFAULT 'staging',  -- training, staging, paper, production, archived
    features JSON NOT NULL,
    hyperparameters JSON NOT NULL,
    metrics JSON,
    mlflow_model_uri VARCHAR(500),
    mlflow_run_id VARCHAR(100),
    paper_trading_results JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    promoted_at TIMESTAMP NULL,
    promoted_by INT,  -- dashboard_users.id (for audit)
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE SET NULL,
    INDEX idx_stage (stage),
    INDEX idx_experiment (experiment_id),
    INDEX idx_mlflow_run (mlflow_run_id)
);

-- Paper trading sessions
CREATE TABLE IF NOT EXISTS paper_trading_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'running',  -- running, completed, stopped
    start_balance DECIMAL(15, 2),
    current_balance DECIMAL(15, 2),
    total_trades INT DEFAULT 0,
    winning_trades INT DEFAULT 0,
    pnl DECIMAL(15, 2) DEFAULT 0,
    sharpe_ratio DECIMAL(10, 4),
    max_drawdown DECIMAL(10, 4),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP NULL,
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE,
    INDEX idx_model_status (model_id, status),
    INDEX idx_started_at (started_at)
);
