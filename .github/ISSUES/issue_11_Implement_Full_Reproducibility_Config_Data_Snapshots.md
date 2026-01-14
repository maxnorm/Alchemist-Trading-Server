Implement Full Reproducibility (Config + Data Snapshots)

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: mvp-blocker, mlops, reproducibility, P0
Milestone: Gate B - Live Training
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #11: Implement Full Reproducibility (Config + Data Snapshots)

## Problem Statement

Currently, training loop logs random seed (`src/trading_server/src/application/training/training_loop.py:242`), but full reproducibility requires:
- Code version (git commit)
- Configuration snapshot (hyperparameters, features, etc.)
- Data snapshot pointers (timestamp ranges, data version)
- Environment snapshot (Python version, dependencies)

Without full reproducibility, we cannot:
- Reproduce training runs
- Debug training issues
- Validate model behavior
- Meet ML Test Score requirements

## Proposed Solution

1. **Log Code Version:**
   - Get git commit hash: `git rev-parse HEAD`
   - Log to MLflow: `tracker.log_param("code_version", commit_hash)`
   - Log git tag if available: `tracker.log_param("code_tag", tag)`

2. **Log Configuration Snapshot:**
   - Already exists: `experiment_config` logged as artifact
   - Enhance: Also log as params for queryability
   - Include: Hyperparameters, features, currency pairs, training config

3. **Log Data Snapshot Pointers:**
   - Log data timestamp range: `start_time`, `end_time`
   - Log data version (if using DVC): `dvc_version`
   - Log data source versions: `mt5_connector_version`, etc.
   - Store in MLflow: `tracker.log_param("data_start_time", start_time)`

4. **Log Environment Snapshot:**
   - Log Python version: `sys.version`
   - Log dependency versions: `requirements.txt` hash or `pip freeze`
   - Log system info: OS, CPU, memory

5. **Create Reproducibility Report:**
   - Generate report from MLflow run: `reproducibility_report.json`
   - Include all snapshots
   - Store as MLflow artifact

6. **Add Reproducibility API Endpoint:**
   - `GET /api/v1/experiments/{id}/reproducibility` - Get reproducibility info

## Metadata

- **Effort:** M (5 story points)
- **Dependencies:** None
- **Owner Role:** MLOps
