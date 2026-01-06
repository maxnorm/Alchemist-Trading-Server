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
    ['method', 'endpoint', 'status_code'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

api_requests_total = Counter(
    'api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status_code']
)

database_query_duration = Histogram(
    'database_query_duration_seconds',
    'Database query duration',
    ['query_type'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
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

# Data Quality Metrics
quarantine_ticks_total = Counter(
    'data_quarantine_ticks_total',
    'Total ticks quarantined',
    ['symbol', 'rejection_category']
)

quarantine_rate = Gauge(
    'data_quarantine_rate',
    'Quarantine rate percentage',
    ['symbol']
)