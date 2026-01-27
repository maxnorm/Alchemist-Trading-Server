Implement Feature Filtering in Environment Factory

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: mvp-blocker, mlops, rl-training, P0
Milestone: Gate B - Live Training
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #27: Implement Feature Filtering in Environment Factory

## Problem Statement

The environment factory system does not filter features based on experiment configuration. When an experiment specifies a subset of features to use, the environment still uses **all available features** from connectors, ignoring the experiment's feature selection.

**Validated Finding from Training Readiness Report:**
- **Status:** ✅ VALIDATED - Confirmed in codebase
- **Priority:** P0 - High priority for correctness
- **Impact:** Experiments may use more features than specified, feature selection in experiment config is ignored, potential performance impact from unnecessary features

**Evidence:**
- **File:** `src/trading_server/src/experiments/runner.py`
- **Line 121:** `# TODO: Enhance environment factory to support feature selection`
- **Line 127-132:** Environment created without feature filtering
- **Line 571:** `# TODO: Enhance to support feature filtering` in `_get_connectors_for_pairs()`

**Current Behavior:**
1. User creates experiment with specific features: `["price_bid_EURUSD", "rsi_14_EURUSD"]`
2. `ExperimentRunner` creates environment with all connectors
3. Environment uses **all features** from all connectors, not just the selected ones
4. Feature selection in experiment config is effectively ignored

**Impact:**
- ❌ Feature selection in experiments doesn't work as expected
- ❌ Experiments may use unintended features, affecting results
- ❌ Performance impact from processing unnecessary features
- ❌ Difficulty in feature ablation studies
- ❌ Potential overfitting from using too many features

## Proposed Solution

Implement feature filtering at the environment factory level to ensure only selected features are used.

### Architecture Changes

1. **Add Features Parameter to Factory:**
   - Update `EnvironmentFactory.create_environment()` to accept `features: Optional[List[str]]` parameter
   - Filter connectors/features before creating environment
   - Pass filtered feature list to environment

2. **Update Environment Creation:**
   - Modify `LiveTradingEnv` to accept and use only specified features
   - Update `FeatureEngine` to filter by feature list
   - Ensure `StateBuilder` only uses selected features

3. **Update ExperimentRunner:**
   - Pass `experiment.features` to environment factory
   - Validate features exist in catalog before creating environment
   - Log which features are being used

### Implementation Steps

#### 1. Update EnvironmentFactory

**File:** `src/trading_server/src/infrastructure/factories/environment_factory.py`

**Changes:**
- Add `features: Optional[List[str]] = None` parameter to `create_environment()`
- Filter connectors to only include those providing selected features
- Pass filtered feature list to environment constructor

**Method Signature:**
```python
def create_environment(
    self,
    account: Account,
    connectors: List[IDataSourceConnector],
    window_size: Optional[int] = None,
    seed: Optional[int] = None,
    features: Optional[List[str]] = None,  # NEW: Filter by these features
) -> LiveTradingEnv:
```

**Implementation Logic:**
```python
# Filter connectors to only those providing selected features
if features:
    filtered_connectors = self._filter_connectors_by_features(connectors, features)
    if not filtered_connectors:
        raise ValueError(f"No connectors provide the selected features: {features}")
    connectors = filtered_connectors

env = LiveTradingEnv(
    account=account,
    connectors=connectors,
    window_size=window_size,
    seed=seed,
    selected_features=features,  # Pass to environment
)
```

#### 2. Add Connector Filtering Method

**File:** `src/trading_server/src/infrastructure/factories/environment_factory.py`

**New Method:**
```python
def _filter_connectors_by_features(
    self,
    connectors: List[IDataSourceConnector],
    features: List[str]
) -> List[IDataSourceConnector]:
    """
    Filter connectors to only those that provide at least one of the selected features.
    
    :param connectors: List of all available connectors
    :param features: List of feature names to filter by
    :return: Filtered list of connectors
    """
    filtered = []
    for connector in connectors:
        # Get features provided by this connector
        connector_features = connector.get_available_features()  # Need to implement this
        # Check if connector provides any of the selected features
        if any(feat in connector_features for feat in features):
            filtered.append(connector)
    return filtered
```

#### 3. Update LiveTradingEnv

**File:** `src/trading_server/src/environments/live_env.py`

**Changes:**
- Add `selected_features: Optional[List[str]] = None` parameter to `__init__()`
- Update `FeatureEngine` to filter by selected features
- Ensure only selected features are included in state

**Implementation:**
```python
def __init__(
    self,
    account: Account,
    connectors: List[IDataSourceConnector],
    window_size: int = 50,
    seed: Optional[int] = None,
    selected_features: Optional[List[str]] = None,  # NEW
):
    # ... existing initialization ...
    
    # Filter feature engine by selected features
    if selected_features:
        self.feature_engine.filter_features(selected_features)
```

#### 4. Update FeatureEngine

**File:** `src/trading_server/src/application/environment/feature_engine.py`

**New Method:**
```python
def filter_features(self, feature_names: List[str]) -> None:
    """
    Filter feature engine to only use specified features.
    
    :param feature_names: List of feature names to keep
    """
    # Filter feature catalog to only selected features
    self.feature_catalog = {
        name: feature
        for name, feature in self.feature_catalog.items()
        if name in feature_names
    }
    
    # Update feature list
    self.feature_list = [
        name for name in self.feature_list
        if name in feature_names
    ]
```

#### 5. Update ExperimentRunner

**File:** `src/trading_server/src/experiments/runner.py`

**Changes in `start_experiment()` method (around line 121):**

**Before:**
```python
# TODO: Enhance environment factory to support feature selection
connectors = self._get_connectors_for_pairs(experiment.currency_pairs)
environment = self.environment_factory.create_environment(
    account=account,
    connectors=connectors,
    window_size=window_size,
    seed=seed,
)
```

**After:**
```python
connectors = self._get_connectors_for_pairs(experiment.currency_pairs)

# Validate features exist in catalog
if experiment.features:
    self._validate_features_exist(experiment.features)

environment = self.environment_factory.create_environment(
    account=account,
    connectors=connectors,
    window_size=window_size,
    seed=seed,
    features=experiment.features,  # NEW: Pass selected features
)
```

**Add Validation Method:**
```python
def _validate_features_exist(self, feature_names: List[str]) -> None:
    """
    Validate that all specified features exist in the feature catalog.
    
    :param feature_names: List of feature names to validate
    :raises ValueError: If any feature doesn't exist
    """
    # Get feature catalog from server or context
    # This may need to be passed to ExperimentRunner
    available_features = self._get_available_features()
    
    missing = [f for f in feature_names if f not in available_features]
    if missing:
        raise ValueError(
            f"Features not found in catalog: {missing}. "
            f"Available features: {list(available_features)[:10]}..."
        )
```

#### 6. Update _get_connectors_for_pairs

**File:** `src/trading_server/src/experiments/runner.py`

**Changes (around line 571):**

**Before:**
```python
# TODO: Enhance to support feature filtering
```

**After:**
```python
# Note: Feature filtering is now handled by EnvironmentFactory
# This method only filters by currency pairs
```

### Testing Strategy

1. **Unit Tests:**
   - Factory filters connectors correctly by features
   - Factory raises error if no connectors provide selected features
   - Environment only uses selected features
   - FeatureEngine filters correctly

2. **Integration Tests:**
   - Experiment with feature selection uses only those features
   - Experiment without feature selection uses all features (backward compatibility)
   - Validation catches missing features

3. **Backward Compatibility Tests:**
   - **Critical:** Existing code calling `create_environment()` without `features` parameter still works
   - Default behavior (None) uses all features
   - No breaking changes

### Data Flow

```
Experiment.features = ["price_bid_EURUSD", "rsi_14_EURUSD"]
  ↓
ExperimentRunner.start_experiment()
  ↓
Validate features exist in catalog
  ↓
EnvironmentFactory.create_environment(features=experiment.features)
  ↓
Filter connectors by features
  ↓
Create LiveTradingEnv(selected_features=features)
  ↓
FeatureEngine.filter_features(features)
  ↓
Only selected features used in training
```

## Metadata

- **Effort:** M (5 story points / 3-5 days)
  - Phase 1 (Factory Changes): 1-2 days
  - Phase 2 (Environment Integration): 1-2 days
  - Phase 3 (Testing & Validation): 1 day
- **Dependencies:** None (can start immediately)
- **Owner Role:** MLOps / RL Engineering
- **Related Issues:**
  - Issue #20: Enable Paper Trading and Historical Environments (may need feature filtering too)
  - Training Readiness Report: `docs/generated/training-readiness-merged-report.md`

## Open Questions

1. **Feature Catalog Access:** How should `ExperimentRunner` access the feature catalog? Should it be passed as a dependency or queried from database?

2. **Connector Feature Discovery:** Do connectors have a method to list available features? If not, need to implement `get_available_features()` method.

3. **Feature Naming:** How are features named? Need to ensure consistent naming between experiment config and connector features.

4. **Performance:** Should we cache filtered connectors or recompute each time?

## Acceptance Criteria

- [ ] `EnvironmentFactory.create_environment()` accepts `features` parameter
- [ ] Factory filters connectors by selected features
- [ ] `LiveTradingEnv` accepts and uses only selected features
- [ ] `FeatureEngine` filters by selected features
- [ ] `ExperimentRunner` passes experiment features to factory
- [ ] Feature validation catches missing features
- [ ] Backward compatibility: `features=None` uses all features
- [ ] Unit tests for feature filtering
- [ ] Integration tests for experiment with feature selection
- [ ] Backward compatibility tests pass
- [ ] Documentation updated

## Files to Modify

1. `src/trading_server/src/infrastructure/factories/environment_factory.py` (add feature filtering)
2. `src/trading_server/src/environments/live_env.py` (accept selected_features)
3. `src/trading_server/src/application/environment/feature_engine.py` (add filter_features method)
4. `src/trading_server/src/experiments/runner.py` (pass features, add validation)
5. `src/trading_server/src/connectors/base.py` (add get_available_features method if needed)

## Validation Notes

This issue was identified and validated in the Training Readiness Assessment Report (2026-01-25). The TODOs at lines 121 and 571 in `runner.py` confirm this is a known gap that needs to be addressed before production training.
