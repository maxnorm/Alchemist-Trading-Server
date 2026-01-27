Implement Proper Optuna Experiment Completion Waiting and Metric Evaluation

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: mlops, hyperparameter-tuning, P2
Milestone: Gate C - Advanced Features
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #28: Implement Proper Optuna Experiment Completion Waiting and Metric Evaluation

## Problem Statement

The Optuna hyperparameter tuning integration does not properly wait for experiment completion before evaluating metrics. This can lead to inaccurate hyperparameter optimization results.

**Validated Finding from Training Readiness Report:**
- **Status:** ✅ VALIDATED - Confirmed in codebase
- **Priority:** P2 - Nice to have, doesn't block basic training
- **Evidence:**
  - **File:** `src/trading_server/src/experiments/optuna_tuner.py`
  - **Line 175:** `# TODO: Implement proper experiment completion waiting and metric evaluation`
  - **Impact:** Hyperparameter optimization may not wait for full experiment completion, metric evaluation may be inaccurate

**Current Behavior:**
1. Optuna trial starts an experiment
2. Trial immediately returns a placeholder value without waiting
3. Experiment continues running in background
4. Metrics are not properly evaluated when experiment completes

**Impact:**
- ❌ Hyperparameter optimization may use incomplete or placeholder metrics
- ❌ Trials may be pruned or completed based on incorrect data
- ❌ Best hyperparameters may not be truly optimal
- ❌ Wasted compute resources on incomplete experiments

## Proposed Solution

Implement proper asynchronous waiting for experiment completion with timeout handling and accurate metric evaluation.

### Architecture Changes

1. **Add Experiment Status Polling:**
   - Poll experiment status from database
   - Wait for experiment to reach "completed" or "failed" status
   - Implement timeout to prevent infinite waiting

2. **Extract Final Metrics:**
   - Query experiment metrics from MLflow or database
   - Use configured objective metric (e.g., Sharpe ratio, total return)
   - Handle failed experiments gracefully

3. **Update Trial Evaluation:**
   - Wait for experiment completion before returning metric
   - Return actual metric value instead of placeholder
   - Handle timeouts and failures appropriately

### Implementation Steps

#### 1. Add Experiment Status Poller

**File:** `src/trading_server/src/experiments/optuna_tuner.py`

**New Method:**
```python
def _wait_for_experiment_completion(
    self,
    experiment_id: int,
    timeout_seconds: int = 3600,  # 1 hour default
    poll_interval: int = 10,  # Check every 10 seconds
) -> ExperimentStatus:
    """
    Wait for experiment to complete or fail.
    
    :param experiment_id: Experiment ID to wait for
    :param timeout_seconds: Maximum time to wait
    :param poll_interval: Seconds between status checks
    :return: Final experiment status
    :raises TimeoutError: If experiment doesn't complete within timeout
    """
    start_time = time.time()
    
    while True:
        experiment = self.repository.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")
        
        status = experiment.status
        if status in (ExperimentStatus.COMPLETED, ExperimentStatus.FAILED):
            return status
        
        # Check timeout
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            raise TimeoutError(
                f"Experiment {experiment_id} did not complete within {timeout_seconds}s"
            )
        
        # Wait before next poll
        time.sleep(poll_interval)
```

#### 2. Add Metric Extraction

**File:** `src/trading_server/src/experiments/optuna_tuner.py`

**New Method:**
```python
def _extract_experiment_metric(
    self,
    experiment_id: int,
    metric_name: str = "sharpe_ratio",  # Default objective metric
) -> float:
    """
    Extract final metric value from completed experiment.
    
    :param experiment_id: Experiment ID
    :param metric_name: Name of metric to extract
    :return: Metric value
    :raises ValueError: If metric not found or experiment failed
    """
    experiment = self.repository.get_experiment(experiment_id)
    if not experiment:
        raise ValueError(f"Experiment {experiment_id} not found")
    
    if experiment.status == ExperimentStatus.FAILED:
        # Return worst possible value for failed experiments
        return float('-inf') if self.study.direction == 'maximize' else float('inf')
    
    # Try to get metric from MLflow
    if experiment.mlflow_run_id:
        try:
            metric_value = self._get_mlflow_metric(
                experiment.mlflow_run_id,
                metric_name
            )
            return metric_value
        except Exception as e:
            logger.warning(f"Failed to get metric from MLflow: {e}")
    
    # Fallback: Query from database if metrics are stored there
    # This may require additional implementation
    raise ValueError(f"Could not extract metric {metric_name} for experiment {experiment_id}")
```

#### 3. Update Trial Objective Function

**File:** `src/trading_server/src/experiments/optuna_tuner.py`

**Changes (around line 175):**

**Before:**
```python
# TODO: Implement proper experiment completion waiting and metric evaluation

# For now, return a placeholder value
# In real implementation, this would:
# 1. Wait for experiment to complete
# 2. Extract final metric value
# 3. Return actual metric
return 0.0  # Placeholder
```

**After:**
```python
# Wait for experiment to complete
try:
    final_status = self._wait_for_experiment_completion(
        experiment_id=experiment_id,
        timeout_seconds=self.experiment_timeout_seconds,
    )
    
    # Extract objective metric
    metric_value = self._extract_experiment_metric(
        experiment_id=experiment_id,
        metric_name=self.objective_metric,
    )
    
    return metric_value
    
except TimeoutError as e:
    logger.warning(f"Experiment {experiment_id} timed out: {e}")
    # Prune trial if timeout
    raise optuna.TrialPruned(f"Experiment timeout: {e}")
    
except Exception as e:
    logger.error(f"Error evaluating experiment {experiment_id}: {e}")
    # Return worst value for failed experiments
    return float('-inf') if self.study.direction == 'maximize' else float('inf')
```

#### 4. Add Configuration

**File:** `src/trading_server/src/experiments/optuna_tuner.py`

**Add to `__init__()`:**
```python
def __init__(
    self,
    # ... existing parameters ...
    experiment_timeout_seconds: int = 3600,  # 1 hour default
    objective_metric: str = "sharpe_ratio",  # Metric to optimize
):
    # ... existing initialization ...
    self.experiment_timeout_seconds = experiment_timeout_seconds
    self.objective_metric = objective_metric
```

#### 5. Add MLflow Metric Extraction

**File:** `src/trading_server/src/experiments/optuna_tuner.py`

**New Method:**
```python
def _get_mlflow_metric(self, run_id: str, metric_name: str) -> float:
    """
    Get metric value from MLflow run.
    
    :param run_id: MLflow run ID
    :param metric_name: Name of metric
    :return: Metric value
    """
    try:
        import mlflow
        client = mlflow.tracking.MlflowClient()
        metric = client.get_metric_history(run_id, metric_name)
        
        if not metric:
            raise ValueError(f"Metric {metric_name} not found in run {run_id}")
        
        # Return the last (final) value
        return metric[-1].value
        
    except Exception as e:
        logger.error(f"Failed to get MLflow metric: {e}")
        raise
```

### Testing Strategy

1. **Unit Tests:**
   - Status polling waits correctly
   - Timeout handling works
   - Metric extraction from MLflow
   - Failed experiment handling

2. **Integration Tests:**
   - Full Optuna study with experiment completion waiting
   - Verify metrics are accurate
   - Test timeout scenarios
   - Test failed experiment handling

3. **Performance Tests:**
   - Polling doesn't consume excessive resources
   - Timeout values are reasonable
   - Concurrent trials work correctly

### Configuration

Add to experiment hyperparameters or Optuna study config:

```python
optuna_config = {
    "experiment_timeout_seconds": 3600,  # 1 hour
    "objective_metric": "sharpe_ratio",  # or "total_return", "win_rate", etc.
    "poll_interval": 10,  # seconds
}
```

## Metadata

- **Effort:** M (5 story points / 3-5 days)
  - Phase 1 (Status Polling): 1-2 days
  - Phase 2 (Metric Extraction): 1-2 days
  - Phase 3 (Testing & Integration): 1 day
- **Dependencies:** 
  - MLflow integration must be working
  - Experiment status tracking must be reliable
- **Owner Role:** MLOps / Hyperparameter Tuning
- **Related Issues:**
  - Training Readiness Report: `docs/generated/training-readiness-merged-report.md`

## Open Questions

1. **Metric Storage:** Are final metrics stored in database or only in MLflow? May need to add database metric storage.

2. **Objective Metric:** What should be the default objective metric? Sharpe ratio? Total return? Should be configurable.

3. **Timeout Values:** What are reasonable timeout values? Should vary by experiment type?

4. **Concurrent Trials:** How should we handle multiple concurrent trials? Should we limit concurrent experiments?

## Acceptance Criteria

- [ ] Status polling implemented with timeout
- [ ] Metric extraction from MLflow works
- [ ] Failed experiments handled gracefully
- [ ] Timeout scenarios handled correctly
- [ ] Objective metric is configurable
- [ ] Unit tests for status polling
- [ ] Integration tests for full Optuna study
- [ ] Performance tests for concurrent trials
- [ ] Documentation updated

## Files to Modify

1. `src/trading_server/src/experiments/optuna_tuner.py` (add waiting and metric extraction)
2. `src/trading_server/src/experiments/models.py` (if metrics need to be stored in DB)

## Validation Notes

This issue was identified and validated in the Training Readiness Assessment Report (2026-01-25). The TODO at line 175 in `optuna_tuner.py` confirms this is a known gap that should be addressed for accurate hyperparameter optimization.
