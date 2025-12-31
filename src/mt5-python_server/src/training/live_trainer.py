"""
Continuous Live Training for DQN Agent
Trains the agent on real-time market data as it arrives
"""
import os
import time
import threading
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
import json

from agents.dqn_agent import DQNAgent
from environments.live_env import LiveTradingEnv
from utils.risk_management import RiskManager
from models.account import Account


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
        save_freq_steps: int = 1000  # Save model every N steps
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
        """
        self.agent = agent
        self.env = environment
        self.account = account
        self.risk_manager = risk_manager
        self.save_dir = save_dir
        self.decision_interval = decision_interval
        self.training_enabled = training_enabled
        self.trading_enabled = trading_enabled
        self.episode_duration_hours = episode_duration_hours
        self.min_experiences_before_training = min_experiences_before_training
        self.save_freq_steps = save_freq_steps
        self.contract_size = 100000
        
        os.makedirs(save_dir, exist_ok=True)
        
        # Training state
        self.is_running = False
        self.training_thread = None
        self.simulated_balance = self.account.balance if self.account else 0.0
        self.simulated_position = None  # For train-only mode mark-to-market
        
        # Episode tracking
        self.current_episode = 1
        self.episode_start_time = datetime.now()
        self.episode_start_balance = account.balance if account else 0.0
        
        # Metrics
        self.total_steps = 0
        self.total_reward = 0.0
        self.episode_rewards = []
        self.episode_profits = []
        self.episode_losses = []
        self.step_rewards = []
        
        # Initialize risk manager
        if account:
            self.risk_manager.initialize(account)
    
    def start(self):
        """Start continuous live training"""
        if self.is_running:
            print("Live trainer is already running")
            return
        
        self.is_running = True
        self.episode_start_time = datetime.now()
        self.episode_start_balance = self.account.balance if self.account else 0.0
        
        print(f"=== Starting Live Training ===")
        print(f"Training: {'ENABLED' if self.training_enabled else 'DISABLED'}")
        print(f"Trading: {'ENABLED' if self.trading_enabled else 'DISABLED'}")
        print(f"Decision Interval: {self.decision_interval}s")
        print(f"Episode Duration: {self.episode_duration_hours} hours")
        print(f"Account: {self.account.login if self.account else 'N/A'}")
        print("=" * 40)
        
        # Start training in separate thread
        self.training_thread = threading.Thread(target=self._training_loop, daemon=True)
        self.training_thread.start()
    
    def stop(self):
        """Stop live training"""
        self.is_running = False
        if self.training_thread:
            self.training_thread.join(timeout=5)
        print("Live training stopped")
    
    def _training_loop(self):
        """Main training loop - runs continuously"""
        previous_state = None
        previous_balance = self._get_effective_balance()
        
        try:
            while self.is_running:
                # Wait for sufficient data
                state = self.env.get_state()
                
                # Check if we have enough data (need at least window_size)
                if state is None or state.shape[0] < self.env.window_size:
                    print(f"Waiting for data... (have {state.shape[0] if state is not None else 0}/{self.env.window_size})")
                    time.sleep(self.decision_interval)
                    previous_balance = self._get_effective_balance()
                    continue
                
                # Choose action
                action = self.agent.act(state, training=self.training_enabled)
                
                # Check risk limits
                can_trade, reason = self.risk_manager.can_trade(self.account)
                if not can_trade and action != 0:
                    action = 0  # Force hold
                    if self.training_enabled:
                        print(f"Action blocked: {reason}")
                
                # Execute action if trading enabled
                if self.trading_enabled:
                    reward = self._execute_action(action, previous_balance)
                else:
                    # Simulate action for training (no real execution)
                    reward = self._simulate_action(action, previous_balance)
                
                # Get next state
                next_state = self.env.get_state()
                
                # Check if episode should end (time-based)
                episode_elapsed = datetime.now() - self.episode_start_time
                done = episode_elapsed.total_seconds() >= (self.episode_duration_hours * 3600)
                
                # Store experience for training
                if previous_state is not None and self.training_enabled:
                    self.agent.remember(previous_state, action, reward, next_state, done)
                    
                    # Train if we have enough experiences
                    if len(self.agent.memory) >= self.min_experiences_before_training:
                        loss = self.agent.replay()
                        if loss > 0:
                            self.episode_losses.append(loss)
                
                # Update metrics
                current_balance = self._get_effective_balance()
                self.total_reward += reward
                self.total_steps += 1
                self.step_rewards.append(reward)
                
                # Log periodically
                if self.total_steps % 10 == 0:
                    profit = current_balance - self.episode_start_balance
                    profit_pct = (profit / self.episode_start_balance * 100) if self.episode_start_balance > 0 else 0.0
                    
                    avg_loss = np.mean(self.episode_losses[-10:]) if self.episode_losses else 0.0
                    
                    print(f"[Step {self.total_steps}] Action: {action}, "
                          f"Reward: {reward:.4f}, "
                          f"Balance: {current_balance:.2f}, "
                          f"Profit: {profit:.2f} ({profit_pct:.2f}%), "
                          f"Experiences: {len(self.agent.memory)}, "
                          f"Loss: {avg_loss:.4f}, "
                          f"Epsilon: {self.agent.epsilon:.4f}, "
                          f"Mode: {'TRADING' if self.trading_enabled else 'SIM'}")
                
                # Save checkpoint periodically
                if self.total_steps % self.save_freq_steps == 0:
                    self._save_checkpoint()
                
                # Handle episode end
                if done:
                    self._end_episode()
                    self._start_new_episode()
                
                previous_state = state
                previous_balance = current_balance
                
                # Wait before next decision
                time.sleep(self.decision_interval)
        
        except KeyboardInterrupt:
            print("\nTraining interrupted by user")
        except Exception as e:
            print(f"Error in training loop: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._end_episode()
            self._save_final_checkpoint()
    
    def _execute_action(self, action: int, previous_balance: float) -> float:
        """Execute action and return reward"""
        has_position = len(self.account.current_trade) > 0 if self.account else False
        
        # Get currency pair
        pair = None
        if self.env.data_providers:
            pair = self.env.data_providers[0].currency_pair
        
        if pair is None:
            return 0.0
        
        # Initialize trade information variables
        entry_price = None
        exit_price = None
        lot_size = None
        is_long = None
        
        try:
            from codes.order_type import OrderType
            
            if action == 1:  # Buy
                if not has_position and self.risk_manager.can_trade(self.account)[0]:
                    entry_price = pair.ask
                    lot_size = self.risk_manager.calculate_position_size(
                        self.account, pair, entry_price
                    )
                    is_long = True
                    sl = self.risk_manager.calculate_stop_loss(entry_price, True)
                    tp = self.risk_manager.calculate_take_profit(entry_price, True)
                    
                    self.account.send_order(OrderType.BUY, pair, lot_size, None, sl, tp)
            
            elif action == 2:  # Sell
                if not has_position and self.risk_manager.can_trade(self.account)[0]:
                    entry_price = pair.bid
                    lot_size = self.risk_manager.calculate_position_size(
                        self.account, pair, entry_price
                    )
                    is_long = False
                    sl = self.risk_manager.calculate_stop_loss(entry_price, False)
                    tp = self.risk_manager.calculate_take_profit(entry_price, False)
                    
                    self.account.send_order(OrderType.SELL, pair, lot_size, None, sl, tp)
            
            elif action == 3:  # Close position
                if has_position and self.account.current_trade:
                    # Get information from existing trade before closing
                    trade = list(self.account.current_trade.values())[0]
                    entry_price = trade.open_price
                    lot_size = trade.lotsize
                    # Determine if long or short from order type
                    # OrderType.BUY = 0, OrderType.SELL = 1
                    is_long = (trade.ordertype.value == 0)  # 0 = BUY
                    # Exit price is the opposite of entry (bid for long, ask for short)
                    exit_price = pair.bid if is_long else pair.ask
                    
                    for ticket in list(self.account.current_trade.keys()):
                        self.account.close_order(ticket)
        
        except Exception as e:
            print(f"Error executing action {action}: {e}")
        
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
            action, 
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
        has_position = self.simulated_position is not None
        
        # Get currency pair
        pair = None
        if self.env.data_providers:
            pair = self.env.data_providers[0].currency_pair
        
        if pair is None:
            return 0.0
        mid_price = None
        if pair.bid is not None and pair.ask is not None:
            try:
                mid_price = pair.mid_price
            except Exception:
                mid_price = (pair.ask + pair.bid) / 2
        
        current_balance_effective = self._get_effective_balance()
        
        # Get trade information for cost calculation (simulated)
        entry_price = None
        exit_price = None
        lot_size = None
        is_long = None
        
        if action == 1:  # Buy
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
                    'is_long': is_long
                }
        elif action == 2:  # Sell
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
                    'is_long': is_long
                }
        elif action == 3:  # Close
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
            action, 
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
    
    def _start_new_episode(self):
        """Start a new episode"""
        self.current_episode += 1
        self.episode_start_time = datetime.now()
        self.episode_start_balance = self.account.balance if self.account else 0.0
        self.risk_manager.reset_daily(self.account)
        print(f"\n=== Starting Episode {self.current_episode} ===")
    
    def _end_episode(self):
        """End current episode and record metrics"""
        episode_duration = datetime.now() - self.episode_start_time
        final_balance = self.account.balance if self.account else 0.0
        profit = final_balance - self.episode_start_balance
        profit_pct = (profit / self.episode_start_balance * 100) if self.episode_start_balance > 0 else 0.0
        
        episode_reward = sum(self.step_rewards)
        avg_loss = np.mean(self.episode_losses) if self.episode_losses else 0.0
        
        self.episode_rewards.append(episode_reward)
        self.episode_profits.append(profit)
        
        print(f"\n=== Episode {self.current_episode} Complete ===")
        print(f"Duration: {episode_duration}")
        print(f"Total Reward: {episode_reward:.2f}")
        print(f"Profit: {profit:.2f} ({profit_pct:.2f}%)")
        print(f"Average Loss: {avg_loss:.4f}")
        print(f"Total Steps: {self.total_steps}")
        print("=" * 40)
        
        # Reset episode metrics
        self.step_rewards = []
        self.episode_losses = []
    
    def _save_checkpoint(self):
        """Save model checkpoint"""
        checkpoint_dir = os.path.join(self.save_dir, f"live_checkpoint_step{self.total_steps}")
        os.makedirs(checkpoint_dir, exist_ok=True)
        
        self.agent.save(checkpoint_dir)
        
        # Save metrics
        metrics = {
            'total_steps': self.total_steps,
            'current_episode': self.current_episode,
            'total_reward': self.total_reward,
            'episode_rewards': self.episode_rewards[-50:],  # Last 50 episodes
            'episode_profits': self.episode_profits[-50:],
            'experiences': len(self.agent.memory),
            'epsilon': self.agent.epsilon,
            'timestamp': datetime.now().isoformat()
        }
        
        metrics_file = os.path.join(checkpoint_dir, 'metrics.json')
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        print(f"Checkpoint saved: {checkpoint_dir}")
    
    def _save_final_checkpoint(self):
        """Save final checkpoint"""
        final_dir = os.path.join(self.save_dir, f"live_final_step{self.total_steps}")
        os.makedirs(final_dir, exist_ok=True)
        
        self.agent.save(final_dir)
        
        # Save complete metrics
        metrics = {
            'total_steps': self.total_steps,
            'total_episodes': self.current_episode,
            'total_reward': self.total_reward,
            'episode_rewards': self.episode_rewards,
            'episode_profits': self.episode_profits,
            'experiences': len(self.agent.memory),
            'epsilon': self.agent.epsilon,
            'timestamp': datetime.now().isoformat()
        }
        
        metrics_file = os.path.join(final_dir, 'metrics.json')
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        print(f"Final checkpoint saved: {final_dir}")
    
    def enable_trading(self):
        """Enable live trading (use with caution!)"""
        self.trading_enabled = True
        print("⚠️  LIVE TRADING ENABLED - Real money at risk!")
    
    def disable_trading(self):
        """Disable live trading"""
        self.trading_enabled = False
        print("Trading disabled - training only mode")

    def _get_effective_balance(self) -> float:
        """
        Get balance adjusted for simulation mode (mark-to-market when trading disabled)
        """
        if self.trading_enabled:
            return self.account.balance if self.account else 0.0
        
        if self.simulated_position:
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
