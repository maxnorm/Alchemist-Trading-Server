"""
Pre-Trade Controls Module

Comprehensive pre-trade validation before order execution.
Implements exposure limits, throttle controls, leverage validation,
market hours, and feed quality checks.
"""

from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta
from models.account import Account
from utils.risk_management import RiskManager


class PreTradeControls:
    """Comprehensive pre-trade validation before order execution"""

    def __init__(
        self,
        max_total_exposure_pct: float = 0.30,  # Max 30% total exposure
        max_trades_per_minute: int = 3,
        max_trades_per_hour: int = 20,
        max_leverage: float = 100.0,
        trading_hours_start: int = 0,  # 00:00 UTC
        trading_hours_end: int = 24,  # 24:00 UTC
    ):
        """
        Initialize pre-trade controls

        :param max_total_exposure_pct: Maximum total exposure as percentage of account balance
        :param max_trades_per_minute: Maximum number of trades per minute
        :param max_trades_per_hour: Maximum number of trades per hour
        :param max_leverage: Maximum leverage allowed
        :param trading_hours_start: Start hour for trading (UTC, 0-23)
        :param trading_hours_end: End hour for trading (UTC, 0-23)
        """
        self.max_total_exposure_pct = max_total_exposure_pct
        self.max_trades_per_minute = max_trades_per_minute
        self.max_trades_per_hour = max_trades_per_hour
        self.max_leverage = max_leverage
        self.trading_hours_start = trading_hours_start
        self.trading_hours_end = trading_hours_end

        # Trade throttle tracking: List of (timestamp, action_type) tuples
        self.trade_timestamps: List[Tuple[datetime, str]] = []

    def validate_action(
        self,
        account: Account,
        pair: Any,  # CurrencyPair
        action_type: str,  # "BUY", "SELL", "CLOSE"
        risk_manager: RiskManager,
        current_positions: Dict[str, Any],
        feed_status: Dict[str, Any],
        entry_price: Optional[float] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Comprehensive pre-trade validation for an action

        :param account: Account object
        :param pair: Currency pair
        :param action_type: Action type ("BUY", "SELL", "CLOSE")
        :param risk_manager: Risk manager for position size calculation
        :param current_positions: Current open positions (account.current_trade)
        :param feed_status: Market feed status dictionary
        :param entry_price: Entry price (optional, will use pair.ask/bid if not provided)
        :return: Tuple of (is_valid, reason_if_invalid)
        """
        # For CLOSE actions, skip exposure and leverage checks
        if action_type == "CLOSE":
            checks = [
                self.check_throttle_limits(),
                self.check_market_hours(),
                self.check_feed_quality(feed_status),
            ]
        else:
            # Calculate order details for BUY/SELL
            if entry_price is None:
                # Use ask for BUY, bid for SELL
                entry_price = pair.ask if action_type == "BUY" else pair.bid

            # Calculate position size that would be used
            lot_size = risk_manager.calculate_position_size(
                account, pair, entry_price
            )

            if lot_size <= 0:
                return False, "Calculated position size is zero or negative"

            # Calculate order value (volume * price)
            contract_size = 100000  # Standard lot
            order_value = lot_size * entry_price * contract_size

            checks = [
                self.check_exposure_limits(
                    account, order_value, current_positions, pair
                ),
                self.check_throttle_limits(),
                self.check_leverage_limits(account, lot_size, entry_price),
                self.check_market_hours(),
                self.check_feed_quality(feed_status),
            ]

        # Run all checks
        for passed, reason in checks:
            if not passed:
                return False, reason

        return True, None

    def check_exposure_limits(
        self,
        account: Account,
        order_value: float,
        current_positions: Dict[str, Any],
        pair: Any,
    ) -> Tuple[bool, Optional[str]]:
        """Check total exposure across all positions"""
        # Calculate current exposure from open positions
        current_exposure = 0.0
        for trade in current_positions.values():
            # Get position value: volume * entry_price * contract_size
            volume = getattr(trade, "lotsize", None) or getattr(
                trade, "volume", 0.0
            )
            entry_price = getattr(trade, "open_price", None) or getattr(
                trade, "entry_price", 0.0
            )
            contract_size = 100000  # Standard lot
            current_exposure += volume * entry_price * contract_size

        # Calculate new exposure if order executes
        new_exposure = current_exposure + order_value

        # Check against account balance
        max_exposure = account.balance * self.max_total_exposure_pct

        if new_exposure > max_exposure:
            exposure_pct = (new_exposure / account.balance) * 100
            return False, (
                f"Total exposure limit exceeded: "
                f"{exposure_pct:.1f}% > {self.max_total_exposure_pct * 100:.1f}% "
                f"(current: {current_exposure:.2f}, new order: {order_value:.2f})"
            )

        return True, None

    def check_throttle_limits(self) -> Tuple[bool, Optional[str]]:
        """Check trade frequency limits"""
        now = datetime.now()

        # Clean old timestamps (older than 1 hour)
        self.trade_timestamps = [
            ts for ts in self.trade_timestamps
            if (now - ts[0]).total_seconds() < 3600
        ]

        # Check per-minute limit
        recent_minute = [
            ts for ts in self.trade_timestamps
            if (now - ts[0]).total_seconds() < 60
        ]
        if len(recent_minute) >= self.max_trades_per_minute:
            return False, (
                f"Trade throttle limit exceeded: "
                f"{len(recent_minute)} trades in last minute > {self.max_trades_per_minute}"
            )

        # Check per-hour limit
        if len(self.trade_timestamps) >= self.max_trades_per_hour:
            return False, (
                f"Trade throttle limit exceeded: "
                f"{len(self.trade_timestamps)} trades in last hour > {self.max_trades_per_hour}"
            )

        return True, None

    def record_trade(self, action_type: str):
        """Record trade execution for throttle tracking"""
        self.trade_timestamps.append((datetime.now(), action_type))

    def check_leverage_limits(
        self, account: Account, lot_size: float, entry_price: float
    ) -> Tuple[bool, Optional[str]]:
        """Check leverage limits"""
        # Calculate required margin
        contract_size = 100000  # Standard lot
        required_margin = (lot_size * entry_price * contract_size) / self.max_leverage

        # Check available margin
        margin_free = getattr(account, "margin_free", None)
        if margin_free is None:
            # Fallback: use balance if margin_free not available
            margin_free = account.balance

        if required_margin > margin_free:
            return False, (
                f"Insufficient margin: required={required_margin:.2f}, "
                f"available={margin_free:.2f}"
            )

        return True, None

    def check_market_hours(self) -> Tuple[bool, Optional[str]]:
        """Check if trading is allowed during current market hours"""
        now = datetime.utcnow()
        current_hour = now.hour

        # Handle wrap-around (e.g., 22:00-02:00)
        if self.trading_hours_start > self.trading_hours_end:
            # Trading hours span midnight (e.g., 22:00-02:00)
            is_allowed = (
                current_hour >= self.trading_hours_start
                or current_hour < self.trading_hours_end
            )
        else:
            # Normal case (e.g., 0:00-24:00)
            is_allowed = (
                self.trading_hours_start <= current_hour < self.trading_hours_end
            )

        if not is_allowed:
            return False, (
                f"Outside trading hours: {current_hour}:00 UTC "
                f"(allowed: {self.trading_hours_start}:00-{self.trading_hours_end}:00)"
            )

        return True, None

    def check_feed_quality(
        self, feed_status: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Check market feed quality before trading"""
        if not feed_status.get("ready", False):
            return False, "Market feed not ready"

        # Check for stale data
        # get_market_feed_status doesn't return max_staleness_seconds directly,
        # but we can check feed_live status
        feed_live = feed_status.get("feed_live", False)
        if not feed_live:
            return False, "Market feed not live"

        # If max_staleness_seconds is provided, check it
        max_staleness = feed_status.get("max_staleness_seconds", None)
        if max_staleness is not None and max_staleness > 300:  # 5 minutes
            return False, f"Market feed stale: {max_staleness:.0f} seconds"

        return True, None
