"""
Reward Normalization for DRL Trading Agents
Prevents reward hacking by normalizing rewards to stable distribution
"""

import numpy as np
from typing import Optional, Tuple, List, Dict
from collections import deque


class RewardNormalizer:
    """
    Normalizes rewards using running statistics
    Prevents reward hacking by maintaining stable reward distribution
    """

    def __init__(
        self,
        alpha: float = 0.99,
        clip_range: Tuple[float, float] = (-3.0, 3.0),
        window_size: Optional[int] = None,
        use_window: bool = False,
    ):
        """
        Initialize reward normalizer

        :param alpha: Exponential moving average factor (0 < alpha <= 1)
                      Higher alpha = slower adaptation (more stable)
        :param clip_range: Range to clip normalized rewards (in standard deviations)
        :param window_size: Window size for window-based normalization (if use_window=True)
        :param use_window: Whether to use window-based normalization instead of EMA
        """
        self.alpha = alpha
        self.clip_range = clip_range
        self.use_window = use_window
        self.window_size = window_size or 1000

        # Running statistics
        self.reward_mean = 0.0
        self.reward_std = 1.0
        self.reward_variance = 1.0
        self.count = 0

        # Window-based statistics (if enabled)
        self.reward_window: Optional[deque] = deque(maxlen=self.window_size) if use_window else None

        # Statistics history for monitoring
        self.mean_history: List[float] = []
        self.std_history: List[float] = []

    def normalize(self, reward: float) -> float:
        """
        Normalize reward using running statistics

        :param reward: Raw reward value
        :return: Normalized reward value
        """
        self.count += 1

        if self.use_window and self.reward_window is not None:
            # Window-based normalization
            self.reward_window.append(reward)
            if len(self.reward_window) > 1:
                window_array = np.array(self.reward_window)
                self.reward_mean = float(np.mean(window_array))
                self.reward_std = float(np.std(window_array))
                if self.reward_std < 1e-8:
                    self.reward_std = 1.0
            else:
                # First reward in window
                self.reward_mean = reward
                self.reward_std = 1.0
        else:
            # Exponential moving average normalization
            if self.count == 1:
                # Initialize with first reward
                self.reward_mean = reward
                self.reward_std = 1.0
                self.reward_variance = 1.0
            else:
                # Update mean using EMA
                self.reward_mean = (
                    self.alpha * self.reward_mean + (1 - self.alpha) * reward
                )

                # Update variance using EMA
                # Variance update: Var = E[X^2] - E[X]^2
                # We approximate E[X^2] using EMA
                if self.count == 2:
                    # Initialize variance estimate
                    self.reward_variance = (reward - self.reward_mean) ** 2
                else:
                    # Update variance estimate
                    squared_diff = (reward - self.reward_mean) ** 2
                    self.reward_variance = (
                        self.alpha * self.reward_variance
                        + (1 - self.alpha) * squared_diff
                    )

                # Standard deviation from variance
                self.reward_std = np.sqrt(self.reward_variance)
                if self.reward_std < 1e-8:
                    self.reward_std = 1.0

        # Normalize reward (z-score)
        normalized = (reward - self.reward_mean) / (self.reward_std + 1e-8)

        # Clip to prevent extreme values
        normalized = np.clip(normalized, self.clip_range[0], self.clip_range[1])

        # Store statistics for monitoring
        self.mean_history.append(self.reward_mean)
        self.std_history.append(self.reward_std)

        return float(normalized)

    def get_statistics(self) -> Dict[str, float]:
        """
        Get current reward statistics

        :return: Dictionary with mean, std, count, and other statistics
        """
        return {
            'mean': self.reward_mean,
            'std': self.reward_std,
            'variance': self.reward_variance,
            'count': self.count,
            'min': float(np.min(self.mean_history)) if self.mean_history else 0.0,
            'max': float(np.max(self.mean_history)) if self.mean_history else 0.0,
        }

    def reset(self):
        """Reset normalizer statistics"""
        self.reward_mean = 0.0
        self.reward_std = 1.0
        self.reward_variance = 1.0
        self.count = 0
        if self.reward_window is not None:
            self.reward_window.clear()
        self.mean_history.clear()
        self.std_history.clear()

    def detect_distribution_shift(
        self, window_size: int = 100, threshold: float = 2.0
    ) -> bool:
        """
        Detect if reward distribution has shifted significantly
        Useful for detecting reward hacking or market regime changes

        :param window_size: Size of recent window to compare
        :param threshold: Number of standard deviations for shift detection
        :return: True if distribution shift detected
        """
        if len(self.mean_history) < window_size * 2:
            return False

        # Compare recent window to previous window
        recent_means = np.array(self.mean_history[-window_size:])
        previous_means = np.array(
            self.mean_history[-window_size * 2 : -window_size]
        )

        recent_mean = np.mean(recent_means)
        previous_mean = np.mean(previous_means)
        pooled_std = np.std(np.concatenate([recent_means, previous_means]))

        if pooled_std < 1e-8:
            return False

        # Z-score for mean shift
        z_score = abs(recent_mean - previous_mean) / (pooled_std + 1e-8)

        return z_score > threshold
