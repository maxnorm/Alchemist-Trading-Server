Create Grafana Dashboard for Data Quality Metrics

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: mvp-blocker, observability, data-pipeline, P0
Milestone: Gate A - Production Data Collection
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #5: Create Grafana Dashboard for Data Quality Metrics

## Problem Statement

While Prometheus alerts exist for data quality (`src/monitoring/prometheus/alerts/data_quality_alerts.yml`), there are no Grafana dashboards to visualize:
- Data freshness (time since last data point)
- Data volume (records per hour/day)
- Quality score (pass rate of validations)
- Quarantine rate (percentage of data quarantined)
- Expectation violations over time

Without dashboards, operators cannot monitor data quality trends or identify issues early.

## Proposed Solution

1. **Create Grafana Dashboard JSON:**
   - File: `src/monitoring/grafana/dashboards/data-quality.json`
   - Panels:
     - **Data Freshness:** Time since last data point per symbol (gauge)
     - **Data Volume:** Records per hour/day (time series)
     - **Quality Score:** Pass rate percentage (gauge)
     - **Quarantine Rate:** Percentage quarantined (gauge)
     - **Expectation Violations:** Violations over time (time series, grouped by expectation)
     - **Top Violations:** Table of most common violations

2. **Configure Grafana Provisioning:**
   - Ensure dashboard is auto-loaded: `src/monitoring/grafana/provisioning/dashboards/`
   - Configure datasource: Prometheus

3. **Add Required Prometheus Metrics:**
   - Ensure metrics exist (from Issue #4):
     - `data_freshness_seconds{symbol, source}`
     - `data_volume_total{symbol, source}`
     - `data_quality_score{symbol, source}`
     - `data_quarantine_rate{symbol, source}`
     - `data_quality_expectation_violations_total{expectation_name, symbol}`

4. **Create Alert Rules:**
   - Link alerts to dashboard (already exist in `data_quality_alerts.yml`)

## Metadata

- **Effort:** M (5 story points)
- **Dependencies:** Issue #4 (Great Expectations Integration) - needs metrics
- **Owner Role:** DevOps / Observability
