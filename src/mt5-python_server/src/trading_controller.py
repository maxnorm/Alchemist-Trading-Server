"""
Trading Controller
Main controller that integrates agent with environment for live trading

Includes safety mechanisms:
- Kill switch for emergency trading halt
- Circuit breaker for automatic risk-based halts
- Order Management System for order tracking
"""

import os
import time
import numpy as np
from typing import Optional, TYPE_CHECKING, Any
from agents.dqn_agent import DQNAgent
from environments.live_env import LiveTradingEnv
from utils.risk_management import RiskManager
from models.account import Account
from application.services.action_executor import ActionExecutor
from utils.market_utils import get_market_feed_status
from utils.logging_config import get_logger
import logging

# Import safety components
if TYPE_CHECKING:
    from risk import KillSwitch, CircuitBreaker, OrderManagementSystem


class TradingController:
    """
    Controller for live AI trading.

    Integrates safety mechanisms:
    - KillSwitch: Emergency stop that closes all positions
    - CircuitBreaker: Automatic halt on excessive loss/volatility
    - OMS: Order tracking and reconciliation
    """

    def __init__(
        self,
        agent: DQNAgent,
        environment: LiveTradingEnv,
        account: Account,
        risk_manager: RiskManager,
        trading_enabled: bool = False,
        kill_switch: Optional["KillSwitch"] = None,
        circuit_breaker: Optional["CircuitBreaker"] = None,
        oms: Optional["OrderManagementSystem"] = None,
        database: Optional[Any] = None,
        model_id: Optional[int] = None,
        session_id: Optional[int] = None,
        trade_logger: Optional[Any] = None,
        equity_tracker: Optional[Any] = None,
    ):
        """
        Initialize trading controller
        :param agent: Trained DQN agent
        :param environment: Live trading environment
        :param account: Trading account
        :param risk_manager: Risk manager
        :param trading_enabled: Whether to enable live trading (default False for safety)
        :param kill_switch: Kill switch for emergency halt (optional)
            Note: If database is provided, pass it when creating KillSwitch for persistence
        :param circuit_breaker: Circuit breaker for automatic halts (optional)
            Note: If database is provided, pass it when creating CircuitBreaker for persistence
        :param oms: Order management system (optional)
            Note: If database is provided, pass it when creating OMS for persistence
        :param database: Database connection for safety component persistence (optional)
            Note: This is stored for reference but should be passed to safety components at creation time
        :param model_id: Model ID for performance tracking (optional, set when model is assigned)
        :param session_id: Trading session ID for performance tracking (optional, set when model is assigned)
        :param trade_logger: TradeLogger instance for performance tracking (optional)
        :param equity_tracker: EquityTracker instance for performance tracking (optional)
        """
        self.agent = agent
        self.env = environment
        self.account = account
        self.risk_manager = risk_manager
        self.trading_enabled = trading_enabled
        self.feed_stale_threshold = float(
            os.getenv("FEED_STALE_THRESHOLD_SECONDS", "180")
        )

        # Safety components
        self.kill_switch = kill_switch
        self.circuit_breaker = circuit_breaker
        self.oms = oms
        self.database = database

        # Performance tracking components (optional - set when model is assigned to account)
        self.model_id = model_id
        self.session_id = session_id
        self.trade_logger = trade_logger
        self.equity_tracker = equity_tracker

        # Note: Database should be passed to safety components when creating them
        # This reference is stored for potential future use or logging

        self.is_running = False
        self.decision_interval = 60  # Make decision every 60 seconds
        self._last_ready_state = None
        self._last_daily_reset = None
        self._last_hourly_reset = None
        self._last_reconciliation = None
        self.reconciliation_interval = 300  # Reconcile every 5 minutes

        # Initialize structured logger
        try:
            self.logger = get_logger("trading_controller", "trading_controller.log")
        except Exception:
            self.logger = logging.getLogger(__name__)
        self.action_executor = ActionExecutor(self.logger)

        # Register kill switch callback
        if self.kill_switch:
            self.kill_switch.on_kill_callback = self._handle_kill_switch

        # Register OMS alert callback
        if self.oms:
            self.oms.on_alert = self._handle_oms_alert

        # Set up circuit breaker price history provider
        if self.circuit_breaker and self.env:
            # Provide a callable that returns price histories
            def get_price_histories():
                if hasattr(self.env, "price_history_manager"):
                    return self.env.price_history_manager.get_all_histories()
                elif hasattr(self.env, "price_history_by_pair"):
                    return self.env.price_history_by_pair
                return {}

            self.circuit_breaker.price_history_provider = get_price_histories

    def _handle_kill_switch(self, reason: str) -> None:
        """Handle kill switch activation"""
        self.logger.critical(f"🚨 KILL SWITCH ACTIVATED: {reason}")
        self.is_running = False
        self.trading_enabled = False

        # Close all positions through account
        if self.account and hasattr(self.account, "current_trade"):
            for trade_id in list(self.account.current_trade.keys()):
                try:
                    self.account.close_order(trade_id)
                    self.logger.info(f"Closed trade {trade_id} due to kill switch")
                except Exception as e:
                    self.logger.error(f"Failed to close trade {trade_id}: {e}")

    def _handle_oms_alert(self, alert_type: str, alert_data: dict) -> None:
        """Handle OMS alerts"""
        self.logger.warning(f"OMS Alert: {alert_type} - {alert_data}")

        # For critical position mismatches, consider triggering kill switch
        if alert_type == "position_mismatch":
            discrepancy_pct = alert_data.get("discrepancy_pct", 0)
            # If discrepancy is very large (>50%), trigger kill switch
            if discrepancy_pct > 0.50 and self.kill_switch:
                self.logger.critical(
                    f"Critical position mismatch detected ({discrepancy_pct:.1%}) - "
                    f"triggering kill switch"
                )
                self.kill_switch.trigger(
                    f"Critical position mismatch: {alert_data.get('symbol')} - "
                    f"{discrepancy_pct:.1%} difference",
                    "OMS Alert",
                )

    def start(self):
        """Start the trading controller"""
        if self.is_running:
            print("Controller is already running")
            return

        # Check if kill switch is active
        if self.kill_switch and self.kill_switch.is_active():
            self.logger.critical(
                "Cannot start - kill switch is active. Reset required."
            )
            print("Cannot start - kill switch is active. Reset required.")
            return

        self.is_running = True
        self.risk_manager.initialize(self.account)

        # Initialize circuit breaker with account balance
        if self.circuit_breaker and self.account:
            self.circuit_breaker.initialize(self.account.balance)

        # Start equity tracking if available
        if self.equity_tracker and self.session_id:
            try:
                self.equity_tracker.start_tracking(
                    model_id=self.model_id, session_id=self.session_id
                )
            except Exception as e:
                self.logger.warning(f"Failed to start equity tracking: {e}")

        # Arm kill switch
        if self.kill_switch:
            self.kill_switch.arm()

        if hasattr(self.logger, "log_event"):
            self.logger.log_event(
                event_type="trading_controller_started",
                message=f"Trading Controller started (Trading: {'ENABLED' if self.trading_enabled else 'DISABLED'})",
                metrics={
                    "trading_enabled": self.trading_enabled,
                    "account_login": self.account.login if self.account else None,
                    "kill_switch_armed": self.kill_switch is not None,
                    "circuit_breaker_enabled": self.circuit_breaker is not None,
                },
            )
        print(
            f"Trading Controller started (Trading: {'ENABLED' if self.trading_enabled else 'DISABLED'})"
        )

        try:
            while self.is_running:
                # Check and perform resets if needed
                self._check_and_reset_circuit_breaker()

                # Periodic reconciliation
                self._reconcile_positions()

                # Check kill switch first - highest priority
                if self.kill_switch and self.kill_switch.is_active():
                    self.logger.critical("Kill switch active - halting trading loop")
                    break

                # Check circuit breaker
                if self.circuit_breaker:
                    cb_can_trade, cb_reason = self.circuit_breaker.check()
                    if not cb_can_trade:
                        if hasattr(self.logger, "log_event"):
                            self.logger.log_event(
                                event_type="circuit_breaker_halt",
                                message=f"Circuit breaker halt: {cb_reason}",
                                metrics=self.circuit_breaker.get_metrics(),
                                level="WARNING",
                            )
                        print(f"⚡ Circuit breaker: {cb_reason}")
                        time.sleep(self.decision_interval)
                        continue

                status = get_market_feed_status(
                    self.env.data_providers, self.feed_stale_threshold
                )
                ready = status["ready"]

                # Log readiness transitions without spamming
                if self._last_ready_state is None or self._last_ready_state != ready:
                    if hasattr(self.logger, "log_event"):
                        self.logger.log_event(
                            event_type="market_feed_state_change",
                            message=f"Trading readiness changed: {'READY' if ready else 'NOT READY'}",
                            metrics=status,
                            level="INFO" if ready else "WARNING",
                        )
                    else:
                        self.logger.info(
                            f"Trading readiness changed: {'READY' if ready else 'NOT READY'} | {status}"
                        )
                    self._last_ready_state = ready

                if not ready:
                    if hasattr(self.logger, "log_event"):
                        self.logger.log_event(
                            event_type="market_not_ready",
                            message="Market/feed not ready - skipping action execution",
                            metrics=status,
                            level="INFO",
                        )
                    else:
                        self.logger.info(
                            f"Market/feed not ready - skipping action execution {status}"
                        )
                    time.sleep(self.decision_interval)
                    continue

                # Get current state
                state = self.env.get_state()

                # Build action mask based on current state
                action_mask = self._build_action_mask()

                # Get action from agent (no exploration in live trading)
                action = self.agent.act(state, training=False, action_mask=action_mask)

                # Check risk limits
                can_trade, reason = self.risk_manager.can_trade(self.account)

                if not can_trade:
                    if hasattr(self.logger, "log_event"):
                        self.logger.log_event(
                            event_type="trading_blocked",
                            message=f"Trading blocked: {reason}",
                            metrics={"reason": reason},
                            level="WARNING",
                        )
                    print(f"Trading blocked: {reason}")
                    action = 0  # Force hold

                # Execute action if trading is enabled
                if self.trading_enabled:
                    try:
                        previous_balance = self.account.balance
                        self._execute_action(action)

                        # Record trade results to circuit breaker
                        if self.circuit_breaker and self.account:
                            new_balance = self.account.balance
                            pnl = new_balance - previous_balance
                            self.circuit_breaker.record_trade(pnl, balance=new_balance)

                            # Record volatility if available
                            if self.env and hasattr(self.env, "performance_metrics"):
                                metrics = self.env.performance_metrics.get_all_metrics()
                                volatility = metrics.get("volatility")
                                if volatility:
                                    # Convert annualized to daily if needed
                                    daily_vol = (
                                        volatility / np.sqrt(252)
                                        if volatility > 0.01
                                        else volatility
                                    )
                                    self.circuit_breaker.record_volatility(
                                        volatility=daily_vol
                                    )

                        # Record equity snapshot if tracker is available
                        if self.equity_tracker and self.session_id and self.account:
                            if self.equity_tracker.should_record_snapshot(
                                self.session_id
                            ):
                                try:
                                    current_balance = self.account.balance
                                    current_equity = (
                                        self.account.equity
                                        if hasattr(self.account, "equity")
                                        else current_balance
                                    )
                                    unrealized_pnl = current_equity - current_balance

                                    self.equity_tracker.record_snapshot(
                                        model_id=self.model_id,
                                        session_id=self.session_id,
                                        balance=current_balance,
                                        equity=current_equity,
                                        unrealized_pnl=unrealized_pnl,
                                    )
                                except Exception as e:
                                    self.logger.warning(
                                        f"Failed to record equity snapshot: {e}"
                                    )
                    except Exception as e:
                        # Record error to circuit breaker
                        if self.circuit_breaker:
                            self.circuit_breaker.record_error(e)
                        raise
                else:
                    if hasattr(self.logger, "log_event"):
                        self.logger.log_event(
                            event_type="action_suggested",
                            message=f"Action suggested: {action} (Trading disabled - no execution)",
                            metrics={"action": action},
                        )
                    print(
                        f"Action suggested: {action} (Trading disabled - no execution)"
                    )

                # Wait before next decision
                time.sleep(self.decision_interval)

        except KeyboardInterrupt:
            if hasattr(self.logger, "log_event"):
                self.logger.log_event(
                    event_type="trading_controller_stopped",
                    message="Trading controller stopped by user",
                    level="WARNING",
                )
            print("Trading controller stopped by user")
        finally:
            self.stop()

    def stop(self):
        """Stop the trading controller"""
        # Idempotent: only stop if currently running
        if not self.is_running:
            return

        self.is_running = False

        # Stop equity tracking if active
        if self.equity_tracker and self.session_id:
            try:
                self.equity_tracker.stop_tracking(self.session_id)
            except Exception as e:
                self.logger.warning(f"Failed to stop equity tracking: {e}")

        # Disarm kill switch (but don't clear triggered state)
        if self.kill_switch and not self.kill_switch.is_active():
            self.kill_switch.disarm()

        if hasattr(self.logger, "log_event"):
            self.logger.log_event(
                event_type="trading_controller_stopped",
                message="Trading Controller stopped",
            )
        print("Trading Controller stopped")

    def trigger_kill_switch(self, reason: str = "Manual trigger") -> None:
        """Manually trigger the kill switch"""
        if self.kill_switch:
            self.kill_switch.trigger(reason, "Manual")
        else:
            self.logger.warning("No kill switch configured")

    def reset_kill_switch(self, approver: str) -> bool:
        """Reset the kill switch (requires approver name)"""
        if self.kill_switch:
            return self.kill_switch.reset(approver)
        return False

    def get_safety_status(self) -> dict:
        """Get status of all safety components"""
        status = {
            "trading_enabled": self.trading_enabled,
            "is_running": self.is_running,
        }

        if self.kill_switch:
            status["kill_switch"] = self.kill_switch.get_status()

        if self.circuit_breaker:
            status["circuit_breaker"] = self.circuit_breaker.get_metrics()

        if self.oms:
            status["oms"] = self.oms.get_statistics()

        return status

    def _build_action_mask(self) -> np.ndarray:
        """
        Build action mask based on current state
        :return: Binary mask array (1=valid, 0=invalid) for each action
        """
        if not self.env.data_providers:
            # If no data providers, only HOLD is valid
            mask = np.zeros(self.agent.action_size, dtype=np.int32)
            mask[0] = 1  # HOLD is always valid
            return mask

        n_pairs = len(self.env.data_providers)
        action_mask = np.ones((n_pairs * 3) + 1, dtype=np.int32)  # +1 for global HOLD

        # Action 0 (HOLD) is always valid
        action_mask[0] = 1

        # Check if there's an open position
        has_position = len(self.account.current_trade) > 0 if self.account else False

        # For each pair, mask actions based on position status
        # Allow multiple positions up to max_open_positions (enforced by risk manager)
        # Only mask CLOSE when no position exists
        for pair_index in range(n_pairs):
            if not has_position:
                # No position: mask CLOSE
                # CLOSE action: action = 1 + (pair_index * 3 + 2)
                close_action = 1 + (pair_index * 3 + 2)
                action_mask[close_action] = 0

        return action_mask

    def _execute_action(self, action: int):
        """
        Execute trading action using ActionExecutor
        :param action: Encoded action
                0 = Global HOLD (no pair)
                1+ = 1 + (pair_index * 3 + action_type_offset)
        """
        try:
            # Use ActionExecutor to execute the action
            previous_balance = self.account.balance
            self.action_executor.execute(
                action=action,
                environment=self.env,
                account=self.account,
                risk_manager=self.risk_manager,
                previous_balance=previous_balance,
                trading_enabled=self.trading_enabled,
                model_id=self.model_id,
                session_id=self.session_id,
                trade_logger=self.trade_logger,
            )
        except Exception as e:
            # Decode action for error message
            try:
                pair_index, action_type = self.env.decode_action(action)
                if action == 0:
                    symbol = "N/A"
                    action_type_str = "HOLD"
                else:
                    pair = (
                        self.env.data_providers[pair_index].currency_pair
                        if self.env.data_providers and pair_index is not None
                        else None
                    )
                    symbol = pair.symbol if pair else "UNKNOWN"
                    action_type_str = str(action_type)
            except Exception:
                symbol = "UNKNOWN"
                action_type_str = "UNKNOWN"

            error_msg = f"Error executing action {action} (action_type={action_type_str}) on {symbol}: {e}"
            print(error_msg)
            if hasattr(self.logger, "log_error"):
                self.logger.log_error(
                    event_type="action_execution_error",
                    error=error_msg,
                    symbol=symbol if symbol != "N/A" else None,
                    account_login=self.account.login if self.account else None,
                    metrics={"action": action, "action_type": action_type_str},
                    exc_info=True,
                )
            else:
                self.logger.error(error_msg, exc_info=True)

            # Record error to circuit breaker
            if self.circuit_breaker:
                self.circuit_breaker.record_error(e)

    def _check_and_reset_circuit_breaker(self) -> None:
        """Check if circuit breaker needs daily/hourly reset"""
        from datetime import datetime

        now = datetime.now()

        # Daily reset (at start of trading day - configurable, default 00:00 UTC)
        if self.circuit_breaker and self.account:
            if (
                self._last_daily_reset is None
                or (now - self._last_daily_reset).days >= 1
            ):
                # Check if it's start of trading day (00:00 UTC)
                if now.hour == 0 and now.minute < 5:  # Within first 5 minutes of hour
                    self.circuit_breaker.reset_daily(self.account.balance)
                    self._last_daily_reset = now
                    self.logger.info("Circuit breaker daily reset performed")

            # Hourly reset
            if (
                self._last_hourly_reset is None
                or (now - self._last_hourly_reset).total_seconds() >= 3600
            ):
                # Reset at start of each hour
                if now.minute < 5:  # Within first 5 minutes of hour
                    self.circuit_breaker.reset_hourly(self.account.balance)
                    self._last_hourly_reset = now
                    self.logger.debug("Circuit breaker hourly reset performed")

    def _reconcile_positions(self) -> None:
        """Periodically reconcile OMS positions with broker"""
        from datetime import datetime

        if not self.oms or not self.account:
            return

        now = datetime.now()

        # Check if reconciliation is needed
        if (
            self._last_reconciliation is None
            or (now - self._last_reconciliation).total_seconds()
            >= self.reconciliation_interval
        ):

            try:
                # Get broker positions (assuming account has method to get positions)
                broker_positions = {}
                if hasattr(self.account, "get_positions"):
                    positions = self.account.get_positions()
                    for pos in positions:
                        symbol = getattr(pos, "symbol", None) or getattr(
                            pos, "pair", None
                        )
                        quantity = getattr(pos, "volume", None) or getattr(
                            pos, "quantity", None
                        )
                        if symbol and quantity:
                            broker_positions[symbol] = float(quantity)
                elif hasattr(self.account, "current_trade"):
                    # Fallback: extract from current_trade dict
                    for trade_id, trade in self.account.current_trade.items():
                        symbol = getattr(trade, "symbol", None) or getattr(
                            trade, "pair", None
                        )
                        volume = getattr(trade, "volume", None) or getattr(
                            trade, "quantity", None
                        )
                        if symbol and volume:
                            broker_positions[symbol] = float(volume)

                # Reconcile
                if broker_positions:
                    discrepancies = self.oms.reconcile(broker_positions)
                    if discrepancies:
                        self.logger.warning(
                            f"Position reconciliation found {len(discrepancies)} discrepancies"
                        )
                    else:
                        self.logger.debug("Position reconciliation: no discrepancies")

                self._last_reconciliation = now

            except Exception as e:
                self.logger.error(
                    f"Error during position reconciliation: {e}", exc_info=True
                )
