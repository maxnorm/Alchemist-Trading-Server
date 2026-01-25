"""
Prometheus metrics definitions for trading system observability

This module defines all metrics that will be collected and exposed via Prometheus.
Metrics are organized into categories:
- Trading metrics (trades, latency, equity, drawdown)
- System metrics (API requests, database queries)
- ML metrics (inference latency, feature extraction)
- Safety metrics (kill switch, circuit breaker, OMS errors)
"""

from prometheus_client import Counter, Histogram, Gauge

# Trading Metrics
trades_executed_total = Counter(
    "trading_trades_total",
    "Total trades executed",
    ["symbol", "action_type"],  # action_type: 'buy', 'sell', 'close'
)

trade_latency_seconds = Histogram(
    "trading_latency_seconds",
    "Trade execution latency in seconds",
    ["symbol"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
)

account_equity = Gauge("trading_account_equity", "Current account equity")

current_drawdown_pct = Gauge("trading_drawdown_pct", "Current drawdown percentage")

win_rate = Gauge(
    "trading_win_rate", "Win rate", ["period"]
)  # period: '24h', '7d', '30d'

# System Metrics
api_request_duration = Histogram(
    "api_request_duration_seconds",
    "API request duration",
    ["method", "endpoint", "status_code"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)

api_requests_total = Counter(
    "api_requests_total", "Total API requests", ["method", "endpoint", "status_code"]
)

database_query_duration = Histogram(
    "database_query_duration_seconds",
    "Database query duration",
    ["query_type"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0],
)

database_connections_active = Gauge(
    "database_connections_active", "Active database connections"
)

# ML Metrics
model_inference_latency = Histogram(
    "model_inference_latency_seconds",
    "Model inference latency",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

feature_extraction_duration = Histogram(
    "feature_extraction_duration_seconds",
    "Feature extraction time",
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
)

training_episode_reward = Gauge(
    "training_episode_reward", "Training episode reward", ["episode"]
)

# Safety Metrics
kill_switch_active = Gauge(
    "kill_switch_active", "Kill switch status (1=active, 0=inactive)"
)

circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state",
    ["state"],  # state: 'closed', 'open', 'half_open'
)

oms_reconciliation_errors = Counter(
    "oms_reconciliation_errors_total", "OMS reconciliation errors"
)

# Data Quality Metrics
quarantine_ticks_total = Counter(
    "data_quarantine_ticks_total",
    "Total ticks quarantined",
    ["symbol", "rejection_category"],
)

# Quality Gate Metrics
quality_gate_ticks_processed_total = Counter(
    "quality_gate_ticks_processed_total",
    "Total ticks processed by quality gate",
    ["symbol"],  # Empty string for aggregate
)

quality_gate_ticks_accepted_total = Counter(
    "quality_gate_ticks_accepted_total",
    "Total ticks accepted by quality gate",
    ["symbol"],
)

quality_gate_outliers_rejected_total = Counter(
    "quality_gate_outliers_rejected_total",
    "Total ticks rejected as outliers",
    ["symbol"],
)

quality_gate_duplicates_rejected_total = Counter(
    "quality_gate_duplicates_rejected_total",
    "Total ticks rejected as duplicates",
    ["symbol"],
)

quality_gate_stale_rejected_total = Counter(
    "quality_gate_stale_rejected_total",
    "Total ticks rejected as stale",
    ["symbol"],
)

quality_gate_missing_data_rejected_total = Counter(
    "quality_gate_missing_data_rejected_total",
    "Total ticks rejected due to missing data",
    ["symbol"],
)

quality_gate_stale_accepted_price_change_total = Counter(
    "quality_gate_stale_accepted_price_change_total",
    "Total stale ticks accepted due to price change",
    ["symbol"],
)

# Rate metrics (calculated from counters, updated periodically)
quality_gate_acceptance_rate = Gauge(
    "quality_gate_acceptance_rate",
    "Quality gate acceptance rate (0-1)",
    ["symbol"],
)

quality_gate_rejection_rate = Gauge(
    "quality_gate_rejection_rate",
    "Quality gate rejection rate (0-1)",
    ["symbol"],
)

# Drift Detection Metrics
data_drift_psi_score = Gauge(
    "data_drift_psi_score",
    "Population Stability Index score for feature drift",
    ["feature_name", "symbol"],
)

data_drift_ks_statistic = Gauge(
    "data_drift_ks_statistic",
    "Kolmogorov-Smirnov test statistic for feature drift",
    ["feature_name", "symbol"],
)

data_drift_detections_total = Counter(
    "data_drift_detections_total",
    "Total drift detections",
    ["feature_name", "symbol", "severity"],  # severity: 'none', 'minor', 'major'
)

data_drift_alerts_total = Counter(
    "data_drift_alerts_total",
    "Total drift alerts triggered",
    ["feature_name", "symbol", "severity"],
)

# Lineage Tracking Metrics
lineage_runs_total = Counter(
    "lineage_runs_total",
    "Total lineage runs",
    ["job_name", "namespace", "status"],  # status: 'RUNNING', 'COMPLETE', 'FAILED'
)

lineage_runs_duration_seconds = Histogram(
    "lineage_runs_duration_seconds",
    "Lineage run duration",
    ["job_name", "namespace"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0],
)

# Data Collection Pipeline Metrics
data_collection_tasks_total = Counter(
    "data_collection_tasks_total",
    "Total data collection tasks executed",
    [
        "task_type",
        "source",
        "status",
    ],  # task_type: 'mt5', 'news', 'economic', status: 'success', 'failed'
)

data_collection_records_collected = Counter(
    "data_collection_records_collected_total",
    "Total records collected by data collection tasks",
    ["task_type", "source"],  # task_type: 'tick', 'bar', 'news', 'economic'
)

data_collection_duration_seconds = Histogram(
    "data_collection_duration_seconds",
    "Data collection task duration",
    ["task_type", "source"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0],
)

data_collection_errors_total = Counter(
    "data_collection_errors_total",
    "Total data collection errors",
    [
        "task_type",
        "source",
        "error_type",
    ],  # error_type: 'connection', 'validation', 'database', 'other'
)

data_collection_last_success_time = Gauge(
    "data_collection_last_success_time",
    "Timestamp of last successful data collection",
    ["task_type", "source"],
)

data_collection_backfill_progress = Gauge(
    "data_collection_backfill_progress",
    "Backfill progress percentage (0-100)",
    ["connector_type", "symbol"],
)

data_collection_backfill_records = Gauge(
    "data_collection_backfill_records",
    "Number of records collected in current backfill",
    ["connector_type", "symbol"],
)

lineage_runs_failed_total = Counter(
    "lineage_runs_failed_total",
    "Total failed lineage runs",
    ["job_name", "namespace"],
)

lineage_datasets_total = Gauge(
    "lineage_datasets_total",
    "Total datasets tracked",
    ["namespace"],
)

lineage_events_emitted_total = Counter(
    "lineage_events_emitted_total",
    "Total lineage events emitted",
    ["event_type"],  # event_type: 'START', 'COMPLETE', 'FAIL', 'DATASET'
)

# Phase 1: Additional Data Quality Metrics
data_freshness_seconds = Gauge(
    "data_freshness_seconds",
    "Time since last data received in seconds",
    ["source", "symbol"],  # source: 'mt5', 'news', 'economic', etc.
)

data_volume_total = Counter(
    "data_volume_total",
    "Total data records collected",
    ["source", "symbol"],
)

data_quality_score = Gauge(
    "data_quality_score",
    "Data quality score (0-1)",
    ["source", "symbol"],
)

data_quarantine_rate = Gauge(
    "data_quarantine_rate",
    "Quarantine rate percentage (0-1)",
    ["source", "symbol"],
)

# Gap Detection Metrics
data_gaps_detected_total = Counter(
    "data_gaps_detected_total",
    "Total data gaps detected",
    ["data_type", "symbol"],  # data_type: 'tick', 'bar', 'news', 'economic'
)

data_gap_minutes = Gauge(
    "data_gap_minutes",
    "Current data gap duration in minutes",
    ["symbol", "data_type"],  # data_type: 'tick', 'bar', 'news', 'economic'
)

gap_fill_attempts_total = Counter(
    "gap_fill_attempts_total",
    "Total gap fill attempts",
    ["data_type", "strategy"],  # strategy: 're_query', 'interpolate', 'forward_fill'
)

gap_fill_success_total = Counter(
    "gap_fill_success_total",
    "Total successful gap fills",
    ["data_type", "strategy"],
)

gap_fill_success_rate = Gauge(
    "gap_fill_success_rate",
    "Gap fill success rate (0-1)",
    ["data_type", "strategy"],
)

# Backfill Metrics (aliases for dashboard compatibility)
backfill_progress_percent = Gauge(
    "backfill_progress_percent",
    "Backfill progress percentage (0-100)",
    ["symbol", "data_type"],
)

backfill_records_processed_total = Counter(
    "backfill_records_processed_total",
    "Total records processed during backfill",
    ["symbol", "data_type"],
)

# Clock Synchronization Metrics
clock_drift_seconds = Gauge(
    "clock_drift_seconds",
    "Clock drift in seconds",
    ["source"],  # source: "server_ntp" or "mt5_broker"
)

negative_latency_rate = Gauge(
    "negative_latency_rate",
    "Percentage of ticks with negative latency (0.0-1.0)",
)

clock_sync_status = Gauge(
    "clock_sync_status",
    "Clock synchronization status (1=healthy, 0=unhealthy)",
    ["source"],  # source: "server_ntp" or "mt5_broker"
)
