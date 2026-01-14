Create Operational Runbooks for Data Collection Failures

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: mvp-blocker, documentation, operations, P0
Milestone: Gate A - Production Data Collection
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #9: Create Operational Runbooks for Data Collection Failures

## Problem Statement

While deployment checklists exist (`docs/DEPLOYMENT_CHECKLIST.md`), there are no operational runbooks for:
- Starting/stopping data collection
- Troubleshooting data quality issues
- Handling data gaps
- Responding to alerts
- Emergency procedures

Without runbooks, operators cannot effectively operate the system.

## Proposed Solution

1. **Create Runbook Directory:**
   - `docs/runbooks/`

2. **Create Runbooks:**
   - `data-collection-start.md` - Starting data collection
   - `data-collection-stop.md` - Stopping data collection (emergency)
   - `data-quality-troubleshooting.md` - Debugging quality issues
   - `data-gap-handling.md` - Handling data gaps
   - `alert-response.md` - Responding to alerts
   - `backfill-procedures.md` - Running backfills

3. **Format:**
   - Problem statement
   - Prerequisites
   - Step-by-step procedures
   - Verification steps
   - Rollback procedures
   - Escalation contacts

4. **Link to Monitoring:**
   - Reference Grafana dashboards
   - Reference alert rules
   - Reference API endpoints

## Metadata

- **Effort:** S (3 story points)
- **Dependencies:** Issues #5, #6 (dashboards and emergency stop needed for runbooks)
- **Owner Role:** Technical Writing / Operations
