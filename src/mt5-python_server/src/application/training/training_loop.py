"""
Training loop for live training
Extracted from LiveTrainer to isolate training logic
"""
import time
import numpy as np
from datetime import datetime
from typing import Optional

from agents.dqn_agent import DQNAgent
from environments.live_env import LiveTradingEnv
from models.account import Account
from utils.risk_management import RiskManager
from application.services.action_executor import ActionExecutor
from application.training.metrics_tracker import MetricsTracker
from application.training.checkpoint_manager import CheckpointManager
from application.training.episode_manager import EpisodeManager
from domain.config.training_config import TrainingConfig


class TrainingLoop:
    """Main training loop for live training"""
    
    def __init__(
        self,
        agent: DQNAgent,
        environment: LiveTradingEnv,
        action_executor: ActionExecutor,
        metrics_tracker: MetricsTracker,
        checkpoint_manager: CheckpointManager,
        episode_manager: EpisodeManager,
        account: Account,
        risk_manager: RiskManager,
        config: TrainingConfig,
        get_effective_balance_func,
        logger,
        simulate_action_func=None
    ):
        """
        Initialize training loop
        :param agent: DQN agent
        :param environment: Trading environment
        :param action_executor: Action executor service
        :param metrics_tracker: Metrics tracker
        :param checkpoint_manager: Checkpoint manager
        :param episode_manager: Episode manager
        :param account: Trading account
        :param risk_manager: Risk manager
        :param config: Training configuration
        :param get_effective_balance_func: Function to get effective balance
        :param logger: Logger instance
        """
        self.agent = agent
        self.env = environment
        self.action_executor = action_executor
        self.metrics_tracker = metrics_tracker
        self.checkpoint_manager = checkpoint_manager
        self.episode_manager = episode_manager
        self.account = account
        self.risk_manager = risk_manager
        self.config = config
        self.get_effective_balance = get_effective_balance_func
        self.logger = logger
        self.simulate_action_func = simulate_action_func
        
        self.is_running = False
        self.previous_state = None
    
    def run(self):
        """Run the training loop"""
        self.is_running = True
        previous_balance = self.get_effective_balance()
        
        try:
            while self.is_running:
                # Wait for sufficient data
                state = self._wait_for_state()
                if state is None:
                    time.sleep(self.config.decision_interval)
                    previous_balance = self.get_effective_balance()
                    continue
                
                # Select action
                action = self._select_action(state)
                
                # Execute action
                reward = self._execute_action(action, previous_balance, self.simulate_action_func)
                
                # Get current balance after action
                current_balance = self.get_effective_balance()
                
                # Calculate reward if trading enabled (balance change based)
                if self.config.trading_enabled and reward == 0.0:
                    # Calculate reward from balance change
                    balance_change = current_balance - previous_balance
                    reward = balance_change / previous_balance if previous_balance > 0 else 0.0
                
                # Get next state
                next_state = self.env.get_state()
                
                # Check if episode should end
                done = self.episode_manager.should_end_episode()
                
                # Record experience and train
                if self.previous_state is not None and self.config.training_enabled:
                    self._record_experience(self.previous_state, action, reward, next_state, done)
                    loss = self._train_if_ready()
                    if loss is not None:
                        self.metrics_tracker.record_step(reward, loss)
                    else:
                        self.metrics_tracker.record_step(reward)
                else:
                    self.metrics_tracker.record_step(reward)
                
                # Update metrics and log
                self._update_and_log_metrics(action, reward, current_balance, previous_balance)
                
                # Save checkpoint if needed
                if self.checkpoint_manager.should_save(self.metrics_tracker.total_steps):
                    self._save_checkpoint()
                
                # Handle episode end
                if done:
                    self._end_episode(current_balance)
                    self._start_new_episode(current_balance)
                
                self.previous_state = state
                previous_balance = current_balance
                
                # Wait before next decision
                time.sleep(self.config.decision_interval)
        
        except KeyboardInterrupt:
            if hasattr(self.logger, 'log_event'):
                self.logger.log_event(
                    event_type='training_interrupted',
                    message="Training interrupted by user",
                    level='WARNING'
                )
            else:
                self.logger.warning("Training interrupted by user")
            print("\nTraining interrupted by user")
        except Exception as e:
            if hasattr(self.logger, 'log_error'):
                self.logger.log_error(
                    event_type='training_loop_error',
                    error=f"Error in training loop: {e}",
                    exc_info=True
                )
            else:
                self.logger.error(f"Error in training loop: {e}", exc_info=True)
            print(f"Error in training loop: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if hasattr(self.logger, 'log_event'):
                self.logger.log_event(
                    event_type='training_loop_ended',
                    message="Training loop ended, saving final checkpoint"
                )
            else:
                self.logger.info("Training loop ended, saving final checkpoint")
            self._end_episode(self.get_effective_balance())
            self._save_final_checkpoint()
    
    def stop(self):
        """Stop the training loop"""
        self.is_running = False
    
    def _wait_for_state(self) -> Optional[np.ndarray]:
        """Wait for sufficient data and return state"""
        state = self.env.get_state()
        
        if state is None or state.shape[0] < self.env.window_size:
            # Log detailed data availability per pair
            data_status = []
            if self.env.data_providers:
                for provider in self.env.data_providers:
                    symbol = provider.currency_pair.symbol
                    history_len = len(self.env.price_history_by_pair.get(symbol, []))
                    data_status.append(f"{symbol}: {history_len}/{self.env.window_size}")
            
            msg = (f"Waiting for data... (have {state.shape[0] if state is not None else 0}/{self.env.window_size}) | "
                   f"Pairs: {', '.join(data_status) if data_status else 'none'}")
            if hasattr(self.logger, 'log_event'):
                self.logger.log_event(
                    event_type='waiting_for_data',
                    message=msg,
                    metrics={
                        'current_data_points': state.shape[0] if state is not None else 0,
                        'required_data_points': self.env.window_size,
                        'data_status': data_status
                    },
                    level='DEBUG' if self.metrics_tracker.total_steps % 5 != 0 else 'INFO'
                )
            else:
                self.logger.debug(msg)
                if self.metrics_tracker.total_steps % 5 == 0:
                    self.logger.info(msg)
            print(msg)
            return None
        
        # Log state information periodically
        if self.metrics_tracker.total_steps % 20 == 0:
            if hasattr(self.logger, 'log_event'):
                self.logger.log_event(
                    event_type='state_info',
                    message="State information",
                    metrics={
                        'state_shape': state.shape,
                        'state_min': float(state.min()),
                        'state_max': float(state.max())
                    },
                    level='DEBUG'
                )
            else:
                self.logger.debug(f"State shape: {state.shape}, State range: [{state.min():.6f}, {state.max():.6f}]")
        
        return state
    
    def _select_action(self, state: np.ndarray) -> int:
        """Select action from agent"""
        action = self.agent.act(state, training=self.config.training_enabled)
        
        # Check risk limits and force hold if needed
        can_trade, reason = self.risk_manager.can_trade(self.account)
        if not can_trade and action != 0:
            action = 0  # Force hold
            pair_index, _ = self.env.decode_action(action)
            pair_symbol = (self.env.data_providers[pair_index].currency_pair.symbol 
                          if self.env.data_providers and pair_index < len(self.env.data_providers) 
                          else "UNKNOWN")
            if self.config.training_enabled:
                if hasattr(self.logger, 'log_event'):
                    self.logger.log_event(
                        event_type='action_blocked',
                        message=f"Action blocked on {pair_symbol}: {reason}",
                        symbol=pair_symbol,
                        metrics={'reason': reason},
                        level='WARNING'
                    )
                else:
                    self.logger.warning(f"Action blocked on {pair_symbol}: {reason}")
                print(f"Action blocked: {reason}")
        
        return action
    
    def _execute_action(self, action: int, previous_balance: float, simulate_func=None) -> float:
        """
        Execute action and return reward
        :param action: Action to execute
        :param previous_balance: Previous balance
        :param simulate_func: Optional function to simulate action (for training mode)
        :return: Reward value
        """
        if self.config.trading_enabled:
            if hasattr(self.logger, 'log_event'):
                self.logger.log_event(
                    event_type='action_execution',
                    message=f"Executing action: {action}",
                    metrics={'action': action},
                    level='DEBUG'
                )
            else:
                self.logger.debug(f"Executing action: {action}")
            # Execute action via executor
            self.action_executor.execute(
                action=action,
                environment=self.env,
                account=self.account,
                risk_manager=self.risk_manager,
                previous_balance=previous_balance,
                trading_enabled=self.config.trading_enabled
            )
            # Reward will be calculated by environment based on balance change
            # For now return 0, actual reward calculated in update step
            return 0.0
        else:
            # Simulate action for training (no real execution)
            if hasattr(self.logger, 'log_event'):
                self.logger.log_event(
                    event_type='action_simulation',
                    message=f"Simulating action: {action}",
                    metrics={'action': action},
                    level='DEBUG'
                )
            else:
                self.logger.debug(f"Simulating action: {action}")
            if simulate_func:
                return simulate_func(action, previous_balance)
            # Fallback: return 0.0 if no simulation function provided
            return 0.0
    
    def _record_experience(self, state, action, reward, next_state, done):
        """Record experience for training"""
        self.agent.remember(state, action, reward, next_state, done)
    
    def _train_if_ready(self) -> Optional[float]:
        """Train agent if enough experiences"""
        if len(self.agent.memory) >= self.config.min_experiences_before_training:
            loss = self.agent.replay()
            if loss > 0:
                if self.metrics_tracker.total_steps % 10 == 0:
                    if hasattr(self.logger, 'log_event'):
                        self.logger.log_event(
                            event_type='training_step',
                            message="Training step completed",
                            metrics={
                                'loss': loss,
                                'memory_size': len(self.agent.memory),
                                'step': self.metrics_tracker.total_steps
                            },
                            level='DEBUG'
                        )
                    else:
                        self.logger.debug(f"Training step completed | Loss: {loss:.6f} | Memory size: {len(self.agent.memory)}")
                return loss
        return None
    
    def _update_and_log_metrics(self, action: int, reward: float, current_balance: float, previous_balance: float):
        """Update metrics and log information"""
        # Decode action for logging
        pair_index, action_type = self.env.decode_action(action)
        action_names = {0: "HOLD", 1: "BUY", 2: "SELL", 3: "CLOSE"}
        pair_symbol = (self.env.data_providers[pair_index].currency_pair.symbol 
                       if self.env.data_providers and pair_index < len(self.env.data_providers) 
                       else "UNKNOWN")
        action_name = action_names.get(action_type, "UNKNOWN")
        
        has_position = len(self.account.current_trade) > 0 if self.account else False
        
        # Calculate profit
        profit = current_balance - self.episode_manager.episode_start_balance
        profit_pct = (profit / self.episode_manager.episode_start_balance * 100) if self.episode_manager.episode_start_balance > 0 else 0.0
        
        avg_loss = self.metrics_tracker.get_average_loss(10)
        
        # Get position information
        position_info = "No position"
        if has_position and self.account and self.account.current_trade:
            trades = list(self.account.current_trade.values())
            if trades:
                trade = trades[0]
                position_info = f"Position: {trade.ordertype.name} {trade.lotsize} lots @ {trade.open_price:.5f} (P/L: {trade.profit:.2f})"
        
        # Detailed log message
        log_msg = (f"[Step {self.metrics_tracker.total_steps}] Action: {action} ({action_name} on {pair_symbol}) | "
                  f"Reward: {reward:.4f} | "
                  f"Balance: {current_balance:.2f} | "
                  f"Profit: {profit:.2f} ({profit_pct:.2f}%) | "
                  f"{position_info} | "
                  f"Experiences: {len(self.agent.memory)} | "
                  f"Loss: {avg_loss:.4f} | "
                  f"Epsilon: {self.agent.epsilon:.4f} | "
                  f"Mode: {'TRADING' if self.config.trading_enabled else 'SIM'}")
        
        # Prepare metrics for structured logging
        metrics = {
            'step': self.metrics_tracker.total_steps,
            'action': action,
            'action_name': action_name,
            'reward': reward,
            'balance': current_balance,
            'profit': profit,
            'profit_pct': profit_pct,
            'experiences': len(self.agent.memory),
            'loss': avg_loss,
            'epsilon': self.agent.epsilon,
            'mode': 'TRADING' if self.config.trading_enabled else 'SIM'
        }
        
        # Log at different levels based on importance
        if hasattr(self.logger, 'log_event'):
            level = 'INFO' if self.metrics_tracker.total_steps % 10 == 0 else 'DEBUG'
            self.logger.log_event(
                event_type='training_metrics',
                message=log_msg,
                symbol=pair_symbol,
                metrics=metrics,
                level=level
            )
        else:
            if self.metrics_tracker.total_steps % 10 == 0:
                self.logger.info(log_msg)
            else:
                self.logger.debug(log_msg)
        
        # Always print to console for visibility
        if self.metrics_tracker.total_steps % 5 == 0:
            print(log_msg)
    
    def _save_checkpoint(self):
        """Save checkpoint"""
        metrics = self.metrics_tracker.get_metrics()
        if hasattr(self.logger, 'log_event'):
            self.logger.log_event(
                event_type='checkpoint_saved',
                message=f"Saving checkpoint at step {self.metrics_tracker.total_steps}",
                metrics={
                    'step': self.metrics_tracker.total_steps,
                    'episode': self.episode_manager.current_episode,
                    **metrics
                }
            )
        else:
            self.logger.info(f"Saving checkpoint at step {self.metrics_tracker.total_steps}")
        self.checkpoint_manager.save_checkpoint(
            agent=self.agent,
            step=self.metrics_tracker.total_steps,
            episode=self.episode_manager.current_episode,
            metrics=metrics,
            logger=self.logger
        )
    
    def _save_final_checkpoint(self):
        """Save final checkpoint"""
        metrics = self.metrics_tracker.get_metrics()
        self.checkpoint_manager.save_final(
            agent=self.agent,
            step=self.metrics_tracker.total_steps,
            episode=self.episode_manager.current_episode,
            metrics=metrics,
            logger=self.logger
        )
    
    def _end_episode(self, current_balance: float):
        """End current episode"""
        # Get step rewards and losses from metrics tracker
        step_rewards = self.metrics_tracker.step_rewards
        episode_losses = self.metrics_tracker.episode_losses
        
        summary = self.episode_manager.get_episode_summary(
            current_balance=current_balance,
            step_rewards=step_rewards,
            episode_losses=episode_losses,
            total_steps=self.metrics_tracker.total_steps,
            logger=self.logger
        )
        
        # Record episode metrics
        if summary:
            self.metrics_tracker.record_episode(
                episode_reward=summary.get('episode_reward', 0.0),
                profit=summary.get('profit', 0.0)
            )
        
        # Reset episode-specific metrics
        self.metrics_tracker.step_rewards = []
        self.metrics_tracker.episode_losses = []
        self.episode_manager.reset_episode()
    
    def _start_new_episode(self, current_balance: float):
        """Start new episode"""
        self.episode_manager.start_episode(current_balance, self.logger)
        self.risk_manager.reset_daily(self.account)
