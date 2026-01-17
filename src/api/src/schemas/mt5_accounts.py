"""
Pydantic schemas for MT5 Accounts
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class AccountType(str, Enum):
    """Account type enumeration"""

    DEMO = "demo"
    LIVE = "live"


class ConnectionStatus(str, Enum):
    """Connection status enumeration"""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    PAUSED = "paused"


class MT5AccountBase(BaseModel):
    """Base MT5 account schema"""

    account_login: int
    account_type: AccountType
    broker_name: Optional[str] = None
    broker_server: Optional[str] = None
    account_currency: Optional[str] = None
    account_leverage: Optional[int] = None
    account_name: Optional[str] = None
    balance: Optional[float] = None
    equity: Optional[float] = None
    profit: Optional[float] = None


class MT5AccountCreateRequest(MT5AccountBase):
    """Request schema for creating MT5 account"""

    mt5_password: str = Field(..., description="MT5 account password (required for Python API connection)")
    mt5_server: str = Field(..., description="MT5 broker server name (required, e.g., 'ICMarkets-Demo', 'FXCM-Demo')")
    ea_version: Optional[str] = None
    connection_ip: Optional[str] = None
    terminal_id: Optional[int] = None


class MT5AccountUpdateRequest(BaseModel):
    """Request schema for updating MT5 account"""

    account_name: Optional[str] = None
    notes: Optional[str] = None  # For future use


class MT5AccountResponse(MT5AccountBase):
    """Response schema for MT5 account"""

    id: int
    is_active: bool
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # User ownership fields (optional, for admin views and audit)
    user_id: Optional[str] = None  # Clerk user ID (owner)
    created_by: Optional[str] = None  # Clerk user ID (creator, for audit)
    # Computed fields
    connection_status: Optional[ConnectionStatus] = None
    current_model_id: Optional[int] = None
    current_model_version: Optional[str] = None
    trading_enabled: bool = True
    # Connection details from EA
    terminal_id: Optional[int] = None
    ea_version: Optional[str] = None
    connection_ip: Optional[str] = None
    connected_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MT5AccountListResponse(BaseModel):
    """Response schema for list of MT5 accounts"""

    accounts: List[MT5AccountResponse]
    total: int


class MT5ConnectionStatusResponse(BaseModel):
    """Response schema for connection status"""

    account_id: int
    is_connected: bool
    connection_status: ConnectionStatus
    connected_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    terminal_id: Optional[int] = None
    connection_ip: Optional[str] = None
    ea_version: Optional[str] = None


class MT5ConnectionHistoryItem(BaseModel):
    """Schema for connection history item"""

    id: int
    connected_at: datetime
    disconnected_at: Optional[datetime] = None
    disconnect_reason: Optional[str] = None
    connection_ip: Optional[str] = None
    ea_version: Optional[str] = None
    terminal_id: Optional[int] = None

    class Config:
        from_attributes = True


class MT5ConnectionHistoryResponse(BaseModel):
    """Response schema for connection history"""

    connections: List[MT5ConnectionHistoryItem]
    total: int


class MT5AccountSecretResponse(MT5AccountResponse):
    """Response schema for account registration (legacy - kept for backward compatibility)"""

    # Note: auth_token, server_host, server_port are no longer used for Python API accounts
    # but kept in schema for backward compatibility with existing code
    auth_token: Optional[str] = None
    server_host: Optional[str] = None
    server_port: Optional[int] = None


class ModelAssignmentRequest(BaseModel):
    """Request schema for model assignment"""

    model_id: int
    trading_mode: str = Field(default="live", description="Trading mode: 'paper' or 'live'")
    notes: Optional[str] = None


class ModelAssignmentResponse(BaseModel):
    """Response schema for model assignment"""

    id: int
    account_id: int
    model_id: int
    model_version: Optional[str] = None
    trading_mode: str
    is_active: bool
    assigned_at: datetime
    assigned_by: Optional[int] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True
