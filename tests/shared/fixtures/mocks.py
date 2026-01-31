"""
Mock factories for test fixtures
"""
from unittest.mock import Mock, MagicMock, AsyncMock
from typing import Dict, Any


def create_mock_mt5_terminal() -> Mock:
    """Create a mock MT5 terminal"""
    terminal = Mock()
    terminal.connect = Mock(return_value=True)
    terminal.disconnect = Mock(return_value=True)
    terminal.is_connected = Mock(return_value=True)
    terminal.get_account_info = Mock(return_value={
        "balance": 10000.0,
        "equity": 10000.0,
        "margin": 0.0,
        "free_margin": 10000.0
    })
    terminal.send_order = AsyncMock(return_value={"order_id": 12345, "status": "success"})
    return terminal


def create_mock_redis() -> Mock:
    """Create a mock Redis client"""
    redis = Mock()
    redis.get = Mock(return_value=None)
    redis.set = Mock(return_value=True)
    redis.delete = Mock(return_value=1)
    redis.exists = Mock(return_value=False)
    redis.publish = Mock(return_value=1)
    return redis


def create_mock_data_provider() -> Mock:
    """Create a mock data provider"""
    provider = Mock()
    provider.get_latest = Mock(return_value=None)
    provider.get_historical = Mock(return_value=[])
    provider.is_ready = Mock(return_value=True)
    return provider
