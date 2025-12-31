"""
Episode manager for training
Manages episode lifecycle
"""
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


class EpisodeManager:
    """Manages episode lifecycle"""
    
    def __init__(self, duration_hours: int = 24):
        """
        Initialize episode manager
        :param duration_hours: Duration of each episode in hours
        """
        self.duration_hours = duration_hours
        self.current_episode = 1
        self.episode_start_time: Optional[datetime] = None
        self.episode_start_balance = 0.0
    
    def start_episode(self, balance: float, logger=None):
        """
        Start a new episode
        :param balance: Starting balance for episode
        :param logger: Optional logger for logging
        """
        self.current_episode += 1
        self.episode_start_time = datetime.now()
        self.episode_start_balance = balance
        
        if logger:
            logger.info(f"=== Starting Episode {self.current_episode} ===")
        else:
            print(f"\n=== Starting Episode {self.current_episode} ===")
    
    def should_end_episode(self) -> bool:
        """
        Check if episode should end
        :return: True if episode duration exceeded
        """
        if not self.episode_start_time:
            return False
        
        elapsed = datetime.now() - self.episode_start_time
        return elapsed >= timedelta(hours=self.duration_hours)
    
    def is_episode_complete(self) -> bool:
        """Alias for should_end_episode"""
        return self.should_end_episode()
    
    def get_episode_summary(
        self,
        current_balance: float,
        step_rewards: list,
        episode_losses: list,
        total_steps: int,
        logger=None
    ) -> Dict[str, Any]:
        """
        Get episode summary
        :param current_balance: Current balance
        :param step_rewards: List of step rewards for this episode
        :param episode_losses: List of losses for this episode
        :param total_steps: Total steps across all episodes
        :param logger: Optional logger for logging
        :return: Episode summary dictionary
        """
        if not self.episode_start_time:
            return {}
        
        episode_duration = datetime.now() - self.episode_start_time
        profit = current_balance - self.episode_start_balance
        profit_pct = (profit / self.episode_start_balance * 100) if self.episode_start_balance > 0 else 0.0
        
        episode_reward = sum(step_rewards) if step_rewards else 0.0
        avg_loss = float(np.mean(episode_losses)) if episode_losses else 0.0
        
        summary = {
            'episode': self.current_episode,
            'duration': episode_duration,
            'duration_hours': episode_duration.total_seconds() / 3600,
            'start_balance': self.episode_start_balance,
            'end_balance': current_balance,
            'profit': profit,
            'profit_pct': profit_pct,
            'episode_reward': episode_reward,
            'average_loss': avg_loss,
            'total_steps': total_steps,
            'episode_steps': len(step_rewards)
        }
        
        # Format summary string
        episode_summary_str = (
            f"=== Episode {self.current_episode} Complete ===\n"
            f"Duration: {episode_duration}\n"
            f"Total Reward: {episode_reward:.2f}\n"
            f"Profit: {profit:.2f} ({profit_pct:.2f}%)\n"
            f"Average Loss: {avg_loss:.4f}\n"
            f"Total Steps: {total_steps}\n"
            f"{'=' * 40}"
        )
        
        if logger:
            logger.info(episode_summary_str)
        else:
            print(f"\n{episode_summary_str}")
        
        return summary
    
    def reset_episode(self):
        """Reset episode state (called after episode ends)"""
        self.episode_start_time = None
        self.episode_start_balance = 0.0
    
    def get_current_episode(self) -> int:
        """Get current episode number"""
        return self.current_episode
    
    def get_episode_duration(self) -> Optional[timedelta]:
        """
        Get current episode duration
        :return: Duration since episode start or None
        """
        if not self.episode_start_time:
            return None
        return datetime.now() - self.episode_start_time
