---
name: Week 3 Data Versioning Reproducibility
overview: Complete DVC-MLflow integration to link data versions to MLflow runs, and implement a comprehensive reproducibility checklist storing code commit hash, config hash, data version, and environment information in MLflow metadata.
todos:
  - id: week3_dvc_mlflow_integration
    content: "Complete DVC-MLflow integration: execute DVC pipeline, link data versions to MLflow runs, store in tags"
    status: pending
    dependencies:
      - week2_cscv_pbo
  - id: week3_reproducibility
    content: "Implement reproducibility checklist: store code commit hash, config hash, data version, environment in MLflow"
    status: pending
    dependencies:
      - week3_dvc_mlflow
---

# Week 3: Data Versioning & Reproducibility

## Overview

Week 3 focuses on establishing complete data versioning and reproducibility tracking. This includes integrating DVC (Data Version Control) with MLflow to track which data versions were used in each experiment, and implementing a comprehensive reproducibility checklist that captures all necessary information to reproduce any experiment.

## Task 3.1: DVC-MLflow Integration (Days 7-9)

### Current State

- DVC pipeline is defined in `dvc.yaml` but not executed
- `DataVersioner` class exists in `src/mt5-python_server/src/mlops/data_versioner.py` with methods for DVC operations
- `ExperimentTracker` class exists in `src/mt5-python_server/src/mlops/experiment_tracker.py` with MLflow integration
- `scripts/export-data.py` exports data but doesn't auto-version with DVC
- No linkage between DVC data versions and MLflow runs

### Implementation

#### 3.1.1: Enhance DataVersioner for MLflow Integration

**File:** `src/mt5-python_server/src/mlops/data_versioner.py`

**Changes:**

1. Add method to get all tracked data file versions:
   ```python
   def get_all_data_versions(self) -> Dict[str, str]:
       """Get versions for all DVC-tracked data files"""
       versions = {}
       for file_path in self.list_files():
           version = self.get_version(file_path)
           if version:
               versions[file_path] = version
       return versions
   ```

2. Add method to create data version summary:
   ```python
   def get_data_version_summary(self) -> Dict[str, Any]:
       """Get summary of all data versions for MLflow tagging"""
       versions = self.get_all_data_versions()
       return {
           "data_versions": versions,
           "dvc_repo_root": str(self.repo_root),
           "dvc_available": self._dvc_available,
           "timestamp": datetime.now().isoformat()
       }
   ```


#### 3.1.2: Enhance ExperimentTracker to Store Data Versions

**File:** `src/mt5-python_server/src/mlops/experiment_tracker.py`

**Changes:**

1. Add method to log data versions from DVC:
   ```python
   def log_data_versions(self, data_versioner: Optional[DataVersioner] = None) -> None:
       """Log DVC data versions to MLflow tags"""
       if not self.is_run_active:
           raise RuntimeError("No active run. Call start_run() first.")
       
       if data_versioner is None:
           from mlops.data_versioner import DataVersioner
           data_versioner = DataVersioner()
       
       if not data_versioner._dvc_available:
           mlflow.set_tag("dvc_available", "false")
           self.logger.warning("DVC not available - skipping data version logging")
           return
       
       # Get data version summary
       summary = data_versioner.get_data_version_summary()
       
       # Store as tags
       mlflow.set_tag("dvc_available", "true")
       mlflow.set_tag("dvc_repo_root", summary["dvc_repo_root"])
       
       # Store individual data file versions
       for file_path, version in summary["data_versions"].items():
           tag_key = f"data_version_{file_path.replace('/', '_').replace('.', '_')}"
           mlflow.set_tag(tag_key, version)
       
       # Store summary as JSON artifact
       mlflow.log_dict(summary, "data_versions.json")
   ```

2. Update `start_run()` to optionally accept and use DataVersioner:
   ```python
   def start_run(
       self,
       run_name: Optional[str] = None,
       tags: Optional[Dict[str, str]] = None,
       description: Optional[str] = None,
       experiment_id: Optional[int] = None,
       log_data_versions: bool = True,  # New parameter
   ) -> str:
       # ... existing code ...
       
       # Log data versions if requested
       if log_data_versions:
           try:
               self.log_data_versions()
           except Exception as e:
               self.logger.warning(f"Failed to log data versions: {e}")
   ```


#### 3.1.3: Execute DVC Pipeline Before Experiments

**File:** `src/mt5-python_server/src/experiments/runner.py`

**Changes:**

1. Import DataVersioner at the top
2. In `start_experiment()`, before starting MLflow run, execute DVC pipeline:
   ```python
   # Execute DVC pipeline to ensure data is up-to-date
   try:
       from mlops.data_versioner import DataVersioner
       data_versioner = DataVersioner()
       if data_versioner._dvc_available:
           # Check if pipeline needs to be run
           status = data_versioner.get_pipeline_status()
           if not status.get("up_to_date", False):
               logger.info("DVC pipeline not up-to-date, running pipeline...")
               data_versioner.run_pipeline()
           else:
               logger.info("DVC pipeline is up-to-date")
   except Exception as e:
       logger.warning(f"Failed to execute DVC pipeline: {e}")
   ```

3. Pass DataVersioner to experiment tracker for data version logging:
   ```python
   if self.experiment_tracker:
       try:
           # Log data versions
           self.experiment_tracker.log_data_versions(data_versioner)
           
           mlflow_run_id = self.experiment_tracker.start_run(...)
           # ... rest of existing code ...
   ```


#### 3.1.4: Auto-Version Data Exports

**File:** `scripts/export-data.py`

**Changes:**

1. Add DVC integration to auto-version exports:
   ```python
   def auto_version_export(output_path: str, metadata: dict) -> None:
       """Automatically version exported data with DVC"""
       try:
           from mlops.data_versioner import DataVersioner
           versioner = DataVersioner()
           
           if versioner._dvc_available:
               # Add to DVC tracking
               dvc_file = versioner.add(output_path)
               print(f"Added to DVC tracking: {dvc_file}")
               
               # Optionally push to remote (commented out for now)
               # versioner.push()
           else:
               print("DVC not available - skipping versioning")
       except Exception as e:
           print(f"Warning: Failed to version with DVC: {e}")
   ```

2. Call `auto_version_export()` after each export in `export_ticks()` and `export_calendar()`

### Success Criteria

- DVC pipeline executes before experiments start
- All MLflow runs have data version tags
- Data exports are automatically versioned with DVC
- Data version information is stored in MLflow as both tags and JSON artifact

---

## Task 3.2: Reproducibility Checklist (Days 9-10)

### Current State

- `ExperimentTracker._log_system_info()` already logs:
  - Python version
  - Platform
  - Git commit (partial - only first 8 chars)
  - Start time
  - TensorFlow/NumPy versions (if available)
- Missing:
  - Full git commit hash
  - Config hash (params.yaml)
  - Environment identifier (Docker image hash or conda env)
  - Complete reproducibility metadata structure

### Implementation

#### 3.2.1: Enhance Reproducibility Metadata Collection

**File:** `src/mt5-python_server/src/mlops/experiment_tracker.py`

**Changes:**

1. Add method to compute config hash:
   ```python
   def _compute_config_hash(self, config_path: str = "params.yaml") -> Optional[str]:
       """Compute hash of params.yaml for reproducibility"""
       try:
           config_file = Path(config_path)
           if not config_file.exists():
               self.logger.warning(f"Config file not found: {config_path}")
               return None
           
           hasher = hashlib.sha256()
           with open(config_file, 'rb') as f:
               for chunk in iter(lambda: f.read(8192), b""):
                   hasher.update(chunk)
           return hasher.hexdigest()[:16]
       except Exception as e:
           self.logger.warning(f"Failed to compute config hash: {e}")
           return None
   ```

2. Add method to get environment identifier:
   ```python
   def _get_environment_id(self) -> Optional[str]:
       """Get environment identifier (Docker image or conda env)"""
       # Check for Docker
       docker_image = os.getenv("DOCKER_IMAGE_TAG")
       if docker_image:
           return f"docker:{docker_image}"
       
       # Check for conda
       conda_env = os.getenv("CONDA_DEFAULT_ENV")
       if conda_env:
           return f"conda:{conda_env}"
       
       # Check for virtualenv
       venv = os.getenv("VIRTUAL_ENV")
       if venv:
           venv_name = Path(venv).name
           return f"venv:{venv_name}"
       
       # Fallback to Python executable path hash
       try:
           python_path = sys.executable
           hasher = hashlib.sha256(python_path.encode())
           return f"python:{hasher.hexdigest()[:8]}"
       except Exception:
           return None
   ```

3. Enhance `_get_git_commit()` to return full hash:
   ```python
   def _get_git_commit(self, short: bool = False) -> Optional[str]:
       """Get current git commit hash"""
       try:
           import subprocess
           result = subprocess.run(
               ["git", "rev-parse", "HEAD"],
               capture_output=True,
               text=True,
               cwd=os.getcwd(),
           )
           if result.returncode == 0:
               commit_hash = result.stdout.strip()
               return commit_hash[:8] if short else commit_hash
       except Exception:
           pass
       return None
   ```

4. Create comprehensive reproducibility logging method:
   ```python
   def log_reproducibility_metadata(self, data_versioner: Optional[DataVersioner] = None) -> None:
       """Log complete reproducibility checklist"""
       if not self.is_run_active:
           raise RuntimeError("No active run. Call start_run() first.")
       
       reproducibility = {
           "code_commit_hash": self._get_git_commit(short=False),
           "code_commit_short": self._get_git_commit(short=True),
           "config_hash": self._compute_config_hash(),
           "config_path": "params.yaml",
           "environment_id": self._get_environment_id(),
           "python_version": sys.version.split()[0],
           "platform": sys.platform,
           "timestamp": datetime.now().isoformat(),
       }
       
       # Add data versions if available
       if data_versioner:
           try:
               summary = data_versioner.get_data_version_summary()
               reproducibility["data_versions"] = summary.get("data_versions", {})
               reproducibility["dvc_repo_root"] = summary.get("dvc_repo_root")
           except Exception as e:
               self.logger.warning(f"Failed to get data versions: {e}")
       
       # Log as tags for easy filtering
       mlflow.set_tag("reproducibility_code_commit", reproducibility["code_commit_hash"] or "unknown")
       mlflow.set_tag("reproducibility_config_hash", reproducibility["config_hash"] or "unknown")
       mlflow.set_tag("reproducibility_environment", reproducibility["environment_id"] or "unknown")
       
       # Log as parameters
       mlflow.log_param("reproducibility_code_commit", reproducibility["code_commit_hash"] or "unknown")
       mlflow.log_param("reproducibility_config_hash", reproducibility["config_hash"] or "unknown")
       mlflow.log_param("reproducibility_environment", reproducibility["environment_id"] or "unknown")
       
       # Store complete metadata as JSON artifact
       mlflow.log_dict(reproducibility, "reproducibility_metadata.json")
       
       self.logger.info("Logged reproducibility metadata")
   ```

5. Update `start_run()` to call reproducibility logging:
   ```python
   def start_run(
       self,
       run_name: Optional[str] = None,
       tags: Optional[Dict[str, str]] = None,
       description: Optional[str] = None,
       experiment_id: Optional[int] = None,
       log_data_versions: bool = True,
       log_reproducibility: bool = True,  # New parameter
   ) -> str:
       # ... existing code ...
       
       # Log reproducibility metadata
       if log_reproducibility:
           try:
               data_versioner = None
               if log_data_versions:
                   from mlops.data_versioner import DataVersioner
                   data_versioner = DataVersioner()
               self.log_reproducibility_metadata(data_versioner)
           except Exception as e:
               self.logger.warning(f"Failed to log reproducibility metadata: {e}")
   ```


#### 3.2.2: Create Reproducibility Report Function

**File:** `src/mt5-python_server/src/mlops/experiment_tracker.py`

**Add method:**

```python
def get_reproducibility_report(self, run_id: Optional[str] = None) -> Dict[str, Any]:
    """Get reproducibility report for a run"""
    if run_id is None:
        run_id = self._run_id
    
    if run_id is None:
        raise ValueError("No run ID provided")
    
    run = self.get_run(run_id)
    if run is None:
        return {"error": "Run not found"}
    
    # Extract reproducibility information from run
    tags = run.data.tags
    params = run.data.params
    
    report = {
        "run_id": run_id,
        "code_commit": tags.get("reproducibility_code_commit") or params.get("reproducibility_code_commit"),
        "config_hash": tags.get("reproducibility_config_hash") or params.get("reproducibility_config_hash"),
        "environment": tags.get("reproducibility_environment") or params.get("reproducibility_environment"),
        "python_version": params.get("python_version"),
        "platform": params.get("platform"),
        "start_time": params.get("start_time"),
    }
    
    # Try to get data versions from artifact
    try:
        client = MlflowClient(self.tracking_uri)
        artifacts = client.list_artifacts(run_id)
        for artifact in artifacts:
            if artifact.path == "reproducibility_metadata.json":
                import json
                artifact_data = client.download_artifacts(run_id, artifact.path)
                with open(artifact_data, 'r') as f:
                    report["full_metadata"] = json.load(f)
                break
    except Exception as e:
        self.logger.warning(f"Failed to load full reproducibility metadata: {e}")
    
    return report
```

### Success Criteria

- All MLflow runs have complete reproducibility metadata:
  - Full git commit hash (not just 8 chars)
  - Config hash (params.yaml SHA256)
  - Environment identifier (Docker/conda/venv)
  - Data versions (from DVC)
- Reproducibility metadata stored as both tags (for filtering) and JSON artifact (for complete info)
- Reproducibility report function can retrieve all metadata for any run

---

## Testing

### Integration Tests

**File:** `tests/integration/test_dataset_versioning.py` (NEW)

**Test cases:**

1. Test DVC pipeline execution before experiment
2. Test data version logging to MLflow
3. Test auto-versioning of data exports
4. Test reproducibility metadata collection
5. Test reproducibility report generation
6. Test that all required tags are present in MLflow runs

### Unit Tests

**File:** `tests/unit/test_data_versioner.py` (NEW if doesn't exist)

**Test cases:**

1. Test `get_all_data_versions()`
2. Test `get_data_version_summary()`
3. Test DVC availability checking

**File:** `tests/unit/test_experiment_tracker.py` (ENHANCE if exists)

**Test cases:**

1. Test `log_data_versions()`
2. Test `log_reproducibility_metadata()`
3. Test `_compute_config_hash()`
4. Test `_get_environment_id()`
5. Test `get_reproducibility_report()`

---

## Dependencies

- **Week 2 completion**: Walk-forward validation and CSCV/PBO implementation should be complete
- **DVC installation**: Ensure DVC is installed and configured
- **MLflow server**: Ensure MLflow tracking server is accessible

---

## Files to Modify

1. `src/mt5-python_server/src/mlops/data_versioner.py` - Add MLflow integration methods
2. `src/mt5-python_server/src/mlops/experiment_tracker.py` - Add data version and reproducibility logging
3. `src/mt5-python_server/src/experiments/runner.py` - Execute DVC pipeline and pass DataVersioner to tracker
4. `scripts/export-data.py` - Auto-version exports with DVC

## Files to Create

1. `tests/integration/test_dataset_versioning.py` - Integration tests for data versioning
2. `tests/unit/test_data_versioner.py` - Unit tests for DataVersioner enhancements (if doesn't exist)

---

## Success Metrics

- ✅ DVC pipeline executes automatically before experiments
- ✅ 100% of MLflow runs have data version tags
- ✅ 100% of MLflow runs have complete reproducibility metadata
- ✅ Data exports are automatically versioned
- ✅ Reproducibility report can be generated for any historical run
- ✅ All integration and unit tests pass