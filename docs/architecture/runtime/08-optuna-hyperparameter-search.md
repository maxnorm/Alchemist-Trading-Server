# Runtime Scenario: Optuna Hyperparameter Search

## Purpose
This diagram answers: **How does the platform perform automated hyperparameter optimization using Optuna?**

## Scope
- **Includes**: Study creation, trial execution, pruning, best params selection
- **Excludes**: Individual training details

## Source of Truth References
| Step | Evidence Path |
|------|---------------|
| Optuna Tuner | `src/trading_server/src/experiments/optuna_tuner.py` |
| Hyperparameters API | `src/api/src/routers/hyperparameters.py` |
| Optuna Schema | `src/database/scripts/08_experiments.sql:55-93` |
| Dashboard Page | `src/dashboard/src/pages/HyperparameterSearch.tsx` |
| API Client | `src/dashboard/src/services/api.ts:116-143` |

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant Dashboard
    participant API as FastAPI
    participant DB as PostgreSQL
    participant Tuner as Optuna Tuner
    participant Optuna as Optuna Framework
    participant Runner as Experiment Runner
    participant Tracker as MLflow Tracker

    %% Configure search
    User->>Dashboard: Configure search<br/>(n_trials, metric, param_ranges)
    Dashboard->>API: POST /api/hyperparameters/search<br/>{experiment_id, n_trials, metric, param_space}
    
    API->>DB: Validate experiment exists
    API->>DB: INSERT INTO optuna_studies<br/>{experiment_id, study_name, direction, metric, n_trials}
    DB-->>API: study_id
    
    API->>Tuner: start_study(experiment_id, config)
    API-->>Dashboard: 202 Accepted + study_id
    Dashboard-->>User: Search started

    %% Study initialization
    Tuner->>Optuna: create_study(direction="maximize")
    Optuna-->>Tuner: study object
    
    Tuner->>DB: UPDATE optuna_studies SET status='running'

    %% Trial loop
    loop n_trials
        Tuner->>Optuna: study.ask()
        Optuna-->>Tuner: trial (suggested params)
        
        Note over Tuner: Suggested params:<br/>learning_rate: 0.001<br/>gamma: 0.95<br/>epsilon_decay: 0.995
        
        %% Log trial start
        Tuner->>DB: INSERT INTO optuna_trials<br/>{study_id, trial_number, params, state: 'running'}
        
        %% Execute trial (shortened training)
        Tuner->>Runner: run_trial(experiment, params)
        Runner->>Tracker: start_run(f"trial_{trial_number}")
        Tracker->>Tracker: Log params
        
        Runner->>Runner: Train for N episodes
        
        loop Each Episode
            Runner->>Runner: Training step
            
            %% Pruning check
            alt Intermediate result bad
                Runner->>Optuna: trial.report(intermediate_value, step)
                Optuna->>Optuna: Check pruning
                alt Should prune
                    Optuna-->>Runner: raise TrialPruned
                    Runner->>Tracker: end_run("KILLED")
                    Tuner->>DB: UPDATE optuna_trials SET state='pruned'
                    
                    %% Broadcast pruned
                    Tuner->>API: WebSocket /ws/optuna
                    API->>Dashboard: Trial pruned
                    Dashboard-->>User: Trial X pruned
                end
            end
        end
        
        %% Trial completed
        Runner->>Runner: Calculate final metric
        Runner-->>Tuner: metric_value (e.g., sharpe_ratio = 1.5)
        
        Tuner->>Optuna: study.tell(trial, value)
        Tuner->>Tracker: log_metrics({objective_value: 1.5})
        Tuner->>Tracker: end_run("FINISHED")
        
        %% Update trial in DB
        Tuner->>DB: UPDATE optuna_trials SET<br/>value=1.5, state='complete', metrics=...
        
        %% WebSocket broadcast
        Tuner->>API: Broadcast trial result
        API->>Dashboard: WebSocket /ws/optuna
        Dashboard-->>User: Trial X complete: 1.5
        
        %% Update best if applicable
        Optuna->>Optuna: Update best_trial if better
    end

    %% Study complete
    Tuner->>Optuna: study.best_trial
    Optuna-->>Tuner: best_trial with params
    
    Tuner->>Optuna: get_param_importances(study)
    Optuna-->>Tuner: importance scores
    
    Tuner->>DB: UPDATE optuna_studies SET<br/>status='completed',<br/>best_trial_number=X,<br/>best_value=1.8,<br/>best_params={...},<br/>param_importance={...}
    
    %% Notify completion
    Tuner->>API: Broadcast study complete
    API->>Dashboard: WebSocket /ws/optuna
    Dashboard-->>User: 🎉 Search complete!

    %% View results
    User->>Dashboard: View best parameters
    Dashboard->>API: GET /api/hyperparameters/{exp_id}/optuna/best
    API->>DB: SELECT best_params FROM optuna_studies
    DB-->>API: {learning_rate: 0.0005, gamma: 0.99, ...}
    API-->>Dashboard: Best params
    Dashboard-->>User: Display optimal hyperparameters
    
    %% Apply best params
    User->>Dashboard: Apply best params to experiment
    Dashboard->>API: PUT /api/experiments/{id}<br/>{hyperparameters: best_params}
    API->>DB: UPDATE experiments SET hyperparameters=...
    API-->>Dashboard: Experiment updated
    Dashboard-->>User: Ready to train with optimal params
```

## Optuna Configuration

### Search Space Definition
```python
param_space = {
    "learning_rate": {
        "type": "loguniform",
        "low": 1e-5,
        "high": 1e-2
    },
    "gamma": {
        "type": "uniform",
        "low": 0.9,
        "high": 0.999
    },
    "epsilon_decay": {
        "type": "uniform",
        "low": 0.99,
        "high": 0.9999
    },
    "batch_size": {
        "type": "categorical",
        "choices": [32, 64, 128, 256]
    },
    "hidden_size": {
        "type": "int",
        "low": 64,
        "high": 512,
        "step": 64
    }
}
```

### Study Configuration
| Parameter | Description | Default |
|-----------|-------------|---------|
| `n_trials` | Number of trials to run | 50 |
| `direction` | Optimization direction | "maximize" |
| `metric` | Target metric | "sharpe_ratio" |
| `sampler` | TPE, Random, Grid | TPESampler |
| `pruner` | MedianPruner, NopPruner | MedianPruner |

## Database Schema

### optuna_studies
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Study ID |
| experiment_id | INT | Parent experiment |
| study_name | VARCHAR | Unique study name |
| direction | ENUM | maximize/minimize |
| metric | VARCHAR | Target metric |
| n_trials | INT | Total trials |
| status | ENUM | running/completed/failed/stopped |
| best_trial_number | INT | Best trial index |
| best_value | DECIMAL | Best objective value |
| best_params | JSONB | Best hyperparameters |
| param_importance | JSONB | Feature importance |

### optuna_trials
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Trial ID |
| study_id | INT | Parent study |
| trial_number | INT | Trial index |
| params | JSONB | Hyperparameters used |
| value | DECIMAL | Objective value |
| state | ENUM | running/complete/pruned/fail |
| metrics | JSONB | All metrics |
| mlflow_run_id | VARCHAR | Linked MLflow run |

## Pruning Strategy

### MedianPruner
- Prunes trial if intermediate value worse than median of previous trials
- Warm-up period: 5 trials before pruning starts
- Check interval: every 10 episodes

```python
# Pruning check in training loop
for episode in range(max_episodes):
    reward = train_episode()
    trial.report(reward, episode)
    
    if trial.should_prune():
        raise optuna.TrialPruned()
```

## Metrics Tracked

| Metric | Description | Optimization |
|--------|-------------|--------------|
| `sharpe_ratio` | Risk-adjusted returns | Maximize |
| `win_rate` | Percentage winning trades | Maximize |
| `total_pnl` | Total profit/loss | Maximize |
| `max_drawdown` | Maximum drawdown | Minimize |
| `sortino_ratio` | Downside risk-adjusted | Maximize |

## Parameter Importance

After study completion, Optuna calculates parameter importance using:
- **fANOVA** (functional ANOVA)
- Measures how much each parameter contributes to variance

```json
{
  "learning_rate": 0.45,
  "gamma": 0.28,
  "batch_size": 0.15,
  "hidden_size": 0.08,
  "epsilon_decay": 0.04
}
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/hyperparameters/search` | POST | Start new search |
| `/api/hyperparameters/{exp_id}/optuna/status` | GET | Get study status |
| `/api/hyperparameters/{exp_id}/optuna/trials` | GET | List all trials |
| `/api/hyperparameters/{exp_id}/optuna/best` | GET | Get best params |
| `/api/hyperparameters/{exp_id}/optuna/stop` | POST | Stop running study |

## Assumptions
- **None** - All Optuna flows verified in codebase
