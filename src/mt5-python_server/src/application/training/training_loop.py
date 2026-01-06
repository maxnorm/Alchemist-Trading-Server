"""
Training loop for live training
Extracted from LiveTrainer to isolate training logic

Includes MLflow experiment tracking integration for:
- Logging hyperparameters at run start
- Logging metrics at each step
- Logging checkpoints as artifacts
- Registering trained models
"""

import time
import numpy as np
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from agents.dqn_agent import DQNAgent
from environments.live_env import LiveTradingEnv
from models.account import Account
from utils.risk_management import RiskManager
from application.services.action_executor import ActionExecutor
from application.training.metrics_tracker import MetricsTracker
from application.training.checkpoint_manager import CheckpointManager
from application.training.episode_manager import EpisodeManager
from domain.config.training_config import TrainingConfig

if TYPE_CHECKING:
    from mlops.experiment_tracker import ExperimentTracker


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
        simulate_action_func=None,
        experiment_tracker: Optional["ExperimentTracker"] = None,
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
        :param simulate_action_func: Optional function to simulate actions
        :param experiment_tracker: Optional MLflow experiment tracker
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
        self.tracker = experiment_tracker

        self.is_running = False
        self.previous_state = None

    def run(self):
        """Run the training loop with MLflow tracking"""
        self.is_running = True
        previous_balance = self.get_effective_balance()

        # Start MLflow run if tracker is available
        run_name = f"live_training_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if self.tracker:
            try:
                self.tracker.start_run(run_name)
                self._log_training_params()
            except Exception as e:
                self.logger.warning(f"Failed to start MLflow run: {e}")

        try:
            while self.is_running:
                # Update adaptive epsilon periodically
                self._update_adaptive_epsilon()

                # Wait for sufficient data
                state = self._wait_for_state()
                if state is None:
                    time.sleep(self.config.decision_interval)
                    previous_balance = self.get_effective_balance()
                    continue

                # Select action
                action = self._select_action(state)

                # Execute action
                reward = self._execute_action(
                    action, previous_balance, self.simulate_action_func
                )

                # Get current balance after action
                current_balance = self.get_effective_balance()

                # Calculate reward if trading enabled (balance change based)
                if self.config.trading_enabled and reward == 0.0:
                    # Calculate reward from balance change
                    balance_change = current_balance - previous_balance
                    reward = (
                        balance_change / previous_balance
                        if previous_balance > 0
                        else 0.0
                    )

                # Get next state with latency awareness (training mode for point-in-time constraint)
                next_state = self.env.get_state(mode='training', include_latency=True)

                # Check if episode should end
                done = self.episode_manager.should_end_episode()

                # Record experience and train
                if self.previous_state is not None and self.config.training_enabled:
                    self._record_experience(
                        self.previous_state, action, reward, next_state, done
                    )
                    loss = self._train_if_ready()
                    if loss is not None:
                        self.metrics_tracker.record_step(reward, loss)
                    else:
                        self.metrics_tracker.record_step(reward)
                else:
                    self.metrics_tracker.record_step(reward)

                # Log metrics to MLflow periodically
                if self.tracker and self.metrics_tracker.total_steps % 10 == 0:
                    self._log_step_metrics(reward, current_balance)

                # Update metrics and log
                self._update_and_log_metrics(
                    action, reward, current_balance, previous_balance
                )

                # Save checkpoint if needed
                if self.checkpoint_manager.should_save(
                    self.metrics_tracker.total_steps
                ):
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
            if hasattr(self.logger, "log_event"):
                self.logger.log_event(
                    event_type="training_interrupted",
                    message="Training interrupted by user",
                    level="WARNING",
                )
            else:
                self.logger.warning("Training interrupted by user")
            print("\nTraining interrupted by user")
        except Exception as e:
            if hasattr(self.logger, "log_error"):
                self.logger.log_error(
                    event_type="training_loop_error",
                    error=f"Error in training loop: {e}",
                    exc_info=True,
                )
            else:
                self.logger.error(f"Error in training loop: {e}", exc_info=True)
            print(f"Error in training loop: {e}")
            import traceback

            traceback.print_exc()
        finally:
            if hasattr(self.logger, "log_event"):
                self.logger.log_event(
                    event_type="training_loop_ended",
                    message="Training loop ended, saving final checkpoint",
                )
            else:
                self.logger.info("Training loop ended, saving final checkpoint")
            self._end_episode(self.get_effective_balance())
            self._save_final_checkpoint()

            # End MLflow run
            if self.tracker:
                try:
                    self._log_final_metrics()
                    self.tracker.end_run()
                except Exception as e:
                    self.logger.warning(f"Failed to end MLflow run: {e}")

    def stop(self):
        """Stop the training loop"""
        self.is_running = False

    def _wait_for_state(self) -> Optional[np.ndarray]:
        """Wait for sufficient data and return state with latency awareness"""
        state = self.env.get_state(mode='training', include_latency=True)

        if state is None or state.shape[0] < self.env.window_size:
            # Log detailed data availability per pair
            data_status = []
            if self.env.data_providers:
                for provider in self.env.data_providers:
                    symbol = provider.currency_pair.symbol
                    history_len = len(self.env.price_history_by_pair.get(symbol, []))
                    data_status.append(
                        f"{symbol}: {history_len}/{self.env.window_size}"
                    )

            msg = (
                f"Waiting for data... (have {state.shape[0] if state is not None else 0}/{self.env.window_size}) | "
                f"Pairs: {', '.join(data_status) if data_status else 'none'}"
            )
            if hasattr(self.logger, "log_event"):
                self.logger.log_event(
                    event_type="waiting_for_data",
                    message=msg,
                    metrics={
                        "current_data_points": (
                            state.shape[0] if state is not None else 0
                        ),
                        "required_data_points": self.env.window_size,
                        "data_status": data_status,
                    },
                    level=(
                        "DEBUG" if self.metrics_tracker.total_steps % 5 != 0 else "INFO"
                    ),
                )
            else:
                self.logger.debug(msg)
                if self.metrics_tracker.total_steps % 5 == 0:
                    self.logger.info(msg)
            print(msg)
            return None

        # Log state information periodically
        if self.metrics_tracker.total_steps % 20 == 0:
            if hasattr(self.logger, "log_event"):
                self.logger.log_event(
                    event_type="state_info",
                    message="State information",
                    metrics={
                        "state_shape": state.shape,
                        "state_min": float(state.min()),
                        "state_max": float(state.max()),
                    },
                    level="DEBUG",
                )
            else:
                self.logger.debug(
                    f"State shape: {state.shape}, State range: [{state.min():.6f}, {state.max():.6f}]"
                )

        return state

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

    def _update_adaptive_epsilon(self):
        """Update epsilon adaptively based on current experience count and performance"""
        if not self.config.training_enabled:
            return

        experience_count = len(self.agent.memory)

        # Get recent rewards for performance-based adjustment
        recent_rewards = None
        if (
            hasattr(self.metrics_tracker, "step_rewards")
            and len(self.metrics_tracker.step_rewards) > 0
        ):
            recent_rewards = self.metrics_tracker.step_rewards

        # Update epsilon every 10 steps to avoid constant updates
        if experience_count > 0 and self.metrics_tracker.total_steps % 10 == 0:
            old_epsilon = self.agent.epsilon
            new_epsilon = self.agent.update_epsilon_adaptive(
                experience_count, recent_rewards
            )

            # Log significant changes
            if abs(old_epsilon - new_epsilon) > 0.05:
                if hasattr(self.logger, "log_event"):
                    self.logger.log_event(
                        event_type="epsilon_update",
                        message=f"Adaptive epsilon updated: {old_epsilon:.4f} -> {new_epsilon:.4f}",
                        metrics={
                            "old_epsilon": old_epsilon,
                            "new_epsilon": new_epsilon,
                            "experience_count": experience_count,
                            "step": self.metrics_tracker.total_steps,
                        },
                        level="DEBUG",
                    )
                else:
                    self.logger.debug(
                        f"Adaptive epsilon update: {old_epsilon:.4f} -> {new_epsilon:.4f} "
                        f"(experiences: {experience_count}, step: {self.metrics_tracker.total_steps})"
                    )

    def _select_action(self, state: np.ndarray) -> int:
        """Select action from agent with action masking"""
        # Build action mask based on current state
        action_mask = self._build_action_mask()

        # Select action with masking
        action = self.agent.act(
            state, training=self.config.training_enabled, action_mask=action_mask
        )

        # Check risk limits and force hold if needed
        can_trade, reason = self.risk_manager.can_trade(self.account)
        if not can_trade and action != 0:
            action = 0  # Force hold (global HOLD, no pair)
            if self.config.training_enabled:
                if hasattr(self.logger, "log_event"):
                    self.logger.log_event(
                        event_type="action_blocked",
                        message=f"Action blocked: {reason} (forced HOLD)",
                        metrics={"reason": reason},
                        level="WARNING",
                    )
                else:
                    self.logger.warning(f"Action blocked: {reason} (forced HOLD)")
                print(f"Action blocked: {reason}")

        return action

    def _execute_action(
        self, action: int, previous_balance: float, simulate_func=None
    ) -> float:
        """
        Execute action and return reward
        :param action: Action to execute
        :param previous_balance: Previous balance
        :param simulate_func: Optional function to simulate action (for training mode)
        :return: Reward value
        """
        if self.config.trading_enabled:
            if hasattr(self.logger, "log_event"):
                self.logger.log_event(
                    event_type="action_execution",
                    message=f"Executing action: {action}",
                    metrics={"action": action},
                    level="DEBUG",
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
                trading_enabled=self.config.trading_enabled,
            )
            # Reward will be calculated by environment based on balance change
            # For now return 0, actual reward calculated in update step
            return 0.0
        else:
            # Simulate action for training (no real execution)
            if hasattr(self.logger, "log_event"):
                self.logger.log_event(
                    event_type="action_simulation",
                    message=f"Simulating action: {action}",
                    metrics={"action": action},
                    level="DEBUG",
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
                    if hasattr(self.logger, "log_event"):
                        self.logger.log_event(
                            event_type="training_step",
                            message="Training step completed",
                            metrics={
                                "loss": loss,
                                "memory_size": len(self.agent.memory),
                                "step": self.metrics_tracker.total_steps,
                            },
                            level="DEBUG",
                        )
                    else:
                        self.logger.debug(
                            f"Training step completed | Loss: {loss:.6f} | Memory size: {len(self.agent.memory)}"
                        )
                return loss
        return None

    def _update_and_log_metrics(
        self,
        action: int,
        reward: float,
        current_balance: float,
        previous_balance: float,
    ):
        """Update metrics and log information"""
        # Handle global HOLD (action 0) specially
        if action == 0:
            action_name = "HOLD"
            pair_symbol = "N/A"
        else:
            # Decode action for logging
            pair_index, action_type = self.env.decode_action(action)
            action_names = {1: "BUY", 2: "SELL", 3: "CLOSE"}
            pair_symbol = (
                self.env.data_providers[pair_index].currency_pair.symbol
                if self.env.data_providers
                and pair_index is not None
                and pair_index < len(self.env.data_providers)
                else "UNKNOWN"
            )
            action_name = action_names.get(
                action_type.value if hasattr(action_type, "value") else action_type,
                "UNKNOWN",
            )

        has_position = len(self.account.current_trade) > 0 if self.account else False

        # Calculate profit
        profit = current_balance - self.episode_manager.episode_start_balance
        profit_pct = (
            (profit / self.episode_manager.episode_start_balance * 100)
            if self.episode_manager.episode_start_balance > 0
            else 0.0
        )

        avg_loss = self.metrics_tracker.get_average_loss(10)

        # Get position information
        position_info = "No position"
        if has_position and self.account and self.account.current_trade:
            trades = list(self.account.current_trade.values())
            if trades:
                trade = trades[0]
                position_info = (
                    f"Position: {trade.ordertype.name} {trade.lotsize} lots "
                    f"@ {trade.open_price:.5f} (P/L: {trade.profit:.2f})"
                )

        # Detailed log message
        if action == 0:
            action_desc = f"{action_name}"
        else:
            action_desc = f"{action_name} on {pair_symbol}"

        log_msg = (
            f"[Step {self.metrics_tracker.total_steps}] Action: {action} ({action_desc}) | "
            f"Reward: {reward:.4f} | "
            f"Balance: {current_balance:.2f} | "
            f"Profit: {profit:.2f} ({profit_pct:.2f}%) | "
            f"{position_info} | "
            f"Experiences: {len(self.agent.memory)} | "
            f"Loss: {avg_loss:.4f} | "
            f"Epsilon: {self.agent.epsilon:.4f} | "
            f"Mode: {'TRADING' if self.config.trading_enabled else 'SIM'}"
        )

        # Prepare metrics for structured logging
        metrics = {
            "step": self.metrics_tracker.total_steps,
            "action": action,
            "action_name": action_name,
            "reward": reward,
            "balance": current_balance,
            "profit": profit,
            "profit_pct": profit_pct,
            "experiences": len(self.agent.memory),
            "loss": avg_loss,
            "epsilon": self.agent.epsilon,
            "mode": "TRADING" if self.config.trading_enabled else "SIM",
        }

        # Log at different levels based on importance
        if hasattr(self.logger, "log_event"):
            level = "INFO" if self.metrics_tracker.total_steps % 10 == 0 else "DEBUG"
            self.logger.log_event(
                event_type="training_metrics",
                message=log_msg,
                symbol=pair_symbol,
                metrics=metrics,
                level=level,
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
        """Save checkpoint and log to MLflow"""
        metrics = self.metrics_tracker.get_metrics()
        if hasattr(self.logger, "log_event"):
            self.logger.log_event(
                event_type="checkpoint_saved",
                message=f"Saving checkpoint at step {self.metrics_tracker.total_steps}",
                metrics={
                    "step": self.metrics_tracker.total_steps,
                    "episode": self.episode_manager.current_episode,
                    **metrics,
                },
            )
        else:
            self.logger.info(
                f"Saving checkpoint at step {self.metrics_tracker.total_steps}"
            )
        self.checkpoint_manager.save_checkpoint(
            agent=self.agent,
            step=self.metrics_tracker.total_steps,
            episode=self.episode_manager.current_episode,
            metrics=metrics,
            logger=self.logger,
        )

        # Log checkpoint to MLflow
        if self.tracker:
            try:
                checkpoint_path = self.checkpoint_manager.get_latest_checkpoint_path()
                if checkpoint_path:
                    self.tracker.log_artifact(checkpoint_path, "checkpoints")
            except Exception as e:
                self.logger.warning(f"Failed to log checkpoint to MLflow: {e}")

    def _save_final_checkpoint(self):
        """Save final checkpoint"""
        metrics = self.metrics_tracker.get_metrics()
        self.checkpoint_manager.save_final(
            agent=self.agent,
            step=self.metrics_tracker.total_steps,
            episode=self.episode_manager.current_episode,
            metrics=metrics,
            logger=self.logger,
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
            logger=self.logger,
        )

        # Record episode metrics
        if summary:
            self.metrics_tracker.record_episode(
                episode_reward=summary.get("episode_reward", 0.0),
                profit=summary.get("profit", 0.0),
            )

        # Reset episode-specific metrics
        self.metrics_tracker.step_rewards = []
        self.metrics_tracker.episode_losses = []
        self.episode_manager.reset_episode()

    def _start_new_episode(self, current_balance: float):
        """Start new episode"""
        self.episode_manager.start_episode(current_balance, self.logger)
        self.risk_manager.reset_daily(self.account)

    # ==================== MLflow Tracking Methods ====================

    def _log_training_params(self) -> None:
        """Log hyperparameters to MLflow at run start"""
        if not self.tracker:
            return

        try:
            # Extract seed from environment if available
            seed = None
            if hasattr(self.env, "get_seed"):
                seed = self.env.get_seed()
            elif hasattr(self.env, "_seed"):
                seed = self.env._seed
            
            params = {
                # Agent hyperparameters
                "learning_rate": self.agent.learning_rate,
                "gamma": self.agent.discount_factor,
                "epsilon_start": self.agent.epsilon,
                "epsilon_min": self.agent.epsilon_min,
                "epsilon_decay": self.agent.epsilon_decay,
                "batch_size": self.agent.batch_size,
                "memory_size": self.agent.memory_size,
                "use_double_dqn": self.agent.use_double_dqn,
                "use_per": self.agent.use_per,
                # Training configuration
                "decision_interval": self.config.decision_interval,
                "training_enabled": self.config.training_enabled,
                "trading_enabled": self.config.trading_enabled,
                "min_experiences": self.config.min_experiences_before_training,
                # Environment
                "window_size": self.env.window_size,
                "n_pairs": (
                    len(self.env.data_providers) if self.env.data_providers else 0
                ),
            }
            
            # Add seed if available
            if seed is not None:
                params["seed"] = seed
                self.tracker.set_tag("seed", str(seed))
            
            self.tracker.log_params(params)
        except Exception as e:
            self.logger.warning(f"Failed to log params to MLflow: {e}")

    def _log_step_metrics(self, reward: float, balance: float) -> None:
        """Log step metrics to MLflow"""
        if not self.tracker:
            return

        try:
            metrics = {
                "reward": reward,
                "balance": balance,
                "epsilon": self.agent.epsilon,
                "memory_size": len(self.agent.memory),
            }

            # Add average loss if available
            avg_loss = self.metrics_tracker.get_average_loss(10)
            if avg_loss > 0:
                metrics["loss"] = avg_loss

            self.tracker.log_metrics(metrics, step=self.metrics_tracker.total_steps)
        except Exception as e:
            self.logger.warning(f"Failed to log metrics to MLflow: {e}")

    def _log_final_metrics(self) -> None:
        """Log final training metrics to MLflow"""
        if not self.tracker:
            return

        try:
            final_balance = self.get_effective_balance()
            metrics = self.metrics_tracker.get_metrics()

            final_metrics = {
                "final_balance": final_balance,
                "total_steps": self.metrics_tracker.total_steps,
                "total_episodes": self.episode_manager.current_episode,
                "total_reward": metrics.get("total_reward", 0),
                "avg_reward": metrics.get("avg_reward", 0),
                "avg_loss": metrics.get("avg_loss", 0),
            }

            self.tracker.log_metrics(final_metrics)

            # Log summary as artifact
            summary = {
                "training_complete": True,
                "final_metrics": final_metrics,
                "config": {
                    "decision_interval": self.config.decision_interval,
                    "trading_enabled": self.config.trading_enabled,
                },
            }
            self.tracker.log_dict(summary, "training_summary.json")
        except Exception as e:
            self.logger.warning(f"Failed to log final metrics to MLflow: {e}")
