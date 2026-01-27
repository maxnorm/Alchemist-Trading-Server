---
name: Week 7 Feature Versioning
overview: Implement feature pipeline versioning system to track feature computation code versions, store feature metadata with models in MLflow, and enable feature rollback and reproducibility.
todos:
  - id: week7_feature_registry
    content: Create FeatureRegistry module with pipeline version tracking, database schema, and version management methods
    status: pending
  - id: week7_feature_engine_versioning
    content: Add version tracking to FeatureEngine with metadata export and auto-registration
    status: pending
    dependencies:
      - week7_feature_registry
  - id: week7_mlflow_integration
    content: Integrate feature metadata logging with MLflow experiment tracker and link models to feature versions
    status: pending
    dependencies:
      - week7_feature_engine_versioning
  - id: week7_dvc_integration
    content: Extend DataVersioner to version feature computation code and link DVC commits to pipeline versions
    status: pending
    dependencies:
      - week7_feature_registry
  - id: week7_catalog_updates
    content: Update FeatureCatalog to track pipeline versions and enable version-aware queries
    status: pending
    dependencies:
      - week7_feature_registry
  - id: week7_integration_tests
    content: Create comprehensive integration tests for feature versioning workflow including MLflow and DVC integration
    status: pending
    dependencies:
      - week7_mlflow_integration
      - week7_dvc_integration
      - week7_catalog_updates
---

# Week 7: Feature Versioning Implementation Plan

## Overview

Week 7 implements a comprehensive feature versioning system that tracks feature pipeline code versions, stores feature metadata with models in MLflow, and enables feature rollback and reproducibility. This builds on Week 6's event normalization and connector interface work.

## Goals

1. **Feature Pipeline Versioning**: Version feature computation code and track changes
2. **Feature Metadata Storage**: Store feature definitions and metadata with models in MLflow
3. **Feature Registry**: Create a centralized registry for feature pipeline versions
4. **Model-Feature Linking**: Link models to the exact feature versions used during training
5. **Reproducibility**: Enable exact reproduction of feature sets used in experiments

## Current State Analysis

### Existing Components

- **FeatureCatalog** ([`src/mt5-python_server/src/features/catalog.py`](src/mt5-python_server/src/features/catalog.py)): Stores feature metadata in database but no versioning
- **FeatureEngine** ([`src/mt5-python_server/src/application/environment/feature_engine.py`](src/mt5-python_server/src/application/environment/feature_engine.py)): Computes features on-the-fly without version tracking
- **ExperimentTracker** ([`src/mt5-python_server/src/mlops/experiment_tracker.py`](src/mt5-python_server/src/mlops/experiment_tracker.py)): MLflow integration exists, can log metadata
- **DataVersioner** ([`src/mt5-python_server/src/mlops/data_versioner.py`](src/mt5-python_server/src/mlops/data_versioner.py)): DVC integration for data versioning

### Gaps

- No version tracking for feature computation code
- Feature metadata not stored with models
- No feature pipeline version registry
- Cannot reproduce exact feature sets used in historical experiments

## Implementation Tasks

### Task 7.1: Create Feature Registry Module (Day 21)

**New File**: [`src/mt5-python_server/src/mlops/feature_registry.py`](src/mt5-python_server/src/mlops/feature_registry.py)

**Purpose**: Centralized registry for feature pipeline versions and metadata

**Key Components**:

1. **FeaturePipelineVersion Class**:
   ```python
   @dataclass
   class FeaturePipelineVersion:
       version: str  # Semantic version: "v1.2.0"
       pipeline_hash: str  # Hash of feature computation code
       feature_list: List[str]  # List of feature names
       feature_definitions: Dict[str, Any]  # Feature metadata
       created_at: datetime
       code_commit: Optional[str]  # Git commit hash
   ```

2. **FeatureRegistry Class**:

   - `register_pipeline()`: Register new feature pipeline version
   - `get_pipeline_version()`: Retrieve pipeline by version
   - `get_latest_version()`: Get most recent version
   - `list_versions()`: List all registered versions
   - `get_features_for_version()`: Get feature list for a version

3. **Integration Points**:

   - Store versions in database table `feature_pipelines`
   - Generate pipeline hash from feature computation code
   - Link to DVC for code versioning

**Database Schema** (New migration):

```sql
CREATE TABLE IF NOT EXISTS feature_pipelines (
    id INT PRIMARY KEY AUTO_INCREMENT,
    version VARCHAR(50) UNIQUE NOT NULL,
    pipeline_hash VARCHAR(64) NOT NULL,
    feature_list JSON NOT NULL,
    feature_definitions JSON,
    code_commit VARCHAR(40),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_version (version),
    INDEX idx_hash (pipeline_hash)
);
```

**Success Criteria**:

- Feature registry can register and retrieve pipeline versions
- Pipeline hash computed from feature code
- Database schema created and tested

---

### Task 7.2: Add Versioning to FeatureEngine (Day 21-22)

**File to Modify**: [`src/mt5-python_server/src/application/environment/feature_engine.py`](src/mt5-python_server/src/application/environment/feature_engine.py)

**Changes**:

1. **Add Version Tracking**:

   - Add `pipeline_version` attribute to `FeatureEngine`
   - Generate feature list and metadata during initialization
   - Compute pipeline hash from feature computation logic

2. **Feature Metadata Collection**:

   - Track which features are computed (technical indicators, economic calendar, etc.)
   - Store feature parameters (window sizes, indicator parameters)
   - Capture feature engineering transformations

3. **Version Export Method**:
   ```python
   def get_pipeline_metadata(self) -> Dict[str, Any]:
       """Export feature pipeline metadata for versioning"""
       return {
           "version": self.pipeline_version,
           "features": self.feature_list,
           "parameters": {
               "window_size": self.window_size,
               "features_per_pair": self.features_per_pair,
           },
           "feature_definitions": self._get_feature_definitions(),
       }
   ```

4. **Integration with FeatureRegistry**:

   - Auto-register pipeline version on first use
   - Link to experiment tracker for MLflow logging

**Success Criteria**:

- FeatureEngine tracks its pipeline version
- Feature metadata can be exported
- Version auto-registered in FeatureRegistry

---

### Task 7.3: Integrate Feature Metadata with MLflow (Day 22)

**Files to Modify**:

- [`src/mt5-python_server/src/mlops/experiment_tracker.py`](src/mt5-python_server/src/mlops/experiment_tracker.py)
- [`src/mt5-python_server/src/experiments/runner.py`](src/mt5-python_server/src/experiments/runner.py)

**Changes**:

1. **Add Feature Logging to ExperimentTracker**:
   ```python
   def log_feature_pipeline(
       self,
       pipeline_version: str,
       feature_list: List[str],
       feature_metadata: Dict[str, Any],
   ) -> None:
       """Log feature pipeline version and metadata"""
       self.set_tag("feature_pipeline_version", pipeline_version)
       self.log_dict(
           {
               "pipeline_version": pipeline_version,
               "features": feature_list,
               "metadata": feature_metadata,
           },
           "feature_pipeline.json",
       )
   ```

2. **Update ExperimentRunner**:

   - Extract feature pipeline metadata from FeatureEngine
   - Log to MLflow before training starts
   - Store feature version in experiment metadata

3. **Model-Feature Linking**:

   - When model is logged, include feature pipeline version in model metadata
   - Store feature list in model artifacts
   - Enable querying models by feature version

**Success Criteria**:

- Feature pipeline version logged to MLflow runs
- Feature metadata stored as MLflow artifacts
- Models linked to feature versions

---

### Task 7.4: DVC Integration for Feature Code Versioning (Day 22-23)

**Files to Modify**:

- [`src/mt5-python_server/src/mlops/data_versioner.py`](src/mt5-python_server/src/mlops/data_versioner.py)
- [`src/mt5-python_server/src/mlops/feature_registry.py`](src/mt5-python_server/src/mlops/feature_registry.py)

**Changes**:

1. **Extend DataVersioner**:

   - Add method to version feature computation code files
   - Track feature pipeline code changes in DVC
   - Link feature code versions to pipeline versions

2. **Feature Code Versioning**:
   ```python
   def version_feature_code(
       self,
       feature_files: List[str],
       version: str,
       message: str = "Feature pipeline version update"
   ) -> str:
       """Version feature computation code with DVC"""
       # Add feature files to DVC tracking
       # Create version tag
       # Return DVC commit hash
   ```

3. **Integration with FeatureRegistry**:

   - Store DVC commit hash in feature pipeline version
   - Enable retrieval of exact code version used
   - Link to git commit for full traceability

**Files to Version**:

- `src/mt5-python_server/src/application/environment/feature_engine.py`
- `src/mt5-python_server/src/utils/technical_indicators.py`
- `src/mt5-python_server/src/utils/feature_engineering.py`

**Success Criteria**:

- Feature code versioned in DVC
- DVC commit hash stored in feature registry
- Can retrieve exact code version for any pipeline version

---

### Task 7.5: Update Feature Catalog for Versioning (Day 23)

**File to Modify**: [`src/mt5-python_server/src/features/catalog.py`](src/mt5-python_server/src/features/catalog.py)

**Changes**:

1. **Add Version Tracking**:

   - Link features to pipeline versions
   - Track when features were added/modified
   - Store feature version history

2. **Database Schema Update**:
   ```sql
   ALTER TABLE features
   ADD COLUMN pipeline_version VARCHAR(50),
   ADD COLUMN first_seen_version VARCHAR(50),
   ADD INDEX idx_pipeline_version (pipeline_version);
   ```

3. **Version-Aware Queries**:

   - `get_features_by_pipeline_version()`: Get features for specific version
   - `get_feature_history()`: Track feature changes across versions
   - `compare_versions()`: Compare feature sets between versions

**Success Criteria**:

- Features linked to pipeline versions
- Can query features by version
- Feature history tracked

---

### Task 7.6: Create Integration Tests (Day 23)

**New File**: [`tests/integration/test_feature_versioning.py`](tests/integration/test_feature_versioning.py)

**Test Cases**:

1. **Feature Registry Tests**:

   - Test pipeline version registration
   - Test version retrieval
   - Test version listing

2. **FeatureEngine Versioning Tests**:

   - Test version tracking in FeatureEngine
   - Test metadata export
   - Test auto-registration

3. **MLflow Integration Tests**:

   - Test feature metadata logging to MLflow
   - Test model-feature linking
   - Test feature version retrieval from MLflow

4. **DVC Integration Tests**:

   - Test feature code versioning
   - Test DVC commit hash storage
   - Test code version retrieval

5. **End-to-End Tests**:

   - Test complete workflow: feature computation → versioning → MLflow logging
   - Test feature version reproduction
   - Test model training with versioned features

**Success Criteria**:

- All tests pass
- Test coverage > 80% for new code
- Integration tests validate complete workflow

---

## Database Migrations

**New Migration File**: [`src/database/scripts/12_feature_versioning.sql`](src/database/scripts/12_feature_versioning.sql)

**Schema Changes**:

1. Create `feature_pipelines` table
2. Add version columns to `features` table
3. Create indexes for version queries

---

## Dependencies

**Week 6 Prerequisites** (Must be completed):

- Event normalization layer implemented
- Data source connector interface created
- Event normalization tests passing

**External Dependencies**:

- MLflow server running (already in docker-compose.yml)
- DVC initialized (check if exists, create if not)
- Git repository (for commit hash tracking)

---

## Success Metrics

1. **Feature Pipeline Versioning**:

   - ✅ Feature pipeline versions registered and retrievable
   - ✅ Pipeline hash computed from code
   - ✅ DVC integration working

2. **MLflow Integration**:

   - ✅ Feature metadata logged to all MLflow runs
   - ✅ Models linked to feature versions
   - ✅ Feature versions queryable from MLflow

3. **Reproducibility**:

   - ✅ Can reproduce exact feature set for any experiment
   - ✅ Feature code version retrievable
   - ✅ Feature definitions stored with models

4. **Testing**:

   - ✅ Integration tests pass
   - ✅ Test coverage > 80%
   - ✅ End-to-end workflow validated

---

## Rollback Plan

If issues arise:

1. Feature versioning is additive - existing code continues to work
2. Can disable auto-registration if needed
3. MLflow logging is optional - can be disabled
4. Database migrations are reversible

---

## Documentation Updates

1. **Developer Guide**: Document feature versioning workflow
2. **API Documentation**: Document FeatureRegistry API
3. **User Guide**: Explain how to query feature versions

---

## Timeline

- **Day 21**: Feature Registry module + database schema
- **Day 22**: FeatureEngine versioning + MLflow integration
- **Day 23**: DVC integration + Feature Catalog updates + Tests

**Total Effort**: 3 days (Days 21-23)