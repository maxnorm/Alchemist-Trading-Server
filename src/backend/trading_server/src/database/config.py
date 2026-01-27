"""
Unified database configuration management.

Reads database connection settings from environment variables, supporting
both DATABASE_URL and individual DB_* variables.
"""

import os


def get_database_url() -> str:
    """
    Get database connection URL from environment variables.

    Supports two formats:
    1. DATABASE_URL - Full connection string (takes precedence)
    2. Individual DB_* variables - Constructed from components

    Returns:
        PostgreSQL connection URL string

    Environment Variables:
        DATABASE_URL: Full connection string (optional)
        DB_HOST: Database host
        DB_PORT: Database port
        DB_USER: Database user
        DB_PASSWORD: Database password
        DB_NAME: Database name
    """
    # Check for full DATABASE_URL first
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    # Construct from individual components
    db_host = os.getenv("DB_HOST") or "localhost"
    db_port_str = os.getenv("DB_PORT") or "5432"
    db_port = int(db_port_str)
    db_user = os.getenv("DB_USER") or "postgres"
    db_password = os.getenv("DB_PASSWORD") or ""
    db_name = os.getenv("DB_NAME") or "trading_db"

    return (
        f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    )


def get_pool_config() -> dict:
    """
    Get connection pool configuration from environment variables.

    Returns:
        Dictionary with pool configuration parameters
    """
    return {
        "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
        "pool_pre_ping": os.getenv("DB_POOL_PRE_PING", "true").lower() == "true",
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "3600")),
    }


def get_retry_config() -> dict:
    """
    Get retry configuration from environment variables.

    Returns:
        Dictionary with retry configuration parameters
    """
    return {
        "max_retries": int(os.getenv("DB_MAX_RETRIES", "5")),
        "retry_delay": float(os.getenv("DB_RETRY_DELAY", "2.0")),
    }
