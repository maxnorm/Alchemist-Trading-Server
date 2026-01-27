"""
SQLAlchemy ORM models for MT5 Accounts
"""

from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Boolean,
    Text,
    ForeignKey,
    DateTime,
    UniqueConstraint,
    Numeric,
    LargeBinary,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from . import Base


class MT5Account(Base):  # type: ignore[misc,valid-type]
    """MT5 Account model"""

    __tablename__ = "mt5_accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_login = Column(BigInteger, unique=True, nullable=False, index=True)
    account_type = Column(String(20), nullable=False, index=True)  # 'demo', 'live'
    broker_name = Column(String(100), nullable=True)
    broker_server = Column(String(100), nullable=True)
    account_currency = Column(String(10), nullable=True)
    account_leverage = Column(Integer, nullable=True)
    account_name = Column(String(100), nullable=True)  # User-friendly name
    balance = Column(Numeric(15, 2), nullable=True)  # Account balance
    equity = Column(Numeric(15, 2), nullable=True)  # Account equity
    profit = Column(Numeric(15, 2), nullable=True)  # Account profit/loss
    auth_token = Column(
        String(128), nullable=True, index=True
    )  # Legacy field, not used for Python API accounts
    mt5_password_encrypted = Column(
        LargeBinary, nullable=True
    )  # Encrypted password for Python API
    mt5_server = Column(String(100), nullable=True)  # MT5 broker server name
    user_id = Column(String(255), nullable=True, index=True)  # Clerk user ID (owner)
    created_by = Column(
        String(255), nullable=True
    )  # Clerk user ID (creator, for audit)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    assignments = relationship(
        "AccountModelAssignment", back_populates="account", cascade="all, delete-orphan"
    )
    connections = relationship(
        "MT5Connection", back_populates="account", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<MT5Account(id={self.id}, login={self.account_login}, type={self.account_type})>"


class AccountModelAssignment(Base):  # type: ignore[misc,valid-type]
    """Model assignment to MT5 account"""

    __tablename__ = "account_model_assignments"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(
        Integer, ForeignKey("mt5_accounts.id", ondelete="CASCADE"), nullable=False
    )
    model_id = Column(
        Integer, ForeignKey("models.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trading_mode = Column(String(20), nullable=False)  # 'paper', 'live'
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    assigned_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    assigned_by = Column(
        Integer, nullable=True
    )  # dashboard_users.id (nullable for now)
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
    deactivated_by = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    account = relationship("MT5Account", back_populates="assignments")

    # Unique constraint: only one active assignment per account
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "is_active",
            name="unique_active_account",
            deferrable=True,
            initially="DEFERRED",
        ),
    )

    def __repr__(self):
        return (
            f"<AccountModelAssignment(id={self.id}, account_id={self.account_id}, "
            f"model_id={self.model_id}, active={self.is_active})>"
        )


class MT5Connection(Base):  # type: ignore[misc,valid-type]
    """MT5 connection history"""

    __tablename__ = "mt5_connections"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(
        Integer,
        ForeignKey("mt5_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    terminal_id = Column(Integer, nullable=True)  # Terminal ID from MT5Terminal
    ea_version = Column(String(50), nullable=True)
    connection_ip = Column(String(45), nullable=True)
    connected_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    disconnected_at = Column(DateTime(timezone=True), nullable=True)
    disconnect_reason = Column(String(100), nullable=True)
    is_connected = Column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    account = relationship("MT5Account", back_populates="connections")

    def __repr__(self):
        return f"<MT5Connection(id={self.id}, account_id={self.account_id}, connected={self.is_connected})>"
