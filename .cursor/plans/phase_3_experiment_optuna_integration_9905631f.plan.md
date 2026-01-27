---
name: Phase 3 Experiment Optuna Integration
overview: Implement complete experiment management system with Optuna hyperparameter search integration, enabling users to create, configure, and run experiments with automated hyperparameter optimization.
todos:
  - id: phase3-database-schema
    content: Create database migration script 07_experiments.sql with experiments, optuna_studies, and optuna_trials tables
    status: completed
  - id: phase3-experiment-model
    content: Create Experiment dataclass and database repository methods in experiments/models.py
    status: completed
  - id: phase3-experiment-builder
    content: Implement ExperimentBuilder with validation and cloning in experiments/builder.py
    status: completed
  - id: phase3-experiment-runner
    content: Implement ExperimentRunner to start/stop experiments and integrate with TrainingLoop
    status: completed
  - id: phase3-optuna-tuner
    content: Create OptunaHyperparameterTuner with database integration and search space from PRD
    status: completed
  - id: phase3-mlflow-linking
    content: Enhance ExperimentTracker to link MLflow runs to experiments via tags and metadata
    status: completed
  - id: phase3-server-integration
    content: Initialize experiment components in Server.__init__ and wire up dependencies
    status: completed
  - id: phase3-unit-tests
    content: Write unit tests for ExperimentBuilder, ExperimentRunner, and OptunaTuner
    status: completed
  - id: phase3-integration-tests
    content: Write integration tests for complete experiment workflow and Optuna search
    status: completed
---

# Phase 3: Experiment & Optuna Integration Plan

## Overview

Phase 3 implements the core experimentation infrastructure that enables users to:

- Create and configure experiments with feature selection
- Run experiments with manual or Optuna-optimized hyperparameters
- Track experiment lifecycle and link to MLflow runs
- Store and query Optuna study and trial results

## Current State

**Existing Components:**

- `HyperparameterTuner` class exists but is basic and not integrated with experiments
- `ExperimentTracker` (MLflow) exists but doesn't link to experiment database records
- `TrainingLoop` exists but doesn't accept experiment configuration
- Database tables for experiments/Optuna do NOT exist yet

**Missing Components:**

- Experiment model and database persistence
- ExperimentBuilder for creating/validating experiments
- ExperimentRunner for executing experiments
- OptunaHyperparameterTuner integrated with database
- MLflow linking to experiment records

## Implementation Tasks

### 3.1 Database Schema Creation

**File**: `database/scripts/07_experiments.sql`

Create tables for experiments and Optuna integration:

```sql
-- Experiments table
CREATE TABLE experiments (
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
CREATE TABLE optuna_studies (
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
CREATE TABLE optuna_trials (
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
```

**Integration**: Run this migration script before implementing other components.

### 3.2 Experiment Model

**New File**: `src/mt5-python_server/src/experiments/__init__.py`

**New File**: `src/mt5-python_server/src/experiments/models.py`

Create Experiment dataclass and database operations:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

class ExperimentStatus(Enum):
    CREATED = 'created'
    TRAINING = 'training'
    COMPLETED = 'completed'
    FAILED = 'failed'
    PAUSED = 'paused'

@dataclass
class Experiment:
    id: Optional[int]
    name: str
    description: str
    features: List[str]  # Feature names from catalog
    currency_pairs: List[str]
    training_mode: str  # 'live' or 'historical'
    hyperparameters: Dict[str, Any]
    status: ExperimentStatus
    mlflow_run_id: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        ...
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Experiment':
        """Create from dictionary"""
        ...
```

**Database Operations**: Add methods to `database.py` or create `experiments/repository.py`:

- `create_experiment(experiment: Experiment) -> int` (returns experiment_id)
- `get_experiment(experiment_id: int) -> Optional[Experiment]`
- `update_experiment_status(experiment_id: int, status: ExperimentStatus)`
- `list_experiments(status: Optional[ExperimentStatus] = None) -> List[Experiment]`

### 3.3 Experiment Builder

**New File**: `src/mt5-python_server/src/experiments/builder.py`

Implement ExperimentBuilder for creating and validating experiments:

```python
class ExperimentBuilder:
    def __init__(self, db_connection, feature_catalog):
        """
        :param db_connection: Database connection
        :param feature_catalog: FeatureCatalog instance to validate features
        """
        ...
    
    def create_experiment(
        self,
        name: str,
        description: str,
        features: List[str],
        currency_pairs: List[str],
        training_mode: str,
        hyperparameters: Dict[str, Any]
    ) -> Experiment:
        """
        Create and validate a new experiment
        
        Validates:
        - Feature names exist in catalog
        - Currency pairs are valid
        - Hyperparameters match expected schema
        - Training mode is valid
        """
        ...
    
    def validate_experiment(self, experiment: Experiment) -> Tuple[bool, List[str]]:
        """
        Validate experiment configuration
        Returns: (is_valid, list_of_errors)
        """
        ...
    
    def clone_experiment(
        self,
        experiment_id: int,
        new_name: str,
        modifications: Optional[Dict[str, Any]] = None
    ) -> Experiment:
        """
        Clone an existing experiment with optional modifications
        """
        ...
```

**Validation Rules**:

- All features must exist in feature catalog
- At least one currency pair required
- Hyperparameters must include all required fields (learning_rate, gamma, batch_size, etc.)
- Training mode must be 'live' or 'historical'

### 3.4 Experiment Runner

**New File**: `src/mt5-python_server/src/experiments/runner.py`

Implement ExperimentRunner to execute experiments:

```python
class ExperimentRunner:
    def __init__(
        self,
        db_connection,
        experiment_tracker: ExperimentTracker,
        agent_factory,
        environment_factory,
        training_loop_factory
    ):
        """
        :param agent_factory: Factory to create agents with hyperparameters
        :param environment_factory: Factory to create environments with features
        :param training_loop_factory: Factory to create training loops
        """
        ...
    
    def start_experiment(self, experiment_id: int) -> bool:
        """
        Start training for an experiment
        
        Steps:
        1. Load experiment from database
        2. Validate experiment is in 'created' status
        3. Create agent with experiment hyperparameters
        4. Create environment with experiment features
        5. Start MLflow run and link to experiment
        6. Update experiment status to 'training'
        7. Start training loop in background thread
        8. Store training thread reference for stop capability
        """
        ...
    
    def stop_experiment(self, experiment_id: int) -> bool:
        """
        Stop a running experiment
        """
        ...
    
    def get_experiment_status(self, experiment_id: int) -> Dict[str, Any]:
        """
        Get current status and metrics for an experiment
        """
        ...
```

**Integration Points**:

- Use existing `AgentFactory` to create agents with hyperparameters
- Use existing `EnvironmentFactory` to create environments with selected features
- Use existing `TrainingLoop` but pass experiment_id and link MLflow run
- Update `ExperimentTracker` to accept and store `experiment_id` as tag

### 3.5 Optuna Hyperparameter Tuner

**New File**: `src/mt5-python_server/src/experiments/optuna_tuner.py`

Create OptunaHyperparameterTuner integrated with database:

```python
class OptunaHyperparameterTuner:
    def __init__(self, db_connection, experiment_runner: ExperimentRunner):
        """
        :param db_connection: Database connection
        :param experiment_runner: ExperimentRunner to execute trials
        """
        ...
    
    def create_study(
        self,
        experiment_id: int,
        metric: str = 'sharpe_ratio',
        direction: str = 'maximize',
        n_trials: int = 50,
        study_name: Optional[str] = None
    ) -> int:
        """
        Create Optuna study linked to experiment
        
        Returns: study_id
        """
        ...
    
    def run_trials(
        self,
        study_id: int,
        n_trials: Optional[int] = None,
        timeout: Optional[float] = None,
        n_jobs: int = 1
    ) -> Dict[str, Any]:
        """
        Run Optuna optimization trials
        
        Objective function:
        1. Create trial experiment with suggested hyperparameters
        2. Run experiment via ExperimentRunner
        3. Evaluate on validation set (or live performance)
        4. Return metric value (Sharpe ratio, win rate, etc.)
        5. Store trial results in database
        """
        ...
    
    def get_best_params(self, study_id: int) -> Dict[str, Any]:
        """Get best hyperparameters from study"""
        ...
    
    def get_trial_results(self, study_id: int) -> List[Dict[str, Any]]:
        """Get all trial results for a study"""
        ...
    
    def get_param_importance(self, study_id: int) -> Dict[str, float]:
        """Calculate parameter importance using Optuna"""
        ...
    
    def _suggest_hyperparameters(self, trial: optuna.Trial) -> Dict[str, Any]:
        """
        Define search space per PRD Section 10.3:
        - learning_rate: [0.00001, 0.01] log scale
        - gamma: [0.9, 0.999]
        - batch_size: [32, 64, 128, 256]
        - hidden_layers: [[64,64], [128,64], [256,128], [512,256]]
        - window_size: [20, 50, 100]
        - replay_buffer_size: [10000, 100000, 500000]
        - epsilon_end: [0.01, 0.1]
        - epsilon_decay: [5000, 10000, 50000]
        - target_update_freq: [100, 1000, 5000]
        """
        ...
```

**Database Integration**:

- Store study metadata in `optuna_studies` table
- Store each trial in `optuna_trials` table with params, value, metrics
- Link trials to MLflow runs via `mlflow_run_id`
- Update study best_params and best_value after each trial

**Pruning**: Use Optuna's MedianPruner to stop bad trials early (as per PRD FR-9.4)

### 3.6 Enhanced MLflow Integration

**File**: `src/mt5-python_server/src/mlops/experiment_tracker.py`

Enhance ExperimentTracker to link MLflow runs to experiments:

```python
class ExperimentTracker:
    def start_run(
        self,
        run_name: str,
        experiment_id: Optional[int] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Start MLflow run with experiment linking
        
        If experiment_id provided:
        - Add 'experiment_id' tag
        - Add experiment metadata as tags (features, pairs, mode)
        - Store run_id in experiments table
        """
        ...
    
    def log_experiment_config(self, experiment: Experiment):
        """Log experiment configuration as MLflow params"""
        ...
```

**Integration**: Update `TrainingLoop` to accept `experiment_id` and pass to tracker.

### 3.7 Server Integration

**File**: `src/mt5-python_server/src/server.py`

Initialize experiment components on server startup:

```python
class Server:
    def __init__(self, ...):
        ...
        # Initialize experiment components
        self.experiment_builder = ExperimentBuilder(
            db_connection=self.db,
            feature_catalog=self.feature_catalog
        )
        self.experiment_runner = ExperimentRunner(
            db_connection=self.db,
            experiment_tracker=self.experiment_tracker,
            agent_factory=self.agent_factory,
            environment_factory=self.environment_factory,
            training_loop_factory=self._create_training_loop
        )
        self.optuna_tuner = OptunaHyperparameterTuner(
            db_connection=self.db,
            experiment_runner=self.experiment_runner
        )
```

## Database Migration

**File**: `database/scripts/07_experiments.sql`

Run migration before implementing code:

```bash
mysql -u user -p database < database/scripts/07_experiments.sql
```

## Testing Requirements

**New File**: `tests/unit/test_experiments.py`

- Test ExperimentBuilder validation
- Test ExperimentRunner start/stop
- Test OptunaTuner study creation and trial execution
- Test database persistence

**New File**: `tests/integration/test_experiment_workflow.py`

- Test complete workflow: create → start → train → complete
- Test Optuna search with multiple trials
- Test MLflow linking

## Dependencies

**Phase 2 Prerequisites**:

- Feature catalog must be populated (Phase 2)
- Data providers must be registered (Phase 2)

**External Dependencies**:

- `optuna>=3.0.0` (already in requirements)
- `mlflow>=2.10.0` (already integrated)

## Success Criteria

- [ ] Database tables created and migrations run
- [ ] Experiments can be created via ExperimentBuilder
- [ ] Experiments can be started and stopped via ExperimentRunner
- [ ] TrainingLoop integrates with experiments and links MLflow runs
- [ ] Optuna studies can be created and trials executed
- [ ] Trial results stored in database with metrics
- [ ] Best hyperparameters can be retrieved and applied
- [ ] Parameter importance analysis works
- [ ] All PRD requirements (FR-7, FR-8, FR-9) met

## Files to Create/Modify

**New Files**:

- `database/scripts/07_experiments.sql`
- `src/mt5-python_server/src/experiments/__init__.py`
- `src/mt5-python_server/src/experiments/models.py`
- `src/mt5-python_server/src/experiments/builder.py`
- `src/mt5-python_server/src/experiments/runner.py`
- `src/mt5-python_server/src/experiments/optuna_tuner.py`
- `tests/unit/test_experiments.py`
- `tests/integration/test_experiment_workflow.py`

**Modified Files**:

- `src/mt5-python_server/src/mlops/experiment_tracker.py` (add experiment linking)
- `src/mt5-python_server/src/application/training/training_loop.py` (accept experiment_id)
- `src/mt5-python_server/src/server.py` (initialize experiment components)
- `src/mt5-python_server/src/database.py` (add experiment repository methods if needed)