"""
Custom exception classes for the trading system
Provides consistent error handling across the application
"""


class TradingSystemError(Exception):
    """Base exception for trading system"""

    pass


class DataValidationError(TradingSystemError):
    """Data validation failed"""

    pass


class ModelError(TradingSystemError):
    """Model-related error"""

    pass


class RiskManagementError(TradingSystemError):
    """Risk management constraint violation"""

    pass


class DatabaseError(TradingSystemError):
    """Database operation error"""

    pass


class ConnectionError(TradingSystemError):
    """Connection error (MT5, database, etc.)"""

    pass


class FeatureEngineeringError(TradingSystemError):
    """Feature engineering error"""

    pass


class StateBuildingError(TradingSystemError):
    """State building error"""

    pass


class TradingExecutionError(TradingSystemError):
    """Trading execution error"""

    pass
