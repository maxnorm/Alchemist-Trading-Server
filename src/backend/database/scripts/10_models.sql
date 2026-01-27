-- Model Registry and Paper Trading Sessions
-- Phase 7: MLOps & Model Lifecycle

-- Model registry (matches PRD Section 17.4)
CREATE TABLE IF NOT EXISTS models (
    id SERIAL PRIMARY KEY,
    version VARCHAR(50) UNIQUE NOT NULL,
    experiment_id INT,
    stage VARCHAR(20) NOT NULL DEFAULT 'staging',  -- training, staging, paper, production, archived
    features JSONB NOT NULL,
    hyperparameters JSONB NOT NULL,
    metrics JSONB,
    mlflow_model_uri VARCHAR(500),
    mlflow_run_id VARCHAR(100),
    paper_trading_results JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    promoted_at TIMESTAMP NULL,
    promoted_by INT,  -- dashboard_users.id (for audit)
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_stage ON models(stage);
CREATE INDEX IF NOT EXISTS idx_experiment ON models(experiment_id);
CREATE INDEX IF NOT EXISTS idx_mlflow_run ON models(mlflow_run_id);

-- Paper trading sessions
CREATE TABLE IF NOT EXISTS paper_trading_sessions (
    id SERIAL PRIMARY KEY,
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
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_model_status ON paper_trading_sessions(model_id, status);
CREATE INDEX IF NOT EXISTS idx_started_at ON paper_trading_sessions(started_at);
