"""
MT5 Account Management endpoints
Allows users to connect, manage, and monitor their MT5 accounts
"""

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, List
from datetime import datetime
from dependencies import get_db
from config import settings
from services import mt5_accounts_service
from services.mt5_accounts_service import (
    get_all_accounts,
    get_account_by_id,
    get_account_by_login,
    create_account,
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

router = APIRouter(prefix="/accounts/mt5", tags=["MT5 Accounts"])


@router.get("", response_model=MT5AccountListResponse)
async def list_accounts(
    connected_only: bool = Query(False, description="Show only connected accounts"),
    account_type: Optional[str] = Query(None, description="Filter by account type (demo/live)"),
    db: Session = Depends(get_db),
):
    """List all MT5 accounts"""
    try:
        accounts = get_all_accounts(db, connected_only=connected_only, account_type=account_type)
        return MT5AccountListResponse(accounts=accounts, total=len(accounts))
    except HTTPException:
        # Re-raise HTTPException to preserve status code (e.g., 503 from get_db)
        raise
    except SQLAlchemyError as e:
        # Database errors should return 503
        raise HTTPException(
            status_code=503,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list accounts: {str(e)}")


@router.get("/connected", response_model=MT5AccountListResponse)
async def list_connected_accounts(db: Session = Depends(get_db)):
    """List currently connected MT5 accounts"""
    try:
        accounts = get_connected_accounts(db)
        return MT5AccountListResponse(accounts=accounts, total=len(accounts))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get connected accounts: {str(e)}")


@router.get("/{account_id}", response_model=MT5AccountResponse)
async def get_account(account_id: int, db: Session = Depends(get_db)):
    """Get MT5 account details"""
    try:
        account = get_account_by_id(db, account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        return account
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get account: {str(e)}")


@router.post("", response_model=MT5AccountResponse, status_code=201)
async def register_account(
    request: MT5AccountCreateRequest,
    db: Session = Depends(get_db),
):
    """Register a new MT5 account (typically auto-registered when EA connects)"""
    try:
        account = create_account(db, request)
        return account
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register account: {str(e)}")


@router.post("/register", response_model=MT5AccountSecretResponse, status_code=201)
async def register_account_with_secret(
    request: MT5AccountCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Register a new MT5 account for external EA connection.

    Returns the auth token and public MT5 server coordinates so the user can
    configure their Expert Advisors.
    """
    try:
        # Create or update account (returns MT5AccountResponse)
        account = create_account(db, request)

        # Load ORM account to access auth_token
        orm_account = get_account_by_login(db, account.account_login)
        if not orm_account or not orm_account.auth_token:
            raise HTTPException(status_code=500, detail="Failed to load account auth token")

        server_host = settings.mt5_server_public_host
        server_port = settings.mt5_server_public_port

        if server_host is None or server_port is None:
            # Fall back to API host/port if public MT5 server is not configured
            server_host = settings.api_host
            server_port = settings.api_port

        return MT5AccountSecretResponse(
            **account.model_dump(),
            auth_token=orm_account.auth_token,
            server_host=server_host,
            server_port=server_port,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register account with secret: {str(e)}")


@router.get("/{account_id}/secret", response_model=MT5AccountSecretResponse)
async def get_account_secret(account_id: int, db: Session = Depends(get_db)):
    """
    Get MT5 account details including auth token.

    Intended for dashboard/admin usage to display EA configuration.
    """
    try:
        account_response = mt5_accounts_service.get_account_by_id(db, account_id)
        if not account_response:
            raise HTTPException(status_code=404, detail="Account not found")

        # Load ORM account to access auth_token
        orm_account = db.query(mt5_accounts_service.MT5Account).filter(  # type: ignore[attr-defined]
            mt5_accounts_service.MT5Account.id == account_id  # type: ignore[attr-defined]
        ).first()
        if not orm_account or not orm_account.auth_token:
            raise HTTPException(status_code=500, detail="Failed to load account auth token")

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
        raise HTTPException(status_code=500, detail=f"Failed to get account secret: {str(e)}")


@router.put("/{account_id}", response_model=MT5AccountResponse)
async def update_account_settings(
    account_id: int,
    request: MT5AccountUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update MT5 account settings (name, notes, etc.)"""
    try:
        account = update_account(db, account_id, request)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        return account
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update account: {str(e)}")


@router.delete("/{account_id}", status_code=204)
async def remove_account(
    account_id: int,
    confirm: bool = Query(False, description="Confirmation required to delete"),
    db: Session = Depends(get_db),
):
    """Remove MT5 account (soft delete)"""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Set 'confirm' to true to delete account.",
        )

    try:
        success = delete_account(db, account_id)
        if not success:
            raise HTTPException(status_code=404, detail="Account not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete account: {str(e)}")


@router.get("/{account_id}/status", response_model=MT5ConnectionStatusResponse)
async def get_account_status(account_id: int, db: Session = Depends(get_db)):
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
    limit: int = Query(50, ge=1, le=500, description="Maximum number of connections to return"),
    db: Session = Depends(get_db),
):
    """Get connection history for an account"""
    try:
        history = get_connection_history(db, account_id, limit=limit)
        return MT5ConnectionHistoryResponse(connections=history, total=len(history))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get connection history: {str(e)}")


@router.post("/{account_id}/assign-model", response_model=ModelAssignmentResponse)
async def assign_model(
    account_id: int,
    request: ModelAssignmentRequest,
    db: Session = Depends(get_db),
):
    """Assign a model to an MT5 account"""
    try:
        assignment = assign_model_to_account(
            db, account_id, request.model_id, request.trading_mode, request.notes
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
    account_id: int,
    confirm: bool = Query(False, description="Confirmation required to unassign"),
    db: Session = Depends(get_db),
):
    """Unassign model from account"""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Set 'confirm' to true to unassign model.",
        )

    try:
        success = unassign_model_from_account(db, account_id)
        if not success:
            raise HTTPException(status_code=404, detail="Account not found or no assignment")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unassign model: {str(e)}")


@router.get("/{account_id}/assignment", response_model=ModelAssignmentResponse)
async def get_current_assignment_route(account_id: int, db: Session = Depends(get_db)):
    """Get current model assignment for account"""
    try:
        assignment = get_current_assignment(db, account_id)
        if not assignment:
            raise HTTPException(status_code=404, detail="No assignment found")
        return assignment
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get assignment: {str(e)}")


@router.post("/{account_id}/pause", response_model=MT5ConnectionStatusResponse)
async def pause_account_trading(account_id: int, db: Session = Depends(get_db)):
    """Pause trading on an account"""
    try:
        status = pause_trading(db, account_id)
        if not status:
            raise HTTPException(status_code=404, detail="Account not found")
        return status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pause trading: {str(e)}")


@router.post("/{account_id}/resume", response_model=MT5ConnectionStatusResponse)
async def resume_account_trading(
    account_id: int,
    confirm: bool = Query(False, description="Confirmation required to resume trading"),
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
        raise HTTPException(status_code=500, detail=f"Failed to resume trading: {str(e)}")


# WebSocket endpoint for real-time account status updates
@router.websocket("/{account_id}/status/ws")
async def websocket_account_status(websocket: WebSocket, account_id: int):
    """WebSocket endpoint for real-time account status updates"""
    await websocket_manager.connect(websocket, f"mt5_account_{account_id}")

    try:
        while True:
            # Keep connection alive and send updates
            data = await websocket.receive_text()
            # Echo or handle client messages if needed
            await websocket_manager.send_personal_message(
                {"type": "pong", "timestamp": datetime.utcnow().isoformat()},
                websocket
            )
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket, f"mt5_account_{account_id}")
