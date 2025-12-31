"""
Continuous Live Training for DQN Agent
Trains the agent on real-time market data as it arrives
"""
import os
import threading
from datetime import datetime
from typing import Optional

from agents.dqn_agent import DQNAgent
from environments.live_env import LiveTradingEnv
from utils.risk_management import RiskManager
from models.account import Account
from utils.logging_config import get_ai_model_logger
from application.services.action_executor import ActionExecutor
from application.training.training_loop import TrainingLoop
from application.training.metrics_tracker import MetricsTracker
from application.training.checkpoint_manager import CheckpointManager
from application.training.episode_manager import EpisodeManager
from domain.config.training_config import TrainingConfig


class LiveTrainer:
    """
    Continuous live trainer that learns from real-time market data
    No fixed episodes - learns continuously as data arrives
    """
    
    def __init__(
        self,
        agent: DQNAgent,
        environment: LiveTradingEnv,
        account: Account,
        risk_manager: RiskManager,
        save_dir: str = "models",
        decision_interval: int = 60,  # Make decision every 60 seconds
        training_enabled: bool = True,
        trading_enabled: bool = False,  # Start with trading disabled for safety
        episode_duration_hours: int = 24,  # Episode = 1 day
        min_experiences_before_training: int = 100,
        save_freq_steps: int = 1000,  # Save model every N steps
        config: Optional[TrainingConfig] = None
    ):
        """
        Initialize live trainer
        :param agent: DQN agent to train
        :param environment: Live trading environment
        :param account: Trading account (should be paper trading for safety)
        :param risk_manager: Risk manager
        :param save_dir: Directory to save models
        :param decision_interval: Seconds between decisions
        :param training_enabled: Whether to train the agent
        :param trading_enabled: Whether to execute trades (start False!)
        :param episode_duration_hours: Hours per episode (for metrics)
        :param min_experiences_before_training: Min experiences before training starts
        :param save_freq_steps: Save model every N steps
        :param config: Optional training configuration
        """
        self.agent = agent
        self.env = environment
        self.account = account
        self.risk_manager = risk_manager
        self.save_dir = save_dir
        self.contract_size = 100000
        
        # Use config or create from parameters
        if config is None:
            config = TrainingConfig(
                decision_interval=decision_interval,
                episode_duration_hours=episode_duration_hours,
                min_experiences_before_training=min_experiences_before_training,
                save_freq_steps=save_freq_steps,
                training_enabled=training_enabled,
                trading_enabled=trading_enabled
            )
        self.config = config
        
        os.makedirs(save_dir, exist_ok=True)
        
        # Initialize logger
        self.logger = get_ai_model_logger()
        account_login = account.login if account else "unknown"
        self.logger.info(f"Initializing live trainer for account: {account_login}")
        
        # Training state
        self.is_running = False
        self.training_thread = None
        self.simulated_balance = self.account.balance if self.account else 0.0
        self.simulated_position = None  # For train-only mode mark-to-market
        
        # Initialize components
        self.action_executor = ActionExecutor(self.logger)
        self.metrics_tracker = MetricsTracker()
        self.checkpoint_manager = CheckpointManager(save_dir, config.save_freq_steps)
        self.episode_manager = EpisodeManager(config.episode_duration_hours)
        
        # Initialize risk manager
        if account:
            self.risk_manager.initialize(account)
        
        # Initialize training loop
        self.training_loop = TrainingLoop(
            agent=agent,
            environment=environment,
            action_executor=self.action_executor,
            metrics_tracker=self.metrics_tracker,
            checkpoint_manager=self.checkpoint_manager,
            episode_manager=self.episode_manager,
            account=account,
            risk_manager=risk_manager,
            config=config,
            get_effective_balance_func=self._get_effective_balance,
            logger=self.logger,
            simulate_action_func=self._simulate_action
        )
        
        self.logger.info(f"Live trainer initialized - Training: {self.config.training_enabled}, "
                        f"Trading: {self.config.trading_enabled}, Decision interval: {self.config.decision_interval}s, "
                        f"Episode duration: {self.config.episode_duration_hours}h")
    
    def start(self):
        """Start continuous live training"""
        if self.is_running:
            self.logger.warning("Live trainer is already running")
            print("Live trainer is already running")
            return
        
        self.is_running = True
        self.training_loop.is_running = True
        
        # Start episode
        initial_balance = self.account.balance if self.account else 0.0
        self.episode_manager.start_episode(initial_balance, self.logger)
        
        account_login = self.account.login if self.account else 'N/A'
        self.logger.info("=" * 40)
        self.logger.info("Starting Live Training")
        self.logger.info(f"Training: {'ENABLED' if self.config.training_enabled else 'DISABLED'}")
        self.logger.info(f"Trading: {'ENABLED' if self.config.trading_enabled else 'DISABLED'}")
        self.logger.info(f"Decision Interval: {self.config.decision_interval}s")
        self.logger.info(f"Episode Duration: {self.config.episode_duration_hours} hours")
        self.logger.info(f"Account: {account_login}")
        self.logger.info("=" * 40)
        
        print(f"=== Starting Live Training ===")
        print(f"Training: {'ENABLED' if self.config.training_enabled else 'DISABLED'}")
        print(f"Trading: {'ENABLED' if self.config.trading_enabled else 'DISABLED'}")
        print(f"Decision Interval: {self.config.decision_interval}s")
        print(f"Episode Duration: {self.config.episode_duration_hours} hours")
        print(f"Account: {account_login}")
        print("=" * 40)
        
        # Start training in separate thread
        self.training_thread = threading.Thread(target=self.training_loop.run, daemon=True)
        self.training_thread.start()
        self.logger.info("Training thread started")
    
    def stop(self):
        """Stop live training"""
        self.logger.info("Stopping live training")
        self.is_running = False
        self.training_loop.stop()
        if self.training_thread:
            self.training_thread.join(timeout=5)
        self.logger.info("Live training stopped")
        print("Live training stopped")
    
    # Training loop is now handled by TrainingLoop component
    # This method is kept for backward compatibility but delegates to training_loop
    
    def _execute_action(self, action: int, previous_balance: float) -> float:
        """Execute action and return reward"""
        # Decode action to get pair_index and action_type for reward calculation
        pair_index, action_type = self.env.decode_action(action)
        
        # Validate pair_index
        if not self.env.data_providers or pair_index >= len(self.env.data_providers):
            return 0.0
        
        # Get currency pair for the selected pair_index
        pair = self.env.data_providers[pair_index].currency_pair
        
        if pair is None:
            return 0.0
        
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
            is_long = (trade.ordertype.value == 0)  # 0 = BUY
            exit_price = pair.bid if is_long else pair.ask
        
        # Execute action using ActionExecutor
        try:
            self.action_executor.execute(
                action=action,
                environment=self.env,
                account=self.account,
                risk_manager=self.risk_manager,
                previous_balance=previous_balance,
                trading_enabled=self.trading_enabled
            )
        except Exception as e:
            from domain.action_type import ActionType
            try:
                action_type_enum = ActionType.from_value(action_type)
                action_name = str(action_type_enum)
            except:
                action_name = f"UNKNOWN({action_type})"
            
            error_msg = (f"❌ ERROR executing action {action} ({action_name} on {pair.symbol}) | "
                        f"Pair index: {pair_index} | "
                        f"Action type: {action_type} | "
                        f"Error: {e}")
            self.logger.error(error_msg, exc_info=True)
            print(error_msg)
        
        # Update trade info after execution for reward calculation
        if action_type == 1 or action_type == 2:  # Buy or Sell
            # New position opened
            if self.account.current_trade:
                trade = list(self.account.current_trade.values())[0]
                entry_price = trade.open_price
                lot_size = trade.lotsize
                is_long = (trade.ordertype.value == 0)  # 0 = BUY
        elif action_type == 3:  # Close
            # Position closed, use stored values
            pass
        
        # Calculate reward with detailed transaction cost model
        current_balance = self.account.balance
        
        # Get current volatility from environment metrics
        volatility = None
        if hasattr(self.env, 'performance_metrics'):
            metrics = self.env.performance_metrics.get_all_metrics()
            volatility = metrics.get('volatility', None)
            # Convert annualized volatility to daily if needed
            if volatility is not None:
                volatility = volatility / np.sqrt(252)  # Convert to daily
        
        reward = self.env.calculate_reward(
            previous_balance, 
            current_balance, 
            action_type,  # Use action_type (0-3) for reward calculation, not encoded action
            has_position,
            transaction_cost=None,  # Use detailed model instead
            entry_price=entry_price,
            exit_price=exit_price,
            lot_size=lot_size,
            is_long=is_long,
            pair=pair,
            volatility=volatility
        )
        
        return reward
    
    def _simulate_action(self, action: int, previous_balance: float) -> float:
        """
        Simulate action without executing (for training without trading)
        Uses current price movement to estimate reward and mark-to-market balance
        """
        # Decode action to get pair_index and action_type
        pair_index, action_type = self.env.decode_action(action)
        
        # Validate pair_index
        if not self.env.data_providers or pair_index >= len(self.env.data_providers):
            return 0.0
        
        # Get currency pair for the selected pair_index
        pair = self.env.data_providers[pair_index].currency_pair
        
        if pair is None:
            return 0.0
        
        mid_price = None
        if pair.bid is not None and pair.ask is not None:
            try:
                mid_price = pair.mid_price
            except Exception:
                mid_price = (pair.ask + pair.bid) / 2
        
        has_position = self.simulated_position is not None
        
        current_balance_effective = self._get_effective_balance()
        
        # Get trade information for cost calculation (simulated)
        entry_price = None
        exit_price = None
        lot_size = None
        is_long = None
        
        if action_type == 1:  # Buy
            if not has_position:
                entry_price = pair.ask
                lot_size = self.risk_manager.calculate_position_size(
                    self.account, pair, entry_price
                ) if self.account and entry_price else 0.01
                is_long = True
                # Reserve entry costs immediately
                cost = self.env.transaction_cost_model.calculate_cost_for_action(
                    action=action,
                    entry_price=entry_price,
                    exit_price=None,
                    lot_size=lot_size,
                    is_long=is_long,
                    pair=pair,
                    volatility=None
                )
                self.simulated_balance -= cost
                self.simulated_position = {
                    'entry_price': entry_price,
                    'lot_size': lot_size,
                    'is_long': is_long,
                    'pair_index': pair_index  # Track which pair this position is for
                }
        elif action_type == 2:  # Sell
            if not has_position:
                entry_price = pair.bid
                lot_size = self.risk_manager.calculate_position_size(
                    self.account, pair, entry_price
                ) if self.account and entry_price else 0.01
                is_long = False
                cost = self.env.transaction_cost_model.calculate_cost_for_action(
                    action=action,
                    entry_price=entry_price,
                    exit_price=None,
                    lot_size=lot_size,
                    is_long=is_long,
                    pair=pair,
                    volatility=None
                )
                self.simulated_balance -= cost
                self.simulated_position = {
                    'entry_price': entry_price,
                    'lot_size': lot_size,
                    'is_long': is_long,
                    'pair_index': pair_index  # Track which pair this position is for
                }
        elif action_type == 3:  # Close
            if has_position:
                entry_price = self.simulated_position['entry_price']
                lot_size = self.simulated_position['lot_size']
                is_long = self.simulated_position['is_long']
                exit_price = pair.bid if is_long else pair.ask
                direction = 1 if is_long else -1
                pnl = (exit_price - entry_price) * direction * self.contract_size * lot_size
                cost = self.env.transaction_cost_model.calculate_cost_for_action(
                    action=action,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    lot_size=lot_size,
                    is_long=is_long,
                    pair=pair,
                    volatility=None
                )
                self.simulated_balance += (pnl - cost)
                self.simulated_position = None
        
        # Mark-to-market current balance (realized + unrealized)
        if self.simulated_position:
            entry_price = self.simulated_position['entry_price']
            lot_size = self.simulated_position['lot_size']
            is_long = self.simulated_position['is_long']
            direction = 1 if is_long else -1
            if mid_price is not None:
                unrealized = (mid_price - entry_price) * direction * self.contract_size * lot_size
                current_balance_effective = self.simulated_balance + unrealized
        else:
            current_balance_effective = self.simulated_balance
        
        # Get current volatility from environment metrics
        volatility = None
        if hasattr(self.env, 'performance_metrics'):
            metrics = self.env.performance_metrics.get_all_metrics()
            volatility = metrics.get('volatility', None)
            if volatility is not None:
                volatility = volatility / np.sqrt(252)  # Convert to daily
        
        reward = self.env.calculate_reward(
            previous_balance, 
            current_balance_effective, 
            action_type,  # Use action_type (0-3) for reward calculation, not encoded action
            has_position,
            transaction_cost=None,  # Use detailed model instead
            entry_price=entry_price,
            exit_price=exit_price,
            lot_size=lot_size,
            is_long=is_long,
            pair=pair,
            volatility=volatility
        )
        
        return reward
    
    # Episode and checkpoint management is now handled by EpisodeManager and CheckpointManager
    # These methods are kept for backward compatibility
    def _start_new_episode(self):
        """Start a new episode (delegates to EpisodeManager)"""
        current_balance = self.account.balance if self.account else 0.0
        self.episode_manager.start_episode(current_balance, self.logger)
        self.risk_manager.reset_daily(self.account)
    
    def _end_episode(self):
        """End current episode (delegates to EpisodeManager)"""
        current_balance = self.account.balance if self.account else 0.0
        summary = self.episode_manager.get_episode_summary(
            current_balance=current_balance,
            step_rewards=self.metrics_tracker.step_rewards,
            episode_losses=self.metrics_tracker.episode_losses,
            total_steps=self.metrics_tracker.total_steps,
            logger=self.logger
        )
        if summary:
            self.metrics_tracker.record_episode(
                episode_reward=summary.get('episode_reward', 0.0),
                profit=summary.get('profit', 0.0)
            )
        self.metrics_tracker.step_rewards = []
        self.metrics_tracker.episode_losses = []
        self.episode_manager.reset_episode()
    
    def _save_checkpoint(self):
        """Save checkpoint (delegates to CheckpointManager)"""
        metrics = self.metrics_tracker.get_metrics()
        self.checkpoint_manager.save_checkpoint(
            agent=self.agent,
            step=self.metrics_tracker.total_steps,
            episode=self.episode_manager.current_episode,
            metrics=metrics,
            logger=self.logger
        )
    
    def _save_final_checkpoint(self):
        """Save final checkpoint (delegates to CheckpointManager)"""
        metrics = self.metrics_tracker.get_metrics()
        self.checkpoint_manager.save_final(
            agent=self.agent,
            step=self.metrics_tracker.total_steps,
            episode=self.episode_manager.current_episode,
            metrics=metrics,
            logger=self.logger
        )
    
    def enable_trading(self):
        """Enable live trading (use with caution!)"""
        self.config.trading_enabled = True
        self.training_loop.config.trading_enabled = True
        self.logger.warning("⚠️  LIVE TRADING ENABLED - Real money at risk!")
        print("⚠️  LIVE TRADING ENABLED - Real money at risk!")
    
    def disable_trading(self):
        """Disable live trading"""
        self.config.trading_enabled = False
        self.training_loop.config.trading_enabled = False
        self.logger.info("Trading disabled - training only mode")
        print("Trading disabled - training only mode")
    
    # Properties for backward compatibility
    @property
    def total_steps(self):
        return self.metrics_tracker.total_steps
    
    @property
    def total_reward(self):
        return self.metrics_tracker.total_reward
    
    @property
    def current_episode(self):
        return self.episode_manager.current_episode
    
    @property
    def episode_start_time(self):
        return self.episode_manager.episode_start_time
    
    @property
    def episode_start_balance(self):
        return self.episode_manager.episode_start_balance
    
    @property
    def episode_rewards(self):
        return self.metrics_tracker.episode_rewards
    
    @property
    def episode_profits(self):
        return self.metrics_tracker.episode_profits
    
    @property
    def episode_losses(self):
        return self.metrics_tracker.episode_losses
    
    @property
    def step_rewards(self):
        return self.metrics_tracker.step_rewards
    
    @property
    def training_enabled(self):
        return self.config.training_enabled
    
    @property
    def trading_enabled(self):
        return self.config.trading_enabled
    
    @property
    def decision_interval(self):
        return self.config.decision_interval
    
    @property
    def episode_duration_hours(self):
        return self.config.episode_duration_hours
    
    @property
    def min_experiences_before_training(self):
        return self.config.min_experiences_before_training
    
    @property
    def save_freq_steps(self):
        return self.config.save_freq_steps

    def _get_effective_balance(self) -> float:
        """
        Get balance adjusted for simulation mode (mark-to-market when trading disabled)
        """
        if self.trading_enabled:
            return self.account.balance if self.account else 0.0
        
        if self.simulated_position:
            # Get the pair for the simulated position
            pair_index = self.simulated_position.get('pair_index', 0)
            if self.env.data_providers and pair_index < len(self.env.data_providers):
                pair = self.env.data_providers[pair_index].currency_pair
            else:
                pair = self.env.data_providers[0].currency_pair if self.env.data_providers else None
            
            if pair:
                mid_price = None
                if pair.bid is not None and pair.ask is not None:
                    try:
                        mid_price = pair.mid_price
                    except Exception:
                        mid_price = (pair.ask + pair.bid) / 2
                if mid_price is not None:
                    entry_price = self.simulated_position['entry_price']
                    lot_size = self.simulated_position['lot_size']
                    is_long = self.simulated_position['is_long']
                    direction = 1 if is_long else -1
                    unrealized = (mid_price - entry_price) * direction * self.contract_size * lot_size
                    return self.simulated_balance + unrealized
        return self.simulated_balance
