---
name: Audit Upgrade Implementation Plan
overview: A phased 12-week implementation plan to transform the AI Forex Trading System from 60% to 95% production-ready, addressing 15 critical issues including data correctness, evaluation realism, observability, and modularity.
todos:
  - id: week1_data_quality
    content: Implement data quality gates (outliers, duplicates, staleness, missing data) in src/mt5-python_server/src/data/quality_gates.py
    status: pending
  - id: week1_feature_timestamps
    content: Add point-in-time constraints to feature_engine.py with timestamp validation and latency buffers
    status: pending
  - id: week2_walk_forward
    content: Implement walk-forward validation in scripts/walk_forward_validation.py with expanding/rolling windows
    status: pending
    dependencies:
      - week1_data_quality
  - id: week2_cscv_pbo
    content: Implement CSCV algorithm in src/mt5-python_server/src/training/cscv.py to calculate PBO for experiments
    status: pending
    dependencies:
      - week2_walk_forward
  - id: week3_dvc_mlflow
    content: "Complete DVC-MLflow integration: execute DVC pipeline, link data versions to MLflow runs, store in tags"
    status: pending
    dependencies:
      - week2_cscv_pbo
  - id: week3_reproducibility
    content: "Implement reproducibility checklist: store code commit hash, config hash, data version, environment in MLflow"
    status: pending
    dependencies:
      - week3_dvc_mlflow
  - id: week4_prometheus
    content: Implement Prometheus metrics (trading, system, ML, safety) and expose /metrics endpoint
    status: pending
    dependencies:
      - week3_reproducibility
  - id: week4_grafana
    content: Create Grafana dashboards for trading metrics, system health, and safety controls
    status: pending
    dependencies:
      - week4_prometheus
  - id: week5_market_impact
    content: Enhance slippage models with market impact modeling (square-root model, volatility adjustment)
    status: pending
    dependencies:
      - week4_grafana
  - id: week5_stress_tests
    content: Create stress testing framework for slippage models with widened spreads and high volatility scenarios
    status: pending
    dependencies:
      - week5_market_impact
  - id: week6_event_normalization
    content: Implement event normalization layer with canonical schema, timestamp alignment, and quality gates
    status: pending
    dependencies:
      - week5_stress_tests
  - id: week6_connector_interface
    content: Create IDataSourceConnector interface and refactor MT5 provider to use it
    status: pending
    dependencies:
      - week6_event_normalization
  - id: week7_feature_versioning
    content: Implement feature pipeline versioning with metadata storage in MLflow
    status: pending
    dependencies:
      - week6_connector_interface
  - id: week8_drl_robustness
    content: Add adaptive learning rates and reward normalization to DQN agent and environment
    status: pending
    dependencies:
      - week7_feature_versioning
  - id: week9_pre_trade_controls
    content: Add pre-trade exposure limits and throttle controls to trading_controller.py
    status: pending
    dependencies:
      - week8_drl_robustness
  - id: week9_secrets_management
    content: Implement secrets management service (Vault/AWS Secrets Manager) with rotation
    status: pending
    dependencies:
      - week8_drl_robustness
  - id: week10_cicd_promotion
    content: Create CI/CD workflow for automated model promotion with gates and tests
    status: pending
    dependencies:
      - week9_pre_trade_controls
      - week9_secrets_management
  - id: week10_promotion_workflow
    content: Enhance model_promoter.py with automated gates, paper trading validation, and 2FA
    status: pending
    dependencies:
      - week10_cicd_promotion
  - id: week11_alerting
    content: Configure AlertManager with alerts for kill switch, circuit breaker, drawdown, and system failures
    status: pending
    dependencies:
      - week10_promotion_workflow
  - id: week11_enhanced_monitoring
    content: Add data pipeline and model performance monitoring dashboards to Grafana
    status: pending
    dependencies:
      - week11_alerting
  - id: week12_runbooks
    content: Create operational runbooks for kill switch, circuit breaker, reconciliation, and data pipeline failures
    status: pending
    dependencies:
      - week11_enhanced_monitoring
  - id: week12_incident_response
    content: Develop incident response plan with escalation paths, recovery procedures, and post-mortem templates
    status: pending
    dependencies:
      - week12_runbooks
---

# Audit Upgrade Implementation Plan

## Overview

This plan implements the comprehensive audit upgrade roadmap over 12 weeks, organized into 3 phases. The plan is optimized for solo development with clear dependencies and sequential task execution.

## Phase 1: Correctness + Reproducibility + Observability Baseline (Weeks 1-4)

### Week 1: Data Quality & Look-Ahead Prevention

#### Task 1.1: Data Quality Gates (Days 1-2)

**Files to create:**

- `src/mt5-python_server/src/data/quality_gates.py` - Systematic quality pipeline
- `tests/integration/test_data_quality_gates.py` - Quality gate tests

**Implementation:**

- Create `QualityGate` class with checks for:
  - Outliers (statistical bounds)
  - Duplicates (timestamp + symbol uniqueness)
  - Staleness (max age threshold)
  - Missing data (required fields)
- Integrate with `mt5_connection/tick_streamer.py` validation
- Add quality metrics logging

**Success Criteria:** Invalid ticks rejected; quality metrics logged; tests pass

#### Task 1.2: Feature Point-in-Time Constraints (Days 2-3)

**Files to modify:**

- `src/mt5-python_server/src/application/environment/feature_engine.py` - Add timestamp validation

**Implementation:**

- Modify `extract_features()` to accept `current_time: datetime` parameter
- Filter `price_history` to only include `timestamp <= current_time`
- Add latency buffer (5 minutes) for economic calendar features
- Update all call sites to pass `current_time`

**Files to create:**

- `tests/unit/test_feature_timestamps.py` - Verify no look-ahead bias

**Success Criteria:** All features pass timestamp validation; no look-ahead in tests

### Week 2: Walk-Forward & Overfitting Defense

#### Task 2.1: Walk-Forward Validation (Days 3-5)

**Files to create:**

- `scripts/walk_forward_validation.py` - Walk-forward implementation
- `tests/integration/test_walk_forward.py` - Walk-forward tests

**Implementation:**

- Implement `walk_forward_validation()` function with:
  - Expanding/rolling window support
  - Configurable train/test window sizes
  - Step size configuration
  - Temporal ordering enforcement (no future data)
- Integrate with `scripts/run-backtest.py` to replace single split

**Success Criteria:** Walk-forward produces expanding/rolling window results; no future data leakage

#### Task 2.2: CSCV/PBO Implementation (Days 5-7)

**Files to create:**

- `src/mt5-python_server/src/training/cscv.py` - CSCV algorithm implementation
- `tests/unit/test_cscv.py` - CSCV tests

**Implementation:**

- Implement `combinatorially_symmetric_cross_validation()` per Bailey & López de Prado (2014)
- Calculate PBO (Probability of Backtest Overfitting)
- Integrate with `experiments/runner.py` to calculate PBO for each experiment
- Store PBO in MLflow run tags

**Success Criteria:** PBO calculated for strategy configurations; PBO < 0.05 indicates low risk

### Week 3: Data Versioning & Reproducibility

#### Task 3.1: DVC-MLflow Integration (Days 7-9)

**Files to modify:**

- `src/mt5-python_server/src/mlops/data_versioner.py` - Enhance DVC integration
- `src/mt5-python_server/src/mlops/experiment_tracker.py` - Link data versions

**Implementation:**

- Execute DVC pipeline (currently defined but not executed)
- Store data version in MLflow tags: `mlflow.set_tag("data_version", "ticks_v1.2.3")`
- Link `data_versioner.py` with `experiment_tracker.py`
- Auto-version raw data exports from `scripts/export-data.py`

**Files to create:**

- `tests/integration/test_dataset_versioning.py` - Dataset versioning tests

**Success Criteria:** All MLflow runs linked to data versions; reproducibility checklist implemented

#### Task 3.2: Reproducibility Checklist (Days 9-10)

**Files to modify:**

- `src/mt5-python_server/src/mlops/experiment_tracker.py` - Add reproducibility metadata

**Implementation:**

- Store in MLflow run tags:
  - Code commit hash (`git rev-parse HEAD`)
  - Config hash (hash of `params.yaml`)
  - Data version (DVC)
  - Environment (Docker image hash or Python version)
- Create reproducibility report function

**Success Criteria:** All experiments have complete reproducibility metadata

### Week 4: Observability Baseline

#### Task 4.1: Prometheus Metrics (Days 10-12)

**Files to create:**

- `src/mt5-python_server/src/monitoring/metrics.py` - Prometheus metrics
- `tests/unit/test_metrics_collection.py` - Metrics tests

**Implementation:**

- Define metrics:
  - Trading: `trades_total`, `trade_latency_seconds`, `account_equity`, `drawdown_pct`
  - System: `api_request_duration`, `database_query_duration`
  - ML: `model_inference_latency`, `feature_extraction_duration`
  - Safety: `kill_switch_active`, `circuit_breaker_state`, `oms_reconciliation_errors`
- Expose `/metrics` endpoint in API
- Integrate metrics into `trading_controller.py`, `server.py`, feature extraction

**Files to modify:**

- `docker-compose.yml` - Add Prometheus service
- `src/api/src/main.py` - Add metrics endpoint

**Success Criteria:** Metrics exposed on `/metrics` endpoint; metrics collected in real-time

#### Task 4.2: Grafana Dashboards (Days 12-14)

**Files to create:**

- `monitoring/prometheus/prometheus.yml` - Prometheus configuration
- `monitoring/grafana/dashboards/trading.json` - Trading metrics dashboard
- `monitoring/grafana/dashboards/system.json` - System health dashboard
- `monitoring/grafana/dashboards/safety.json` - Safety controls dashboard

**Implementation:**

- Configure Prometheus to scrape metrics
- Create Grafana dashboards with:
  - Trading performance (equity, drawdown, trades)
  - System health (latency, errors, throughput)
  - Safety controls (kill switch, circuit breaker status)

**Files to modify:**

- `docker-compose.yml` - Add Grafana service

**Success Criteria:** Dashboards display real-time metrics

**Phase 1 Gates:**

- All data quality gates pass
- No look-ahead bias in feature tests
- Walk-forward validation working
- PBO calculated for experiments
- Data versions linked to MLflow runs
- Prometheus metrics exposed
- Grafana dashboards operational

---

## Phase 2: Evaluation Realism + Anti-Overfitting Defenses (Weeks 5-8)

### Week 5: Enhanced Transaction Costs

#### Task 5.1: Market Impact Modeling (Days 14-16)

**Files to modify:**

- `src/mt5-python_server/src/environments/slippage_models.py` - Add market impact

**Implementation:**

- Create `MarketImpactSlippage` class with:
  - Square-root model: `impact = base * sqrt(quantity/market_depth)`
  - Volatility adjustment factor
  - Market depth consideration
- Enhance existing `VolumeBasedSlippage` with volatility adjustment

**Files to create:**

- `tests/unit/test_market_impact.py` - Market impact tests

**Success Criteria:** Market impact scales with order size and volatility

#### Task 5.2: Stress Testing Framework (Days 16-17)

**Files to create:**

- `tests/stress/test_slippage_models.py` - Stress test suite

**Implementation:**

- Create stress test scenarios:
  - Widened spreads (5x normal)
  - High volatility (3x normal)
  - Low liquidity
- Verify performance degradation is realistic (not catastrophic)

**Success Criteria:** Performance degradation is realistic under stress

### Week 6: Event Normalization & Data Correctness

#### Task 6.1: Event Normalization Layer (Days 17-19)

**Files to create:**

- `src/mt5-python_server/src/events/normalizer.py` - `IEventNormalizer` implementation
- `src/mt5-python_server/src/events/schema_registry.py` - Canonical schema definitions
- `src/mt5-python_server/src/events/quality_gates.py` - Event quality checks
- `tests/integration/test_event_normalizer.py` - Normalizer tests

**Implementation:**

- Define canonical event schema:
  ```python
  {
    "timestamp": datetime,  # UTC normalized
    "source": str,
    "symbol": str,
    "data_type": str,  # "tick", "bar", "news"
    "payload": Dict
  }
  ```

- Implement `EventNormalizer` with:
  - `normalize()` - Convert raw events to canonical format
  - `validate()` - Schema and quality validation
  - `align_timestamps()` - Cross-source timestamp alignment

**Success Criteria:** All sources normalized to canonical format; timestamp alignment validated

#### Task 6.2: Data Source Connector Interface (Days 19-21)

**Files to create:**

- `src/mt5-python_server/src/connectors/base.py` - `IDataSourceConnector` interface
- `src/mt5-python_server/src/connectors/mt5_tick_connector.py` - MT5 connector implementation

**Files to modify:**

- `src/mt5-python_server/src/mt5_connection/tick_streamer.py` - Refactor to use connector
- `src/mt5-python_server/src/server.py` - Update to use connector interface

**Implementation:**

- Define `IDataSourceConnector` with methods:
  - `stream()` - Real-time streaming
  - `batch()` - Historical batch fetch
  - `get_schema()` - Schema definition
  - `get_latest_timestamp()` - Latest data timestamp
- Refactor MT5 provider to implement interface

**Files to create:**

- `tests/integration/test_connector_interface.py` - Connector tests

**Success Criteria:** New data sources can be added by implementing interface

### Week 7: Feature Versioning

#### Task 7.1: Feature Pipeline Versioning (Days 21-23)

**Files to create:**

- `src/mt5-python_server/src/mlops/feature_registry.py` - Feature versioning
- `src/mt5-python_server/src/features/base.py` - `IFeaturePipeline` interface

**Files to modify:**

- `src/mt5-python_server/src/features/catalog.py` - Track feature versions
- `src/mt5-python_server/src/mlops/experiment_tracker.py` - Store feature metadata

**Implementation:**

- Add version tracking to feature pipelines
- Store feature metadata with models in MLflow
- Version feature computation code with DVC

**Files to create:**

- `tests/integration/test_feature_versioning.py` - Feature versioning tests

**Success Criteria:** Feature versions tracked; metadata stored with models

### Week 8: DRL Robustness

#### Task 8.1: Adaptive Learning Rates (Days 23-25)

**Files to modify:**

- `src/mt5-python_server/src/agents/dqn_agent.py` - Add adaptive learning rate scheduler
- `src/mt5-python_server/src/environments/live_env.py` - Add reward normalization

**Implementation:**

- Implement adaptive learning rate scheduler (reduce on plateau, cosine annealing)
- Add reward normalization to prevent reward hacking
- Monitor reward function stability

**Files to create:**

- `tests/unit/test_adaptive_learning.py` - Adaptive learning tests

**Success Criteria:** Learning rates adapt to market conditions; reward function stable

**Phase 2 Gates:**

- Market impact modeling complete
- Stress tests pass
- Event normalization working
- Connector interface implemented
- Feature versioning operational
- DRL robustness improved

---

## Phase 3: Execution/Risk Hardening + Model Registry Promotion (Weeks 9-12)

### Week 9: Risk Controls Enhancement

#### Task 9.1: Pre-Trade Exposure Limits (Days 25-27)

**Files to modify:**

- `src/mt5-python_server/src/trading_controller.py` - Add pre-trade checks

**Implementation:**

- Add pre-trade exposure limit checks
- Implement throttle controls (max trades per minute/hour)
- Integrate with existing risk manager

**Files to create:**

- `tests/integration/test_pre_trade_controls.py` - Pre-trade control tests

**Success Criteria:** Trades blocked when exposure limits exceeded

#### Task 9.2: Secrets Management (Days 27-28)

**Files to create:**

- `src/mt5-python_server/src/utils/secrets_manager.py` - Secrets management

**Implementation:**

- Implement HashiCorp Vault or AWS Secrets Manager integration
- Add secrets rotation automation
- Replace environment variable usage with secrets service

**Files to create:**

- `tests/unit/test_secrets_manager.py` - Secrets manager tests

**Success Criteria:** Secrets stored securely; rotation working

### Week 10: Model Promotion Automation

#### Task 10.1: CI/CD Integration (Days 28-30)

**Files to create:**

- `.github/workflows/model_promotion.yml` - Model promotion workflow

**Implementation:**

- Automated promotion gates:
  - Training → Staging: Auto-promote
  - Staging → Paper: Manual review + metrics validation
  - Paper → Production: Automated tests + 2FA approval
- Integration tests for promotion workflow

**Files to create:**

- `tests/integration/test_model_promotion.py` - Promotion tests

**Success Criteria:** Models promoted automatically when criteria met

#### Task 10.2: Promotion Workflow Enhancement (Days 30-32)

**Files to modify:**

- `src/mt5-python_server/src/mlops/model_promoter.py` - Add automated gates

**Implementation:**

- Enhance promotion workflow with:
  - Automated metric validation
  - Paper trading result verification
  - 2FA for production promotion
  - Audit trail

**Success Criteria:** Promotion workflow automated with manual approval gates

### Week 11: Observability & Alerting

#### Task 11.1: Alerting System (Days 32-34)

**Files to create:**

- `monitoring/prometheus/alerts.yml` - AlertManager configuration

**Implementation:**

- Configure AlertManager with alerts for:
  - Kill switch activated
  - Circuit breaker tripped
  - Drawdown > 15%
  - API down
  - Database failures
- Set up alert channels (Slack, PagerDuty, Email)

**Files to modify:**

- `docker-compose.yml` - Add AlertManager service

**Success Criteria:** Alerts trigger on critical events

#### Task 11.2: Enhanced Monitoring (Days 34-35)

**Files to modify:**

- `monitoring/grafana/dashboards/` - Add data pipeline and model performance dashboards

**Implementation:**

- Add dashboards for:
  - Data pipeline monitoring (freshness, quality scores)
  - Model performance monitoring (inference latency, accuracy drift)
  - Feature drift detection

**Success Criteria:** All critical metrics monitored

### Week 12: Operational Readiness

#### Task 12.1: Runbooks (Days 35-37)

**Files to create:**

- `docs/runbooks/kill_switch_activation.md`
- `docs/runbooks/circuit_breaker_trip.md`
- `docs/runbooks/position_reconciliation_failure.md`
- `docs/runbooks/data_pipeline_failure.md`

**Implementation:**

- Document procedures for:
  - Kill switch activation (investigation, reset, post-mortem)
  - Circuit breaker trip (review metrics, determine cause, recovery)
  - Position reconciliation failure (OMS vs broker mismatch, resolution)
  - Data pipeline failures (diagnosis, recovery, data re-sync)

**Success Criteria:** Runbooks cover all critical incidents

#### Task 12.2: Incident Response Plan (Days 37-38)

**Files to create:**

- `docs/INCIDENT_RESPONSE_PLAN.md`

**Implementation:**

- Develop incident response procedures:
  - Escalation paths
  - Communication protocols
  - Recovery procedures
  - Post-mortem templates
- Test recovery procedures

**Success Criteria:** Incident response tested and documented

**Phase 3 Gates:**

- Pre-trade controls working
- Secrets management operational
- Model promotion automated
- Alerting configured
- Runbooks complete
- Incident response tested

---

## Dependencies & Sequencing

### Critical Path

1. **Week 1** → **Week 2**: Data quality gates must be in place before walk-forward validation
2. **Week 2** → **Week 3**: Walk-forward validation needed before data versioning integration
3. **Week 3** → **Week 4**: Data versioning needed before observability (to track data in metrics)
4. **Week 6** → **Week 7**: Event normalization needed before feature versioning
5. **Week 9** → **Week 10**: Risk controls needed before model promotion automation

### Parallel Opportunities (Limited for Solo)

- Task 4.1 (Prometheus) and Task 4.2 (Grafana) can be done sequentially but are independent
- Task 9.1 (Pre-trade) and Task 9.2 (Secrets) are independent
- Task 11.1 (Alerting) and Task 11.2 (Monitoring) are sequential but related

## Testing Strategy

Each task includes:

- Unit tests for new functionality
- Integration tests for cross-component interactions
- Success criteria validation

**Test Coverage Target:** 80%+ by end of Phase 3

## Risk Mitigation

1. **Rollback Plans**: Each phase has defined rollback procedures
2. **Incremental Deployment**: Changes are backward-compatible where possible
3. **Feature Flags**: Use feature flags for new functionality (optional enhancement)
4. **Documentation**: Update documentation as changes are made

## Success Metrics

- **Phase 1**: Data correctness (0 look-ahead bias), evaluation realism (PBO < 0.05), observability (metrics exposed)
- **Phase 2**: Transaction cost realism (backtest vs live gap < 20%), modularity (new sources in < 1 day)
- **Phase 3**: Production readiness (95% reliability score), automated promotion, operational excellence

## Extended Roadmap (Weeks 13+)

- **Weeks 13-14**: Broker Modularity (`IBrokerAdapter` interface, cTrader adapter)
- **Weeks 15-16**: Multi-Account Support
- **Weeks 17-18**: Disaster Recovery (comprehensive backup strategy, recovery testing)