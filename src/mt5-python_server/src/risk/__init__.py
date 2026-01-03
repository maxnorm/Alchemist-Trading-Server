"""
Risk Management Module

Provides safety controls for live trading:
- KillSwitch: Emergency trading halt with multiple trigger mechanisms
- CircuitBreaker: Automatic trading halt based on loss/volatility/errors
- OrderManagementSystem: Order tracking with idempotency and reconciliation
"""

from .kill_switch import (
    KillSwitch,
    KillSwitchTrigger,
    FileTrigger,
    EnvironmentTrigger,
    NetworkTrigger,
    KillSwitchState
)
from .circuit_breaker import CircuitBreaker, CircuitBreakerState, CircuitBreakerConfig
from .oms import OrderManagementSystem, Order, OrderState

__all__ = [
    # Kill Switch
    'KillSwitch',
    'KillSwitchTrigger',
    'FileTrigger',
    'EnvironmentTrigger',
    'NetworkTrigger',
    'KillSwitchState',
    # Circuit Breaker
    'CircuitBreaker',
    'CircuitBreakerState',
    'CircuitBreakerConfig',
    # Order Management
    'OrderManagementSystem',
    'Order',
    'OrderState',
]
