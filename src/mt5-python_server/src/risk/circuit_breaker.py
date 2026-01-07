"""
Circuit Breaker Module

Automatic trading halt based on loss, volatility, error rate, and latency thresholds.
Implements the circuit breaker pattern for trading systems.

States:
- CLOSED: Normal operation, trading allowed
- OPEN: Trading halted due to threshold breach
- HALF_OPEN: Testing recovery, limited trading allowed
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque
from typing import Optional, Dict, List, Any
import threading
import logging
import numpy as np

from monitoring.metrics import circuit_breaker_state


class CircuitBreakerState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Trading halted
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker thresholds"""

    # Loss thresholds
    max_loss_per_hour_pct: float = 0.03  # 3% loss per hour
    max_loss_per_day_pct: float = 0.05  # 5% loss per day

    # Volatility thresholds
    max_volatility_multiple: float = 3.0  # 3x normal volatility
    volatility_lookback_hours: int = 24
    baseline_volatility: float = 0.01  # 1% baseline

    # Error thresholds
    max_error_rate: float = 0.10  # 10% error rate
    error_window_minutes: int = 5
    min_operations_for_error_rate: int = 10  # Min operations before checking

    # Latency thresholds
    max_latency_ms: int = 1000  # 1 second
    latency_window_minutes: int = 5

    # Recovery
    cooldown_minutes: int = 30
    auto_reset: bool = False  # Require manual reset by default
    half_open_max_trades: int = 3  # Max trades in half-open state


@dataclass
class CircuitBreakerMetrics:
    """Tracked metrics for circuit breaker decisions"""

    hourly_pnl: float = 0.0
    daily_pnl: float = 0.0
    starting_balance: float = 0.0
    hourly_start_balance: float = 0.0
    daily_start_balance: float = 0.0
    current_volatility: float = 0.0
    error_count: int = 0
    operation_count: int = 0
    avg_latency_ms: float = 0.0
    last_trade_time: Optional[datetime] = None
    trip_time: Optional[datetime] = None
    trip_reason: Optional[str] = None


class CircuitBreaker:
    """
    Circuit breaker for trading systems.

    Monitors trading activity and automatically halts trading when
    thresholds are breached to prevent excessive losses.

    Usage:
        config = CircuitBreakerConfig(max_loss_per_hour_pct=0.02)
        cb = CircuitBreaker(config)
        cb.initialize(starting_balance=10000.0)

        # Before each trade:
        can_trade, reason = cb.check()
        if not can_trade:
            print(f"Trading blocked: {reason}")

        # After each trade:
        cb.record_trade(pnl=50.0)

        # On errors:
        cb.record_error(exception)
    """

    def __init__(
        self,
        config: Optional[CircuitBreakerConfig] = None,
        database: Any = None,
        price_history_provider: Any = None,
    ):
        """
        Initialize circuit breaker.

        Args:
            config: Configuration thresholds (uses defaults if None)
            database: Database connection for persistence (optional)
            price_history_provider: Callable that returns price history dict (optional)
                Should return Dict[str, List[float]] where key is symbol and value is price list
        """
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState.CLOSED
        self._metrics = CircuitBreakerMetrics()
        self._lock = threading.RLock()
        self.database = database
        self.price_history_provider = price_history_provider

        # Initialize metrics
        self._update_circuit_breaker_metrics()

        # Rolling windows for metrics
        self._trade_history: deque = deque(maxlen=1000)
        self._error_history: deque = deque(maxlen=100)
        self._latency_history: deque = deque(maxlen=100)
        self._volatility_history: deque = deque(maxlen=1000)

        # Half-open state tracking
        self._half_open_trades = 0

        # Track last trip event ID for database updates
        self._last_trip_event_id: Optional[int] = None

        self.logger = logging.getLogger(__name__)

    @property
    def state(self) -> CircuitBreakerState:
        """Current circuit breaker state"""
        return self._state

    def initialize(self, starting_balance: float) -> None:
        """
        Initialize with starting balance.

        Args:
            starting_balance: Account starting balance
        """
        with self._lock:
            self._metrics.starting_balance = starting_balance
            self._metrics.hourly_start_balance = starting_balance
            self._metrics.daily_start_balance = starting_balance
            self._reset_windows()
            self.logger.info(
                f"CircuitBreaker initialized with balance: {starting_balance}"
            )

    def check(self) -> tuple[bool, Optional[str]]:
        """
        Check if trading is allowed.

        Returns:
            (can_trade, reason) - reason is None if can trade
        """
        with self._lock:
            # If open, check for recovery
            if self._state == CircuitBreakerState.OPEN:
                if self._should_attempt_recovery():
                    self._state = CircuitBreakerState.HALF_OPEN
                    self._half_open_trades = 0
                    self._update_circuit_breaker_metrics()
                    self.logger.info("Circuit breaker entering HALF_OPEN state")
                else:
                    return False, f"Circuit breaker OPEN: {self._metrics.trip_reason}"

            # If half-open, check trade count
            if self._state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_trades >= self.config.half_open_max_trades:
                    return False, "Half-open trade limit reached"

            # Check all conditions
            checks = [
                self._check_hourly_loss(),
                self._check_daily_loss(),
                self._check_volatility(),
                self._check_error_rate(),
                self._check_latency(),
            ]

            for can_trade, reason in checks:
                if not can_trade:
                    if reason is not None:
                        self._trip(reason)
                    return False, reason

            return True, None

    def record_trade(self, pnl: float, balance: Optional[float] = None) -> None:
        """
        Record a completed trade.

        Args:
            pnl: Profit/loss from the trade
            balance: Current balance (optional, for recalculating losses)
        """
        with self._lock:
            now = datetime.now()

            self._trade_history.append({"timestamp": now, "pnl": pnl})

            self._metrics.hourly_pnl += pnl
            self._metrics.daily_pnl += pnl
            self._metrics.last_trade_time = now
            self._metrics.operation_count += 1

            # Update balances if provided
            if balance is not None:
                self._metrics.starting_balance = max(
                    self._metrics.starting_balance, balance
                )

            # If in half-open, track trade
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._half_open_trades += 1

                # Successful trades in half-open -> close circuit
                if (
                    pnl >= 0
                    and self._half_open_trades >= self.config.half_open_max_trades
                ):
                    self._close()

            self._cleanup_old_data()

    def record_error(self, error: Optional[Exception] = None) -> None:
        """
        Record an error occurrence.

        Args:
            error: The exception that occurred
        """
        with self._lock:
            self._error_history.append(
                {
                    "timestamp": datetime.now(),
                    "error": str(error) if error else "Unknown error",
                }
            )
            self._metrics.error_count += 1
            self._metrics.operation_count += 1

    def record_latency(self, latency_ms: float) -> None:
        """
        Record operation latency.

        Args:
            latency_ms: Latency in milliseconds
        """
        with self._lock:
            self._latency_history.append(
                {"timestamp": datetime.now(), "latency_ms": latency_ms}
            )

            # Update average
            if self._latency_history:
                total = sum(entry["latency_ms"] for entry in self._latency_history)
                self._metrics.avg_latency_ms = total / len(self._latency_history)

    def record_volatility(
        self,
        volatility: Optional[float] = None,
        price_history: Optional[List[float]] = None,
    ) -> None:
        """
        Record current volatility.

        If volatility is not provided, calculates it from price_history.
        If price_history is not provided, uses stored volatility history.

        Args:
            volatility: Current volatility measure (optional)
            price_history: List of prices to calculate volatility from (optional)
        """
        with self._lock:
            # Calculate volatility from price history if not provided
            if volatility is None:
                if price_history and len(price_history) >= 2:
                    volatility = self._calculate_volatility_from_prices(price_history)
                elif len(self._volatility_history) > 0:
                    # Use most recent volatility
                    volatility = self._volatility_history[-1]["volatility"]
                else:
                    # No data available
                    return

            self._volatility_history.append(
                {"timestamp": datetime.now(), "volatility": volatility}
            )
            self._metrics.current_volatility = volatility

    def _calculate_volatility_from_prices(self, prices: List[float]) -> float:
        """
        Calculate volatility (standard deviation of returns) from price history.

        Args:
            prices: List of prices

        Returns:
            Volatility as decimal (e.g., 0.01 = 1%)
        """
        if len(prices) < 2:
            return 0.0

        # Calculate returns
        returns = []
        for i in range(1, len(prices)):
            if prices[i - 1] > 0:
                ret = (prices[i] - prices[i - 1]) / prices[i - 1]
                returns.append(ret)

        if len(returns) < 2:
            return 0.0

        # Calculate standard deviation of returns (volatility)
        volatility = np.std(returns)

        return float(volatility)

    def trip(self, reason: str) -> None:
        """
        Manually trip the circuit breaker.

        Args:
            reason: Reason for tripping
        """
        self._trip(reason)

    def reset(self, manual: bool = False) -> bool:
        """
        Reset the circuit breaker.

        Args:
            manual: True if manual reset, False if automatic

        Returns:
            True if reset successful
        """
        with self._lock:
            if self._state == CircuitBreakerState.CLOSED:
                return True

            if not self.config.auto_reset and not manual:
                self.logger.warning("Auto-reset disabled, manual reset required")
                return False

            self._close()
            return True

    def reset_daily(self, balance: float) -> None:
        """
        Reset daily tracking (call at start of trading day).

        Args:
            balance: Current balance
        """
        with self._lock:
            self._metrics.daily_pnl = 0.0
            self._metrics.daily_start_balance = balance
            self.logger.info(f"Daily reset - balance: {balance}")

    def reset_hourly(self, balance: float) -> None:
        """
        Reset hourly tracking.

        Args:
            balance: Current balance
        """
        with self._lock:
            self._metrics.hourly_pnl = 0.0
            self._metrics.hourly_start_balance = balance

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        with self._lock:
            return {
                "state": self._state.value,
                "hourly_pnl": self._metrics.hourly_pnl,
                "daily_pnl": self._metrics.daily_pnl,
                "hourly_loss_pct": self._calculate_hourly_loss_pct(),
                "daily_loss_pct": self._calculate_daily_loss_pct(),
                "current_volatility": self._metrics.current_volatility,
                "error_rate": self._calculate_error_rate(),
                "avg_latency_ms": self._metrics.avg_latency_ms,
                "operation_count": self._metrics.operation_count,
                "trip_reason": self._metrics.trip_reason,
                "trip_time": (
                    self._metrics.trip_time.isoformat()
                    if self._metrics.trip_time
                    else None
                ),
            }

    def _trip(self, reason: str) -> None:
        """Internal method to trip the circuit breaker"""
        if self._state == CircuitBreakerState.OPEN:
            return

        self._state = CircuitBreakerState.OPEN
        self._metrics.trip_time = datetime.now()
        self._metrics.trip_reason = reason
        self._update_circuit_breaker_metrics()

        # Determine breaker type from reason
        breaker_type = self._extract_breaker_type(reason)
        trigger_value, threshold_value = self._extract_values(reason, breaker_type)

        # Log to database
        self._log_trip_to_database(breaker_type, trigger_value, threshold_value, reason)

        self.logger.warning(f"⚡ Circuit breaker TRIPPED: {reason}")

    def _close(self) -> None:
        """Internal method to close the circuit breaker"""
        # Update database with resume timestamp before clearing metrics
        if self._last_trip_event_id:
            self._update_database_resume()

        self._state = CircuitBreakerState.CLOSED
        self._metrics.trip_time = None
        self._metrics.trip_reason = None
        self._half_open_trades = 0
        self._last_trip_event_id = None
        self._update_circuit_breaker_metrics()
        self.logger.info("Circuit breaker CLOSED - normal operation resumed")

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed for recovery attempt"""
        if not self._metrics.trip_time:
            return True

        cooldown = timedelta(minutes=self.config.cooldown_minutes)
        return datetime.now() - self._metrics.trip_time >= cooldown

    def _check_hourly_loss(self) -> tuple[bool, Optional[str]]:
        """Check hourly loss threshold"""
        loss_pct = self._calculate_hourly_loss_pct()
        if loss_pct > self.config.max_loss_per_hour_pct:
            return (
                False,
                f"Hourly loss exceeded: {loss_pct:.2%} > {self.config.max_loss_per_hour_pct:.2%}",
            )
        return True, None

    def _check_daily_loss(self) -> tuple[bool, Optional[str]]:
        """Check daily loss threshold"""
        loss_pct = self._calculate_daily_loss_pct()
        if loss_pct > self.config.max_loss_per_day_pct:
            return (
                False,
                f"Daily loss exceeded: {loss_pct:.2%} > {self.config.max_loss_per_day_pct:.2%}",
            )
        return True, None

    def _check_volatility(self) -> tuple[bool, Optional[str]]:
        """Check volatility threshold"""
        # Try to get current volatility from price history if not set
        if self._metrics.current_volatility <= 0 and self.price_history_provider:
            try:
                price_histories = self.price_history_provider()
                if price_histories:
                    # Calculate volatility from all available price histories
                    all_volatilities = []
                    for symbol, prices in price_histories.items():
                        if len(prices) >= 2:
                            vol = self._calculate_volatility_from_prices(prices)
                            if vol > 0:
                                all_volatilities.append(vol)

                    if all_volatilities:
                        # Use average volatility across all symbols
                        avg_volatility = float(np.mean(all_volatilities))
                        self.record_volatility(volatility=avg_volatility)
            except Exception as e:
                self.logger.warning(
                    f"Failed to calculate volatility from price history: {e}"
                )

        if self._metrics.current_volatility <= 0:
            return True, None

        vol_multiple = (
            self._metrics.current_volatility / self.config.baseline_volatility
        )
        if vol_multiple > self.config.max_volatility_multiple:
            return False, f"Volatility spike: {vol_multiple:.1f}x normal"
        return True, None

    def _check_error_rate(self) -> tuple[bool, Optional[str]]:
        """Check error rate threshold"""
        error_rate = self._calculate_error_rate()
        if (
            self._metrics.operation_count >= self.config.min_operations_for_error_rate
            and error_rate > self.config.max_error_rate
        ):
            return (
                False,
                f"Error rate exceeded: {error_rate:.2%} > {self.config.max_error_rate:.2%}",
            )
        return True, None

    def _check_latency(self) -> tuple[bool, Optional[str]]:
        """Check latency threshold"""
        if self._metrics.avg_latency_ms > self.config.max_latency_ms:
            return (
                False,
                f"High latency: {self._metrics.avg_latency_ms:.0f}ms > {self.config.max_latency_ms}ms",
            )
        return True, None

    def _calculate_hourly_loss_pct(self) -> float:
        """Calculate hourly loss percentage"""
        if self._metrics.hourly_start_balance <= 0:
            return 0.0
        return max(0, -self._metrics.hourly_pnl / self._metrics.hourly_start_balance)

    def _calculate_daily_loss_pct(self) -> float:
        """Calculate daily loss percentage"""
        if self._metrics.daily_start_balance <= 0:
            return 0.0
        return max(0, -self._metrics.daily_pnl / self._metrics.daily_start_balance)

    def _calculate_error_rate(self) -> float:
        """Calculate error rate in recent window"""
        if self._metrics.operation_count == 0:
            return 0.0

        now = datetime.now()
        window = timedelta(minutes=self.config.error_window_minutes)
        recent_errors = sum(
            1 for e in self._error_history if now - e["timestamp"] <= window
        )
        recent_ops = max(1, self._metrics.operation_count)

        return recent_errors / recent_ops

    def _reset_windows(self) -> None:
        """Reset all rolling windows"""
        self._trade_history.clear()
        self._error_history.clear()
        self._latency_history.clear()
        self._volatility_history.clear()

    def _cleanup_old_data(self) -> None:
        """Remove old data from rolling windows"""
        now = datetime.now()

        # Keep only last hour of trades
        hour_ago = now - timedelta(hours=1)
        while self._trade_history and self._trade_history[0]["timestamp"] < hour_ago:
            self._trade_history.popleft()

        # Keep only recent errors
        error_window = now - timedelta(minutes=self.config.error_window_minutes)
        while (
            self._error_history and self._error_history[0]["timestamp"] < error_window
        ):
            self._error_history.popleft()

        # Keep only recent latency
        latency_window = now - timedelta(minutes=self.config.latency_window_minutes)
        while (
            self._latency_history
            and self._latency_history[0]["timestamp"] < latency_window
        ):
            self._latency_history.popleft()

    def _extract_breaker_type(self, reason: str) -> str:
        """Extract breaker type from reason string"""
        reason_lower = reason.lower()
        if "hourly loss" in reason_lower or "loss per hour" in reason_lower:
            return "hourly_loss"
        elif "daily loss" in reason_lower or "loss per day" in reason_lower:
            return "daily_loss"
        elif "volatility" in reason_lower:
            return "volatility"
        elif "error rate" in reason_lower or "error" in reason_lower:
            return "error_rate"
        elif "latency" in reason_lower:
            return "latency"
        else:
            return "unknown"

    def _extract_values(
        self, reason: str, breaker_type: str
    ) -> tuple[Optional[float], Optional[float]]:
        """Extract trigger value and threshold value from reason string"""
        trigger_value = None
        threshold_value = None

        try:
            if breaker_type == "hourly_loss":
                # Extract from reason like "Hourly loss exceeded: 3.50% > 3.00%"
                import re

                match = re.search(r"(\d+\.?\d*)%", reason)
                if match:
                    trigger_value = float(match.group(1)) / 100
                match = re.search(r">\s*(\d+\.?\d*)%", reason)
                if match:
                    threshold_value = float(match.group(1)) / 100
            elif breaker_type == "daily_loss":
                # Similar pattern
                import re

                match = re.search(r"(\d+\.?\d*)%", reason)
                if match:
                    trigger_value = float(match.group(1)) / 100
                match = re.search(r">\s*(\d+\.?\d*)%", reason)
                if match:
                    threshold_value = float(match.group(1)) / 100
            elif breaker_type == "volatility":
                # Extract from reason like "Volatility spike: 3.0x normal"
                import re

                match = re.search(r"(\d+\.?\d*)x", reason)
                if match:
                    trigger_value = float(match.group(1))
                    threshold_value = self.config.max_volatility_multiple
            elif breaker_type == "error_rate":
                # Extract from reason like "Error rate exceeded: 15.00% > 10.00%"
                import re

                match = re.search(r"(\d+\.?\d*)%", reason)
                if match:
                    trigger_value = float(match.group(1)) / 100
                match = re.search(r">\s*(\d+\.?\d*)%", reason)
                if match:
                    threshold_value = float(match.group(1)) / 100
            elif breaker_type == "latency":
                # Extract from reason like "High latency: 1500ms > 1000ms"
                import re

                match = re.search(r"(\d+)ms", reason)
                if match:
                    trigger_value = float(match.group(1))
                match = re.search(r">\s*(\d+)ms", reason)
                if match:
                    threshold_value = float(match.group(1))
        except Exception as e:
            self.logger.warning(f"Failed to extract values from reason: {e}")

        return trigger_value, threshold_value

    def _log_trip_to_database(
        self,
        breaker_type: str,
        trigger_value: Optional[float],
        threshold_value: Optional[float],
        reason: str,
    ) -> None:
        """Log circuit breaker trip to database"""
        if not self.database:
            return

        try:
            conn = self.database.get_connection()
            cursor = conn.cursor()

            query = """
                INSERT INTO circuit_breaker_events (
                    breaker_type, trigger_value, threshold_value, trip_reason, created_at, resumed_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """

            cursor.execute(
                query,
                (
                    breaker_type,
                    trigger_value or 0.0,
                    threshold_value or 0.0,
                    reason,
                    datetime.now(),
                    None,
                ),
            )

            # Store the event ID for later resume update
            self._last_trip_event_id = cursor.lastrowid

            conn.commit()
            cursor.close()
            conn.close()

            self.logger.debug(
                f"Logged circuit breaker trip to database: {breaker_type}"
            )

        except Exception as e:
            self.logger.error(
                f"Failed to log circuit breaker trip to database: {e}", exc_info=True
            )
            # Don't raise - allow operation to continue

    def _update_database_resume(self) -> None:
        """Update database with circuit breaker resume timestamp"""
        if not self.database or not self._last_trip_event_id:
            return

        try:
            conn = self.database.get_connection()
            cursor = conn.cursor()

            query = """
                UPDATE circuit_breaker_events
                SET resumed_at = ?
                WHERE id = ?
            """

            cursor.execute(query, (datetime.now(), self._last_trip_event_id))

            conn.commit()
            cursor.close()
            conn.close()

            self.logger.debug("Updated circuit breaker resume in database")

        except Exception as e:
            self.logger.error(
                f"Failed to update circuit breaker resume in database: {e}",
                exc_info=True,
            )
            # Don't raise - allow operation to continue

    def _update_circuit_breaker_metrics(self) -> None:
        """Update circuit breaker state metrics"""
        # Reset all state gauges to 0
        circuit_breaker_state.labels(state="closed").set(0)
        circuit_breaker_state.labels(state="open").set(0)
        circuit_breaker_state.labels(state="half_open").set(0)

        # Set current state to 1
        state_value = self._state.value
        circuit_breaker_state.labels(state=state_value).set(1)
