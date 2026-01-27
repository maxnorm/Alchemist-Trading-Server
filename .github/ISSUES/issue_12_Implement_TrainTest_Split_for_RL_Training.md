Implement Time Series Train/Test Split Infrastructure for RL Training

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: mvp-blocker, mlops, data-pipeline, P0
Milestone: Gate B - Live Training
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #12: Implement Time Series Train/Test Split Infrastructure for RL Training

## Problem Statement

While historical backtesting is deferred, **train/test split infrastructure is essential** for live training to:
- Prevent data leakage (look-ahead bias)
- Enable validation during training
- Support early stopping based on validation performance
- Ensure realistic performance evaluation

Current training loop (`src/trading_server/src/application/training/training_loop.py`) uses all available data without temporal boundaries, risking data leakage and overfitting.

## Proposed Solution

1. **Create TimeSeriesSplitter Service:**
   - File: `src/trading_server/src/data/time_series_splitter.py`
   - Methods:
     - `split_chronological()` - Basic train/validation/test split (80/10/10)
     - `split_walk_forward()` - Walk-forward validation (integrate existing script)
     - `get_live_validation_split()` - Get validation period for live training
   - Validate no temporal leakage (training always before test)

2. **Integrate with Training Loop:**
   - Modify `TrainingLoop` to accept validation data
   - Add periodic validation evaluation (every N episodes)
   - Implement early stopping based on validation performance
   - Log validation metrics to MLflow

3. **Update Experiment Configuration:**
   - Add split parameters to experiment config:
     ```yaml
     training:
       data_split:
         method: "chronological"  # or "walk_forward"
         train_ratio: 0.8
         validation_ratio: 0.1
         test_ratio: 0.1
     ```

4. **Log Split Information:**
   - Log train/validation/test time ranges to MLflow
   - Include in reproducibility report

5. **Add Unit Tests:**
   - Test chronological split
   - Test temporal leakage validation
   - Test walk-forward integration

## Metadata

- **Effort:** M (5 story points)
- **Dependencies:** None (can start immediately)
- **Owner Role:** MLOps / Data Engineering
