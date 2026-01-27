Create Grafana Dashboard for Training Job Health

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: mvp-blocker, observability, mlops, P0
Milestone: Gate B - Live Training
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #10: Create Grafana Dashboard for Training Job Health

## Problem Statement

While training loop exists with health monitoring (`src/trading_server/src/application/training/health_monitor.py`), there are no Grafana dashboards to visualize:
- Training progress (steps, episodes, rewards)
- Health metrics (divergence, NaN detection, gradient norms)
- Resource usage (CPU, memory, GPU if available)
- MLflow run status
- Checkpoint frequency

Without dashboards, operators cannot monitor training health or identify issues early.

## Proposed Solution

1. **Create Grafana Dashboard:**
   - File: `src/monitoring/grafana/dashboards/training-health.json`
   - Panels:
     - **Training Progress:** Steps/episodes over time
     - **Reward Trends:** Reward per episode (time series)
     - **Health Metrics:** Divergence, NaN rate, gradient norms (gauges/time series)
     - **Resource Usage:** CPU, memory (time series)
     - **MLflow Runs:** Active runs table
     - **Checkpoint Status:** Last checkpoint time, frequency

2. **Add Prometheus Metrics:**
   - Ensure training loop exposes metrics:
     - `training_steps_total{experiment_id}`
     - `training_episodes_total{experiment_id}`
     - `training_reward{experiment_id}`
     - `training_divergence_detected{experiment_id}`
     - `training_nan_detected{experiment_id}`
     - `training_gradient_norm{experiment_id}`

3. **Integrate with MLflow:**
   - Query MLflow API for run status
   - Display active runs in dashboard

## Metadata

- **Effort:** M (5 story points)
- **Dependencies:** None (can start immediately)
- **Owner Role:** MLOps / Observability
