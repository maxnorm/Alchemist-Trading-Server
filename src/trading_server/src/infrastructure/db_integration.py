"""
Database integration for MT5 server to persist accounts and connections

Uses local database connector package for connection management.
"""

from typing import Optional, Dict, Any
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Import from local database connector package
from database.core import init_db, get_engine
from utils.time_utils import print_with_datetime


def _get_db_engine():
    """Get or create database engine using centralized module"""
    # Initialize centralized database connection
    init_db()
    return get_engine()


def register_account_in_db(
    login: int,
    account_type: str,
    broker_name: Optional[str] = None,
    broker_server: Optional[str] = None,
    currency: Optional[str] = None,
    leverage: Optional[int] = None,
    account_name: Optional[str] = None,
) -> Optional[int]:
    """
    Register or update MT5 account in database
    Returns account ID if successful, None otherwise
    """
    try:
        engine = _get_db_engine()

        with engine.connect() as conn:
            # Check if account exists
            result = conn.execute(
                text("SELECT id FROM mt5_accounts WHERE account_login = :login"),
                {"login": login},
            )
            existing = result.fetchone()

            if existing:
                # Update existing account
                account_id = existing[0]
                # Preserve user_id if it exists (don't overwrite with NULL)
                # This allows accounts to be claimed by users later
                conn.execute(
                    text(
                        """
                        UPDATE mt5_accounts
                        SET account_type = :account_type,
                            broker_name = :broker_name,
                            broker_server = :broker_server,
                            account_currency = :currency,
                            account_leverage = :leverage,
                            account_name = COALESCE(:account_name, account_name),
                            is_active = TRUE,
                            last_seen_at = NOW(),
                            updated_at = NOW()
                        WHERE id = :id
                    """
                    ),
                    {
                        "id": account_id,
                        "account_type": account_type,
                        "broker_name": broker_name,
                        "broker_server": broker_server,
                        "currency": currency,
                        "leverage": leverage,
                        "account_name": account_name,
                    },
                )
                conn.commit()
                return account_id
            else:
                # Create new account
                result = conn.execute(
                    text(
                        """
                        INSERT INTO mt5_accounts
                        (account_login, account_type, broker_name, broker_server,
                         account_currency, account_leverage, account_name, is_active, last_seen_at)
                        VALUES (:login, :account_type, :broker_name, :broker_server,
                                :currency, :leverage, :account_name, TRUE, NOW())
                        RETURNING id
                    """
                    ),
                    {
                        "login": login,
                        "account_type": account_type,
                        "broker_name": broker_name,
                        "broker_server": broker_server,
                        "currency": currency,
                        "leverage": leverage,
                        "account_name": account_name,
                    },
                )
                account_id = result.scalar()
                conn.commit()
                return account_id

    except SQLAlchemyError as e:
        print_with_datetime(f"Error registering account in database: {e}")
        return None
    except Exception as e:
        print_with_datetime(f"Unexpected error registering account: {e}")
        return None


def update_account_in_db(
    login: int,
    account_type: str,
    broker_name: Optional[str] = None,
    broker_server: Optional[str] = None,
    currency: Optional[str] = None,
    leverage: Optional[int] = None,
    account_name: Optional[str] = None,
) -> Optional[int]:
    """
    Update existing MT5 account in database.
    Returns account ID if successful, None if account doesn't exist.
    Does NOT create new accounts - account must be pre-registered via API.
    """
    try:
        engine = _get_db_engine()

        with engine.connect() as conn:
            # Check if account exists
            result = conn.execute(
                text("SELECT id FROM mt5_accounts WHERE account_login = :login"),
                {"login": login},
            )
            existing = result.fetchone()

            if not existing:
                # Account doesn't exist - return None (do not create)
                return None

            # Update existing account
            account_id = existing[0]
            # Preserve user_id if it exists (don't overwrite with NULL)
            conn.execute(
                text(
                    """
                    UPDATE mt5_accounts
                    SET account_type = :account_type,
                        broker_name = :broker_name,
                        broker_server = :broker_server,
                        account_currency = :currency,
                        account_leverage = :leverage,
                        account_name = COALESCE(:account_name, account_name),
                        is_active = TRUE,
                        last_seen_at = NOW(),
                        updated_at = NOW()
                    WHERE id = :id
                """
                ),
                {
                    "id": account_id,
                    "account_type": account_type,
                    "broker_name": broker_name,
                    "broker_server": broker_server,
                    "currency": currency,
                    "leverage": leverage,
                    "account_name": account_name,
                },
            )
            conn.commit()
            return account_id

    except SQLAlchemyError as e:
        print_with_datetime(f"Error updating account in database: {e}")
        return None
    except Exception as e:
        print_with_datetime(f"Unexpected error updating account: {e}")
        return None


def log_connection(
    account_id: int,
    terminal_id: Optional[int] = None,
    ea_version: Optional[str] = None,
    connection_ip: Optional[str] = None,
) -> Optional[int]:
    """
    Log a new connection event
    Returns connection ID if successful, None otherwise
    """
    try:
        engine = _get_db_engine()

        with engine.connect() as conn:
            # Close any existing active connections for this account
            conn.execute(
                text(
                    """
                    UPDATE mt5_connections
                    SET is_connected = FALSE, disconnected_at = NOW(), disconnect_reason = 'New connection'
                    WHERE account_id = :account_id AND is_connected = TRUE
                """
                ),
                {"account_id": account_id},
            )

            # Create new connection record
            result = conn.execute(
                text(
                    """
                    INSERT INTO mt5_connections
                    (account_id, terminal_id, ea_version, connection_ip, is_connected)
                    VALUES (:account_id, :terminal_id, :ea_version, :connection_ip, TRUE)
                    RETURNING id
                """
                ),
                {
                    "account_id": account_id,
                    "terminal_id": terminal_id,
                    "ea_version": ea_version,
                    "connection_ip": connection_ip,
                },
            )
            connection_id = result.scalar()

            # Update account last_seen_at
            conn.execute(
                text("UPDATE mt5_accounts SET last_seen_at = NOW() WHERE id = :id"),
                {"id": account_id},
            )

            conn.commit()
            return connection_id

    except SQLAlchemyError as e:
        print_with_datetime(f"Error logging connection: {e}")
        return None
    except Exception as e:
        print_with_datetime(f"Unexpected error logging connection: {e}")
        return None


def update_connection_status(
    account_id: int,
    terminal_id: Optional[int] = None,
    is_connected: bool = False,
    disconnect_reason: Optional[str] = None,
) -> bool:
    """
    Update connection status (for disconnects or heartbeats)
    Returns True if successful, False otherwise
    """
    try:
        engine = _get_db_engine()

        with engine.connect() as conn:
            if is_connected:
                # Update last_seen_at (heartbeat)
                conn.execute(
                    text("UPDATE mt5_accounts SET last_seen_at = NOW() WHERE id = :id"),
                    {"id": account_id},
                )
            else:
                # Mark connection as disconnected
                if terminal_id:
                    conn.execute(
                        text(
                            """
                            UPDATE mt5_connections
                            SET is_connected = FALSE, disconnected_at = NOW(), disconnect_reason = :reason
                            WHERE account_id = :account_id AND terminal_id = :terminal_id AND is_connected = TRUE
                        """
                        ),
                        {
                            "account_id": account_id,
                            "terminal_id": terminal_id,
                            "reason": disconnect_reason or "Disconnected",
                        },
                    )
                else:
                    conn.execute(
                        text(
                            """
                            UPDATE mt5_connections
                            SET is_connected = FALSE, disconnected_at = NOW(), disconnect_reason = :reason
                            WHERE account_id = :account_id AND is_connected = TRUE
                        """
                        ),
                        {
                            "account_id": account_id,
                            "reason": disconnect_reason or "Disconnected",
                        },
                    )

            conn.commit()
            return True

    except SQLAlchemyError as e:
        print_with_datetime(f"Error updating connection status: {e}")
        return False
    except Exception as e:
        print_with_datetime(f"Unexpected error updating connection status: {e}")
        return False


def get_account_from_db(login: int) -> Optional[Dict[str, Any]]:
    """
    Get account from database by login
    Returns account dict if found, None otherwise
    """
    try:
        engine = _get_db_engine()

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM mt5_accounts WHERE account_login = :login"),
                {"login": login},
            )
            row = result.fetchone()

            if row:
                return dict(row._mapping)
            return None

    except SQLAlchemyError as e:
        print_with_datetime(f"Error getting account from database: {e}")
        return None
    except Exception as e:
        print_with_datetime(f"Unexpected error getting account: {e}")
        return None


def get_account_auth_token(login: int) -> Optional[str]:
    """
    Get auth token for account from database by login.
    Returns auth token if found, None otherwise.
    """
    try:
        engine = _get_db_engine()

        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT auth_token FROM mt5_accounts WHERE account_login = :login"
                ),
                {"login": login},
            )
            row = result.fetchone()

            if row and row[0]:
                return row[0]
            return None

    except SQLAlchemyError as e:
        print_with_datetime(f"Error getting account auth token from database: {e}")
        return None
    except Exception as e:
        print_with_datetime(f"Unexpected error getting account auth token: {e}")
        return None
