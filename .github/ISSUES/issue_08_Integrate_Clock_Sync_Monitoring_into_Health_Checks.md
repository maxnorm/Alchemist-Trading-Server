Add Clock Sync Status to Health Check Endpoints

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: mvp-blocker, observability, P0
Milestone: Gate A - Production Data Collection
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #8: Add Clock Sync Status to Health Check Endpoints

## Problem Statement

Clock sync monitoring exists (`docs/CLOCK_SYNC_SETUP.md`, `scripts/check_clock_sync.py`) but is not integrated into health checks. If clock drift occurs, services may not detect it until data quality issues arise.

## Proposed Solution

1. **Add Clock Sync Check to Health Endpoints:**
   - Update `src/api/src/routers/health.py`
   - Add clock sync status check
   - Return clock drift in seconds

2. **Expose Clock Sync Status as Metric:**
   - `clock_drift_seconds` (gauge, drift from NTP server)

3. **Add Alert for Clock Drift:**
   - Alert if clock drift > 1 second

4. **Document Clock Sync Requirements:**
   - Update `docs/CLOCK_SYNC_SETUP.md`

5. **Test Clock Sync Monitoring:**
   - Simulate clock drift and verify detection

## Metadata

- **Effort:** S (2 story points)
- **Dependencies:** None
- **Owner Role:** DevOps
