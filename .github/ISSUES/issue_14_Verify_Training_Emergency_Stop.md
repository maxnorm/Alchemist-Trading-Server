Verify Training Emergency Stop Endpoint

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: mvp-blocker, safety, mlops, P0
Milestone: Gate B - Live Training
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #14: Verify Training Emergency Stop Endpoint

## Problem Statement

API endpoint exists for stopping experiments (`src/api/src/routers/experiments.py:96-115`), but we need to verify:
- Stop endpoint works correctly
- Training loop respects stop signal
- Resources are cleaned up
- State is persisted correctly
- Emergency stop works under load

## Proposed Solution

1. **Verify API Endpoint:**
   - Test `POST /api/v1/experiments/{id}/stop`
   - Verify endpoint returns correct status
   - Verify experiment status updated in database

2. **Verify Training Loop Stop:**
   - Ensure training loop checks `is_running` flag
   - Ensure stop signal propagates to training loop
   - Test graceful shutdown (save checkpoint, close connections)

3. **Add Integration Tests:**
   - Test stop endpoint
   - Test training loop stops within timeout (e.g., 30 seconds)
   - Test resource cleanup (threads, connections)
   - Test state persistence (checkpoint saved)

4. **Add Stress Test:**
   - Test stop under load (multiple experiments)
   - Test stop during heavy training

5. **Add Prometheus Metrics:**
   - `training_stop_duration_seconds` - Time to stop
   - `training_stop_errors_total` - Stop failures

6. **Update Runbook:**
   - Add emergency stop procedure to training runbook

## Metadata

- **Effort:** S (2 story points)
- **Dependencies:** None
- **Owner Role:** MLOps / Backend
