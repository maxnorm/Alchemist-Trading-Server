---
name: Week 4 Observability Baseline
overview: Implement Prometheus metrics collection and Grafana dashboards to establish comprehensive observability for the trading system, enabling real-time monitoring of trading performance, system health, ML operations, and safety controls.
todos:
  - id: week4_metrics_module
    content: Create metrics.py module with Prometheus metric definitions (trading, system, ML, safety)
    status: completed
  - id: week4_api_metrics_endpoint
    content: Add /metrics endpoint to FastAPI application in src/api/src/main.py
    status: completed
    dependencies:
      - week4_metrics_module
  - id: week4_trading_metrics_integration
    content: Integrate trading metrics into trading_controller.py (trades, latency, equity, drawdown)
    status: completed
    dependencies:
      - week4_metrics_module
  - id: week4_system_metrics_integration
    content: Add system metrics to API endpoints (request duration, database queries)
    status: completed
    dependencies:
      - week4_metrics_module
  - id: week4_ml_metrics_integration
    content: Add ML metrics to feature extraction and model inference
    status: completed
    dependencies:
      - week4_metrics_module
  - id: week4_safety_metrics_integration
    content: Add safety metrics to kill switch, circuit breaker, and OMS
    status: completed
    dependencies:
      - week4_metrics_module
  - id: week4_prometheus_setup
    content: Configure Prometheus service in docker-compose.yml and create prometheus.yml config
    status: completed
    dependencies:
      - week4_api_metrics_endpoint
  - id: week4_prometheus_alerts
    content: Create alert rules for kill switch, circuit breaker, drawdown, and system failures
    status: completed
    dependencies:
      - week4_prometheus_setup
  - id: week4_grafana_setup
    content: Configure Grafana service in docker-compose.yml with provisioning
    status: completed
    dependencies:
      - week4_prometheus_setup
  - id: week4_trading_dashboard
    content: Create trading performance dashboard with equity, drawdown, trades, and latency
    status: completed
    dependencies:
      - week4_grafana_setup
  - id: week4_system_dashboard
    content: Create system health dashboard with API and database metrics
    status: completed
    dependencies:
      - week4_grafana_setup
  - id: week4_safety_dashboard
    content: Create safety controls dashboard with kill switch, circuit breaker, and OMS metrics
    status: completed
    dependencies:
      - week4_grafana_setup
  - id: week4_ml_dashboard
    content: Create ML operations dashboard with inference latency and feature extraction metrics
    status: completed
    dependencies:
      - week4_grafana_setup
  - id: week4_metrics_tests
    content: Create unit tests for metrics collection in tests/unit/test_metrics_collection.py
    status: completed
    dependencies:
      - week4_metrics_module
---

# Week 4: Observability Baseline Implementation Plan

## Overview

Week 4 establishes the observability foundation by implementing Prometheus metrics collection and Grafana dashboards. This enables real-time monitoring of trading operations, system health, ML performance, and safety mechanisms.

## Dependencies

- **Prerequisite**: Week 3 (Reproducibility) must be completed
- **Blocks**: Week 5 (Enhanced Transaction Costs) can proceed after Week 4

## Task 4.1: Prometheus Metrics (Days 10-12)

### Files to Create

1. **`src/mt5-python_server/src/monitoring/metrics.py`** - Core metrics definitions

                                                                                                - Trading metrics (trades, latency, equity, drawdown)
                                                                                                - System metrics (API requests, database queries)
                                                                                                - ML metrics (inference latency, feature extraction)
                                                                                                - Safety metrics (kill switch, circuit breaker, OMS errors)

2. **`src/mt5-python_server/src/monitoring/__init__.py`** - Package initialization

3. **`monitoring/prometheus/prometheus.yml`** - Prometheus configuration

                                                                                                - Scrape configs for API, server, and other services
                                                                                                - Alert rule file references

4. **`monitoring/prometheus/alerts/trading-alerts.yml`** - Alert rules

                                                                                                - Kill switch activation
                                                                                                - Circuit breaker trips
                                                                                                - High drawdown
                                                                                                - System failures

5. **`tests/unit/test_metrics_collection.py`** - Metrics collection tests

### Files to Modify

1. **`src/api/src/main.py`** - Add `/metrics` endpoint

                                                                                                - Import Prometheus client
                                                                                                - Expose metrics endpoint using `prometheus_client.generate_latest()`

2. **`src/api/src/routers/health.py`** - Add metrics to health checks

                                                                                                - Track health check duration
                                                                                                - Count health check failures

3. **`src/mt5-python_server/src/trading_controller.py`** - Integrate trading metrics

                                                                                                - Increment `trades_executed_total` on trade execution
                                                                                                - Record `trade_latency_seconds` for order execution
                                                                                                - Update `account_equity` gauge
                                                                                                - Update `current_drawdown_pct` gauge

4. **`src/mt5-python_server/src/application/environment/feature_engine.py`** - Add ML metrics

                                                                                                - Record `feature_extraction_duration` histogram

5. **`src/mt5-python_server/src/agents/dqn_agent.py`** - Add ML metrics

                                                                                                - Record `model_inference_latency` histogram

6. **`src/mt5-python_server/src/risk/kill_switch.py`** - Add safety metrics

                                                                                                - Update `kill_switch_active` gauge (1=active, 0=inactive)

7. **`src/mt5-python_server/src/risk/circuit_breaker.py`** - Add safety metrics

                                                                                                - Update `circuit_breaker_state` gauge with state labels

8. **`src/mt5-python_server/src/risk/oms.py`** - Add safety metrics

                                                                                                - Increment `oms_reconciliation_errors_total` on reconciliation failures

9. **`docker-compose.yml`** - Add Prometheus service

                                                                                                - Configure Prometheus container
                                                                                                - Mount configuration files
                                                                                                - Expose port 9090

10. **`src/api/requirements.txt`** - Add prometheus-client dependency

                                                                                                                                - Add `prometheus-client>=0.19.0`

11. **`src/mt5-python_server/requirements.txt`** - Add prometheus-client dependency

                                                                                                                                - Add `prometheus-client>=0.19.0`

### Implementation Details

#### Metrics Definitions

```python
# src/mt5-python_server/src/monitoring/metrics.py

from prometheus_client import Counter, Histogram, Gauge, Summary

# Trading Metrics
trades_executed_total = Counter(
    'trading_trades_total',
    'Total trades executed',
    ['symbol', 'action_type']  # action_type: 'buy', 'sell', 'close'
)

trade_latency_seconds = Histogram(
    'trading_latency_seconds',
    'Trade execution latency in seconds',
    ['symbol'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

account_equity = Gauge(
    'trading_account_equity',
    'Current account equity'
)

current_drawdown_pct = Gauge(
    'trading_drawdown_pct',
    'Current drawdown percentage'
)

win_rate = Gauge(
    'trading_win_rate',
    'Win rate',
    ['period']  # period: '24h', '7d', '30d'
)

# System Metrics
api_request_duration = Histogram(
    'api_request_duration_seconds',
    'API request duration',
    ['method', 'endpoint', 'status_code']
)

api_requests_total = Counter(
    'api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status_code']
)

database_query_duration = Histogram(
    'database_query_duration_seconds',
    'Database query duration',
    ['query_type']
)

database_connections_active = Gauge(
    'database_connections_active',
    'Active database connections'
)

# ML Metrics
model_inference_latency = Histogram(
    'model_inference_latency_seconds',
    'Model inference latency',
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)

feature_extraction_duration = Histogram(
    'feature_extraction_duration_seconds',
    'Feature extraction time',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

training_episode_reward = Gauge(
    'training_episode_reward',
    'Training episode reward',
    ['episode']
)

# Safety Metrics
kill_switch_active = Gauge(
    'kill_switch_active',
    'Kill switch status (1=active, 0=inactive)'
)

circuit_breaker_state = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state',
    ['state']  # state: 'closed', 'open', 'half_open'
)

oms_reconciliation_errors = Counter(
    'oms_reconciliation_errors_total',
    'OMS reconciliation errors'
)
```

#### API Metrics Endpoint

```python
# src/api/src/main.py additions

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

#### Prometheus Configuration

```yaml
# monitoring/prometheus/prometheus.yml

global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'trading-platform'
    environment: 'production'

alerting:
  alertmanagers:
  - static_configs:
    - targets: ['alertmanager:9093']

rule_files:
 - '/etc/prometheus/alerts/*.yml'

scrape_configs:
 - job_name: 'api'
    static_configs:
   - targets: ['api:8000']
    metrics_path: '/metrics'
    
 - job_name: 'server'
    static_configs:
   - targets: ['server:8080']
    metrics_path: '/metrics'
    
 - job_name: 'prometheus'
    static_configs:
   - targets: ['localhost:9090']
```

### Success Criteria

- [ ] Metrics module created with all metric definitions
- [ ] `/metrics` endpoint exposed in API and returns valid Prometheus format
- [ ] Trading metrics collected in `trading_controller.py`
- [ ] System metrics collected in API endpoints
- [ ] ML metrics collected in feature extraction and model inference
- [ ] Safety metrics collected in kill switch, circuit breaker, and OMS
- [ ] Prometheus service running in Docker Compose
- [ ] Prometheus scraping metrics from API and server
- [ ] Unit tests pass for metrics collection

## Task 4.2: Grafana Dashboards (Days 12-14)

### Files to Create

1. **`monitoring/grafana/dashboards/trading.json`** - Trading performance dashboard

                                                                                                - Equity curve
                                                                                                - Drawdown chart
                                                                                                - Trade count and win rate
                                                                                                - Trade latency
                                                                                                - Open positions

2. **`monitoring/grafana/dashboards/system.json`** - System health dashboard

                                                                                                - API request rate and latency
                                                                                                - Database query performance
                                                                                                - Active connections
                                                                                                - Service uptime

3. **`monitoring/grafana/dashboards/safety.json`** - Safety controls dashboard

                                                                                                - Kill switch status
                                                                                                - Circuit breaker state
                                                                                                - OMS reconciliation errors
                                                                                                - Risk metrics

4. **`monitoring/grafana/dashboards/ml.json`** - ML operations dashboard

                                                                                                - Model inference latency
                                                                                                - Feature extraction duration
                                                                                                - Training progress
                                                                                                - Model performance metrics

5. **`monitoring/grafana/provisioning/dashboards/dashboards.yml`** - Dashboard provisioning

                                                                                                - Auto-load dashboards on Grafana startup

6. **`monitoring/grafana/provisioning/datasources/prometheus.yml`** - Prometheus datasource

                                                                                                - Configure Prometheus as default datasource

### Files to Modify

1. **`docker-compose.yml`** - Add Grafana service

                                                                                                - Configure Grafana container
                                                                                                - Mount dashboard and provisioning files
                                                                                                - Expose port 3001
                                                                                                - Set default admin credentials via environment variables

### Implementation Details

#### Dashboard Structure

Each dashboard should include:

- **Time range selector** (last 1h, 6h, 24h, 7d, 30d)
- **Refresh interval** (auto-refresh every 30s)
- **Panel organization** (grouped by category)
- **Alert indicators** (visual warnings for critical states)

#### Trading Dashboard Panels

1. **Equity Curve** - Line chart of `trading_account_equity`
2. **Drawdown** - Line chart of `trading_drawdown_pct` (red when > 15%)
3. **Trade Count** - Stat panel showing `trades_executed_total`
4. **Win Rate** - Stat panel showing `trading_win_rate{period="24h"}`
5. **Trade Latency** - Histogram of `trading_latency_seconds`
6. **Trades by Symbol** - Bar chart grouped by symbol
7. **Trades by Action Type** - Pie chart of buy/sell/close

#### System Dashboard Panels

1. **API Request Rate** - Rate of `api_requests_total`
2. **API Latency (p50, p95, p99)** - Percentiles of `api_request_duration_seconds`
3. **API Error Rate** - Rate of requests with status_code >= 400
4. **Database Query Duration** - Histogram of `database_query_duration_seconds`
5. **Active Connections** - Gauge of `database_connections_active`
6. **Service Health** - Status indicators for each service

#### Safety Dashboard Panels

1. **Kill Switch Status** - Gauge showing `kill_switch_active` (red when 1)
2. **Circuit Breaker State** - State timeline of `circuit_breaker_state`
3. **Reconciliation Errors** - Rate of `oms_reconciliation_errors_total`
4. **Risk Metrics** - Drawdown, exposure, position size

#### ML Dashboard Panels

1. **Inference Latency** - Histogram of `model_inference_latency_seconds`
2. **Feature Extraction Time** - Histogram of `feature_extraction_duration_seconds`
3. **Training Progress** - Line chart of `training_episode_reward`
4. **Model Performance** - Accuracy, Sharpe ratio, etc.

#### Grafana Configuration

```yaml
# docker-compose.yml additions

services:
  grafana:
    container_name: "grafana"
    image: grafana/grafana:latest
    ports:
   - "3001:3000"
    environment:
   - GF_SECURITY_ADMIN_USER=admin
   - GF_SECURITY_ADMIN_PASSWORD=admin
   - GF_INSTALL_PLUGINS=
    volumes:
   - grafana_data:/var/lib/grafana
   - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
   - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards
    depends_on:
   - prometheus
    restart: unless-stopped
```

### Success Criteria

- [ ] Grafana service running in Docker Compose
- [ ] Prometheus datasource configured automatically
- [ ] All 4 dashboards created and visible in Grafana
- [ ] Dashboards display real-time metrics
- [ ] Trading dashboard shows equity, drawdown, and trade metrics
- [ ] System dashboard shows API and database metrics
- [ ] Safety dashboard shows kill switch and circuit breaker status
- [ ] ML dashboard shows inference and feature extraction metrics
- [ ] Dashboards auto-refresh every 30 seconds
- [ ] Visual indicators for critical states (e.g., kill switch active)

## Testing Strategy

### Unit Tests

- Test metrics collection in isolation
- Verify metric labels are correct
- Test histogram bucket boundaries
- Test gauge updates

### Integration Tests

- Verify `/metrics` endpoint returns valid Prometheus format
- Test metrics are scraped by Prometheus
- Verify dashboards query correct metrics
- Test alert rules trigger correctly

### Manual Verification

1. Start all services: `docker-compose up -d`
2. Execute a trade and verify metrics appear
3. Check Prometheus UI at `http://localhost:9090`
4. Check Grafana UI at `http://localhost:3001`
5. Verify all dashboards load and display data

## Rollback Plan

If issues arise:

1. Remove Prometheus and Grafana services from docker-compose.yml
2. Remove `/metrics` endpoint from API
3. Comment out metrics collection code (don't delete for future use)
4. System continues operating without observability

## Phase 1 Gate

Week 4 completion is required for Phase 1 gate:

- ✅ Prometheus metrics exposed
- ✅ Grafana dashboards operational
- ✅ Real-time monitoring functional

## Next Steps

After Week 4 completion:

- Week 5: Enhanced Transaction Costs (can proceed)
- Week 11: Enhanced Monitoring (will add more dashboards and alerting)