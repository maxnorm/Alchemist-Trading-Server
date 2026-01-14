"""
Paper Trading Environment

Real-time paper trading environment that:
- Uses live data from connectors
- Executes real orders on demo/paper account
- Tracks real P&L from broker

Perfect for model validation before production deployment with real broker execution.
"""

import os
import numpy as np
import threading
import logging
from typing import Optional, Dict, List, Any, Tuple

from environments.base_trading_env import BaseTradingEnv
from utils.feature_engineering import FeatureEngineer
from utils.performance_metrics import PerformanceMetrics
from utils.transaction_costs import TransactionCostModel
from application.environment.price_history_manager import PriceHistoryManager
from application.environment.feature_engine import FeatureEngine
from application.environment.state_builder import StateBuilder
from environments.reward_normalizer import RewardNormalizer
from environments.reward_monitor import RewardMonitor
from connectors.base import IDataSourceConnector
from application.services.action_executor import ActionExecutor
from utils.risk_management import RiskManager


class PaperTradingEnv(BaseTradingEnv):
    """
    Paper trading environment with real-time data.

    Executes real orders on demo/paper account (not simulation).
    Uses same architecture as LiveTradingEnv but with demo account.
    Useful for model validation before live trading.

    Features:
    - Real-time price updates from connectors
    - Real order execution via ActionExecutor (on demo account)
    - Real position and P&L tracking from broker
    - Performance metrics calculation

    Usage:
        # Create with account (demo/paper account) and connectors
        account = Account(login, broker_adapter=demo_broker_adapter)
        connectors = [MT5PriceConnector(pair) for pair in currency_pairs]

        env = PaperTradingEnv(
            account=account,
            connectors=connectors,
            window_size=50
        )

        # Run trading loop
        state, info = env.reset()

        while True:
            action = agent.act(state)
            state, reward, done, truncated, info = env.step(action)

            # Paper trading doesn't have a natural end
            # Use external signals to stop (e.g., time-based)
            if should_stop():
                break

        # Get performance
        metrics = env.get_performance_metrics()
    """

    def __init__(
        self,
        account,
        connectors: List[IDataSourceConnector],
        window_size: int = 50,
        feature_engineer: Optional[FeatureEngineer] = None,
        reward_normalizer: Optional[RewardNormalizer] = None,
        use_reward_normalization: bool = True,
        reward_monitor: Optional[RewardMonitor] = None,
        use_reward_monitoring: bool = True,
        risk_manager: Optional[RiskManager] = None,
        seed: Optional[int] = None,
    ):
        """
        Initialize paper trading environment.

        Args:
            account: Account connected to demo/paper account (Account object)
            connectors: List of data source connectors (IDataSourceConnector objects)
            window_size: Window size for state
            feature_engineer: Optional pre-fitted feature engineer
            reward_normalizer: Optional reward normalizer instance
            use_reward_normalization: Whether to normalize rewards (default: True)
            reward_monitor: Optional reward monitor instance
            use_reward_monitoring: Whether to monitor rewards (default: True)
            risk_manager: Optional risk manager instance
            seed: Random seed for reproducibility
        """
        # Calculate number of pairs and features per pair (like LiveTradingEnv)
        n_pairs = len(connectors) if connectors else 1
        features_per_pair = 15  # Updated for feature count
        total_features = n_pairs * features_per_pair

        # Update action space: (n_pairs * 3) + 1 actions
        action_size = (n_pairs * 3) + 1

        super().__init__(
            window_size, price_shape=total_features, action_size=action_size, seed=seed
        )
        self.account = account
        self.connectors = connectors  # Direct, no adapter
        self.n_pairs = n_pairs
        self.features_per_pair = features_per_pair
        self.state_buffer: List[Any] = []
        self._state_lock = threading.Lock()

        # Initialize feature engineer
        self.feature_engineer = feature_engineer or FeatureEngineer(
            normalization_method="robust"
        )
        self.account_login = getattr(account, "login", "default")
        self.scaler_dir = os.path.join(
            "models", f"account_{self.account_login}", "scalers"
        )
        os.makedirs(self.scaler_dir, exist_ok=True)
        self._load_feature_engineer()

        # Initialize components (like LiveTradingEnv)
        self.price_history_manager = PriceHistoryManager(window_size, connectors)

        # Load historical data if available
        db = None
        try:
            from database import Database

            db = Database()
            symbols = (
                [
                    (
                        getattr(getattr(connector, "config", None), "symbol", "unknown")
                        if getattr(connector, "config", None)
                        else "unknown"
                    )
                    for connector in connectors
                ]
                if connectors
                else []
            )
            if symbols:
                self.price_history_manager.load_historical_data(
                    db, symbols, limit=100, hours=24
                )
        except Exception as e:
            logger = logging.getLogger(__name__)
            if hasattr(logger, "log_error"):
                logger.log_error(
                    event_type="historical_data_load_error",
                    error=f"Could not load historical data: {e}",
                    exc_info=False,
                )
            else:
                logger.warning(f"Could not load historical data: {e}")

        # Initialize feature engine with database for versioning
        try:
            from mlops.feature_registry import FeatureRegistry

            feature_registry = FeatureRegistry(db) if db else None
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to create feature registry: {e}")
            feature_registry = None

        self.feature_engine = FeatureEngine(
            feature_engineer=self.feature_engineer,
            window_size=window_size,
            features_per_pair=features_per_pair,
            database=db,
            feature_registry=feature_registry,
        )
        self.state_builder = StateBuilder(
            price_history_manager=self.price_history_manager,
            feature_engine=self.feature_engine,
            window_size=window_size,
            connectors=connectors,
        )

        # Initialize performance metrics tracker
        self.performance_metrics = PerformanceMetrics(window_size=252)
        self.previous_balance = None

        # Initialize transaction cost model
        self.transaction_cost_model = TransactionCostModel()

        # Initialize reward normalizer
        self.use_reward_normalization = use_reward_normalization
        if reward_normalizer is not None:
            self.reward_normalizer: Optional[RewardNormalizer] = reward_normalizer
        elif use_reward_normalization:
            self.reward_normalizer = RewardNormalizer(
                alpha=0.99, clip_range=(-3.0, 3.0)
            )
        else:
            self.reward_normalizer = None

        # Initialize reward monitor
        self.use_reward_monitoring = use_reward_monitoring
        if reward_monitor is not None:
            self.reward_monitor: Optional[RewardMonitor] = reward_monitor
        elif use_reward_monitoring:
            self.reward_monitor = RewardMonitor(window_size=100, anomaly_threshold=3.0)
        else:
            self.reward_monitor = None

        # Initialize with current balance if account exists
        if account and account.balance:
            self.previous_balance = account.balance

        # Initialize ActionExecutor and RiskManager
        self.action_executor = ActionExecutor()
        self.risk_manager = risk_manager or RiskManager()

        # Note: Connectors are consumed by PriceHistoryManager via background threads
        # No need to subscribe here - data flows through PriceHistoryManager

    def reset(
        self, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Reset paper trading state"""
        super().reset(seed=seed)

        # Reset performance metrics
        self.performance_metrics.reset()
        self.previous_balance = None
        if self.reward_normalizer is not None:
            self.reward_normalizer.reset()
        if self.reward_monitor is not None:
            self.reward_monitor.reset()

        # Initialize with current balance if account exists
        if self.account and self.account.balance:
            self.previous_balance = self.account.balance

        info = {
            "account_balance": self.account.balance if self.account else 0.0,
            "account_login": self.account_login,
        }

        return self.get_state(), info

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """
        Execute one step with real order execution (on demo account).

        Args:
            action: Action to take

        Returns:
            Tuple of (observation, reward, terminated, truncated, info)
        """
        from domain.action_type import ActionType

        # Get previous balance for reward calculation
        previous_balance = self.previous_balance or (
            self.account.balance if self.account else 0.0
        )

        # Handle global HOLD (action 0)
        if action == 0:
            # HOLD does nothing, calculate reward based on account balance change
            current_balance = self.account.balance if self.account else 0.0
            reward = self.calculate_reward(
                previous_balance=previous_balance,
                current_balance=current_balance,
                action=action,
                has_position=(
                    len(self.account.current_trade) > 0 if self.account else False
                ),
            )
            self.previous_balance = current_balance
            return self.get_state(), reward, False, False, self._get_info()

        # Decode action to get pair_index and action_type
        pair_index, action_type = self.decode_action(action)

        # Validate pair_index
        if (
            pair_index is None
            or not self.connectors
            or pair_index >= len(self.connectors)
        ):
            current_balance = self.account.balance if self.account else 0.0
            reward = 0.0
            self.previous_balance = current_balance
            return self.get_state(), reward, False, False, self._get_info()

        # Get currency pair for the selected pair_index
        connector = self.connectors[pair_index]
        pair = getattr(connector, "currency_pair", None)

        if pair is None:
            current_balance = self.account.balance if self.account else 0.0
            reward = 0.0
            self.previous_balance = current_balance
            return self.get_state(), reward, False, False, self._get_info()

        has_position = len(self.account.current_trade) > 0 if self.account else False

        # Initialize trade information variables for reward calculation
        entry_price = None
        exit_price = None
        lot_size = None
        is_long = None

        # Store trade info before execution for reward calculation
        if has_position and self.account.current_trade:
            trade = list(self.account.current_trade.values())[0]
            entry_price = trade.open_price
            lot_size = trade.lotsize
            is_long = trade.ordertype.value == 0  # 0 = BUY
            exit_price = pair.bid if is_long else pair.ask

        # Execute action using ActionExecutor (real orders on demo account)
        try:
            self.action_executor.execute(
                action=action,
                environment=self,
                account=self.account,
                risk_manager=self.risk_manager,
                previous_balance=previous_balance,
                trading_enabled=True,  # Paper trading always enabled (demo account)
            )
        except Exception as e:
            logger = logging.getLogger(__name__)
            if hasattr(logger, "log_error"):
                logger.log_error(
                    event_type="paper_trading_action_error",
                    error=f"Error executing action {action}: {e}",
                    exc_info=True,
                )
            else:
                logger.error(f"Error executing action {action}: {e}", exc_info=True)

        # Update trade info after execution for reward calculation
        if action_type == ActionType.BUY or action_type == ActionType.SELL:
            # New position opened
            if self.account.current_trade:
                trade = list(self.account.current_trade.values())[0]
                entry_price = trade.open_price
                lot_size = trade.lotsize
                is_long = trade.ordertype.value == 0  # 0 = BUY
        elif action_type == ActionType.CLOSE:
            # Position closed, use stored values
            pass

        # Calculate reward with detailed transaction cost model
        current_balance = self.account.balance if self.account else 0.0

        # Get current volatility from environment metrics
        volatility = None
        if hasattr(self, "performance_metrics"):
            metrics = self.performance_metrics.get_all_metrics()
            volatility = metrics.get("volatility", None)
            # Convert annualized volatility to daily if needed
            if volatility is not None:
                volatility = volatility / np.sqrt(252)  # Convert to daily

        reward = self.calculate_reward(
            previous_balance=previous_balance,
            current_balance=current_balance,
            action=action,
            has_position=has_position,
            entry_price=entry_price,
            exit_price=exit_price,
            lot_size=lot_size,
            is_long=is_long,
            pair=pair,
            volatility=volatility,
        )

        self.previous_balance = current_balance

        # Paper trading never terminates on its own
        return self.get_state(), reward, False, False, self._get_info()

    def _get_info(self) -> Dict[str, Any]:
        """Get info dictionary for step() return"""
        return {
            "account_balance": self.account.balance if self.account else 0.0,
            "account_login": self.account_login,
            "positions": len(self.account.current_trade) if self.account else 0,
        }

    def get_state(self, mode: str = "live", include_latency: bool = True):
        """
        Get current state from all data sources - delegates to StateBuilder (like LiveTradingEnv)

        :param mode: 'training' (point-in-time) or 'live' (real-time)
        :param include_latency: Include latency features in state
        :return: State array with latency features
        """
        from utils.time_utils import get_utc_time

        current_time = get_utc_time()
        state = self.state_builder.build_state(
            current_time=current_time, mode=mode, include_latency=include_latency
        )

        # If state is None (not enough data), return zeros
        if state is None:
            if self.observation_space.shape is None:
                raise ValueError("Observation space must have a shape")
            return np.zeros(self.observation_space.shape, dtype=np.float32)

        return state

    # Property for backward compatibility
    @property
    def price_history_by_pair(self) -> Dict[str, List[float]]:
        """Get price history by pair (backward compatibility)"""
        return self.price_history_manager.get_all_histories()

    def calculate_reward(
        self,
        previous_balance: float,
        current_balance: float,
        action: int,
        has_position: bool,
        transaction_cost: Optional[float] = None,
        entry_price: Optional[float] = None,
        exit_price: Optional[float] = None,
        lot_size: Optional[float] = None,
        is_long: Optional[bool] = None,
        pair=None,
        volatility: Optional[float] = None,
    ) -> float:
        """
        Enhanced reward function with risk-adjusted metrics (like LiveTradingEnv)

        Components:
        1. Sharpe ratio reward (risk-adjusted returns)
        2. Drawdown penalty (large losses)
        3. Volatility penalty (high volatility)
        4. Transaction cost penalty (trading costs)
        5. Action-based adjustments (behavior fine-tuning)

        :param previous_balance: Previous account balance
        :param current_balance: Current account balance
        :param action: Action taken (0=Hold, 1=Buy, 2=Sell, 3=Close)
        :param has_position: Whether agent has open position
        :param transaction_cost: Optional fixed transaction cost (for backward compatibility)
        :param entry_price: Entry price for the trade (for detailed cost calculation)
        :param exit_price: Exit price for the trade (for detailed cost calculation)
        :param lot_size: Position size in lots (for detailed cost calculation)
        :param is_long: True for long position, False for short (for detailed cost calculation)
        :param pair: Currency pair object (for actual spread calculation)
        :param volatility: Current volatility (for slippage calculation)
        :return: Reward value
        """
        # Update performance metrics with new balance
        if self.previous_balance is not None and self.previous_balance > 0:
            self.performance_metrics.update(current_balance, self.previous_balance)

        self.previous_balance = current_balance

        # Get current performance metrics
        metrics = self.performance_metrics.get_all_metrics()

        # Component 1: Sharpe Ratio Reward
        sharpe_ratio = metrics["sharpe_ratio"]
        sharpe_reward = np.clip(sharpe_ratio / 3.0, -1.0, 1.0)

        # Component 2: Drawdown Penalty
        current_drawdown = metrics["current_drawdown"]
        if current_drawdown > 0.05:  # More than 5% drawdown
            drawdown_penalty = np.clip(-abs(current_drawdown) / 0.20, -1.0, 0.0)
        else:
            drawdown_penalty = 0.0

        # Component 3: Volatility Penalty
        volatility_metric = metrics["volatility"]
        if volatility_metric > 0.02:  # More than 2% annualized volatility
            volatility_penalty = np.clip(-volatility_metric / 0.10, -1.0, 0.0)
        else:
            volatility_penalty = 0.0

        # Component 4: Transaction Cost Penalty
        if action in [1, 2, 3]:  # Buy, Sell, or Close
            if (
                transaction_cost is None
                and entry_price is not None
                and lot_size is not None
                and is_long is not None
            ):
                cost_value = self.transaction_cost_model.calculate_cost_for_action(
                    action=action,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    lot_size=lot_size,
                    is_long=is_long,
                    pair=pair,
                    volatility=volatility,
                )
                if previous_balance > 0:
                    transaction_cost_pct = cost_value / previous_balance
                else:
                    transaction_cost_pct = 0.0
                transaction_penalty = -transaction_cost_pct
            else:
                if transaction_cost is None:
                    transaction_cost = 0.001  # Default 0.1%
                transaction_penalty = -transaction_cost
        else:
            transaction_penalty = 0.0

        # Component 5: Action-based adjustments
        action_penalty = 0.0
        if action == 0 and not has_position:
            action_penalty = -0.01

        profit = current_balance - previous_balance
        if action == 3 and has_position and profit > 0:  # Close with profit
            action_penalty += 0.1

        # Combine all components
        reward = (
            sharpe_reward
            + drawdown_penalty
            + volatility_penalty
            + transaction_penalty
            + action_penalty
        )

        # Track reward components for monitoring
        reward_components = {
            "sharpe_reward": sharpe_reward,
            "drawdown_penalty": drawdown_penalty,
            "volatility_penalty": volatility_penalty,
            "transaction_penalty": transaction_penalty,
            "action_penalty": action_penalty,
        }

        # Normalize reward if normalizer is configured
        if self.reward_normalizer is not None and self.use_reward_normalization:
            reward = self.reward_normalizer.normalize(reward)

        # Update reward monitor if configured
        if self.reward_monitor is not None and self.use_reward_monitoring:
            self.reward_monitor.update(reward, components=reward_components)

        return reward

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics (like LiveTradingEnv)"""
        metrics = self.performance_metrics.get_all_metrics()

        # Add account-specific metrics
        if self.account:
            metrics["account_balance"] = self.account.balance
            metrics["account_equity"] = (
                getattr(self.account.info, "equity", self.account.balance)
                if hasattr(self.account, "info")
                else self.account.balance
            )
            metrics["open_positions"] = len(self.account.current_trade)

        return metrics

    def reset_metrics(self):
        """Reset performance metrics (useful for new episodes or testing)"""
        self.performance_metrics.reset()
        self.previous_balance = None
        if self.reward_normalizer is not None:
            self.reward_normalizer.reset()
        if self.reward_monitor is not None:
            self.reward_monitor.reset()

    def get_reward_statistics(self) -> dict:
        """Get reward normalization statistics"""
        stats = {}
        if self.reward_normalizer is not None:
            stats["normalizer"] = self.reward_normalizer.get_statistics()
        if self.reward_monitor is not None:
            stats["monitor"] = self.reward_monitor.get_statistics()
        return stats

    def close_all_positions(self) -> int:
        """Close all open positions (e.g., at end of paper trading)"""
        if not self.account or not self.account.current_trade:
            return 0

        closed = 0
        for ticket in list(self.account.current_trade.keys()):
            try:
                self.account.close_order(ticket)
                closed += 1
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to close position {ticket}: {e}")

        return closed

    def update_session_metrics(
        self, session_manager=None, session_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update paper trading session metrics in the database.

        This method should be called periodically during paper trading to sync
        metrics with the PaperTradingSessionManager.

        Args:
            session_manager: Optional PaperTradingSessionManager instance
            session_id: Optional session ID to update

        Returns:
            Dictionary of current metrics
        """
        metrics = self.get_performance_metrics()

        if session_manager and session_id:
            try:
                # Get account balance
                balance = self.account.balance if self.account else 0.0

                # Calculate winning trades from account trade history
                # Note: This would need to track closed trades, which may require
                # additional implementation depending on account interface
                winning_trades = 0  # TODO: Implement based on account trade history
                total_trades = len(self.account.current_trade) if self.account else 0

                # Update session in database
                session_manager.update_session_metrics(
                    session_id=session_id,
                    balance=balance,
                    total_trades=total_trades,
                    winning_trades=winning_trades,
                    pnl=(
                        metrics.get("total_return", 0.0) * balance
                        if balance > 0
                        else 0.0
                    ),
                )
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to update session metrics: {e}")

        return metrics

    def end_session_and_store_results(
        self,
        session_manager=None,
        session_id: Optional[int] = None,
        model_registry=None,
        model_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        End paper trading session and store results.

        This method should be called when paper trading is complete.
        It closes all positions, calculates final metrics, and stores results
        in both the session manager and model registry.

        Args:
            session_manager: Optional PaperTradingSessionManager instance
            session_id: Optional session ID to end
            model_registry: Optional ModelRegistry instance
            model_id: Optional model ID to store results for

        Returns:
            Final metrics dictionary
        """
        # Close all positions
        self.close_all_positions()

        # Get final metrics
        final_metrics = self.get_performance_metrics()

        # End session in database
        if session_manager and session_id:
            try:
                session_manager.end_session(session_id, final_metrics)
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to end session: {e}")

        # Store results in model registry
        if model_registry and model_id:
            try:
                # Format results for model registry
                results = {
                    "total_trades": final_metrics.get("total_trades", 0),
                    "winning_trades": final_metrics.get("winning_trades", 0),
                    "win_rate": final_metrics.get("win_rate", 0.0),
                    "pnl": final_metrics.get("total_return", 0.0)
                    * (self.account.balance if self.account else 0.0),
                    "sharpe_ratio": final_metrics.get("sharpe_ratio"),
                    "max_drawdown": final_metrics.get("max_drawdown"),
                    "trade_count": final_metrics.get("total_trades", 0),
                }

                model_registry.store_paper_trading_results(model_id, results)
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to store results in model registry: {e}")

        return final_metrics

    def _save_feature_engineer(self):
        """Persist fitted feature engineer for reuse across sessions"""
        try:
            import pickle

            filepath = os.path.join(self.scaler_dir, "feature_engineer.pkl")
            with open(filepath, "wb") as f:
                pickle.dump(self.feature_engineer, f)
        except Exception:
            # Persistence failures should not stop trading; safe to ignore
            pass

    def _load_feature_engineer(self):
        """Load persisted feature engineer if available"""
        import pickle

        filepath = os.path.join(self.scaler_dir, "feature_engineer.pkl")
        if os.path.exists(filepath):
            try:
                with open(filepath, "rb") as f:
                    loaded_engineer = pickle.load(f)

                # Validate loaded scaler
                if hasattr(loaded_engineer, "is_fitted") and loaded_engineer.is_fitted:
                    if hasattr(loaded_engineer, "scalers") and loaded_engineer.scalers:
                        # Validate scaler statistics
                        for name, scaler in loaded_engineer.scalers.items():
                            if hasattr(scaler, "mean_") and scaler.mean_ is not None:
                                if np.any(np.isnan(scaler.mean_)) or np.any(
                                    np.isinf(scaler.mean_)
                                ):
                                    raise ValueError(
                                        f"Invalid scaler statistics for {name}"
                                    )
                            if hasattr(scaler, "scale_") and scaler.scale_ is not None:
                                if np.any(np.isnan(scaler.scale_)) or np.any(
                                    np.isinf(scaler.scale_)
                                ):
                                    raise ValueError(f"Invalid scaler scale for {name}")

                        self.feature_engineer = loaded_engineer
                        logger = logging.getLogger(__name__)
                        if hasattr(logger, "log_event"):
                            logger.log_event(
                                event_type="feature_engineer_loaded",
                                message=f"✅ Loaded feature engineer from {filepath}",
                                metrics={"filepath": filepath},
                            )
                        else:
                            logger.info(f"✅ Loaded feature engineer from {filepath}")
                        return

                logger = logging.getLogger(__name__)
                if hasattr(logger, "log_event"):
                    logger.log_event(
                        event_type="feature_engineer_validation_failed",
                        message="Loaded feature engineer failed validation, creating new one",
                        level="WARNING",
                    )
                else:
                    logger.warning(
                        "Loaded feature engineer failed validation, creating new one"
                    )

            except Exception as e:
                logger = logging.getLogger(__name__)
                if hasattr(logger, "log_error"):
                    logger.log_error(
                        event_type="feature_engineer_load_error",
                        error=f"Error loading feature engineer: {e}, creating new one",
                        exc_info=False,
                    )
                else:
                    logger.warning(
                        f"Error loading feature engineer: {e}, creating new one"
                    )

        # On failure, start fresh with new feature engineer
        self.feature_engineer = FeatureEngineer(normalization_method="robust")
