"""
Metrics tracker for training
Tracks step and episode metrics separately
"""
import numpy as np
from typing import List, Optional, Dict, Any


class MetricsTracker:
    """Tracks training metrics"""
    
    def __init__(self):
        """Initialize metrics tracker"""
        self.total_steps = 0
        self.total_reward = 0.0
        self.episode_rewards: List[float] = []
        self.episode_profits: List[float] = []
        self.episode_losses: List[float] = []
        self.step_rewards: List[float] = []
        self.losses: List[float] = []
    
    def record_step(self, reward: float, loss: Optional[float] = None):
        """
        Record step metrics
        :param reward: Reward for this step
        :param loss: Optional training loss
        """
        self.total_steps += 1
        self.total_reward += reward
        self.step_rewards.append(reward)
        
        if loss is not None:
            self.losses.append(loss)
    
    def record_episode(self, episode_reward: float, profit: float):
        """
        Record episode metrics
        :param episode_reward: Total reward for episode
        :param profit: Profit for episode
        """
        self.episode_rewards.append(episode_reward)
        self.episode_profits.append(profit)
    
    def record_episode_loss(self, loss: float):
        """
        Record episode loss
        :param loss: Loss value
        """
        self.episode_losses.append(loss)
    
    def get_average_loss(self, window: int = 100) -> float:
        """
        Get average loss over recent steps
        :param window: Number of recent steps to average
        :return: Average loss
        """
        if not self.losses:
            return 0.0
        recent = self.losses[-window:]
        return float(np.mean(recent))
    
    def get_average_reward(self, window: int = 100) -> float:
        """
        Get average reward over recent steps
        :param window: Number of recent steps to average
        :return: Average reward
        """
        if not self.step_rewards:
            return 0.0
        recent = self.step_rewards[-window:]
        return float(np.mean(recent))
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get all current metrics
        :return: Dictionary of metrics
        """
        return {
            'total_steps': self.total_steps,
            'total_reward': self.total_reward,
            'average_reward': self.get_average_reward(),
            'average_loss': self.get_average_loss(),
            'episode_count': len(self.episode_rewards),
            'episode_rewards': self.episode_rewards.copy(),
            'episode_profits': self.episode_profits.copy(),
            'episode_losses': self.episode_losses.copy()
        }
    
    def reset_episode(self):
        """Reset episode-specific metrics (keeps totals)"""
        # Episode metrics are kept for history
        # Only reset if needed for new episode tracking
        pass
    
    def get_episode_summary(self, episode_number: int) -> Dict[str, Any]:
        """
        Get summary for a specific episode
        :param episode_number: Episode number (1-indexed)
        :return: Episode summary
        """
        if episode_number < 1 or episode_number > len(self.episode_rewards):
            return {}
        
        idx = episode_number - 1
        return {
            'episode': episode_number,
            'reward': self.episode_rewards[idx] if idx < len(self.episode_rewards) else 0.0,
            'profit': self.episode_profits[idx] if idx < len(self.episode_profits) else 0.0,
            'loss': self.episode_losses[idx] if idx < len(self.episode_losses) else 0.0
        }
