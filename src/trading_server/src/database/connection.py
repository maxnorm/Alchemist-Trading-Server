"""
Connection management for Trading Server (raw SQL access).

Provides connection context managers and helper functions for executing
raw SQL queries with automatic transaction handling.
"""

import logging
from contextlib import contextmanager
from typing import List, Dict, Tuple, Optional, Any
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .core import get_engine, init_db

logger = logging.getLogger(__name__)


@contextmanager
def execute_query():
    """
    Context manager for executing queries with automatic transaction handling.

    Automatically commits on success, rolls back on error.
    Connections are automatically returned to the pool.

    Usage:
        with execute_query() as conn:
            result = conn.execute(text("SELECT * FROM table WHERE id = :id"), {"id": 1})

    Yields:
        SQLAlchemy Connection instance
    """
    # Ensure engine is initialized
    init_db()
    engine = get_engine()

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            yield conn
            trans.commit()
        except Exception as e:
            trans.rollback()
            logger.error(f"Transaction rolled back due to error: {e}")
            raise


def execute_with_result(
    query: str, params: Optional[Dict[str, Any]] = None
) -> List[Tuple]:
    """
    Execute query and return all results.

    Args:
        query: SQL query string with named parameters (:param_name)
        params: Dictionary of parameters (optional)

    Returns:
        List of result tuples

    Raises:
        SQLAlchemyError: If query execution fails
    """
    try:
        with execute_query() as conn:
            result = conn.execute(text(query), params or {})
            return result.fetchall()
    except SQLAlchemyError as e:
        logger.error(f"Error executing query: {e}")
        raise


def execute_one(query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Tuple]:
    """
    Execute query and return single result.

    Args:
        query: SQL query string with named parameters (:param_name)
        params: Dictionary of parameters (optional)

    Returns:
        Single result tuple or None if no results

    Raises:
        SQLAlchemyError: If query execution fails
    """
    try:
        with execute_query() as conn:
            result = conn.execute(text(query), params or {})
            return result.fetchone()
    except SQLAlchemyError as e:
        logger.error(f"Error executing query: {e}")
        raise


def execute_transaction(queries_with_params: List[Tuple[str, Dict[str, Any]]]) -> None:
    """
    Execute multiple queries in a single transaction.

    Args:
        queries_with_params: List of (query, params) tuples

    Raises:
        SQLAlchemyError: If any query execution fails (entire transaction rolled back)
    """
    try:
        with execute_query() as conn:
            for query, params in queries_with_params:
                conn.execute(text(query), params or {})
    except SQLAlchemyError as e:
        logger.error(f"Error executing transaction: {e}")
        raise
