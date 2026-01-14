"""
Centralized database access module for API and Trading Server services.

This module provides unified database connection management, supporting both
session-based (API) and connection-based (Trading Server) access patterns.
"""

from .core import init_db, get_engine, close_db, check_db_health
from .session import get_session, SessionLocal
from .connection import execute_query, execute_with_result, execute_one, execute_transaction

__all__ = [
    # Core engine management
    "init_db",
    "get_engine",
    "close_db",
    "check_db_health",
    # Session management (for API service)
    "get_session",
    "SessionLocal",
    # Connection management (for Trading Server)
    "execute_query",
    "execute_with_result",
    "execute_one",
    "execute_transaction",
]
