from abc import ABC, abstractmethod
import random
from typing import Optional, List, Dict, Any, Tuple
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from gymnasium.utils import seeding


class BaseTradingEnv(gym.Env, ABC):
    """
    Base class for trading environments.

    Provides:
    - Gymnasium-compatible interface
    - Action encoding/decoding for multi-pair trading
    - Reproducibility through seeding
    """

    def __init__(
        self,
        window_size: int = 50,
        price_shape: int = 5,
        action_size: int = 4,
        seed: Optional[int] = None,
    ):
        """
        Initialize the trading environment.

        Args:
            window_size: Number of past observations to consider
            price_shape: Number of features per observation
            action_size: Number of actions
                For single pair: 4 (HOLD, Buy, Sell, Close)
                For multiple pairs: (n_pairs * 3) + 1 (global HOLD + 3 actions per pair)
            seed: Random seed for reproducibility
        """
        super(BaseTradingEnv, self).__init__()
        self.window_size = window_size

        # Random state for reproducibility
        self.np_random: Optional[np.random.Generator] = None
        self._seed: Optional[int] = None

        # Define action space
        # Action encoding:
        #   action = 0 → Global HOLD (no pair)
        #   action = 1 + (pair_index * 3 + action_type_offset) for pair actions
        #   where action_type_offset: 0=BUY, 1=SELL, 2=CLOSE
        self.action_space = spaces.Discrete(action_size)

        # Define observation space with proper shape for Keras
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.window_size, price_shape),
            dtype=np.float32,
        )

        self.current_step = 0
        self.position: Optional[Any] = None
        self.position_history: List[Any] = []

        # Initialize seed if provided
        if seed is not None:
            self.seed(seed)

    def decode_action(self, action: int) -> tuple:
        """
        Decode action into (pair_index, action_type)
        :param action: Encoded action
                0 = Global HOLD (no pair)
                1+ = 1 + (pair_index * 3 + action_type_offset)
                where action_type_offset: 0=BUY, 1=SELL, 2=CLOSE
        :return: Tuple of (pair_index, action_type)
                 For HOLD: (None, ActionType.HOLD)
                 For pair actions: (pair_index, ActionType)
        """
        from domain.action_type import ActionType

        if action == 0:
            return (None, ActionType.HOLD)

        action_adjusted = action - 1
        pair_index = action_adjusted // 3
        action_type_offset = action_adjusted % 3

        # Map offset to ActionType: 0=BUY, 1=SELL, 2=CLOSE
        action_type_map = {0: ActionType.BUY, 1: ActionType.SELL, 2: ActionType.CLOSE}
        action_type = action_type_map[action_type_offset]

        return (pair_index, action_type)

    @abstractmethod
    def get_state(self) -> np.ndarray:
        """Get current state from all data sources"""
        pass

    def seed(self, seed: Optional[int] = None) -> List[int]:
        """
        Set random seed for reproducibility.

        Seeds numpy, random, and TensorFlow for consistent results.
        Compatible with Gymnasium's seeding API.

        Args:
            seed: Random seed value

        Returns:
            List containing the seed used
        """
        self.np_random, seed = seeding.np_random(seed)
        self._seed = seed

        # Seed global numpy random state
        np.random.seed(seed)

        # Seed Python's random module
        random.seed(seed)

        # Seed TensorFlow if available
        try:
            import tensorflow as tf

            tf.random.set_seed(seed)
        except ImportError:
            pass

        return [seed]

    def reset(
        self, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Reset the environment to initial state.

        Compatible with Gymnasium's reset API.

        Args:
            seed: Optional seed for reproducibility
            options: Optional configuration options

        Returns:
            Tuple of (observation, info)
        """
        # Apply seed if provided
        if seed is not None:
            self.seed(seed)

        # Reset internal state
        self.current_step = 0
        self.position = None
        self.position_history = []

        # Get initial state
        state = self.get_state()

        # Ensure state is valid
        if state is None:
            state = np.zeros(self.observation_space.shape, dtype=np.float32)

        info = {"seed": self._seed, "current_step": self.current_step}

        return state, info

    def get_seed(self) -> Optional[int]:
        """Get the current seed value"""
        return self._seed

    def get_random_state(self) -> np.random.Generator:
        """Get the numpy random generator for reproducible randomness"""
        if self.np_random is None:
            self.seed(None)  # Initialize with random seed
        return self.np_random
