from abc import ABC, abstractmethod
import numpy as np
import gymnasium as gym
from gymnasium import spaces


class BaseTradingEnv(gym.Env, ABC):
    def __init__(self, window_size=50, price_shape=5):
        """
        Initialize the trading environment
        :param window_size: The number of past prices to consider
        :param price_shape: The shape of the data
        """
        super(BaseTradingEnv, self).__init__()
        self.window_size = window_size
        
        # Define action space: 0=Hold, 1=Buy, 2=Sell, 3=Close
        self.action_space = spaces.Discrete(4)
        
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

    @abstractmethod
    def get_state(self):
        """Get current state from all data sources"""
        pass
    
    

