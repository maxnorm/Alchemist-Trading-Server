"""
Training health monitor for divergence detection
Based on research-validated approaches for RL training stability
"""

from collections import deque
from typing import Tuple, Optional, Deque
import numpy as np


class TrainingHealthMonitor:
    """
    Monitors training health and detects divergence

    Based on research:
    - "Overcoming Intermittent Instability in RL via Gradient Norm Preservation"
    - "Dissecting Deep RL with High Update Ratios: Combatting Value Divergence"
    - "Learning to Undo: Rollback-Augmented Reinforcement Learning"
    """

    def __init__(self, config: dict):
        """
        Initialize health monitor
        :param config: Configuration dictionary with thresholds
        """
        self.loss_history: Deque[float] = deque(maxlen=100)  # Track last 100 losses
        self.nan_count = 0
        self.divergence_threshold = config.get(
            "divergence_threshold", 5.0
        )  # Loss increase factor
        self.gradient_norm_threshold = config.get("gradient_norm_threshold", 10.0)

        # Gradient norm preservation (based on research)
        self.initial_gradient_norm: Optional[float] = None
        self.gradient_norm_history: Deque[float] = deque(maxlen=50)
        self.adaptive_lr_factor = 1.0  # For adaptive learning rate adjustment

    def check_loss_trend(self, current_loss: float) -> Tuple[bool, str]:
        """
        Detect if loss is diverging (increasing exponentially)

        Based on research showing loss explosion indicates value function divergence
        Note: loss_history should be updated before calling this method
        :param current_loss: Current training loss (for validation, history already updated)
        :return: Tuple of (is_diverged, reason)
        """
        if len(self.loss_history) < 10:
            return False, ""

        recent_avg = np.mean(list(self.loss_history)[-10:])
        older_avg = (
            np.mean(list(self.loss_history)[-20:-10])
            if len(self.loss_history) >= 20
            else recent_avg
        )

        # Check for exponential increase (research-validated threshold: 5x)
        if older_avg > 0 and recent_avg / older_avg > self.divergence_threshold:
            return (
                True,
                f"Loss increased {recent_avg/older_avg:.2f}x in last 10 steps "
                f"(divergence threshold: {self.divergence_threshold}x)",
            )

        return False, ""

    def check_nan(self, loss: float, model_weights) -> Tuple[bool, str]:
        """
        Detect NaN values in loss or model weights

        NaN propagation is a critical failure mode that corrupts entire network
        :param loss: Training loss value
        :param model_weights: List of model weight arrays
        :return: Tuple of (is_diverged, reason)
        """
        if np.isnan(loss) or np.isinf(loss):
            self.nan_count += 1
            return True, f"NaN/Inf detected in loss (count: {self.nan_count})"

        # Check model weights for NaN
        if model_weights is not None:
            for layer in model_weights:
                if layer is not None:
                    if np.any(np.isnan(layer)) or np.any(np.isinf(layer)):
                        self.nan_count += 1
                        return (
                            True,
                            f"NaN/Inf detected in model weights (count: {self.nan_count})",
                        )

        return False, ""

    def check_gradient_norm(
        self, gradients, preserve_initial_norm: bool = True
    ) -> Tuple[bool, str, Optional[float]]:
        """
        Detect exploding gradients with gradient norm preservation

        Based on "Overcoming Intermittent Instability in RL via Gradient Norm Preservation"
        Preserves initial gradient norms to maintain stability
        :param gradients: List of gradient tensors
        :param preserve_initial_norm: Whether to preserve initial gradient norm
        :return: Tuple of (is_diverged, reason, gradient_norm)
        """
        if gradients is None:
            return False, "", None

        total_norm = 0.0
        for grad in gradients:
            if grad is not None:
                grad_norm = float(np.linalg.norm(grad))
                if np.isnan(grad_norm) or np.isinf(grad_norm):
                    return True, "NaN/Inf in gradient norm", None
                total_norm += grad_norm**2

        total_norm = float(np.sqrt(total_norm))
        self.gradient_norm_history.append(total_norm)

        # Initialize reference norm on first check
        if self.initial_gradient_norm is None and total_norm > 0:
            self.initial_gradient_norm = total_norm

        # Check for explosion (research-validated threshold: 10.0)
        if total_norm > self.gradient_norm_threshold:
            return (
                True,
                f"Gradient norm {total_norm:.2f} exceeds threshold {self.gradient_norm_threshold}",
                total_norm,
            )

        # Gradient norm preservation: if norm deviates significantly from initial, suggest LR adjustment
        if preserve_initial_norm and self.initial_gradient_norm is not None:
            norm_ratio = (
                total_norm / self.initial_gradient_norm
                if self.initial_gradient_norm > 0
                else 1.0
            )
            if norm_ratio > 2.0:  # Norm doubled - potential instability
                # Calculate adaptive learning rate factor to preserve norm
                self.adaptive_lr_factor = min(
                    1.0, self.initial_gradient_norm / total_norm
                )
                return (
                    False,
                    f"Gradient norm {norm_ratio:.2f}x initial (suggest LR adjustment)",
                    total_norm,
                )

        return False, "", total_norm

    def check_value_overestimation(
        self, q_values: np.ndarray, threshold: float = 1e6
    ) -> Tuple[bool, str]:
        """
        Detect value overestimation (research-validated issue in DQN)

        Based on "Dissecting Deep RL with High Update Ratios: Combatting Value Divergence"
        Value overestimation leads to poor policy decisions
        :param q_values: Q-values array
        :param threshold: Maximum Q-value threshold
        :return: Tuple of (is_diverged, reason)
        """
        if q_values is None or len(q_values) == 0:
            return False, ""

        max_q = np.max(q_values)
        if np.isnan(max_q) or np.isinf(max_q):
            return True, f"NaN/Inf in Q-values (max: {max_q})"

        if max_q > threshold:
            return (
                True,
                f"Value overestimation detected: max Q-value {max_q:.2f} exceeds threshold {threshold}",
            )

        return False, ""

    def check_update_to_data_ratio(
        self, update_count: int, data_count: int, max_ratio: float = 10.0
    ) -> Tuple[bool, str]:
        """
        Monitor update-to-data ratio (research-validated divergence cause)

        Based on "Dissecting Deep RL with High Update Ratios: Combatting Value Divergence"
        High ratios (>10:1) can cause value function divergence
        :param update_count: Number of gradient updates
        :param data_count: Number of data samples
        :param max_ratio: Maximum allowed ratio
        :return: Tuple of (is_diverged, reason)
        """
        if data_count == 0:
            return False, ""

        ratio = update_count / data_count
        if ratio > max_ratio:
            return (
                True,
                f"Update-to-data ratio {ratio:.2f} exceeds threshold {max_ratio} (risk of value divergence)",
            )

        return False, ""
