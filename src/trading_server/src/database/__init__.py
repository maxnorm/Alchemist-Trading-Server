"""
Database package for Trading Server.

Provides:
- Connection pool management (core.py, connection.py, config.py)
- Domain-specific database operations (database.py)
"""

from .core import init_db, get_engine, close_db, check_db_health
from .connection import (
    execute_query,
    execute_with_result,
    execute_one,
    execute_transaction,
)
from .database import Database

__all__ = [
    # Infrastructure layer
    "init_db",
    "get_engine",
    "close_db",
    "check_db_health",
    "execute_query",
    "execute_with_result",
    "execute_one",
    "execute_transaction",
    # Domain layer
    "Database",
]
