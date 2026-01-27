"""
MT5 Accounts service layer
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime
import secrets
import os
import sys
import logging

# Initialize logger early
logger = logging.getLogger(__name__)

# Add trading_server to path for CredentialManager import
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "../../../../backend/trading_server/src")
)

from models.mt5_accounts import (  # noqa: E402
    MT5Account,
    AccountModelAssignment,
    MT5Connection,
)

try:
    from infrastructure.security.credential_manager import CredentialManager

    CREDENTIAL_MANAGER_AVAILABLE = True
except ImportError:
    CREDENTIAL_MANAGER_AVAILABLE = False
    logger.warning("CredentialManager not available - password encryption disabled")
from schemas.mt5_accounts import (  # noqa: E402
    MT5AccountResponse,
    MT5AccountCreateRequest,
    MT5AccountUpdateRequest,
    MT5ConnectionStatusResponse,
    MT5ConnectionHistoryItem,
    ModelAssignmentResponse,
    ConnectionStatus,
)

try:
    from websocket import channels as ws_channels

    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False
    logger.warning("WebSocket channels not available")


def _generate_auth_token() -> str:
    """Generate a high-entropy auth token for MT5 account authentication"""
    return secrets.token_urlsafe(32)


def get_all_accounts(
    db: Session,
    connected_only: bool = False,
    account_type: Optional[str] = None,
    user_id: Optional[str] = None,
) -> List[MT5AccountResponse]:
    """Get all MT5 accounts with optional filtering"""
    query = db.query(MT5Account)

    if connected_only:
        # Join with connections to filter by is_connected
        query = query.join(MT5Connection).filter(MT5Connection.is_connected.is_(True))

    if account_type:
        query = query.filter(MT5Account.account_type == account_type)

    if user_id:
        # Filter by user ownership
        query = query.filter(MT5Account.user_id == user_id)

    accounts = (
        query.filter(MT5Account.is_active.is_(True))
        .order_by(MT5Account.created_at.desc())
        .all()
    )

    # Convert to response models with computed fields
    result = []
    for account in accounts:
        account_dict = _account_to_dict(account, db)
        result.append(MT5AccountResponse(**account_dict))

    return result


def get_account_by_id(db: Session, account_id: int) -> Optional[MT5AccountResponse]:
    """Get MT5 account by ID"""
    account = (
        db.query(MT5Account)
        .filter(MT5Account.id == account_id, MT5Account.is_active.is_(True))
        .first()
    )

    if not account:
        return None

    account_dict = _account_to_dict(account, db)
    return MT5AccountResponse(**account_dict)


def get_account_by_login(db: Session, login: int) -> Optional[MT5Account]:
    """Get MT5 account by login (returns ORM model)"""
    return db.query(MT5Account).filter(MT5Account.account_login == login).first()


def verify_account_ownership(db: Session, account_id: int, user_id: str) -> bool:
    """Verify that user owns the account"""
    account = (
        db.query(MT5Account)
        .filter(
            MT5Account.id == account_id,
            MT5Account.user_id == user_id,
            MT5Account.is_active.is_(True),
        )
        .first()
    )
    return account is not None


def create_account_for_user(
    db: Session,
    request: MT5AccountCreateRequest,
    user_id: str,
    created_by: Optional[str] = None,
) -> MT5AccountResponse:
    """Create a new MT5 account with user association"""
    # Encrypt password if provided
    encrypted_password = None
    if hasattr(request, "mt5_password") and request.mt5_password:
        if not CREDENTIAL_MANAGER_AVAILABLE:
            raise ValueError(
                "CredentialManager not available - cannot encrypt password"
            )
        try:
            credential_manager = CredentialManager()
            encrypted_password = credential_manager.encrypt_password(
                request.mt5_password
            )
        except Exception as e:
            logger.error(f"Failed to encrypt password: {e}", exc_info=True)
            raise ValueError(f"Failed to encrypt password: {e}")

    # Check if account already exists
    existing = get_account_by_login(db, request.account_login)
    if existing:
        # Update existing account
        existing.account_type = (
            request.account_type.value
            if hasattr(request.account_type, "value")
            else request.account_type
        )
        existing.broker_name = request.broker_name
        existing.broker_server = request.broker_server
        existing.account_currency = request.account_currency
        existing.account_leverage = request.account_leverage
        existing.is_active = True

        # Update Python API credentials if provided
        if encrypted_password:
            existing.mt5_password_encrypted = encrypted_password
        if hasattr(request, "mt5_server") and request.mt5_server:
            existing.mt5_server = request.mt5_server

        # Link to user if not already linked (allows claiming)
        if not existing.user_id:
            existing.user_id = user_id
            existing.created_by = created_by or user_id

        # Legacy: Ensure existing accounts have an auth token (for backward compatibility)
        if not existing.auth_token:
            existing.auth_token = _generate_auth_token()

        db.commit()
        db.refresh(existing)
        account_dict = _account_to_dict(existing, db)
        return MT5AccountResponse(**account_dict)

    # Create new account
    account = MT5Account(
        account_login=request.account_login,
        account_type=(
            request.account_type.value
            if hasattr(request.account_type, "value")
            else request.account_type
        ),
        broker_name=request.broker_name,
        broker_server=request.broker_server,
        account_currency=request.account_currency,
        account_leverage=request.account_leverage,
        account_name=request.account_name,
        user_id=user_id,
        created_by=created_by or user_id,
        is_active=True,
        mt5_password_encrypted=encrypted_password,
        mt5_server=request.mt5_server if hasattr(request, "mt5_server") else None,
        auth_token=_generate_auth_token(),  # Legacy field, kept for backward compatibility
    )

    db.add(account)
    db.commit()
    db.refresh(account)

    # Log connection if provided
    if request.connection_ip or request.terminal_id:
        log_connection(
            db,
            account.id,
            terminal_id=request.terminal_id,
            ea_version=request.ea_version,
            connection_ip=request.connection_ip,
        )

    account_dict = _account_to_dict(account, db)
    return MT5AccountResponse(**account_dict)


def create_account(db: Session, request: MT5AccountCreateRequest) -> MT5AccountResponse:
    """Create a new MT5 account"""
    # Encrypt password if provided
    encrypted_password = None
    if hasattr(request, "mt5_password") and request.mt5_password:
        if not CREDENTIAL_MANAGER_AVAILABLE:
            raise ValueError(
                "CredentialManager not available - cannot encrypt password"
            )
        try:
            credential_manager = CredentialManager()
            encrypted_password = credential_manager.encrypt_password(
                request.mt5_password
            )
        except Exception as e:
            logger.error(f"Failed to encrypt password: {e}", exc_info=True)
            raise ValueError(f"Failed to encrypt password: {e}")

    # Check if account already exists
    existing = get_account_by_login(db, request.account_login)
    if existing:
        # Update existing account
        existing.account_type = (
            request.account_type.value
            if hasattr(request.account_type, "value")
            else request.account_type
        )
        existing.broker_name = request.broker_name
        existing.broker_server = request.broker_server
        existing.account_currency = request.account_currency
        existing.account_leverage = request.account_leverage
        existing.is_active = True

        # Update Python API credentials if provided
        if encrypted_password:
            existing.mt5_password_encrypted = encrypted_password
        if hasattr(request, "mt5_server") and request.mt5_server:
            existing.mt5_server = request.mt5_server

        # Legacy: Ensure existing accounts have an auth token (for backward compatibility)
        if not existing.auth_token:
            existing.auth_token = _generate_auth_token()
        db.commit()
        db.refresh(existing)
        account_dict = _account_to_dict(existing, db)
        return MT5AccountResponse(**account_dict)

    # Create new account
    account = MT5Account(
        account_login=request.account_login,
        account_type=(
            request.account_type.value
            if hasattr(request.account_type, "value")
            else request.account_type
        ),
        broker_name=request.broker_name,
        broker_server=request.broker_server,
        account_currency=request.account_currency,
        account_leverage=request.account_leverage,
        account_name=request.account_name,
        is_active=True,
        mt5_password_encrypted=encrypted_password,
        mt5_server=request.mt5_server if hasattr(request, "mt5_server") else None,
        auth_token=_generate_auth_token(),  # Legacy field, kept for backward compatibility
    )

    db.add(account)
    db.commit()
    db.refresh(account)

    # Log connection if provided
    if request.connection_ip or request.terminal_id:
        log_connection(
            db,
            account.id,
            terminal_id=request.terminal_id,
            ea_version=request.ea_version,
            connection_ip=request.connection_ip,
        )

    account_dict = _account_to_dict(account, db)
    return MT5AccountResponse(**account_dict)


def update_account(
    db: Session, account_id: int, request: MT5AccountUpdateRequest
) -> Optional[MT5AccountResponse]:
    """Update MT5 account settings"""
    account = (
        db.query(MT5Account)
        .filter(MT5Account.id == account_id, MT5Account.is_active.is_(True))
        .first()
    )

    if not account:
        return None

    if request.account_name is not None:
        account.account_name = request.account_name

    db.commit()
    db.refresh(account)

    account_dict = _account_to_dict(account, db)
    return MT5AccountResponse(**account_dict)


def delete_account(db: Session, account_id: int) -> bool:
    """Soft delete MT5 account (set is_active=False)"""
    account = db.query(MT5Account).filter(MT5Account.id == account_id).first()

    if not account:
        return False

    account.is_active = False
    db.commit()

    # Broadcast account deletion
    if WS_AVAILABLE:
        try:
            import asyncio

            asyncio.create_task(
                ws_channels.broadcast_account_disconnected(
                    account_id, "Account deleted"
                )
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast account deletion: {e}")

    return True


def get_connection_status(
    db: Session, account_id: int
) -> Optional[MT5ConnectionStatusResponse]:
    """Get current connection status for an account"""
    account = db.query(MT5Account).filter(MT5Account.id == account_id).first()

    if not account:
        return None

    # Get latest connection
    connection = (
        db.query(MT5Connection)
        .filter(MT5Connection.account_id == account_id)
        .order_by(MT5Connection.connected_at.desc())
        .first()
    )

    status = ConnectionStatus.DISCONNECTED
    if connection and connection.is_connected:
        status = ConnectionStatus.CONNECTED

    return MT5ConnectionStatusResponse(
        account_id=account_id,
        is_connected=connection.is_connected if connection else False,
        connection_status=status,
        connected_at=connection.connected_at if connection else None,
        last_seen_at=account.last_seen_at,
        terminal_id=connection.terminal_id if connection else None,
        connection_ip=connection.connection_ip if connection else None,
        ea_version=connection.ea_version if connection else None,
    )


def get_connection_history(
    db: Session, account_id: int, limit: int = 50
) -> List[MT5ConnectionHistoryItem]:
    """Get connection history for an account"""
    connections = (
        db.query(MT5Connection)
        .filter(MT5Connection.account_id == account_id)
        .order_by(MT5Connection.connected_at.desc())
        .limit(limit)
        .all()
    )

    return [
        MT5ConnectionHistoryItem(
            **{
                "id": c.id,
                "connected_at": c.connected_at,
                "disconnected_at": c.disconnected_at,
                "disconnect_reason": c.disconnect_reason,
                "connection_ip": c.connection_ip,
                "ea_version": c.ea_version,
                "terminal_id": c.terminal_id,
            }
        )
        for c in connections
    ]


def assign_model_to_account(
    db: Session,
    account_id: int,
    model_id: int,
    trading_mode: str = "live",
    notes: Optional[str] = None,
) -> Optional[ModelAssignmentResponse]:
    """Assign a model to an MT5 account"""
    # Verify account exists
    account = (
        db.query(MT5Account)
        .filter(MT5Account.id == account_id, MT5Account.is_active.is_(True))
        .first()
    )
    if not account:
        return None

    # Verify model exists and get stage
    result = db.execute(
        text("SELECT id, version, stage FROM models WHERE id = :id"), {"id": model_id}
    )
    model_row = result.fetchone()
    if not model_row:
        return None

    model_version = model_row[1] if len(model_row) > 1 else None
    model_stage = model_row[2] if len(model_row) > 2 else None

    # Validate assignment based on account type and trading mode
    if trading_mode == "live":
        # For live trading, account must be live type
        if account.account_type != "live":
            raise ValueError(
                f"Cannot assign model to account {account_id}: "
                f"Account must be type 'live' for live trading. "
                f"Current account type is '{account.account_type}'."
            )

        # Model must be in production stage (or paper for testing)
        if model_stage not in ("production", "paper"):
            raise ValueError(
                f"Cannot assign model {model_id} to live account: "
                f"Model must be in 'production' or 'paper' stage for live trading. "
                f"Current model stage is '{model_stage}'. "
                f"Promote the model to production first."
            )
    elif trading_mode == "paper":
        # For paper trading, account should be demo type (but allow live for testing)
        if account.account_type == "live":
            logger.warning(
                f"Assigning model to live account {account_id} for paper trading. "
                "This is unusual - typically paper trading uses demo accounts."
            )

    # Deactivate any existing active assignment
    db.execute(
        text("""
            UPDATE account_model_assignments
            SET is_active = FALSE, deactivated_at = NOW()
            WHERE account_id = :account_id AND is_active = TRUE
        """),
        {"account_id": account_id},
    )

    # Create new assignment
    assignment = AccountModelAssignment(
        account_id=account_id,
        model_id=model_id,
        trading_mode=trading_mode,
        is_active=True,
        notes=notes,
    )

    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    # Publish model assignment event to Redis for Trading Server
    try:
        from infrastructure.messaging.experiment_publisher import ExperimentPublisher

        _ = ExperimentPublisher.get_instance()  # Publisher for future use
        # Use a different channel for model assignments
        # We'll extend ExperimentPublisher or create a new publisher
        # For now, we'll publish to a model assignment channel
        try:
            import redis
            import json
            from datetime import datetime

            redis_host = os.getenv("REDIS_HOST", "redis")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_db = int(os.getenv("REDIS_DB", "0"))

            redis_client = redis.Redis(
                host=redis_host, port=redis_port, db=redis_db, decode_responses=True
            )

            payload = {
                "event_type": "model_assignment",
                "account_id": account_id,
                "account_login": account.account_login,
                "model_id": model_id,
                "trading_mode": trading_mode,
                "timestamp": datetime.utcnow().isoformat(),
            }

            redis_client.publish("model_assignments", json.dumps(payload))
            logger.info(
                f"Published model assignment event to Redis: account_id={account_id}, model_id={model_id}"
            )
        except Exception as e:
            logger.warning(f"Failed to publish model assignment to Redis: {e}")
    except Exception as e:
        logger.warning(f"Failed to import Redis publisher: {e}")

    # Broadcast assignment change via WebSocket
    if WS_AVAILABLE:
        try:
            import asyncio

            asyncio.create_task(
                ws_channels.broadcast_model_assigned(
                    account_id, model_id, model_version
                )
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast assignment: {e}")

    return ModelAssignmentResponse(
        id=assignment.id,
        account_id=assignment.account_id,
        model_id=assignment.model_id,
        model_version=model_version,
        trading_mode=assignment.trading_mode,
        is_active=assignment.is_active,
        assigned_at=assignment.assigned_at,
        assigned_by=assignment.assigned_by,
        notes=assignment.notes,
    )


def unassign_model_from_account(db: Session, account_id: int) -> bool:
    """Unassign model from account"""
    assignment = (
        db.query(AccountModelAssignment)
        .filter(
            AccountModelAssignment.account_id == account_id,
            AccountModelAssignment.is_active.is_(True),
        )
        .first()
    )

    if not assignment:
        return False

    assignment.is_active = False
    assignment.deactivated_at = datetime.utcnow()
    db.commit()

    # Broadcast unassignment
    if WS_AVAILABLE:
        try:
            import asyncio

            asyncio.create_task(ws_channels.broadcast_model_unassigned(account_id))
        except Exception as e:
            logger.warning(f"Failed to broadcast unassignment: {e}")

    return True


def get_current_assignment(
    db: Session, account_id: int
) -> Optional[ModelAssignmentResponse]:
    """Get current active model assignment for account"""
    assignment = (
        db.query(AccountModelAssignment)
        .filter(
            AccountModelAssignment.account_id == account_id,
            AccountModelAssignment.is_active.is_(True),
        )
        .first()
    )

    if not assignment:
        return None

    # Get model version
    result = db.execute(
        text("SELECT version FROM models WHERE id = :id"), {"id": assignment.model_id}
    )
    model_row = result.fetchone()
    model_version = model_row[0] if model_row else None

    return ModelAssignmentResponse(
        id=assignment.id,
        account_id=assignment.account_id,
        model_id=assignment.model_id,
        model_version=model_version,
        trading_mode=assignment.trading_mode,
        is_active=assignment.is_active,
        assigned_at=assignment.assigned_at,
        assigned_by=assignment.assigned_by,
        notes=assignment.notes,
    )


def regenerate_account_token(
    db: Session, account_id: int, user_id: str
) -> Optional[str]:
    """Regenerate auth token for an account (requires ownership verification)"""
    # Verify ownership
    if not verify_account_ownership(db, account_id, user_id):
        return None

    account = db.query(MT5Account).filter(MT5Account.id == account_id).first()
    if not account:
        return None

    # Generate new token
    account.auth_token = _generate_auth_token()
    db.commit()
    db.refresh(account)

    return account.auth_token


def pause_trading(
    db: Session, account_id: int
) -> Optional[MT5ConnectionStatusResponse]:
    """Pause trading on an account (mark connection as paused)"""
    # This is a placeholder - actual implementation would depend on trading control logic
    # For now, we'll just return the connection status
    return get_connection_status(db, account_id)


def resume_trading(
    db: Session, account_id: int
) -> Optional[MT5ConnectionStatusResponse]:
    """Resume trading on an account"""
    # This is a placeholder - actual implementation would depend on trading control logic
    return get_connection_status(db, account_id)


def get_connected_accounts(db: Session) -> List[MT5AccountResponse]:
    """Get all currently connected accounts"""
    return get_all_accounts(db, connected_only=True)


def log_connection(
    db: Session,
    account_id: int,
    terminal_id: Optional[int] = None,
    ea_version: Optional[str] = None,
    connection_ip: Optional[str] = None,
) -> MT5Connection:
    """Log a new connection event"""
    # Close any existing active connections for this account
    db.execute(
        text("""
            UPDATE mt5_connections
            SET is_connected = FALSE, disconnected_at = NOW(), disconnect_reason = 'New connection'
            WHERE account_id = :account_id AND is_connected = TRUE
        """),
        {"account_id": account_id},
    )

    # Create new connection record
    connection = MT5Connection(
        account_id=account_id,
        terminal_id=terminal_id,
        ea_version=ea_version,
        connection_ip=connection_ip,
        is_connected=True,
    )

    db.add(connection)
    db.commit()
    db.refresh(connection)

    # Update account last_seen_at
    db.execute(
        text("UPDATE mt5_accounts SET last_seen_at = NOW() WHERE id = :id"),
        {"id": account_id},
    )
    db.commit()

    # Broadcast connection event
    if WS_AVAILABLE:
        try:
            import asyncio

            asyncio.create_task(
                ws_channels.broadcast_account_connected(account_id, terminal_id)
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast connection: {e}")

    return connection


def update_connection_status(
    db: Session,
    account_id: int,
    terminal_id: Optional[int] = None,
    is_connected: bool = False,
    disconnect_reason: Optional[str] = None,
) -> None:
    """Update connection status (for disconnects)"""
    if is_connected:
        # Update last_seen_at
        db.execute(
            text("UPDATE mt5_accounts SET last_seen_at = NOW() WHERE id = :id"),
            {"id": account_id},
        )
    else:
        # Mark connection as disconnected
        query = text("""
            UPDATE mt5_connections
            SET is_connected = FALSE, disconnected_at = NOW(), disconnect_reason = :reason
            WHERE account_id = :account_id AND is_connected = TRUE
        """)
        params = {
            "account_id": account_id,
            "reason": disconnect_reason or "Disconnected",
        }

        if terminal_id:
            query = text("""
                UPDATE mt5_connections
                SET is_connected = FALSE, disconnected_at = NOW(), disconnect_reason = :reason
                WHERE account_id = :account_id AND terminal_id = :terminal_id AND is_connected = TRUE
            """)
            params["terminal_id"] = terminal_id

        db.execute(query, params)

        # Broadcast disconnection
        if WS_AVAILABLE:
            try:
                import asyncio

                asyncio.create_task(
                    ws_channels.broadcast_account_disconnected(
                        account_id, disconnect_reason
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to broadcast disconnection: {e}")

    db.commit()


def _account_to_dict(account: MT5Account, db: Session) -> dict:
    """Convert account ORM model to dict with computed fields"""
    # Get connection status
    connection = (
        db.query(MT5Connection)
        .filter(MT5Connection.account_id == account.id)
        .order_by(MT5Connection.connected_at.desc())
        .first()
    )

    connection_status = ConnectionStatus.DISCONNECTED
    if connection and connection.is_connected:
        connection_status = ConnectionStatus.CONNECTED

    # Get current model assignment
    assignment = (
        db.query(AccountModelAssignment)
        .filter(
            AccountModelAssignment.account_id == account.id,
            AccountModelAssignment.is_active.is_(True),
        )
        .first()
    )

    current_model_id = None
    current_model_version = None
    if assignment:
        current_model_id = assignment.model_id
        # Get model version
        result = db.execute(
            text("SELECT version FROM models WHERE id = :id"),
            {"id": assignment.model_id},
        )
        model_row = result.fetchone()
        current_model_version = model_row[0] if model_row else None

    return {
        "id": account.id,
        "account_login": account.account_login,
        "account_type": account.account_type,
        "broker_name": account.broker_name,
        "broker_server": account.broker_server,
        "account_currency": account.account_currency,
        "account_leverage": account.account_leverage,
        "account_name": account.account_name,
        "balance": float(account.balance) if account.balance is not None else None,
        "equity": float(account.equity) if account.equity is not None else None,
        "profit": float(account.profit) if account.profit is not None else None,
        "is_active": account.is_active,
        "last_seen_at": account.last_seen_at,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
        "user_id": account.user_id,
        "created_by": account.created_by,
        "connection_status": connection_status,
        "current_model_id": current_model_id,
        "current_model_version": current_model_version,
        "trading_enabled": True,  # Default to True, can be enhanced later
        # Connection details from EA
        "terminal_id": connection.terminal_id if connection else None,
        "ea_version": connection.ea_version if connection else None,
        "connection_ip": connection.connection_ip if connection else None,
        "connected_at": connection.connected_at if connection else None,
    }
