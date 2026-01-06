"""
Monitoring package for Prometheus metrics
"""

from .metrics import (
    # Trading Metrics
    trades_executed_total,
    trade_latency_seconds,
    account_equity,
    current_drawdown_pct,
    win_rate,
    # System Metrics
    api_request_duration,
    api_requests_total,
    database_query_duration,
    database_connections_active,
    # ML Metrics
    model_inference_latency,
    feature_extraction_duration,
    training_episode_reward,
    # Safety Metrics
    kill_switch_active,
    circuit_breaker_state,
    oms_reconciliation_errors,
    # Data Quality Metrics
    quarantine_ticks_total,
    quarantine_rate,
)

__all__ = [
    "trades_executed_total",
    "trade_latency_seconds",
    "account_equity",
    "current_drawdown_pct",
    "win_rate",
    "api_request_duration",
    "api_requests_total",
    "database_query_duration",
    "database_connections_active",
    "model_inference_latency",
    "feature_extraction_duration",
    "training_episode_reward",
    "kill_switch_active",
    "circuit_breaker_state",
    "oms_reconciliation_errors",
    "quarantine_ticks_total",
    "quarantine_rate",
]
