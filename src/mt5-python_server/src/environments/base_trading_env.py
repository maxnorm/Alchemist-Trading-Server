from abc import ABC, abstractmethod
import numpy as np
import gymnasium as gym
from gymnasium import spaces


class BaseTradingEnv(gym.Env, ABC):
    def __init__(self, window_size=50, price_shape=5, action_size=4):
        """
        Initialize the trading environment
        :param window_size: The number of past prices to consider
        :param price_shape: The shape of the data
        :param action_size: Number of actions (default 4 for single pair: Hold, Buy, Sell, Close)
                           For multiple pairs: n_pairs * 4
        """
        super(BaseTradingEnv, self).__init__()
        self.window_size = window_size
        
        # Define action space: can be 4 for single pair or n_pairs * 4 for multiple pairs
        # Action encoding: action = pair_index * 4 + action_type
        # where action_type: 0=Hold, 1=Buy, 2=Sell, 3=Close
        self.action_space = spaces.Discrete(action_size)
        
        # Define observation space with proper shape for Keras
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.window_size, price_shape),
            dtype=np.float32
        )

        self.current_step = 0
        self.position = None
        self.position_history = []
    
    def decode_action(self, action: int) -> tuple:
        """
        Decode action into (pair_index, action_type)
        :param action: Encoded action (pair_index * 4 + action_type)
        :return: Tuple of (pair_index, action_type)
                 action_type: 0=Hold, 1=Buy, 2=Sell, 3=Close
        """
        action_type = action % 4
        pair_index = action // 4
        return (pair_index, action_type)

    @abstractmethod
    def get_state(self):
        """Get current state from all data sources"""
        pass
    
    

