---
name: Week 2 Walk-Forward and Overfitting Defense
overview: "Implement walk-forward validation framework and CSCV/PBO algorithm to prevent temporal leakage and quantify overfitting risk in backtests. This addresses critical P0 issues: no walk-forward validation and no PBO/CSCV overfitting defense."
todos:
  - id: walk_forward_skeleton
    content: Create scripts/walk_forward_validation.py with basic structure and expanding window logic
    status: pending
  - id: walk_forward_rolling
    content: Implement rolling window mode and aggregation logic in walk_forward_validation.py
    status: pending
    dependencies:
      - walk_forward_skeleton
  - id: walk_forward_integration
    content: Integrate walk-forward validation with scripts/run-backtest.py CLI
    status: pending
    dependencies:
      - walk_forward_rolling
  - id: walk_forward_tests
    content: Create tests/integration/test_walk_forward.py with comprehensive test coverage
    status: pending
    dependencies:
      - walk_forward_integration
  - id: cscv_skeleton
    content: Create src/mt5-python_server/src/training/cscv.py with data partitioning and basic structure
    status: pending
  - id: cscv_algorithm
    content: Implement CSCV algorithm with PBO calculation and performance degradation
    status: pending
    dependencies:
      - cscv_skeleton
  - id: cscv_integration
    content: Integrate CSCV with experiments/runner.py and store PBO in MLflow tags
    status: pending
    dependencies:
      - cscv_algorithm
  - id: cscv_tests
    content: Create tests/unit/test_cscv.py with algorithm correctness and edge case tests
    status: pending
    dependencies:
      - cscv_algorithm
---

# Week 2: Walk-Forward Validation & Overfitting Defense

## Overview

Week 2 implements two critical anti-overfitting mechanisms:

1. **Walk-Forward Validation** - Prevents temporal leakage by using expanding/rolling windows
2. **CSCV/PBO Algorithm** - Quantifies probability of backtest overfitting using combinatorially symmetric cross-validation

These implementations address P0 issues identified in the audit and are foundational for reliable model evaluation.

## Dependencies

- **Week 1 must be completed first**: Data quality gates are required before walk-forward validation
- Requires existing infrastructure:
                - `scripts/run-backtest.py` - Current backtest runner
                - `src/mt5-python_server/src/environments/historical_env.py` - Historical environment
                - `src/mt5-python_server/src/mlops/experiment_tracker.py` - MLflow integration
                - `src/mt5-python_server/src/experiments/runner.py` - Experiment runner

## Task 2.1: Walk-Forward Validation (Days 3-5)

### Files to Create

1. **`scripts/walk_forward_validation.py`** - Main walk-forward implementation

                        - Walk-forward validation function with expanding/rolling window support
                        - Configurable train/test window sizes and step sizes
                        - Temporal ordering enforcement (no future data)
                        - Integration with existing backtest infrastructure

2. **`tests/integration/test_walk_forward.py`** - Walk-forward tests

                        - Test expanding window mode
                        - Test rolling window mode
                        - Test temporal ordering (no future data leakage)
                        - Test edge cases (insufficient data, single window)

### Implementation Details

**Walk-Forward Function Signature:**

```python
def walk_forward_validation(
    data: pd.DataFrame,
    train_window_days: int = 180,
    test_window_days: int = 30,
    step_days: int = 30,
    window_type: str = "expanding",  # "expanding" or "rolling"
    backtest_func: Callable = None,
    **backtest_kwargs
) -> Dict[str, Any]:
    """
    Walk-forward validation with expanding/rolling windows.
    
    Args:
        data: DataFrame with 'timestamp' column and price data
        train_window_days: Training window size in days
        test_window_days: Test window size in days
        step_days: Step size between windows in days
        window_type: "expanding" (grows) or "rolling" (fixed size)
        backtest_func: Function to run backtest on train/test data
        **backtest_kwargs: Additional arguments for backtest function
    
    Returns:
        Dictionary with:
 - results: List of metrics for each window
 - aggregated_metrics: Aggregated statistics across windows
 - window_info: Information about each window
    """
```

**Key Requirements:**

- Ensure `data` has `timestamp` column (datetime type)
- Sort data by timestamp before processing
- For expanding windows: train window grows, test window fixed
- For rolling windows: both train and test windows fixed size
- Never use future data for training (strict temporal ordering)
- Support integration with `run_backtest()` function from `run-backtest.py`

**Integration Points:**

- Modify `scripts/run-backtest.py` to optionally use walk-forward validation
- Add CLI argument `--walk-forward` to enable walk-forward mode
- Add arguments for `--train-window`, `--test-window`, `--step-size`, `--window-type`

### Success Criteria

- ✅ Walk-forward produces expanding/rolling window results
- ✅ No future data leakage (automated test verification)
- ✅ Results aggregated across all windows
- ✅ Integration with existing backtest script works
- ✅ All tests pass

---

## Task 2.2: CSCV/PBO Implementation (Days 5-7)

### Files to Create

1. **`src/mt5-python_server/src/training/cscv.py`** - CSCV algorithm implementation

                        - Combinatorially Symmetric Cross-Validation per Bailey & López de Prado (2014)
                        - PBO (Probability of Backtest Overfitting) calculation
                        - Performance degradation ratio calculation
                        - Integration with experiment tracking

2. **`tests/unit/test_cscv.py`** - CSCV tests

                        - Test CSCV algorithm correctness
                        - Test PBO calculation
                        - Test edge cases (few strategies, identical performance)
                        - Test with synthetic data

### Implementation Details

**CSCV Algorithm Reference:**

- Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2014). "The Probability of Backtest Overfitting." Journal of Computational Finance, 17(4).

**CSCV Function Signature:**

```python
def combinatorially_symmetric_cross_validation(
    data: pd.DataFrame,
    strategy_configs: List[Dict[str, Any]],
    n_splits: int = 4,
    evaluation_metric: str = "sharpe_ratio",
    train_func: Callable = None,
    evaluate_func: Callable = None
) -> Dict[str, float]:
    """
    Estimate Probability of Backtest Overfitting (PBO) using CSCV.
    
    Args:
        data: Historical data with timestamp column
        strategy_configs: List of strategy configurations to test
        n_splits: Number of partitions for CSCV (typically 4)
        evaluation_metric: Metric to use for ranking ("sharpe_ratio", "total_return", etc.)
        train_func: Function to train strategy on data
        evaluate_func: Function to evaluate strategy on data
    
    Returns:
        Dictionary with:
 - pbo: Probability of backtest overfitting (0-1)
 - performance_degradation: Expected performance drop
 - logit_pbo: Logit of PBO
 - strategy_rankings: Rankings for each split
    """
```

**Algorithm Steps:**

1. Partition data into `n_splits` equal parts
2. For each combination of train/test splits:

                        - Train all strategies on training partition
                        - Evaluate all strategies on test partition
                        - Rank strategies by performance

3. Calculate PBO using combinatorial analysis
4. Calculate performance degradation ratio

**Integration with Experiment Runner:**

- Modify `src/mt5-python_server/src/experiments/runner.py` to:
                - Accept multiple strategy configurations
                - Run CSCV after experiment completion
                - Store PBO in MLflow tags: `mlflow.set_tag("pbo", pbo_value)`
                - Log PBO in experiment metadata

**MLflow Integration:**

- Store PBO in MLflow run tags
- Log PBO interpretation (PBO < 0.05 = low risk, PBO > 0.10 = high risk)
- Store strategy rankings for each split

### Success Criteria

- ✅ PBO calculated for strategy configurations
- ✅ PBO < 0.05 indicates low overfitting risk
- ✅ PBO stored in MLflow tags
- ✅ Integration with experiment runner works
- ✅ All tests pass
- ✅ Algorithm matches reference implementation

---

## Implementation Sequence

### Day 3: Walk-Forward Foundation

1. Create `scripts/walk_forward_validation.py` skeleton
2. Implement basic expanding window logic
3. Add temporal ordering validation
4. Write initial tests

### Day 4: Walk-Forward Completion

1. Implement rolling window mode
2. Add aggregation logic
3. Integrate with `run-backtest.py`
4. Complete test suite

### Day 5: CSCV Foundation

1. Create `src/mt5-python_server/src/training/cscv.py`
2. Implement data partitioning logic
3. Implement basic CSCV structure
4. Write initial tests

### Day 6: CSCV Algorithm

1. Implement PBO calculation
2. Implement performance degradation calculation
3. Add strategy ranking logic
4. Complete algorithm implementation

### Day 7: Integration & Testing

1. Integrate CSCV with experiment runner
2. Add MLflow tag storage
3. Complete test suite
4. End-to-end testing
5. Documentation

---

## Testing Strategy

### Walk-Forward Tests

- **Test expanding window**: Verify train window grows, test window fixed
- **Test rolling window**: Verify both windows fixed size
- **Test temporal ordering**: Verify no future data in training
- **Test edge cases**: Single window, insufficient data
- **Test integration**: Verify works with existing backtest script

### CSCV Tests

- **Test algorithm correctness**: Verify PBO calculation matches reference
- **Test with known overfitting**: High PBO for overfitted strategies
- **Test with diverse strategies**: Low PBO for genuinely good strategies
- **Test edge cases**: Few strategies, identical performance
- **Test integration**: Verify MLflow tags stored correctly

---

## Files to Modify

1. **`scripts/run-backtest.py`**

                        - Add walk-forward CLI arguments
                        - Add walk-forward mode option
                        - Integrate walk-forward validation function

2. **`src/mt5-python_server/src/experiments/runner.py`**

                        - Add CSCV calculation after experiment completion
                        - Store PBO in MLflow tags
                        - Log PBO in experiment metadata

---

## Success Metrics

- **Walk-Forward Validation:**
                - All windows processed without temporal leakage
                - Results aggregated correctly
                - Integration with backtest script functional

- **CSCV/PBO:**
                - PBO calculated correctly for all experiments
                - PBO values stored in MLflow
                - PBO interpretation documented

---

## Risk Mitigation

- **Walk-Forward:**
                - Validate timestamp column exists and is datetime type
                - Handle edge cases (insufficient data) gracefully
                - Provide clear error messages

- **CSCV:**
                - Validate minimum number of strategies (recommend ≥ 10)
                - Handle edge cases (identical performance) gracefully
                - Provide clear PBO interpretation

---

## Documentation Updates

- Update `docs/DEVELOPER_GUIDE.md` with walk-forward usage
- Update `docs/DEVELOPER_GUIDE.md` with CSCV/PBO interpretation
- Add examples to README for walk-forward validation
- Document PBO thresholds and interpretation