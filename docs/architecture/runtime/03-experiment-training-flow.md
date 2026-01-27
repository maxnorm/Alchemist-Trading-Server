# Runtime Scenario: Experiment Training Flow

## Purpose
This diagram answers: **How does the platform execute an experiment training run from creation to completion?**

## Scope
- **Includes**: Experiment creation, training execution, MLflow logging, model registration
- **Excludes**: Optuna hyperparameter search (separate diagram)

## Source of Truth References
| Step | Evidence Path |
|------|---------------|
| Experiment API | `src/api/src/routers/experiments.py` |
| Experiment Service | `src/api/src/services/experiment_service.py` |
| Experiment Builder | `src/trading_server/src/experiments/builder.py` |
| Experiment Runner | `src/trading_server/src/experiments/runner.py` |
| Experiment Tracker | `src/trading_server/src/mlops/experiment_tracker.py` |
| Agent Factory | `src/trading_server/src/infrastructure/factories/agent_factory.py` |
| Environment Factory | `src/trading_server/src/infrastructure/factories/environment_factory.py` |

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant Dashboard
    participant API as FastAPI
    participant DB as PostgreSQL
    participant Server as Trading Server
    participant Builder as Experiment Builder
    participant Runner as Experiment Runner
    participant Tracker as MLflow Tracker
    participant MLflow as MLflow Server
    participant Agent as DRL Agent
    participant Env as Trading Environment

    %% Experiment Creation
    User->>Dashboard: Configure experiment<br/>(features, pairs, hyperparams)
    Dashboard->>API: POST /api/experiments<br/>{name, features, currency_pairs, hyperparameters}
    
    API->>API: Validate request (Pydantic)
    API->>DB: INSERT INTO experiments
    DB-->>API: experiment_id
    API-->>Dashboard: 201 Created + experiment
    Dashboard-->>User: Experiment created (status: created)

    %% Start Training
    User->>Dashboard: Click "Start Training"
    Dashboard->>API: POST /api/experiments/{id}/start<br/>{confirm: true}
    
    API->>DB: UPDATE experiments SET status='training'
    API->>Server: Trigger training (async)
    API-->>Dashboard: 200 OK
    Dashboard-->>User: Training started

    %% Training Initialization
    Server->>Builder: build_experiment(experiment_id)
    Builder->>DB: Fetch experiment config
    Builder->>Builder: Validate features exist
    Builder->>Builder: Create Experiment object
    Builder-->>Server: Experiment instance

    Server->>Runner: run(experiment)
    
    %% MLflow Setup
    Runner->>Tracker: start_run(experiment.name)
    Tracker->>MLflow: Create MLflow run
    MLflow-->>Tracker: run_id
    
    Tracker->>Tracker: log_system_info()
    Tracker->>Tracker: log_reproducibility_metadata()
    Tracker->>MLflow: Log params, tags
    
    Runner->>DB: UPDATE experiments SET mlflow_run_id=?

    %% Agent & Environment Creation
    Runner->>Runner: AgentFactory.create(hyperparams)
    Runner->>Agent: Initialize DQN/Attention agent
    
    Runner->>Runner: EnvironmentFactory.create(mode, features)
    
    alt Historical Mode
        Runner->>Env: Create Historical Environment
        Env->>DB: Load historical data
    else Live Mode
        Runner->>Env: Create Live Environment
        Env->>Server: Connect to live connectors
    end

    %% Training Loop
    loop Each Episode
        Runner->>Env: reset()
        Env-->>Runner: initial_state
        
        loop Each Step
            Runner->>Agent: get_action(state)
            Agent-->>Runner: action
            
            Runner->>Env: step(action)
            Env-->>Runner: next_state, reward, done, info
            
            Runner->>Agent: remember(state, action, reward, next_state, done)
            Runner->>Agent: replay() - train on batch
            
            %% Periodic logging
            alt Every N steps
                Runner->>Tracker: log_metrics({loss, reward, epsilon}, step)
                Tracker->>MLflow: Log metrics
            end
        end
        
        %% Episode summary
        Runner->>Tracker: log_metrics({episode_reward, episode_length})
        
        %% WebSocket broadcast
        Runner->>API: Broadcast training progress
        API->>Dashboard: WebSocket /ws/training
        Dashboard-->>User: Update training metrics
    end

    %% Training Completion
    Runner->>Agent: Get final model
    Runner->>Tracker: log_model(model, "model")
    Tracker->>MLflow: Save model artifact
    
    Runner->>Tracker: log_metrics(final_metrics)
    Runner->>Tracker: end_run("FINISHED")
    
    Runner->>DB: UPDATE experiments SET status='completed'
    
    %% Model Registration
    Runner->>DB: INSERT INTO models (experiment_id, mlflow_run_id, ...)
    
    Runner->>API: Broadcast completion
    API->>Dashboard: WebSocket /ws/training
    Dashboard-->>User: Training completed!
```

## Flow Description

### 1. Experiment Creation
1. User configures experiment in ExperimentBuilder page:
   - Selects features from catalog
   - Chooses currency pairs
   - Sets hyperparameters (learning_rate, gamma, etc.)
   - Chooses training mode (live/historical)
2. API validates and persists to database
3. Experiment created with status `created`

### 2. Training Initiation
1. User clicks "Start Training" with confirmation
2. API updates status to `training`
3. Trading Server receives async trigger

### 3. MLflow Run Setup
1. ExperimentTracker creates new MLflow run
2. Logs reproducibility metadata:
   - Git commit hash
   - Python version
   - Config hash
   - Environment ID
3. Experiment linked via `mlflow_run_id`

### 4. Agent & Environment Setup
1. AgentFactory creates appropriate agent (DQN, Attention DQN)
2. EnvironmentFactory creates environment based on mode:
   - **Historical**: Loads data from database, replays
   - **Live**: Connects to real-time connectors

### 5. Training Loop
1. Standard RL loop: reset → step → remember → replay
2. Periodic metric logging to MLflow
3. WebSocket broadcasts for real-time dashboard updates

### 6. Completion & Model Registration
1. Final model saved as MLflow artifact
2. Experiment status updated to `completed`
3. Model registered in `models` table

## Training Modes

| Mode | Data Source | Use Case |
|------|-------------|----------|
| **Historical** | Database (ticks_forex) | Backtesting, initial training |
| **Live** | Real-time connectors | Online learning, paper trading |

## Logged Metrics

| Metric | Description |
|--------|-------------|
| `loss` | Training loss per step |
| `reward` | Step reward |
| `epsilon` | Exploration rate |
| `episode_reward` | Total episode reward |
| `episode_length` | Steps per episode |
| `sharpe_ratio` | Risk-adjusted returns |
| `win_rate` | Percentage of winning trades |
| `max_drawdown` | Maximum drawdown |

## Assumptions
- **None** - All training flows verified in codebase
