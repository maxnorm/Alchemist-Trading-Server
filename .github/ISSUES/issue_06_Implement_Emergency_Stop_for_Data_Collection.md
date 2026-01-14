Implement Emergency Stop API for Data Collection

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: mvp-blocker, safety, data-pipeline, P0
Milestone: Gate A - Production Data Collection
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #6: Implement Emergency Stop API for Data Collection

## Problem Statement

While kill switch exists for trading (`src/trading_server/src/risk/kill_switch.py`), there's no emergency stop mechanism for data collection. If data collection causes issues (e.g., rate limiting, storage overflow, bad data), operators need a one-command way to halt all data collection.

## Proposed Solution

1. **Create Data Collection Control Service:**
   - File: `src/api/src/services/data_collection_service.py`
   - Methods:
     - `stop_data_collection()` - Pause all Airflow DAGs
     - `resume_data_collection()` - Resume all Airflow DAGs
     - `get_data_collection_status()` - Get status of all DAGs

2. **Add FastAPI Endpoints:**
   - `POST /api/v1/data/collection/stop` - Emergency stop
   - `POST /api/v1/data/collection/resume` - Resume (requires approval)
   - `GET /api/v1/data/collection/status` - Get status

3. **Integrate with Airflow:**
   - Use Airflow REST API or Python client to pause/resume DAGs
   - Pause all data collection DAGs:
     - `data_collection_pipeline`
     - `alternative_data_collection_dag`
     - `historical_backfill_dag` (if running)

4. **Add Audit Logging:**
   - Log stop/resume events to database or file
   - Include timestamp, user, reason

5. **Add Prometheus Metrics:**
   - `data_collection_stopped` (gauge, 1 if stopped, 0 if running)

6. **Add Alert:**
   - Alert if data collection stopped for > 1 hour

## Metadata

- **Effort:** S (3 story points)
- **Dependencies:** None
- **Owner Role:** Backend / DevOps
