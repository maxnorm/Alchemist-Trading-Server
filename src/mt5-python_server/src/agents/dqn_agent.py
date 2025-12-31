"""
Deep Q-Network (DQN) Agent with Double DQN Support
Implements DQN with experience replay and Double DQN to reduce overestimation bias
"""
import numpy as np
import os
import json
from collections import deque
from typing import Optional, Tuple
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers


class DQNAgent:
    """
    DQN Agent with Double DQN for trading
    
    Features:
    - Deep Q-Network with LSTM layers for sequence learning
    - Experience replay buffer
    - Target network for stable learning
    - Double DQN to reduce overestimation bias
    - Epsilon-greedy exploration
    """
    
    def __init__(
        self,
        state_shape: Tuple[int, int],
        action_size: int,
        learning_rate: float = 0.001,
        discount_factor: float = 0.95,
        epsilon: float = 1.0,
        epsilon_min: float = 0.01,
        epsilon_decay: float = 0.995,
        memory_size: int = 10000,
        batch_size: int = 32,
        target_update_freq: int = 100,
        use_double_dqn: bool = True
    ):
        """
        Initialize DQN Agent
        
        :param state_shape: Shape of state (window_size, n_features)
        :param action_size: Number of possible actions
        :param learning_rate: Learning rate for optimizer
        :param discount_factor: Discount factor (gamma) for future rewards
        :param epsilon: Initial exploration rate
        :param epsilon_min: Minimum exploration rate
        :param epsilon_decay: Epsilon decay rate
        :param memory_size: Size of experience replay buffer
        :param batch_size: Batch size for training
        :param target_update_freq: Frequency to update target network
        :param use_double_dqn: Whether to use Double DQN (default: True)
        """
        self.state_shape = state_shape
        self.action_size = action_size
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.memory_size = memory_size
        self.batch_size = batch_size
        self.target_update_freq = target_update_freq
        self.use_double_dqn = use_double_dqn
        
        # Experience replay buffer
        self.memory = deque(maxlen=memory_size)
        
        # Step counter for target network updates
        self.step_count = 0
        
        # Build Q-network and target network
        self.q_network = self._build_model()
        self.target_network = self._build_model()
        self._update_target_network()  # Initialize target network with same weights
        
    def _build_model(self) -> keras.Model:
        """
        Build the Q-network model
        Uses LSTM layers for sequence learning from time-series data
        
        :return: Compiled Keras model
        """
        window_size, n_features = self.state_shape
        
        # Input layer
        inputs = layers.Input(shape=(window_size, n_features))
        
        # LSTM layers for sequence learning
        lstm1 = layers.LSTM(128, return_sequences=True, activation='relu')(inputs)
        lstm1 = layers.Dropout(0.2)(lstm1)
        
        lstm2 = layers.LSTM(64, return_sequences=False, activation='relu')(lstm1)
        lstm2 = layers.Dropout(0.2)(lstm2)
        
        # Dense layers
        dense1 = layers.Dense(64, activation='relu')(lstm2)
        dense1 = layers.Dropout(0.2)(dense1)
        
        dense2 = layers.Dense(32, activation='relu')(dense1)
        
        # Output layer: Q-values for each action
        outputs = layers.Dense(self.action_size, activation='linear')(dense2)
        
        model = keras.Model(inputs=inputs, outputs=outputs)
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=self.learning_rate),
            loss='mse'
        )
        
        return model
    
    def _update_target_network(self):
        """Update target network weights with Q-network weights"""
        self.target_network.set_weights(self.q_network.get_weights())
    
    def remember(self, state: np.ndarray, action: int, reward: float, 
                 next_state: np.ndarray, done: bool):
        """
        Store experience in replay buffer
        
        :param state: Current state
        :param action: Action taken
        :param reward: Reward received
        :param next_state: Next state
        :param done: Whether episode is done
        """
        self.memory.append((state, action, reward, next_state, done))
    
    def act(self, state: np.ndarray, training: bool = True) -> int:
        """
        Choose action using epsilon-greedy policy
        
        :param state: Current state
        :param training: Whether in training mode (affects epsilon)
        :return: Selected action
        """
        if training and np.random.rand() <= self.epsilon:
            return np.random.randint(self.action_size)
        
        # Reshape state for model input
        state = np.expand_dims(state, axis=0)
        
        # Get Q-values from network
        q_values = self.q_network.predict(state, verbose=0)
        
        # Return action with highest Q-value
        return np.argmax(q_values[0])
    
    def replay(self) -> float:
        """
        Train the agent on a batch of experiences
        Uses Double DQN to reduce overestimation bias
        
        :return: Training loss
        """
        if len(self.memory) < self.batch_size:
            return 0.0
        
        # Sample batch from memory
        batch = np.random.choice(len(self.memory), self.batch_size, replace=False)
        states = np.array([self.memory[i][0] for i in batch])
        actions = np.array([self.memory[i][1] for i in batch])
        rewards = np.array([self.memory[i][2] for i in batch])
        next_states = np.array([self.memory[i][3] for i in batch])
        dones = np.array([self.memory[i][4] for i in batch])
        
        # Get current Q-values
        current_q_values = self.q_network.predict(states, verbose=0)
        
        # Calculate target Q-values
        if self.use_double_dqn:
            # Double DQN: Use main network to select action, target network to evaluate
            # This reduces overestimation bias
            
            # Get next actions from main network
            next_q_values_main = self.q_network.predict(next_states, verbose=0)
            next_actions = np.argmax(next_q_values_main, axis=1)
            
            # Get Q-values from target network
            next_q_values_target = self.target_network.predict(next_states, verbose=0)
            
            # Use selected actions from main network, but values from target network
            target_q_values = current_q_values.copy()
            for i in range(self.batch_size):
                if dones[i]:
                    target_q_values[i][actions[i]] = rewards[i]
                else:
                    target_q_values[i][actions[i]] = (
                        rewards[i] + 
                        self.discount_factor * next_q_values_target[i][next_actions[i]]
                    )
        else:
            # Standard DQN: Use target network for both action selection and evaluation
            next_q_values = self.target_network.predict(next_states, verbose=0)
            max_next_q_values = np.max(next_q_values, axis=1)
            
            target_q_values = current_q_values.copy()
            for i in range(self.batch_size):
                if dones[i]:
                    target_q_values[i][actions[i]] = rewards[i]
                else:
                    target_q_values[i][actions[i]] = (
                        rewards[i] + 
                        self.discount_factor * max_next_q_values[i]
                    )
        
        # Train the network
        history = self.q_network.fit(
            states, 
            target_q_values, 
            batch_size=self.batch_size,
            epochs=1,
            verbose=0
        )
        
        loss = history.history['loss'][0]
        
        # Update target network periodically
        self.step_count += 1
        if self.step_count % self.target_update_freq == 0:
            self._update_target_network()
        
        # Decay epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
        
        return loss
    
    def save(self, filepath: str):
        """
        Save the agent model and parameters
        
        :param filepath: Directory to save model
        """
        os.makedirs(filepath, exist_ok=True)
        
        # Save Q-network
        self.q_network.save(os.path.join(filepath, 'q_network.h5'))
        
        # Save target network
        self.target_network.save(os.path.join(filepath, 'target_network.h5'))
        
        # Save agent parameters
        params = {
            'state_shape': self.state_shape,
            'action_size': self.action_size,
            'learning_rate': self.learning_rate,
            'discount_factor': self.discount_factor,
            'epsilon': self.epsilon,
            'epsilon_min': self.epsilon_min,
            'epsilon_decay': self.epsilon_decay,
            'memory_size': self.memory_size,
            'batch_size': self.batch_size,
            'target_update_freq': self.target_update_freq,
            'use_double_dqn': self.use_double_dqn,
            'step_count': self.step_count
        }
        
        with open(os.path.join(filepath, 'agent_params.json'), 'w') as f:
            json.dump(params, f, indent=2)
    
    def load(self, filepath: str):
        """
        Load the agent model and parameters
        
        :param filepath: Directory to load model from
        """
        # Load Q-network
        self.q_network = keras.models.load_model(
            os.path.join(filepath, 'q_network.h5')
        )
        
        # Load target network
        self.target_network = keras.models.load_model(
            os.path.join(filepath, 'target_network.h5')
        )
        
        # Load agent parameters
        with open(os.path.join(filepath, 'agent_params.json'), 'r') as f:
            params = json.load(f)
        
        # Update parameters (except state_shape and action_size which are fixed)
        self.learning_rate = params.get('learning_rate', self.learning_rate)
        self.discount_factor = params.get('discount_factor', self.discount_factor)
        self.epsilon = params.get('epsilon', self.epsilon)
        self.epsilon_min = params.get('epsilon_min', self.epsilon_min)
        self.epsilon_decay = params.get('epsilon_decay', self.epsilon_decay)
        self.memory_size = params.get('memory_size', self.memory_size)
        self.batch_size = params.get('batch_size', self.batch_size)
        self.target_update_freq = params.get('target_update_freq', self.target_update_freq)
        self.use_double_dqn = params.get('use_double_dqn', self.use_double_dqn)
        self.step_count = params.get('step_count', 0)
    
    def get_q_values(self, state: np.ndarray) -> np.ndarray:
        """
        Get Q-values for all actions in a given state
        
        :param state: Current state
        :return: Q-values for all actions
        """
        state = np.expand_dims(state, axis=0)
        q_values = self.q_network.predict(state, verbose=0)
        return q_values[0]
