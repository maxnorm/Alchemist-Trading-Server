import os
import pickle
import numpy as np
from typing import Optional
from environments.base_trading_env import BaseTradingEnv
from utils.technical_indicators import TechnicalIndicators
from utils.feature_engineering import FeatureEngineer
from utils.performance_metrics import PerformanceMetrics
from utils.transaction_costs import TransactionCostModel


class LiveTradingEnv(BaseTradingEnv):
    def __init__(
        self,
        account,
        data_providers,
        window_size: int = 50,
        feature_engineer: FeatureEngineer = None
    ):
        """
        Initialize the live trading environment
        :param account: The account to use for trading (Account object)
        :param data_providers: The data providers to use for the environment (DataProvider objects)
        :param window_size: The window size to use for the environment
        :param feature_engineer: Optional pre-fitted feature engineer
        """
        super().__init__(window_size, price_shape=15)  # Updated for feature count
        self.account = account
        self.data_providers = data_providers
        self.state_buffer = []
        self.price_history = []
        self.feature_engineer = feature_engineer or FeatureEngineer(normalization_method='robust')
        self.account_login = getattr(account, "login", "default")
        self.scaler_dir = os.path.join("models", f"account_{self.account_login}", "scalers")
        os.makedirs(self.scaler_dir, exist_ok=True)
        self._load_feature_engineer()
        
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
        self.state_buffer.append(data)
        if len(self.state_buffer) > self.window_size:
            self.state_buffer.pop(0)
        
        # Extract price for technical indicators
        if 'mid' in data:
            self.price_history.append(data['mid'])
            if len(self.price_history) > self.window_size * 2:  # Keep more for indicators
                self.price_history.pop(0)
            
    def get_state(self):
        """Get current state from all data sources"""
        # Require sufficient history before producing a state
        if len(self.price_history) < self.window_size:
            return None
        
        # Get current prices
        prices = np.array(self.price_history[-self.window_size:])
        
        # Calculate technical indicators
        indicators = TechnicalIndicators.calculate_all_indicators(prices)

        # Fit feature engineer once enough data is present
        if self.feature_engineer and not self.feature_engineer.is_fitted:
            try:
                clean_features = {k: np.nan_to_num(v) for k, v in indicators.items()}
                clean_features['price'] = prices
                self.feature_engineer.fit(clean_features)
                self._save_feature_engineer()
            except Exception:
                # If fitting fails, defer and wait for more data
                return None
        
        # Combine all features
        features = {
            'price': prices,
            **indicators
        }
        
        # Process state using feature engineer if available
        if self.feature_engineer and self.feature_engineer.is_fitted:
            # Create feature matrix
            feature_matrix = self.feature_engineer.transform(features)
            
            # Ensure correct shape (window_size, n_features)
            if len(feature_matrix.shape) == 2:
                if feature_matrix.shape[0] < self.window_size:
                    # Pad with zeros
                    padding = np.zeros((self.window_size - feature_matrix.shape[0], feature_matrix.shape[1]))
                    feature_matrix = np.vstack([padding, feature_matrix])
                elif feature_matrix.shape[0] > self.window_size:
                    # Take last window_size
                    feature_matrix = feature_matrix[-self.window_size:]
            
            return feature_matrix.astype(np.float32)
        
        # If no fitted feature engineer yet, wait for readiness
        return None

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
        pair = None,
        volatility: Optional[float] = None
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
        sharpe_ratio = metrics['sharpe_ratio']
        sharpe_reward = sharpe_ratio * 10  # Scale to meaningful range
        
        # Component 2: Drawdown Penalty
        # Why: Strongly penalize large losses to protect capital
        # Exponential penalty prevents account wipeout
        current_drawdown = metrics['current_drawdown']
        if current_drawdown > 0.05:  # More than 5% drawdown
            drawdown_penalty = -abs(current_drawdown) * 50  # Exponential penalty
        else:
            drawdown_penalty = 0.0
        
        # Component 3: Volatility Penalty
        # Why: Penalize high volatility strategies (harder to execute, higher risk)
        # Encourages consistent, stable strategies
        # Note: volatility is annualized, so 0.02 = ~0.126% daily (2% / sqrt(252))
        volatility = metrics['volatility']
        if volatility > 0.02:  # More than 2% annualized volatility
            # Penalty based on annualized volatility (already in correct units)
            volatility_penalty = -volatility * 20
        else:
            volatility_penalty = 0.0
        
        # Component 4: Transaction Cost Penalty
        # Why: Account for real trading costs (spread, commission, slippage)
        # Prevents overtrading and ensures realistic performance expectations
        if action in [1, 2, 3]:  # Buy, Sell, or Close (actions that involve trading)
            # Use detailed cost model if we have the necessary information
            if (transaction_cost is None and 
                entry_price is not None and 
                lot_size is not None and 
                is_long is not None):
                # Calculate detailed transaction cost
                cost_value = self.transaction_cost_model.calculate_cost_for_action(
                    action=action,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    lot_size=lot_size,
                    is_long=is_long,
                    pair=pair,
                    volatility=volatility
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
            sharpe_reward +
            drawdown_penalty +
            volatility_penalty +
            transaction_penalty +
            action_penalty
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
                    self.feature_engineer = pickle.load(f)
            except Exception:
                # On failure, start fresh with new feature engineer
                self.feature_engineer = FeatureEngineer(normalization_method='robust')