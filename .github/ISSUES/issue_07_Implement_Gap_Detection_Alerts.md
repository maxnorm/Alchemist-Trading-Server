Add Prometheus Alerts for Data Collection Gaps

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: mvp-blocker, observability, data-pipeline, P0
Milestone: Gate A - Production Data Collection
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #7: Add Prometheus Alerts for Data Collection Gaps

## Problem Statement

Gap detection exists (`src/trading_server/src/monitoring/gap_detector.py`) but alerts are not configured. When data collection fails, operators are not notified, leading to data loss.

## Proposed Solution

1. **Add Gap Detection Metrics to Prometheus:**
   - `data_gap_detected{symbol, source}` (gauge, 1 if gap detected)
   - `data_gap_duration_seconds{symbol, source}` (gauge, duration of gap)
   - `data_gaps_total{symbol, source}` (counter, total gaps detected)

2. **Create Alert Rules:**
   - Alert on gaps > 5 minutes (warning)
   - Alert on gaps > 30 minutes (critical)
   - Alert on system-wide gaps

3. **Configure Alert Routing:**
   - Route to on-call engineer (via Alertmanager)

4. **Test Alerts:**
   - Simulate gaps and verify alerts fire

5. **Document Gap Detection:**
   - Update runbooks with gap handling procedures

## Metadata

- **Effort:** S (2 story points)
- **Dependencies:** Issue #2 (Alertmanager) - needs alert routing
- **Owner Role:** Data Eng / DevOps
