"""
Reward Monitoring for DRL Trading Agents
Tracks reward components and detects anomalies (reward hacking, distribution shifts)
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Tuple
from collections import deque
from datetime import datetime


class RewardMonitor:
    """
    Monitors reward components and detects anomalies
    Helps identify reward hacking and market regime changes
    """

    def __init__(
        self,
        window_size: int = 100,
        anomaly_threshold: float = 3.0,
        component_window_size: int = 50,
    ):
        """
        Initialize reward monitor

        :param window_size: Window size for reward history
        :param anomaly_threshold: Number of standard deviations for anomaly detection
        :param component_window_size: Window size for component tracking
        """
        self.window_size = window_size
        self.anomaly_threshold = anomaly_threshold
        self.component_window_size = component_window_size

        # Reward history
        self.reward_history: deque = deque(maxlen=window_size)
        self.reward_timestamps: deque = deque(maxlen=window_size)

        # Component tracking
        self.component_history: Dict[str, deque] = {
            'sharpe_reward': deque(maxlen=component_window_size),
            'drawdown_penalty': deque(maxlen=component_window_size),
            'volatility_penalty': deque(maxlen=component_window_size),
            'transaction_penalty': deque(maxlen=component_window_size),
            'action_penalty': deque(maxlen=component_window_size),
        }

        # Statistics
        self.reward_mean = 0.0
        self.reward_std = 1.0
        self.anomaly_count = 0
        self.last_anomaly_time: Optional[datetime] = None

        # Logger
        self.logger = logging.getLogger(__name__)

    def update(
        self,
        reward: float,
        components: Optional[Dict[str, float]] = None,
        timestamp: Optional[datetime] = None,
    ):
        """
        Update monitor with new reward and components

        :param reward: Reward value
        :param components: Dictionary of reward components (optional)
        :param timestamp: Timestamp for the reward (optional)
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Update reward history
        self.reward_history.append(reward)
        self.reward_timestamps.append(timestamp)

        # Update component history
        if components is not None:
            for component_name, component_value in components.items():
                if component_name in self.component_history:
                    self.component_history[component_name].append(component_value)

        # Update statistics
        if len(self.reward_history) > 1:
            reward_array = np.array(self.reward_history)
            self.reward_mean = float(np.mean(reward_array))
            self.reward_std = float(np.std(reward_array))
            if self.reward_std < 1e-8:
                self.reward_std = 1.0

        # Check for anomalies
        if len(self.reward_history) > 10:  # Need enough data
            is_anomaly = self._detect_anomaly(reward)
            if is_anomaly:
                self.anomaly_count += 1
                self.last_anomaly_time = timestamp
                self._log_anomaly(reward, components)

    def _detect_anomaly(self, reward: float) -> bool:
        """
        Detect if reward is an anomaly

        :param reward: Reward value to check
        :return: True if anomaly detected
        """
        if self.reward_std < 1e-8:
            return False

        # Z-score for anomaly detection
        z_score = abs(reward - self.reward_mean) / self.reward_std
        return z_score > self.anomaly_threshold

    def _log_anomaly(
        self, reward: float, components: Optional[Dict[str, float]] = None
    ):
        """
        Log detected anomaly

        :param reward: Anomalous reward value
        :param components: Reward components (optional)
        """
        z_score = abs(reward - self.reward_mean) / (self.reward_std + 1e-8)
        message = (
            f"Reward anomaly detected: reward={reward:.4f}, "
            f"mean={self.reward_mean:.4f}, std={self.reward_std:.4f}, "
            f"z_score={z_score:.2f}"
        )

        if components:
            component_str = ", ".join(
                [f"{k}={v:.4f}" for k, v in components.items()]
            )
            message += f", components=[{component_str}]"

        self.logger.warning(message)

    def detect_reward_hacking(
        self, component_threshold: float = 0.8
    ) -> Tuple[bool, Optional[str]]:
        """
        Detect potential reward hacking by checking if agent exploits specific component

        :param component_threshold: Threshold for component dominance (0-1)
        :return: Tuple of (is_hacking, component_name)
        """
        if len(self.reward_history) < self.component_window_size:
            return False, None

        # Calculate component contributions
        component_contributions = {}
        for component_name, component_values in self.component_history.items():
            if len(component_values) > 0:
                # Calculate absolute contribution
                abs_values = np.abs(np.array(component_values))
                total_abs = np.sum(abs_values)
                if total_abs > 0:
                    component_contributions[component_name] = float(
                        total_abs / len(component_values)
                    )

        # Check if any component dominates
        if component_contributions:
            total_contribution = sum(component_contributions.values())
            if total_contribution > 0:
                for component_name, contribution in component_contributions.items():
                    relative_contribution = contribution / total_contribution
                    if relative_contribution > component_threshold:
                        self.logger.warning(
                            f"Potential reward hacking detected: "
                            f"component '{component_name}' dominates "
                            f"({relative_contribution:.2%} of total contribution)"
                        )
                        return True, component_name

        return False, None

    def detect_distribution_shift(
        self, window_size: Optional[int] = None, threshold: float = 2.0
    ) -> bool:
        """
        Detect if reward distribution has shifted significantly
        Indicates market regime change or reward function issue

        :param window_size: Size of windows to compare (default: self.window_size // 2)
        :param threshold: Number of standard deviations for shift detection
        :return: True if distribution shift detected
        """
        if window_size is None:
            window_size = self.window_size // 2

        if len(self.reward_history) < window_size * 2:
            return False

        # Compare recent window to previous window
        recent_rewards = np.array(list(self.reward_history)[-window_size:])
        previous_rewards = np.array(
            list(self.reward_history)[-window_size * 2 : -window_size]
        )

        recent_mean = np.mean(recent_rewards)
        previous_mean = np.mean(previous_rewards)
        pooled_std = np.std(np.concatenate([recent_rewards, previous_rewards]))

        if pooled_std < 1e-8:
            return False

        # Z-score for mean shift
        z_score = abs(recent_mean - previous_mean) / (pooled_std + 1e-8)

        if z_score > threshold:
            self.logger.warning(
                f"Reward distribution shift detected: "
                f"recent_mean={recent_mean:.4f}, "
                f"previous_mean={previous_mean:.4f}, "
                f"z_score={z_score:.2f}"
            )
            return True

        return False

    def get_statistics(self) -> Dict:
        """
        Get monitoring statistics

        :return: Dictionary with statistics
        """
        component_stats = {}
        for component_name, component_values in self.component_history.items():
            if len(component_values) > 0:
                component_array = np.array(component_values)
                component_stats[component_name] = {
                    'mean': float(np.mean(component_array)),
                    'std': float(np.std(component_array)),
                    'min': float(np.min(component_array)),
                    'max': float(np.max(component_array)),
                }

        return {
            'reward_mean': self.reward_mean,
            'reward_std': self.reward_std,
            'reward_count': len(self.reward_history),
            'anomaly_count': self.anomaly_count,
            'last_anomaly_time': (
                self.last_anomaly_time.isoformat()
                if self.last_anomaly_time
                else None
            ),
            'component_stats': component_stats,
        }

    def reset(self):
        """Reset monitor statistics"""
        self.reward_history.clear()
        self.reward_timestamps.clear()
        for component_history in self.component_history.values():
            component_history.clear()
        self.reward_mean = 0.0
        self.reward_std = 1.0
        self.anomaly_count = 0
        self.last_anomaly_time = None
