"""
Order Management System (OMS)

Provides order tracking, idempotency, state management, and position reconciliation.
Ensures reliable order handling even in the face of network issues or restarts.

Features:
- Idempotent order submission (same client_order_id returns same order)
- Order state tracking through lifecycle
- Position tracking and reconciliation
- Persistence to database (optional)
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
import uuid
import threading
import json
import logging
from pathlib import Path
from sqlalchemy import text

from monitoring.metrics import oms_reconciliation_errors


class OrderState(Enum):
    """Order lifecycle states"""

    PENDING_NEW = "pending_new"  # Order created, not yet sent
    NEW = "new"  # Order accepted by broker
    PARTIALLY_FILLED = "partially_filled"  # Partial fill received
    FILLED = "filled"  # Fully filled
    PENDING_CANCEL = "pending_cancel"  # Cancel request sent
    CANCELLED = "cancelled"  # Order cancelled
    REJECTED = "rejected"  # Order rejected by broker
    EXPIRED = "expired"  # Order expired


class OrderSide(Enum):
    """Order side"""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order type"""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


@dataclass
class Fill:
    """Represents a fill (partial or complete)"""

    fill_id: str
    quantity: float
    price: float
    timestamp: datetime
    commission: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fill_id": self.fill_id,
            "quantity": self.quantity,
            "price": self.price,
            "timestamp": self.timestamp.isoformat(),
            "commission": self.commission,
        }


@dataclass
class Order:
    """
    Represents a trading order.

    The client_order_id is used for idempotency - submitting the same
    client_order_id will return the existing order instead of creating a new one.
    """

    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_order_id: str = ""
    symbol: str = ""
    side: str = "BUY"
    quantity: float = 0.0
    order_type: str = "MARKET"
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    state: OrderState = OrderState.PENDING_NEW
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    fills: List[Fill] = field(default_factory=list)
    broker_order_id: Optional[str] = None
    reject_reason: Optional[str] = None
    account_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "price": self.price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "state": self.state.value,
            "filled_quantity": self.filled_quantity,
            "average_fill_price": self.average_fill_price,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "fills": [f.to_dict() for f in self.fills],
            "broker_order_id": self.broker_order_id,
            "reject_reason": self.reject_reason,
            "account_id": self.account_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Order":
        fills = [
            Fill(
                fill_id=f["fill_id"],
                quantity=f["quantity"],
                price=f["price"],
                timestamp=datetime.fromisoformat(f["timestamp"]),
                commission=f.get("commission", 0.0),
            )
            for f in data.get("fills", [])
        ]

        return cls(
            order_id=data["order_id"],
            client_order_id=data.get("client_order_id", ""),
            symbol=data["symbol"],
            side=data["side"],
            quantity=data["quantity"],
            order_type=data.get("order_type", "MARKET"),
            price=data.get("price"),
            stop_loss=data.get("stop_loss"),
            take_profit=data.get("take_profit"),
            state=OrderState(data["state"]),
            filled_quantity=data.get("filled_quantity", 0.0),
            average_fill_price=data.get("average_fill_price", 0.0),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            fills=fills,
            broker_order_id=data.get("broker_order_id"),
            reject_reason=data.get("reject_reason"),
            account_id=data.get("account_id"),
            metadata=data.get("metadata", {}),
        )

    @property
    def is_terminal(self) -> bool:
        """Check if order is in a terminal state"""
        return self.state in (
            OrderState.FILLED,
            OrderState.CANCELLED,
            OrderState.REJECTED,
            OrderState.EXPIRED,
        )

    @property
    def is_active(self) -> bool:
        """Check if order is active"""
        return not self.is_terminal

    @property
    def remaining_quantity(self) -> float:
        """Get remaining quantity to fill"""
        return self.quantity - self.filled_quantity


@dataclass
class Position:
    """Represents an open position"""

    symbol: str
    quantity: float  # Positive for long, negative for short
    average_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "average_price": self.average_price,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
        }


@dataclass
class Discrepancy:
    """Represents a position discrepancy between local and broker"""

    symbol: str
    local_quantity: float
    broker_quantity: float
    difference: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "local_quantity": self.local_quantity,
            "broker_quantity": self.broker_quantity,
            "difference": self.difference,
        }


class OrderManagementSystem:
    """
    Order Management System for tracking orders and positions.

    Provides:
    - Idempotent order submission
    - Order state tracking
    - Position tracking
    - Reconciliation with broker
    - Persistence (optional)

    Usage:
        oms = OrderManagementSystem()

        # Submit order (idempotent)
        order = Order(
            client_order_id="my-order-123",
            symbol="EURUSD",
            side="BUY",
            quantity=0.1
        )
        order_id = oms.submit_order(order)

        # Handle fill from broker
        oms.handle_fill({
            'order_id': order_id,
            'quantity': 0.1,
            'price': 1.0850
        })

        # Reconcile positions
        broker_positions = broker.get_positions()
        discrepancies = oms.reconcile(broker_positions)
    """

    def __init__(
        self,
        database: Any = None,
        persistence_path: Optional[str] = None,
        on_order_update: Optional[Callable[[Order], None]] = None,
        on_position_update: Optional[Callable[[Position], None]] = None,
        on_alert: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        alert_threshold_pct: float = 0.10,
    ):
        """
        Initialize OMS.

        Args:
            database: Database connection (optional)
            persistence_path: Path for file-based persistence (optional)
            on_order_update: Callback when order state changes
            on_position_update: Callback when position changes
            on_alert: Callback when alert condition is met (alert_type, alert_data)
            alert_threshold_pct: Alert if position discrepancy exceeds this percentage (default 10%)
        """
        self.db = database
        self.persistence_path = Path(persistence_path) if persistence_path else None
        self.on_order_update = on_order_update
        self.on_position_update = on_position_update
        self.on_alert = on_alert
        self.alert_threshold_pct = alert_threshold_pct

        self.orders: Dict[str, Order] = {}
        self.positions: Dict[str, Position] = {}
        self._idempotency_keys: Dict[str, str] = {}  # client_order_id -> order_id
        self._lock = threading.RLock()

        self.logger = logging.getLogger(__name__)

        # Load persisted state (database first, then file as fallback)
        if self.db:
            try:
                self._load_from_db()
            except Exception as e:
                self.logger.warning(
                    f"Failed to load from database, falling back to file: {e}"
                )
                if self.persistence_path:
                    self._load_state()
        elif self.persistence_path:
            self._load_state()

    def submit_order(self, order: Order) -> str:
        """
        Submit an order.

        If the order has a client_order_id that has been seen before,
        returns the existing order_id (idempotency).

        Args:
            order: Order to submit

        Returns:
            order_id
        """
        with self._lock:
            # Check idempotency
            if (
                order.client_order_id
                and order.client_order_id in self._idempotency_keys
            ):
                existing_id = self._idempotency_keys[order.client_order_id]
                self.logger.info(
                    f"Idempotency hit: {order.client_order_id} -> {existing_id}"
                )
                return existing_id

            # Validate order
            self._validate_order(order)

            # Store order
            self.orders[order.order_id] = order

            # Store idempotency key
            if order.client_order_id:
                self._idempotency_keys[order.client_order_id] = order.order_id

            # Persist to database and/or file
            self._persist_order_to_db(order)
            self._persist()

            self.logger.info(
                f"Order submitted: {order.order_id} ({order.side} {order.quantity} {order.symbol})"
            )

            return order.order_id

    def update_order_state(
        self, order_id: str, new_state: OrderState, **kwargs
    ) -> Optional[Order]:
        """
        Update order state.

        Args:
            order_id: Order ID
            new_state: New state
            **kwargs: Additional fields to update

        Returns:
            Updated order or None if not found
        """
        with self._lock:
            order = self.orders.get(order_id)
            if not order:
                self.logger.warning(f"Order not found: {order_id}")
                return None

            old_state = order.state
            order.state = new_state
            order.updated_at = datetime.now()

            # Update additional fields
            for key, value in kwargs.items():
                if hasattr(order, key):
                    setattr(order, key, value)

            # Persist to database and/or file
            self._persist_order_to_db(order)
            self._persist()

            if self.on_order_update is not None:
                self.on_order_update(order)

            self.logger.info(
                f"Order {order_id} state: {old_state.value} -> {new_state.value}"
            )
            return order

    def handle_fill(self, fill_data: Dict[str, Any]) -> Optional[Order]:
        """
        Process a fill from the broker.

        Args:
            fill_data: Fill information containing:
                - order_id: Order ID
                - quantity: Filled quantity
                - price: Fill price
                - commission: Commission (optional)

        Returns:
            Updated order or None if not found
        """
        with self._lock:
            order_id: Optional[str] = fill_data.get("order_id")
            if not order_id:
                # Try to find by broker_order_id
                broker_id = fill_data.get("broker_order_id")
                for o in self.orders.values():
                    if o.broker_order_id == broker_id:
                        order_id = o.order_id
                        break

            if not order_id:
                self.logger.warning(f"Order ID not found for fill: {fill_data}")
                return None

            order = self.orders.get(order_id)
            if not order:
                self.logger.warning(f"Order not found for fill: {fill_data}")
                return None

            # Create fill record
            fill = Fill(
                fill_id=fill_data.get("fill_id", str(uuid.uuid4())),
                quantity=fill_data["quantity"],
                price=fill_data["price"],
                timestamp=datetime.now(),
                commission=fill_data.get("commission", 0.0),
            )
            order.fills.append(fill)

            # Update filled quantity and average price
            old_filled = order.filled_quantity
            order.filled_quantity += fill.quantity

            # Calculate new average price
            if order.filled_quantity > 0:
                old_value = old_filled * order.average_fill_price
                new_value = fill.quantity * fill.price
                order.average_fill_price = (
                    old_value + new_value
                ) / order.filled_quantity

            # Update state
            if order.filled_quantity >= order.quantity:
                order.state = OrderState.FILLED
            else:
                order.state = OrderState.PARTIALLY_FILLED

            order.updated_at = datetime.now()

            # Update position
            self._update_position(order, fill)

            # Persist to database and/or file
            self._persist_order_to_db(order)
            self._persist()

            if self.on_order_update is not None:
                self.on_order_update(order)

            self.logger.info(
                f"Fill processed: {order_id} - {fill.quantity} @ {fill.price} "
                f"({order.filled_quantity}/{order.quantity})"
            )

            return order

    def handle_rejection(self, order_id: str, reason: str) -> Optional[Order]:
        """
        Handle order rejection from broker.

        Args:
            order_id: Order ID
            reason: Rejection reason

        Returns:
            Updated order or None if not found
        """
        with self._lock:
            order = self.orders.get(order_id)
            if not order:
                self.logger.warning(f"Order not found for rejection: {order_id}")
                return None

            order.state = OrderState.REJECTED
            order.reject_reason = reason
            order.updated_at = datetime.now()

            # Persist to database and/or file
            self._persist_order_to_db(order)
            self._persist()

            if self.on_order_update is not None:
                self.on_order_update(order)

            self.logger.warning(f"Order rejected: {order_id} - {reason}")
            return order

    def cancel_order(self, order_id: str) -> bool:
        """
        Request order cancellation.

        Args:
            order_id: Order ID

        Returns:
            True if cancel request submitted
        """
        with self._lock:
            order = self.orders.get(order_id)
            if not order:
                self.logger.warning(f"Order not found: {order_id}")
                return False

            if order.is_terminal:
                self.logger.warning(f"Cannot cancel terminal order: {order_id}")
                return False

            order.state = OrderState.PENDING_CANCEL
            order.updated_at = datetime.now()

            # Persist to database and/or file
            self._persist_order_to_db(order)
            self._persist()

            if self.on_order_update is not None:
                self.on_order_update(order)

            self.logger.info(f"Cancel requested: {order_id}")
            return True

    def confirm_cancel(self, order_id: str) -> Optional[Order]:
        """
        Confirm order cancellation.

        Args:
            order_id: Order ID

        Returns:
            Updated order or None if not found
        """
        return self.update_order_state(order_id, OrderState.CANCELLED)

    def cancel_all_orders(self) -> int:
        """
        Cancel all active orders.

        Returns:
            Number of orders cancelled
        """
        count = 0
        with self._lock:
            for order_id, order in self.orders.items():
                if order.is_active:
                    if self.cancel_order(order_id):
                        count += 1
        return count

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""
        return self.orders.get(order_id)

    def get_order_by_client_id(self, client_order_id: str) -> Optional[Order]:
        """Get order by client order ID"""
        order_id = self._idempotency_keys.get(client_order_id)
        return self.orders.get(order_id) if order_id else None

    def get_open_orders(self) -> List[Order]:
        """Get all active orders"""
        return [o for o in self.orders.values() if o.is_active]

    def get_orders_by_symbol(self, symbol: str) -> List[Order]:
        """Get orders for a symbol"""
        return [o for o in self.orders.values() if o.symbol == symbol]

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol"""
        return self.positions.get(symbol)

    def get_all_positions(self) -> Dict[str, Position]:
        """Get all positions"""
        return self.positions.copy()

    def reconcile(self, broker_positions: Dict[str, float]) -> List[Discrepancy]:
        """
        Reconcile local positions with broker positions.

        Triggers alerts if discrepancies exceed threshold.

        Args:
            broker_positions: Dict of symbol -> quantity from broker

        Returns:
            List of discrepancies
        """
        discrepancies = []
        critical_discrepancies = []

        with self._lock:
            # Check all broker positions
            for symbol, broker_qty in broker_positions.items():
                local_pos = self.positions.get(symbol)
                local_qty = local_pos.quantity if local_pos else 0.0

                if abs(broker_qty - local_qty) > 0.0001:
                    discrepancy = Discrepancy(
                        symbol=symbol,
                        local_quantity=local_qty,
                        broker_quantity=broker_qty,
                        difference=broker_qty - local_qty,
                    )
                    discrepancies.append(discrepancy)
                    self.logger.warning(
                        f"Position mismatch: {symbol} - "
                        f"local={local_qty}, broker={broker_qty}"
                    )

                    # Check if discrepancy exceeds alert threshold
                    max_qty = max(abs(local_qty), abs(broker_qty))
                    if max_qty > 0:
                        discrepancy_pct = abs(discrepancy.difference) / max_qty
                        if discrepancy_pct >= self.alert_threshold_pct:
                            critical_discrepancies.append(discrepancy)

            # Check for positions we have but broker doesn't
            for symbol, pos in self.positions.items():
                if symbol not in broker_positions and abs(pos.quantity) > 0.0001:
                    discrepancy = Discrepancy(
                        symbol=symbol,
                        local_quantity=pos.quantity,
                        broker_quantity=0.0,
                        difference=-pos.quantity,
                    )
                    discrepancies.append(discrepancy)
                    self.logger.warning(
                        f"Position exists locally but not at broker: {symbol}"
                    )

                    # Missing position is always critical
                    critical_discrepancies.append(discrepancy)

        # Trigger alerts for critical discrepancies
        if critical_discrepancies and self.on_alert is not None:
            for discrepancy in critical_discrepancies:
                alert_data = {
                    "type": "position_mismatch",
                    "symbol": discrepancy.symbol,
                    "local_quantity": discrepancy.local_quantity,
                    "broker_quantity": discrepancy.broker_quantity,
                    "difference": discrepancy.difference,
                    "discrepancy_pct": (
                        abs(discrepancy.difference)
                        / max(
                            abs(discrepancy.local_quantity),
                            abs(discrepancy.broker_quantity),
                            0.0001,
                        )
                        if max(
                            abs(discrepancy.local_quantity),
                            abs(discrepancy.broker_quantity),
                        )
                        > 0
                        else 1.0
                    ),
                    "all_discrepancies": [d.to_dict() for d in discrepancies],
                }
                try:
                    self.on_alert("position_mismatch", alert_data)
                except Exception as e:
                    self.logger.error(f"Error in alert callback: {e}", exc_info=True)

        # Increment reconciliation error counter if discrepancies found
        if discrepancies:
            oms_reconciliation_errors.inc()

        return discrepancies

    def sync_positions(self, broker_positions: Dict[str, float]) -> None:
        """
        Sync local positions with broker positions.

        Overwrites local positions with broker state.
        Use with caution.

        Args:
            broker_positions: Dict of symbol -> quantity from broker
        """
        with self._lock:
            self.positions.clear()

            for symbol, quantity in broker_positions.items():
                if abs(quantity) > 0.0001:
                    self.positions[symbol] = Position(
                        symbol=symbol,
                        quantity=quantity,
                        average_price=0.0,  # Unknown after sync
                    )

            self._persist()
            self.logger.info(f"Positions synced: {len(self.positions)} positions")

    def _validate_order(self, order: Order) -> None:
        """Validate order before submission"""
        if not order.symbol:
            raise ValueError("Order must have a symbol")
        if order.quantity <= 0:
            raise ValueError("Order quantity must be positive")
        if order.side not in ("BUY", "SELL"):
            raise ValueError("Order side must be BUY or SELL")

    def _update_position(self, order: Order, fill: Fill) -> None:
        """Update position based on fill"""
        symbol = order.symbol

        # Get or create position
        position = self.positions.get(symbol)
        if not position:
            position = Position(symbol=symbol, quantity=0.0, average_price=0.0)
            self.positions[symbol] = position

        # Update quantity
        delta = fill.quantity if order.side == "BUY" else -fill.quantity
        old_qty = position.quantity
        new_qty = old_qty + delta

        # Update average price for opening trades
        if (old_qty >= 0 and delta > 0) or (old_qty <= 0 and delta < 0):
            # Adding to position
            if abs(new_qty) > 0.0001:
                old_value = abs(old_qty) * position.average_price
                new_value = abs(delta) * fill.price
                position.average_price = (old_value + new_value) / abs(new_qty)
        elif abs(new_qty) < abs(old_qty):
            # Reducing position - calculate realized P&L
            closed_qty = min(abs(delta), abs(old_qty))
            if old_qty > 0:
                # Closing long
                realized = closed_qty * (fill.price - position.average_price)
            else:
                # Closing short
                realized = closed_qty * (position.average_price - fill.price)
            position.realized_pnl += realized

        position.quantity = new_qty

        # Remove flat positions
        if abs(position.quantity) < 0.0001:
            position.quantity = 0.0

        if self.on_position_update is not None:
            self.on_position_update(position)

    def _persist(self) -> None:
        """Persist state to file/database"""
        if self.persistence_path:
            try:
                state = {
                    "orders": {k: v.to_dict() for k, v in self.orders.items()},
                    "positions": {k: v.to_dict() for k, v in self.positions.items()},
                    "idempotency_keys": self._idempotency_keys,
                }
                self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.persistence_path, "w") as f:
                    json.dump(state, f, indent=2)
            except Exception as e:
                self.logger.error(f"Failed to persist OMS state: {e}")

    def _load_state(self) -> None:
        """Load state from file"""
        if self.persistence_path and self.persistence_path.exists():
            try:
                with open(self.persistence_path, "r") as f:
                    state = json.load(f)

                for order_id, order_data in state.get("orders", {}).items():
                    self.orders[order_id] = Order.from_dict(order_data)

                for symbol, pos_data in state.get("positions", {}).items():
                    self.positions[symbol] = Position(**pos_data)

                self._idempotency_keys = state.get("idempotency_keys", {})

                self.logger.info(
                    f"Loaded OMS state: {len(self.orders)} orders, "
                    f"{len(self.positions)} positions"
                )
            except Exception as e:
                self.logger.error(f"Failed to load OMS state: {e}")

    def _persist_order_to_db(self, order: Order) -> None:
        """Persist order to database"""
        if not self.db:
            return

        try:
            # Convert state enum to database value
            state_value = (
                order.state.value.upper()
                if hasattr(order.state, "value")
                else str(order.state).upper()
            )

            # Prepare metadata JSON
            metadata_json = json.dumps(order.metadata) if order.metadata else None

            # Extract account_login from account_id or metadata
            account_login = None
            if hasattr(order, "account_id") and order.account_id:
                # Try to extract from account_id if it's a number
                try:
                    account_login = int(order.account_id)
                except (ValueError, TypeError):
                    pass

            # If not found, try metadata
            if account_login is None and order.metadata:
                account_login = order.metadata.get("account_login")

            # Default to 0 if still not found (for testing)
            if account_login is None:
                account_login = 0

            # Insert or update order (PostgreSQL ON CONFLICT syntax)
            query = """
                INSERT INTO orders (
                    id, client_order_id, experiment_id, account_login, symbol, side, order_type,
                    quantity, price, stop_loss, take_profit, state, filled_quantity,
                    average_fill_price, broker_order_id, reject_reason, metadata, created_at, updated_at
                ) VALUES (
                    :id, :client_order_id, :experiment_id, :account_login, :symbol, :side, :order_type,
                    :quantity, :price, :stop_loss, :take_profit, :state, :filled_quantity,
                    :average_fill_price, :broker_order_id, :reject_reason, :metadata, :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    state = EXCLUDED.state,
                    filled_quantity = EXCLUDED.filled_quantity,
                    average_fill_price = EXCLUDED.average_fill_price,
                    broker_order_id = EXCLUDED.broker_order_id,
                    reject_reason = EXCLUDED.reject_reason,
                    updated_at = EXCLUDED.updated_at
            """

            params = {
                "id": order.order_id,
                "client_order_id": order.client_order_id or None,
                "experiment_id": None,  # experiment_id (will be set in Phase 3)
                "account_login": account_login,
                "symbol": order.symbol,
                "side": order.side,
                "order_type": order.order_type,
                "quantity": float(order.quantity),
                "price": float(order.price) if order.price else None,
                "stop_loss": float(order.stop_loss) if order.stop_loss else None,
                "take_profit": float(order.take_profit) if order.take_profit else None,
                "state": state_value,
                "filled_quantity": float(order.filled_quantity),
                "average_fill_price": float(order.average_fill_price),
                "broker_order_id": order.broker_order_id,
                "reject_reason": order.reject_reason,
                "metadata": metadata_json,
                "created_at": order.created_at,
                "updated_at": order.updated_at,
            }

            with self.db.execute_query() as conn:
                conn.execute(text(query), params)

        except Exception as e:
            self.logger.error(
                f"Failed to persist order to database: {e}", exc_info=True
            )
            # Don't raise - allow fallback to file persistence

    def _load_from_db(self) -> None:
        """Load orders from database"""
        if not self.db:
            return

        try:
            # Load all non-terminal orders
            query = """
                SELECT id, client_order_id, experiment_id, account_login, symbol, side, order_type,
                       quantity, price, stop_loss, take_profit, state, filled_quantity,
                       average_fill_price, broker_order_id, reject_reason, metadata,
                       created_at, updated_at
                FROM orders
                WHERE state NOT IN ('FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED')
                ORDER BY created_at DESC
            """

            results = self.db.execute_with_result(query)

            for row in results:
                try:
                    # Parse metadata
                    metadata = {}
                    if row[16]:  # metadata column
                        try:
                            metadata = json.loads(row[16])
                        except (json.JSONDecodeError, TypeError):
                            pass

                    # Create order object
                    order = Order(
                        order_id=row[0],
                        client_order_id=row[1] or "",
                        symbol=row[4],
                        side=row[5],
                        order_type=row[6] or "MARKET",
                        quantity=float(row[7]),
                        price=float(row[8]) if row[8] else None,
                        stop_loss=float(row[9]) if row[9] else None,
                        take_profit=float(row[10]) if row[10] else None,
                        state=OrderState(row[11].lower()),
                        filled_quantity=float(row[12]),
                        average_fill_price=float(row[13]) if row[13] else 0.0,
                        broker_order_id=row[14],
                        reject_reason=row[15],
                        created_at=(
                            row[17]
                            if isinstance(row[17], datetime)
                            else datetime.fromisoformat(str(row[17]))
                        ),
                        updated_at=(
                            row[18]
                            if isinstance(row[18], datetime)
                            else datetime.fromisoformat(str(row[18]))
                        ),
                        metadata=metadata,
                    )

                    # Store order
                    self.orders[order.order_id] = order

                    # Store idempotency key
                    if order.client_order_id:
                        self._idempotency_keys[order.client_order_id] = order.order_id

                except Exception as e:
                    self.logger.warning(f"Failed to load order {row[0]}: {e}")
                    continue

            # Reconstruct positions from filled orders
            self._reconstruct_positions_from_db()

            self.logger.info(
                f"Loaded {len(self.orders)} orders from database, "
                f"{len(self.positions)} positions reconstructed"
            )

        except Exception as e:
            self.logger.error(
                f"Failed to load orders from database: {e}", exc_info=True
            )
            raise

    def _reconstruct_positions_from_db(self) -> None:
        """Reconstruct positions from filled orders in database"""
        try:
            # Get all filled orders grouped by symbol
            query = """
                SELECT symbol, side, filled_quantity, average_fill_price
                FROM orders
                WHERE state = 'FILLED' AND filled_quantity > 0
                ORDER BY updated_at DESC
            """

            results = self.db.execute_with_result(query)

            for row in results:
                symbol, side, filled_qty, avg_price = row

                if symbol not in self.positions:
                    self.positions[symbol] = Position(
                        symbol=symbol, quantity=0.0, average_price=0.0
                    )

                position = self.positions[symbol]

                # Update quantity (positive for BUY, negative for SELL)
                delta = float(filled_qty) if side == "BUY" else -float(filled_qty)
                position.quantity += delta

                # Update average price if we're adding to position
                if abs(position.quantity) > 0.0001:
                    # Simplified: use the latest average fill price
                    # In production, you'd want to recalculate properly
                    position.average_price = (
                        float(avg_price) if avg_price else position.average_price
                    )

        except Exception as e:
            self.logger.warning(f"Failed to reconstruct positions from database: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get OMS statistics"""
        with self._lock:
            active_orders = [o for o in self.orders.values() if o.is_active]
            filled_orders = [
                o for o in self.orders.values() if o.state == OrderState.FILLED
            ]

            return {
                "total_orders": len(self.orders),
                "active_orders": len(active_orders),
                "filled_orders": len(filled_orders),
                "rejected_orders": sum(
                    1 for o in self.orders.values() if o.state == OrderState.REJECTED
                ),
                "total_positions": len(self.positions),
                "long_positions": sum(
                    1 for p in self.positions.values() if p.quantity > 0
                ),
                "short_positions": sum(
                    1 for p in self.positions.values() if p.quantity < 0
                ),
                "total_realized_pnl": sum(
                    p.realized_pnl for p in self.positions.values()
                ),
            }
