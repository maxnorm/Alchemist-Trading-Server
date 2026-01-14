Configure Great Expectations for Data Quality Validation

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: mvp-blocker, data-pipeline, mlops, P0
Milestone: Gate A - Production Data Collection
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #4: Configure Great Expectations for Data Quality Validation

## Problem Statement

Great Expectations code exists (`src/trading_server/src/infrastructure/data_quality/ge_context.py`, `src/trading_server/src/data/quality_gates.py:108-116`) but is optional and not fully configured. We need GE operational for standardized, auditable data quality validation.

## Proposed Solution

1. **Install and Initialize Great Expectations:**
   ```bash
   pip install great-expectations
   great_expectations init
   ```

2. **Create Expectation Suites:**
   - Convert existing contract validators to GE expectations:
     - `tick_data_expectations.json` (from tick contract)
     - `bar_data_expectations.json` (from bar contract)
     - `news_data_expectations.json` (from news contract)
     - `economic_data_expectations.json` (from economic contract)

3. **Enable GE in QualityGate:**
   - Update `quality_gates.py` to enable GE by default in production
   - Add configuration flag: `USE_GE_VALIDATION=true`

4. **Create Data Docs Server:**
   - Serve GE Data Docs via FastAPI endpoint: `/api/v1/data/quality/docs`
   - Or serve via static file server (nginx)

5. **Add Prometheus Metrics:**
   - `data_quality_validation_passed_total`
   - `data_quality_validation_failed_total`
   - `data_quality_expectation_violations_total{expectation_name}`

## Metadata

- **Effort:** M (5 story points)
- **Dependencies:** None (can start immediately)
- **Owner Role:** Data Engineering
