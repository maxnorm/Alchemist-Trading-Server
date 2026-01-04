import os
import pickle
import numpy as np
import threading
import logging
from typing import Optional, Dict, List, Any
from environments.base_trading_env import BaseTradingEnv
from utils.feature_engineering import FeatureEngineer
from utils.performance_metrics import PerformanceMetrics
from utils.transaction_costs import TransactionCostModel
from application.environment.price_history_manager import PriceHistoryManager
from application.environment.feature_engine import FeatureEngine
from application.environment.state_builder import StateBuilder


class LiveTradingEnv(BaseTradingEnv):
    def __init__(
        self,
        account,
        data_providers,
        window_size: int = 50,
        feature_engineer: Optional[FeatureEngineer] = None,
    ):
        """
        Initialize the live trading environment
        :param account: The account to use for trading (Account object)
        :param data_providers: The data providers to use for the environment (DataProvider objects)
        :param window_size: The window size to use for the environment
        :param feature_engineer: Optional pre-fitted feature engineer
        """
        # Calculate number of pairs and features per pair
        n_pairs = len(data_providers) if data_providers else 1
        features_per_pair = 15  # Updated for feature count
        # Economic calendar features - DISABLED
        # TODO: Re-enable when new scraping methods are implemented
        # economic_features = 6  # Economic calendar features added by StateBuilder
        # total_features = n_pairs * features_per_pair + economic_features
        total_features = n_pairs * features_per_pair

        # Update action space: (n_pairs * 3) + 1 actions
        # Action encoding:
        #   action = 0 → Global HOLD (no pair)
        #   action = 1 + (pair_index * 3 + action_type_offset) for pair actions
        #   where action_type_offset: 0=BUY, 1=SELL, 2=CLOSE
        action_size = (n_pairs * 3) + 1

        super().__init__(
            window_size, price_shape=total_features, action_size=action_size
        )
        self.account = account
        self.data_providers = data_providers
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

        # Initialize components
        self.price_history_manager = PriceHistoryManager(window_size, data_providers)

        # Load historical data if available
        try:
            from database import Database

            db = Database()
            symbols = (
                [provider.currency_pair.symbol for provider in data_providers]
                if data_providers
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

        self.feature_engine = FeatureEngine(
            feature_engineer=self.feature_engineer,
            window_size=window_size,
            features_per_pair=features_per_pair,
        )
        self.state_builder = StateBuilder(
            price_history_manager=self.price_history_manager,
            feature_engine=self.feature_engine,
            window_size=window_size,
            data_providers=data_providers,
        )

        # Initialize performance metrics tracker
        # Window size of 252 = 1 year of trading days (for annualized metrics)
        self.performance_metrics = PerformanceMetrics(window_size=252)
        self.previous_balance = None

        # Initialize transaction cost model
        self.transaction_cost_model = TransactionCostModel()

        # Initialize with current balance if account exists
        if account and account.balance:
            self.previous_balance = account.balance

        # Subscribe to all data providers
        for provider in self.data_providers:
            provider.subscribe(self._on_data_update)

    def _on_data_update(self, data):
        """Callback function to handle data updates from any provider"""
        with self._state_lock:
            self.state_buffer.append(data)
            if len(self.state_buffer) > self.window_size:
                self.state_buffer.pop(0)

            # Extract price for technical indicators and track by pair
            if "mid" in data and "symbol" in data and data["mid"] is not None:
                symbol = data["symbol"]
                self.price_history_manager.add_price(symbol, data["mid"])

    def get_state(self):
        """Get current state from all data sources - delegates to StateBuilder"""
        return self.state_builder.build_state()

    # Property for backward compatibility
    @property
    def price_history_by_pair(self) -> Dict[str, List[float]]:
        """Get price history by pair (backward compatibility)"""
        return self.price_history_manager.get_all_histories()

    def _process_state(self, state):
        """Convert raw state data into model input format"""
        # State is already processed in get_state()
        return state

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
        Enhanced reward function with risk-adjusted metrics

        Components:
        1. Sharpe ratio reward (risk-adjusted returns)
        2. Drawdown penalty (large losses)
        3. Volatility penalty (high volatility)
        4. Transaction cost penalty (trading costs) - now uses detailed cost model
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
        # Why: Reward risk-adjusted returns, not just returns
        # This is the primary learning signal for risk-adjusted performance
        # Normalize to [-1, 1] range (Sharpe typically ranges from -3 to +3)
        sharpe_ratio = metrics["sharpe_ratio"]
        sharpe_reward = np.clip(sharpe_ratio / 3.0, -1.0, 1.0)

        # Component 2: Drawdown Penalty
        # Why: Strongly penalize large losses to protect capital
        # Normalize drawdown penalty to [-1, 0] range
        # Max drawdown of 20% = -1.0 penalty
        current_drawdown = metrics["current_drawdown"]
        if current_drawdown > 0.05:  # More than 5% drawdown
            drawdown_penalty = np.clip(-abs(current_drawdown) / 0.20, -1.0, 0.0)
        else:
            drawdown_penalty = 0.0

        # Component 3: Volatility Penalty
        # Why: Penalize high volatility strategies (harder to execute, higher risk)
        # Encourages consistent, stable strategies
        # Normalize volatility penalty to [-1, 0] range
        # Max volatility of 10% = -1.0 penalty
        # Note: volatility is annualized, so 0.02 = ~0.126% daily (2% / sqrt(252))
        volatility = metrics["volatility"]
        if volatility > 0.02:  # More than 2% annualized volatility
            volatility_penalty = np.clip(-volatility / 0.10, -1.0, 0.0)
        else:
            volatility_penalty = 0.0

        # Component 4: Transaction Cost Penalty
        # Why: Account for real trading costs (spread, commission, slippage)
        # Prevents overtrading and ensures realistic performance expectations
        if action in [1, 2, 3]:  # Buy, Sell, or Close (actions that involve trading)
            # Use detailed cost model if we have the necessary information
            if (
                transaction_cost is None
                and entry_price is not None
                and lot_size is not None
                and is_long is not None
            ):
                # Calculate detailed transaction cost
                cost_value = self.transaction_cost_model.calculate_cost_for_action(
                    action=action,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    lot_size=lot_size,
                    is_long=is_long,
                    pair=pair,
                    volatility=volatility,
                )
                # Convert absolute cost to percentage of account balance for penalty
                if previous_balance > 0:
                    transaction_cost_pct = cost_value / previous_balance
                else:
                    transaction_cost_pct = 0.0
                transaction_penalty = -transaction_cost_pct
            else:
                # Fallback to fixed transaction cost (backward compatibility)
                if transaction_cost is None:
                    transaction_cost = 0.001  # Default 0.1%
                transaction_penalty = -transaction_cost
        else:
            transaction_penalty = 0.0

        # Component 5: Action-based adjustments
        # Why: Fine-tune agent behavior with small adjustments

        # Small penalty for holding without position (encourage action)
        action_penalty = 0.0
        if action == 0 and not has_position:
            action_penalty = -0.01

        # Bonus for closing profitable position (encourage profit-taking)
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

        return reward

    def get_performance_metrics(self) -> dict:
        """
        Get current performance metrics
        Useful for monitoring and logging
        :return: Dictionary of performance metrics
        """
        return self.performance_metrics.get_all_metrics()

    def reset_metrics(self):
        """
        Reset performance metrics (useful for new episodes or testing)
        """
        self.performance_metrics.reset()
        self.previous_balance = None

    def _save_feature_engineer(self):
        """Persist fitted feature engineer for reuse across sessions"""
        try:
            filepath = os.path.join(self.scaler_dir, "feature_engineer.pkl")
            with open(filepath, "wb") as f:
                pickle.dump(self.feature_engineer, f)
        except Exception:
            # Persistence failures should not stop trading; safe to ignore
            pass

    def _load_feature_engineer(self):
        """Load persisted feature engineer if available"""
        filepath = os.path.join(self.scaler_dir, "feature_engineer.pkl")
        if os.path.exists(filepath):
            try:
                with open(filepath, "rb") as f:
                    loaded_engineer = pickle.load(f)

                # Validate loaded scaler
                if hasattr(loaded_engineer, "is_fitted") and loaded_engineer.is_fitted:
                    # Check that scalers exist and are valid
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
                            # Check for other scaler types (MinMaxScaler, RobustScaler)
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

                # If validation fails, fall through to create new
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
