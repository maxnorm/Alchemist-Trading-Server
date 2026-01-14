Add Alertmanager Service and Configure Alert Routing

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: mvp-blocker, observability, P0
Milestone: Phase 1 - Foundation
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #2: Add Alertmanager Service and Configure Alert Routing

## Problem Statement

Prometheus alert rules exist (`src/monitoring/prometheus/alerts/`) and Prometheus config references Alertmanager (`src/monitoring/prometheus/prometheus.yml:9-11`), but Alertmanager service is not defined in `docker-compose.yml`. Alerts won't be delivered without Alertmanager.

## Proposed Solution

1. **Add Alertmanager Service to docker-compose.yml:**
   ```yaml
   alertmanager:
     container_name: "alertmanager"
     image: prom/alertmanager:latest
     volumes:
       - "./src/monitoring/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro"
     command:
       - '--config.file=/etc/alertmanager/alertmanager.yml'
       - '--storage.path=/alertmanager'
     depends_on:
       - prometheus
     restart: unless-stopped
   ```

2. **Create Alertmanager Configuration:**
   - File: `src/monitoring/alertmanager/alertmanager.yml`
   - Configure notification channels (email, Slack, PagerDuty, etc.)
   - Set up routing rules
   - Configure grouping and deduplication

3. **Test Alert Delivery:**
   - Create test alert
   - Verify delivery to configured channels

4. **Document Alert Routing:**
   - Update `docs/MONITORING_GUIDE.md`

## Metadata

- **Effort:** S (2 story points)
- **Dependencies:** None
- **Owner Role:** DevOps / Observability
