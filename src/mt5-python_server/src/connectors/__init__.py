"""Data source connector interface for modular data sources"""
from .base import IDataSourceConnector, ConnectorConfig
from .mt5_tick_connector import MT5TickConnector

__all__ = [
    "IDataSourceConnector",
    "ConnectorConfig",
    "MT5TickConnector",
]
