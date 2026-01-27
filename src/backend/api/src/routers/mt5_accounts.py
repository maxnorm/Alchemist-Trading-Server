"""
MT5 Account Management endpoints
Allows users to connect, manage, and monitor their MT5 accounts
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    Request,
)
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, Dict
from datetime import datetime
from dependencies import get_db
from middleware.auth import get_current_user
from config import settings
from services import mt5_accounts_service
from services.mt5_accounts_service import (
    get_all_accounts,
    get_account_by_id,
    get_account_by_login,
    create_account,
    create_account_for_user,
    verify_account_ownership,
    regenerate_account_token,
    update_account,
    delete_account,
    get_connection_status,
    get_connection_history,
    assign_model_to_account,
    unassign_model_from_account,
    get_current_assignment,
    pause_trading,
    resume_trading,
    get_connected_accounts,
)
from schemas.mt5_accounts import (
    MT5AccountResponse,
    MT5AccountListResponse,
    MT5AccountCreateRequest,
    MT5AccountUpdateRequest,
    MT5ConnectionStatusResponse,
    MT5ConnectionHistoryResponse,
    ModelAssignmentRequest,
    ModelAssignmentResponse,
    MT5AccountSecretResponse,
)
from websocket.manager import websocket_manager
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/accounts/mt5", tags=["MT5 Accounts"])


@router.get("", response_model=MT5AccountListResponse)
async def list_accounts(
    request: Request,
    connected_only: bool = Query(False, description="Show only connected accounts"),
    account_type: Optional[str] = Query(
        None, description="Filter by account type (demo/live)"
    ),
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List MT5 accounts (filtered to user's accounts, admins see all)"""
    try:
        user_id = user.get("id") or request.state.user_id
        user_roles = request.state.roles

        # Admins can see all accounts, regular users see only their own
        filter_user_id = None if "admin" in user_roles else user_id

        accounts = get_all_accounts(
            db,
            connected_only=connected_only,
            account_type=account_type,
            user_id=filter_user_id,
        )
        return MT5AccountListResponse(accounts=accounts, total=len(accounts))
    except HTTPException:
        # Re-raise HTTPException to preserve status code (e.g., 503 from get_db)
        raise
    except SQLAlchemyError as e:
        # Database errors should return 503
        raise HTTPException(status_code=503, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list accounts: {str(e)}"
        )


@router.get("/connected", response_model=MT5AccountListResponse)
async def list_connected_accounts(
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List currently connected MT5 accounts"""
    try:
        accounts = get_connected_accounts(db)
        return MT5AccountListResponse(accounts=accounts, total=len(accounts))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get connected accounts: {str(e)}"
        )


@router.get("/{account_id}", response_model=MT5AccountResponse)
async def get_account(
    request: Request,
    account_id: int,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get MT5 account details (requires ownership or admin role)"""
    try:
        account = get_account_by_id(db, account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        user_id = user.get("id") or request.state.user_id
        user_roles = request.state.roles

        # Admins can access any account
        if "admin" not in user_roles:
            # Regular users must own the account
            orm_account = get_account_by_login(db, account.account_login)
            if not orm_account or orm_account.user_id != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied. You do not own this account.",
                )

        return account
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get account: {str(e)}")


@router.post("", response_model=MT5AccountResponse, status_code=201)
async def register_account(
    request: MT5AccountCreateRequest,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register a new MT5 account (typically auto-registered when EA connects)"""
    try:
        account = create_account(db, request)
        return account
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to register account: {str(e)}"
        )


@router.post("/register", response_model=MT5AccountSecretResponse, status_code=201)
async def register_account_with_secret(
    request: MT5AccountCreateRequest,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Register a new MT5 account.

    For Python API connection: Requires mt5_password and mt5_server fields.
    The password is encrypted and stored securely.

    For ZeroMQ connection: Leave password/server empty. Auth token will be generated
    and returned for EA configuration.

    ⚠️ SECURITY: The password is encrypted at rest and never returned in responses.
    """
    try:
        user_id = user.get("id")
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID not found in token")

        # Validate: if password provided, server must be provided (and vice versa)
        has_password = hasattr(request, "mt5_password") and request.mt5_password
        has_server = hasattr(request, "mt5_server") and request.mt5_server

        if has_password and not has_server:
            raise HTTPException(
                status_code=400,
                detail="mt5_server is required when mt5_password is provided (for Python API connection)",
            )
        if has_server and not has_password:
            raise HTTPException(
                status_code=400,
                detail="mt5_password is required when mt5_server is provided (for Python API connection)",
            )

        # Create or update account with user association
        account = create_account_for_user(
            db, request, user_id=user_id, created_by=user_id
        )

        # Verify user owns this account (security check)
        orm_account = get_account_by_login(db, account.account_login)
        if not orm_account:
            raise HTTPException(status_code=500, detail="Failed to load account")
        if orm_account.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Get auth_token for ZeroMQ connection
        auth_token = orm_account.auth_token if orm_account.auth_token else None

        # Get server host/port for EA configuration
        server_host = settings.mt5_server_public_host
        server_port = settings.mt5_server_public_port
        if server_host is None or server_port is None:
            server_host = settings.api_host
            server_port = settings.api_port

        # Return account with auth_token (for ZeroMQ) or without (for Python API)
        return MT5AccountSecretResponse(
            **account.model_dump(),
            auth_token=auth_token,
            server_host=server_host,
            server_port=server_port,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to register account: {str(e)}"
        )


@router.get("/{account_id}/secret", response_model=MT5AccountSecretResponse)
async def get_account_secret(
    account_id: int,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get MT5 account details including auth token.

    Intended for dashboard/admin usage to display EA configuration.
    """
    try:
        account_response = mt5_accounts_service.get_account_by_id(db, account_id)
        if not account_response:
            raise HTTPException(status_code=404, detail="Account not found")

        # Load ORM account to access auth_token
        orm_account = (
            db.query(mt5_accounts_service.MT5Account)
            .filter(  # type: ignore[attr-defined]
                mt5_accounts_service.MT5Account.id == account_id  # type: ignore[attr-defined]
            )
            .first()
        )
        if not orm_account or not orm_account.auth_token:
            raise HTTPException(
                status_code=500, detail="Failed to load account auth token"
            )

        server_host = settings.mt5_server_public_host
        server_port = settings.mt5_server_public_port

        if server_host is None or server_port is None:
            server_host = settings.api_host
            server_port = settings.api_port

        return MT5AccountSecretResponse(
            **account_response.model_dump(),
            auth_token=orm_account.auth_token,
            server_host=server_host,
            server_port=server_port,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get account secret: {str(e)}"
        )


@router.put("/{account_id}", response_model=MT5AccountResponse)
async def update_account_settings(
    request: Request,
    account_id: int,
    update_request: MT5AccountUpdateRequest,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update MT5 account settings (name, notes, etc.) - requires ownership or admin role"""
    try:
        user_id = user.get("id") or request.state.user_id
        user_roles = request.state.roles

        # Verify ownership (admins can update any account)
        if "admin" not in user_roles:
            if not verify_account_ownership(db, account_id, user_id):
                raise HTTPException(
                    status_code=403,
                    detail="Access denied. You do not own this account.",
                )

        account = update_account(db, account_id, update_request)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        return account
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update account: {str(e)}"
        )


@router.delete("/{account_id}", status_code=204)
async def remove_account(
    request: Request,
    account_id: int,
    confirm: bool = Query(False, description="Confirmation required to delete"),
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove MT5 account (soft delete) - requires ownership or admin role"""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Set 'confirm' to true to delete account.",
        )

    try:
        user_id = user.get("id") or request.state.user_id
        user_roles = request.state.roles

        # Verify ownership (admins can delete any account)
        if "admin" not in user_roles:
            if not verify_account_ownership(db, account_id, user_id):
                raise HTTPException(
                    status_code=403,
                    detail="Access denied. You do not own this account.",
                )

        success = delete_account(db, account_id)
        if not success:
            raise HTTPException(status_code=404, detail="Account not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete account: {str(e)}"
        )


@router.get("/{account_id}/status", response_model=MT5ConnectionStatusResponse)
async def get_account_status(
    account_id: int,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get real-time connection status for an account"""
    try:
        status = get_connection_status(db, account_id)
        if not status:
            raise HTTPException(status_code=404, detail="Account not found")
        return status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.get("/{account_id}/connections", response_model=MT5ConnectionHistoryResponse)
async def get_connection_history_route(
    account_id: int,
    limit: int = Query(
        50, ge=1, le=500, description="Maximum number of connections to return"
    ),
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get connection history for an account"""
    try:
        history = get_connection_history(db, account_id, limit=limit)
        return MT5ConnectionHistoryResponse(connections=history, total=len(history))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get connection history: {str(e)}"
        )


@router.post("/{account_id}/assign-model", response_model=ModelAssignmentResponse)
async def assign_model(
    request: Request,
    account_id: int,
    assignment_request: ModelAssignmentRequest,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Assign a model to an MT5 account - requires ownership or admin role"""
    try:
        user_id = user.get("id") or request.state.user_id
        user_roles = request.state.roles

        # Verify ownership (admins can assign models to any account)
        if "admin" not in user_roles:
            if not verify_account_ownership(db, account_id, user_id):
                raise HTTPException(
                    status_code=403,
                    detail="Access denied. You do not own this account.",
                )

        assignment = assign_model_to_account(
            db,
            account_id,
            assignment_request.model_id,
            assignment_request.trading_mode,
            assignment_request.notes,
        )
        if not assignment:
            raise HTTPException(status_code=404, detail="Account or model not found")
        return assignment
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to assign model: {str(e)}")


@router.delete("/{account_id}/assignment", status_code=204)
async def unassign_model(
    request: Request,
    account_id: int,
    confirm: bool = Query(False, description="Confirmation required to unassign"),
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unassign model from account - requires ownership or admin role"""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Set 'confirm' to true to unassign model.",
        )

    try:
        user_id = user.get("id") or request.state.user_id
        user_roles = request.state.roles

        # Verify ownership (admins can unassign models from any account)
        if "admin" not in user_roles:
            if not verify_account_ownership(db, account_id, user_id):
                raise HTTPException(
                    status_code=403,
                    detail="Access denied. You do not own this account.",
                )

        success = unassign_model_from_account(db, account_id)
        if not success:
            raise HTTPException(
                status_code=404, detail="Account not found or no assignment"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to unassign model: {str(e)}"
        )


@router.get("/{account_id}/assignment", response_model=ModelAssignmentResponse)
async def get_current_assignment_route(
    request: Request,
    account_id: int,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current model assignment for account - requires ownership or admin role"""
    try:
        user_id = user.get("id") or request.state.user_id
        user_roles = request.state.roles

        # Verify ownership (admins can view assignments for any account)
        if "admin" not in user_roles:
            if not verify_account_ownership(db, account_id, user_id):
                raise HTTPException(
                    status_code=403,
                    detail="Access denied. You do not own this account.",
                )

        assignment = get_current_assignment(db, account_id)
        if not assignment:
            raise HTTPException(status_code=404, detail="No assignment found")
        return assignment
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get assignment: {str(e)}"
        )


@router.post("/{account_id}/pause", response_model=MT5ConnectionStatusResponse)
async def pause_account_trading(
    account_id: int,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pause trading on an account"""
    try:
        status = pause_trading(db, account_id)
        if not status:
            raise HTTPException(status_code=404, detail="Account not found")
        return status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to pause trading: {str(e)}"
        )


@router.post("/{account_id}/resume", response_model=MT5ConnectionStatusResponse)
async def resume_account_trading(
    account_id: int,
    confirm: bool = Query(False, description="Confirmation required to resume trading"),
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resume trading on an account"""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Set 'confirm' to true to resume trading.",
        )

    try:
        status = resume_trading(db, account_id)
        if not status:
            raise HTTPException(status_code=404, detail="Account not found")
        return status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to resume trading: {str(e)}"
        )


@router.post("/{account_id}/regenerate-token", response_model=MT5AccountSecretResponse)
async def regenerate_account_token_endpoint(
    request: Request,
    account_id: int,
    confirm: bool = Query(
        False, description="Confirmation required to regenerate token"
    ),
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Regenerate auth token for an account.

    ⚠️ WARNING: This invalidates the old token. The EA will need to be reconfigured.
    The new token is only shown in this response - store it securely.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Set 'confirm=true' to regenerate token.",
        )

    try:
        user_id = user.get("id") or request.state.user_id

        # Verify ownership
        if not verify_account_ownership(db, account_id, user_id):
            raise HTTPException(
                status_code=403, detail="Access denied. You do not own this account."
            )

        # Regenerate token
        new_token = regenerate_account_token(db, account_id, user_id)
        if not new_token:
            raise HTTPException(status_code=404, detail="Account not found")

        # Get account details
        account = get_account_by_id(db, account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        server_host = settings.mt5_server_public_host
        server_port = settings.mt5_server_public_port

        if server_host is None or server_port is None:
            server_host = settings.api_host
            server_port = settings.api_port

        return MT5AccountSecretResponse(
            **account.model_dump(),
            auth_token=new_token,
            server_host=server_host,
            server_port=server_port,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to regenerate token: {str(e)}"
        )


# WebSocket endpoint for real-time account status updates
@router.websocket("/{account_id}/status/ws")
async def websocket_account_status(websocket: WebSocket, account_id: int):
    """WebSocket endpoint for real-time account status updates"""
    from services.clerk_service import clerk_service

    # Get token from query params
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return

    try:
        # Verify token with Clerk
        session_data = clerk_service.verify_token(token)
        user_id = session_data["user_id"]
        user_data = clerk_service.get_user(user_id)
        roles = clerk_service.extract_roles(user_data)

        # Store user info in websocket state
        websocket.state.user_id = user_id
        websocket.state.roles = roles

        logger.info(
            f"MT5 Account WebSocket authenticated: user_id={user_id}, account_id={account_id}"
        )

        # Accept connection and connect to channel
        await websocket.accept()
        await websocket_manager.connect(
            websocket, f"mt5_account_{account_id}", accept=False
        )

    except ValueError as e:
        logger.warning(f"MT5 Account WebSocket authentication failed: {e}")
        await websocket.close(code=1008, reason="Invalid token")
        return

    try:
        while True:
            # Keep connection alive and send updates
            _ = await websocket.receive_text()  # Receive to keep connection alive
            # Echo or handle client messages if needed
            await websocket_manager.send_personal_message(
                {"type": "pong", "timestamp": datetime.utcnow().isoformat()}, websocket
            )
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket, f"mt5_account_{account_id}")
