"""
Learning Rate Scheduler for Adaptive Learning Rate Management
Implements various scheduling strategies for DRL training in non-stationary markets
"""

import numpy as np
from typing import Optional, List
from abc import ABC, abstractmethod
from tensorflow import keras


class BaseLearningRateScheduler(ABC):
    """Base class for learning rate schedulers"""

    def __init__(self, min_lr: float = 1e-6):
        """
        Initialize base scheduler

        :param min_lr: Minimum learning rate threshold
        """
        self.min_lr = min_lr
        self.lr_history: List[float] = []

    @abstractmethod
    def step(self, metric_value: float, optimizer: keras.optimizers.Optimizer) -> float:
        """
        Update learning rate based on metric

        :param metric_value: Current metric value (loss, reward, etc.)
        :param optimizer: Keras optimizer to update
        :return: New learning rate
        """
        pass

    def get_current_lr(self, optimizer: keras.optimizers.Optimizer) -> float:
        """
        Get current learning rate from optimizer

        :param optimizer: Keras optimizer
        :return: Current learning rate
        """
        if hasattr(optimizer, "learning_rate"):
            lr = optimizer.learning_rate
            if hasattr(lr, "numpy"):
                return float(lr.numpy())
            return float(lr)
        return 0.0

    def set_lr(self, optimizer: keras.optimizers.Optimizer, new_lr: float):
        """
        Set learning rate on optimizer

        :param optimizer: Keras optimizer
        :param new_lr: New learning rate value
        """
        new_lr = max(new_lr, self.min_lr)
        optimizer.learning_rate.assign(new_lr)
        self.lr_history.append(new_lr)


class ReduceLROnPlateauScheduler(BaseLearningRateScheduler):
    """
    Reduces learning rate when metric plateaus
    Useful for adapting to changing market conditions
    """

    def __init__(
        self,
        factor: float = 0.5,
        patience: int = 10,
        min_lr: float = 1e-6,
        monitor: str = "loss",
        mode: str = "min",
    ):
        """
        Initialize ReduceLROnPlateau scheduler

        :param factor: Factor to reduce learning rate by (default: 0.5)
        :param patience: Number of steps without improvement before reducing LR
        :param min_lr: Minimum learning rate threshold
        :param monitor: Metric to monitor ('loss', 'reward', 'sharpe', 'drawdown')
        :param mode: 'min' to minimize metric, 'max' to maximize
        """
        super().__init__(min_lr=min_lr)
        self.factor = factor
        self.patience = patience
        self.monitor = monitor
        self.mode = mode
        self.best_metric: Optional[float] = None
        self.wait_count = 0

    def step(self, metric_value: float, optimizer: keras.optimizers.Optimizer) -> float:
        """
        Update learning rate based on metric plateau

        :param metric_value: Current metric value
        :param optimizer: Keras optimizer
        :return: Current learning rate
        """
        current_lr = self.get_current_lr(optimizer)

        # Initialize best metric
        if self.best_metric is None:
            self.best_metric = metric_value
            self.wait_count = 0
            return current_lr

        # Check if metric improved
        if self.mode == "min":
            improved = metric_value < self.best_metric
        else:  # mode == 'max'
            improved = metric_value > self.best_metric

        if improved:
            self.best_metric = metric_value
            self.wait_count = 0
        else:
            self.wait_count += 1
            if self.wait_count >= self.patience:
                # Reduce learning rate
                new_lr = max(current_lr * self.factor, self.min_lr)
                self.set_lr(optimizer, new_lr)
                self.wait_count = 0

        return self.get_current_lr(optimizer)


class CosineAnnealingScheduler(BaseLearningRateScheduler):
    """
    Cosine annealing scheduler for cyclical learning rates
    Useful for exploring different learning rates during training
    """

    def __init__(
        self,
        T_max: int = 100,
        eta_min: float = 1e-6,
        initial_lr: Optional[float] = None,
    ):
        """
        Initialize CosineAnnealing scheduler

        :param T_max: Maximum number of iterations (cycle length)
        :param eta_min: Minimum learning rate
        :param initial_lr: Initial learning rate (if None, uses optimizer's current LR)
        """
        super().__init__(min_lr=eta_min)
        self.T_max = T_max
        self.eta_min = eta_min
        self.initial_lr = initial_lr
        self.step_count = 0

    def step(self, metric_value: float, optimizer: keras.optimizers.Optimizer) -> float:
        """
        Update learning rate using cosine annealing

        :param metric_value: Current metric value (not used for cosine annealing)
        :param optimizer: Keras optimizer
        :return: New learning rate
        """
        if self.initial_lr is None:
            self.initial_lr = self.get_current_lr(optimizer)

        # Calculate cosine annealing
        self.step_count += 1
        cycle_position = self.step_count % self.T_max
        new_lr = (
            self.eta_min
            + (self.initial_lr - self.eta_min)
            * (1 + np.cos(np.pi * cycle_position / self.T_max))
            / 2
        )

        self.set_lr(optimizer, new_lr)
        return self.get_current_lr(optimizer)


class AdaptiveScheduler(BaseLearningRateScheduler):
    """
    Adaptive scheduler that combines multiple strategies
    Uses reduce on plateau for stability, with cosine annealing for exploration
    """

    def __init__(
        self,
        reduce_on_plateau: Optional[ReduceLROnPlateauScheduler] = None,
        cosine_annealing: Optional[CosineAnnealingScheduler] = None,
        primary_strategy: str = "plateau",
        min_lr: float = 1e-6,
    ):
        """
        Initialize Adaptive scheduler

        :param reduce_on_plateau: ReduceLROnPlateau scheduler instance
        :param cosine_annealing: CosineAnnealing scheduler instance
        :param primary_strategy: Primary strategy ('plateau' or 'cosine')
        :param min_lr: Minimum learning rate threshold
        """
        super().__init__(min_lr=min_lr)
        self.reduce_on_plateau = reduce_on_plateau or ReduceLROnPlateauScheduler()
        self.cosine_annealing = cosine_annealing or CosineAnnealingScheduler()
        self.primary_strategy = primary_strategy

    def step(self, metric_value: float, optimizer: keras.optimizers.Optimizer) -> float:
        """
        Update learning rate using adaptive strategy

        :param metric_value: Current metric value
        :param optimizer: Keras optimizer
        :return: New learning rate
        """
        if self.primary_strategy == "plateau":
            # Use reduce on plateau as primary, cosine as secondary
            lr = self.reduce_on_plateau.step(metric_value, optimizer)
            # Apply cosine annealing on top
            self.cosine_annealing.step(metric_value, optimizer)
            return lr
        else:
            # Use cosine as primary
            lr = self.cosine_annealing.step(metric_value, optimizer)
            # Apply plateau reduction if needed
            self.reduce_on_plateau.step(metric_value, optimizer)
            return lr


def create_scheduler(
    scheduler_type: str = "reduce_on_plateau", **kwargs
) -> BaseLearningRateScheduler:
    """
    Factory function to create learning rate schedulers

    :param scheduler_type: Type of scheduler ('reduce_on_plateau', 'cosine_annealing', 'adaptive')
    :param kwargs: Additional arguments for scheduler initialization
    :return: Scheduler instance
    """
    if scheduler_type == "reduce_on_plateau":
        return ReduceLROnPlateauScheduler(**kwargs)
    elif scheduler_type == "cosine_annealing":
        return CosineAnnealingScheduler(**kwargs)
    elif scheduler_type == "adaptive":
        return AdaptiveScheduler(**kwargs)
    else:
        raise ValueError(f"Unknown scheduler type: {scheduler_type}")
