"""
Training Pipeline for DQN Trading Agent
Trains the agent on historical or live data
"""
import os
import numpy as np
from datetime import datetime
from typing import Optional
import json

from agents.dqn_agent import DQNAgent
from environments.live_env import LiveTradingEnv
from utils.feature_engineering import FeatureEngineer
from utils.risk_management import RiskManager
from models.account import Account
from models.currency_pair import CurrencyPair
from data_providers.price_provider import PriceDataProvider


class AgentTrainer:
    """Trainer for DQN trading agent"""
    
    def __init__(
        self,
        agent: DQNAgent,
        environment: LiveTradingEnv,
        account: Account,
        risk_manager: RiskManager,
        save_dir: str = "models"
    ):
        """
        Initialize trainer
        :param agent: DQN agent to train
        :param environment: Trading environment
        :param account: Account for trading
        :param risk_manager: Risk manager
        :param save_dir: Directory to save models
        """
        self.agent = agent
        self.env = environment
        self.account = account
        self.risk_manager = risk_manager
        self.save_dir = save_dir
        
        os.makedirs(save_dir, exist_ok=True)
        
        # Training metrics
        self.episode_rewards = []
        self.episode_losses = []
        self.episode_profits = []
        
    def train_episode(self, max_steps: int = 1000) -> dict:
        """
        Train agent for one episode
        :param max_steps: Maximum steps per episode
        :return: Episode statistics
        """
        state = self.env.get_state()
        total_reward = 0.0
        total_loss = 0.0
        initial_balance = self.account.balance
        steps = 0
        
        for step in range(max_steps):
            # Choose action
            action = self.agent.act(state, training=True)
            
            # Check risk limits
            can_trade, reason = self.risk_manager.can_trade(self.account)
            if not can_trade and action != 0:  # Action 0 is hold
                action = 0  # Force hold if risk limits exceeded
            
            # Execute action (simplified - in real implementation, this would interact with environment)
            previous_balance = self.account.balance
            reward = self._execute_action(action)
            
            # Get next state
            next_state = self.env.get_state()
            
            # Check if episode is done (simplified)
            done = (step >= max_steps - 1) or (not can_trade)
            
            # Store experience
            self.agent.remember(state, action, reward, next_state, done)
            
            # Train agent
            if len(self.agent.memory) > self.agent.batch_size:
                loss = self.agent.replay()
                total_loss += loss
            
            state = next_state
            total_reward += reward
            steps += 1
            
            if done:
                break
        
        final_balance = self.account.balance
        profit = final_balance - initial_balance
        profit_pct = (profit / initial_balance) * 100 if initial_balance > 0 else 0.0
        
        episode_stats = {
            'total_reward': total_reward,
            'avg_loss': total_loss / max(steps, 1),
            'profit': profit,
            'profit_pct': profit_pct,
            'steps': steps,
            'final_balance': final_balance
        }
        
        self.episode_rewards.append(total_reward)
        self.episode_losses.append(total_loss / max(steps, 1))
        self.episode_profits.append(profit)
        
        return episode_stats
    
    def _execute_action(self, action: int) -> float:
        """
        Execute action and return reward
        :param action: Encoded action (pair_index * 4 + action_type)
        :return: Reward
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
        
        previous_balance = self.account.balance
        has_position = len(self.account.current_trade) > 0
        
        try:
            if action_type == 1:  # Buy
                if not has_position and self.risk_manager.can_trade(self.account)[0]:
                    entry_price = pair.ask
                    lot_size = self.risk_manager.calculate_position_size(
                        self.account, pair, entry_price
                    )
                    sl = self.risk_manager.calculate_stop_loss(entry_price, True)
                    tp = self.risk_manager.calculate_take_profit(entry_price, True)
                    
                    from codes.order_type import OrderType
                    self.account.send_order(OrderType.BUY, pair, lot_size, None, sl, tp)
            
            elif action_type == 2:  # Sell
                if not has_position and self.risk_manager.can_trade(self.account)[0]:
                    entry_price = pair.bid
                    lot_size = self.risk_manager.calculate_position_size(
                        self.account, pair, entry_price
                    )
                    sl = self.risk_manager.calculate_stop_loss(entry_price, False)
                    tp = self.risk_manager.calculate_take_profit(entry_price, False)
                    
                    from codes.order_type import OrderType
                    self.account.send_order(OrderType.SELL, pair, lot_size, None, sl, tp)
            
            elif action_type == 3:  # Close position
                if has_position:
                    for ticket in list(self.account.current_trade.keys()):
                        self.account.close_order(ticket)
            
            # action_type == 0 (Hold) does nothing
        
        except Exception as e:
            print(f"Error executing action {action} (pair_index={pair_index}, action_type={action_type}) on {pair.symbol}: {e}")
        
        # Calculate reward with detailed transaction cost model
        current_balance = self.account.balance
        
        # Get trade information for detailed cost calculation
        entry_price = None
        exit_price = None
        lot_size = None
        is_long = None
        
        if action_type == 1:  # Buy
            entry_price = pair.ask if pair else None
            lot_size = self.risk_manager.calculate_position_size(
                self.account, pair, entry_price
            ) if pair and entry_price else None
            is_long = True
        elif action_type == 2:  # Sell
            entry_price = pair.bid if pair else None
            lot_size = self.risk_manager.calculate_position_size(
                self.account, pair, entry_price
            ) if pair and entry_price else None
            is_long = False
        elif action_type == 3:  # Close
            if has_position and self.account.current_trade:
                trade = list(self.account.current_trade.values())[0]
                entry_price = trade.open_price
                exit_price = pair.bid if pair else None
                lot_size = trade.lotsize
                # OrderType.BUY = 0, OrderType.SELL = 1
                is_long = (trade.ordertype.value == 0)  # 0 = BUY
        
        # Get current volatility from environment metrics
        volatility = None
        if hasattr(self.env, 'performance_metrics'):
            metrics = self.env.performance_metrics.get_all_metrics()
            volatility = metrics.get('volatility', None)
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
    
    def train(self, num_episodes: int = 100, save_freq: int = 10):
        """
        Train agent for multiple episodes
        :param num_episodes: Number of episodes to train
        :param save_freq: Frequency to save model
        """
        print(f"Starting training for {num_episodes} episodes...")
        
        for episode in range(num_episodes):
            stats = self.train_episode()
            
            print(f"Episode {episode + 1}/{num_episodes} - "
                  f"Reward: {stats['total_reward']:.2f}, "
                  f"Profit: {stats['profit']:.2f} ({stats['profit_pct']:.2f}%), "
                  f"Loss: {stats['avg_loss']:.4f}")
            
            # Save model periodically
            if (episode + 1) % save_freq == 0:
                self.save_checkpoint(episode + 1)
        
        # Final save
        self.save_checkpoint(num_episodes, final=True)
        print("Training completed!")
    
    def save_checkpoint(self, episode: int, final: bool = False):
        """Save model checkpoint"""
        checkpoint_dir = os.path.join(self.save_dir, f"checkpoint_ep{episode}")
        self.agent.save(checkpoint_dir)
        
        # Save training metrics
        metrics = {
            'episode': episode,
            'rewards': self.episode_rewards[-100:],  # Last 100 episodes
            'losses': self.episode_losses[-100:],
            'profits': self.episode_profits[-100:],
            'timestamp': datetime.now().isoformat()
        }
        
        metrics_file = os.path.join(checkpoint_dir, 'metrics.json')
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        if final:
            print(f"Model saved to {checkpoint_dir}")
