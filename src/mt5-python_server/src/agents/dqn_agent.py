"""
Deep Q-Network (DQN) Agent with Double DQN Support
Implements DQN with experience replay and Double DQN to reduce overestimation bias
"""
import numpy as np
import os
import json
from collections import deque
from typing import Optional, Tuple, Dict, List
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

from agents.sum_tree import SumTree


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
        use_double_dqn: bool = True,
        use_per: bool = True,
        per_alpha: float = 0.6,
        per_beta: float = 0.4,
        per_beta_increment: float = 0.001,
        architecture_config: Optional[Dict] = None
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
        :param use_per: Whether to use Prioritized Experience Replay (default: True)
        :param per_alpha: Priority exponent (0 = uniform, 1 = full priority)
        :param per_beta: Importance sampling exponent (0 = no correction, 1 = full correction)
        :param per_beta_increment: Beta increment per step
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
        self.use_per = use_per
        
        # Prioritized Experience Replay parameters
        self.per_alpha = per_alpha
        self.per_beta = per_beta
        self.per_beta_increment = per_beta_increment
        self.max_priority = 1.0
        
        # Architecture configuration
        self.architecture_config = architecture_config or {}
        
        # Batch prediction queue
        self.prediction_queue = []
        self.batch_size_pred = 32
        self.batch_timeout = 0.01  # 10ms
        
        # Experience replay buffer
        if self.use_per:
            self.memory = SumTree(memory_size)
        else:
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
        Architecture can be customized via architecture_config
        
        :return: Compiled Keras model
        """
        window_size, n_features = self.state_shape
        
        # Get architecture parameters from config or use defaults
        n_lstm_layers = self.architecture_config.get('n_lstm_layers', 2)
        lstm_units = self.architecture_config.get('lstm_units', [128, 64])
        dense_units = self.architecture_config.get('dense_units', [64, 32])
        dropout_rate = self.architecture_config.get('dropout_rate', 0.2)
        activation = self.architecture_config.get('activation', 'relu')
        
        # Ensure we have enough LSTM units for the number of layers
        if len(lstm_units) < n_lstm_layers:
            lstm_units = lstm_units + [lstm_units[-1]] * (n_lstm_layers - len(lstm_units))
        
        # Input layer
        inputs = layers.Input(shape=(window_size, n_features))
        
        # LSTM layers
        x = inputs
        for i in range(n_lstm_layers):
            return_sequences = (i < n_lstm_layers - 1)  # Last layer doesn't return sequences
            x = layers.LSTM(lstm_units[i], return_sequences=return_sequences, activation=activation)(x)
            x = layers.BatchNormalization()(x)
            x = layers.Dropout(dropout_rate)(x)
        
        # Dense layers
        for units in dense_units:
            x = layers.Dense(units, activation=activation)(x)
            x = layers.BatchNormalization()(x)
            x = layers.Dropout(dropout_rate)(x)
        
        # Output layer: Q-values for each action
        outputs = layers.Dense(self.action_size, activation='linear')(x)
        
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
        if self.use_per:
            # Use maximum priority for new experiences
            priority = self.max_priority ** self.per_alpha
            self.memory.add(priority, (state, action, reward, next_state, done))
        else:
            self.memory.append((state, action, reward, next_state, done))
    
    def act(self, state: np.ndarray, training: bool = True, action_mask: np.ndarray = None) -> int:
        """
        Choose action using epsilon-greedy policy with optional action masking
        
        :param state: Current state
        :param training: Whether in training mode (affects epsilon)
        :param action_mask: Optional binary mask (1=valid, 0=invalid) for each action
        :return: Selected action
        """
        if training and np.random.rand() <= self.epsilon:
            # Exploration: sample only from valid actions when mask provided
            if action_mask is not None:
                valid_actions = np.where(action_mask == 1)[0]
                if len(valid_actions) == 0:
                    # Fallback: if all actions masked, return HOLD (action 0)
                    return 0
                return int(np.random.choice(valid_actions))
            return int(np.random.randint(self.action_size))
        
        # Reshape state for model input
        state = np.expand_dims(state, axis=0)
        
        # Get Q-values from network
        q_values = self.q_network.predict(state, verbose=0)[0]
        
        # Apply action mask: set invalid actions to negative infinity
        if action_mask is not None:
            q_values = q_values.copy()  # Don't modify original array
            q_values[action_mask == 0] = -np.inf
        
        # Return action with highest Q-value (convert to Python int)
        return int(np.argmax(q_values))
    
    def update_epsilon_adaptive(
        self, 
        experience_count: int, 
        recent_rewards: Optional[List[float]] = None
    ) -> float:
        """
        Update epsilon adaptively based on experience count and optionally performance
        
        :param experience_count: Current number of experiences in memory
        :param recent_rewards: Optional list of recent rewards for performance-based adjustment
        :return: New epsilon value
        """
        from domain.constants import TradingConstants
        
        # Calculate base epsilon based on experience count
        if experience_count < TradingConstants.ADAPTIVE_EPSILON_THRESHOLD_1:
            target_epsilon = TradingConstants.ADAPTIVE_EPSILON_HIGH
        elif experience_count < TradingConstants.ADAPTIVE_EPSILON_THRESHOLD_2:
            target_epsilon = TradingConstants.ADAPTIVE_EPSILON_MEDIUM
        elif experience_count < TradingConstants.ADAPTIVE_EPSILON_THRESHOLD_3:
            target_epsilon = TradingConstants.ADAPTIVE_EPSILON_LOW
        else:
            target_epsilon = TradingConstants.ADAPTIVE_EPSILON_MIN
        
        # Optional: Adjust based on performance metrics
        if recent_rewards and len(recent_rewards) >= TradingConstants.PERFORMANCE_WINDOW_SIZE:
            reward_variance = float(np.var(recent_rewards[-TradingConstants.PERFORMANCE_WINDOW_SIZE:]))
            avg_reward = float(np.mean(recent_rewards[-TradingConstants.PERFORMANCE_WINDOW_SIZE:]))
            
            # High variance or negative returns -> explore more
            if (reward_variance > TradingConstants.REWARD_VARIANCE_THRESHOLD_HIGH or 
                avg_reward < 0):
                target_epsilon = min(0.5, target_epsilon * 1.2)
            # Low variance and positive returns -> exploit more
            elif (reward_variance < TradingConstants.REWARD_VARIANCE_THRESHOLD_LOW and 
                  avg_reward > 0):
                target_epsilon = max(self.epsilon_min, target_epsilon * 0.9)
        
        # Smooth transition: only update if change is significant
        if abs(self.epsilon - target_epsilon) > 0.05:  # 5% threshold
            old_epsilon = self.epsilon
            self.epsilon = max(self.epsilon_min, min(0.5, target_epsilon))
            return self.epsilon
        
        return self.epsilon
    
    def replay(self) -> float:
        """
        Train the agent on a batch of experiences
        Uses Double DQN to reduce overestimation bias
        Uses Prioritized Experience Replay if enabled
        
        :return: Training loss
        """
        if len(self.memory) < self.batch_size:
            return 0.0
        
        # Sample batch from memory
        if self.use_per:
            # Prioritized sampling
            batch_idx, batch, priorities = self.memory.sample(self.batch_size)
            states = np.array([exp[0] for exp in batch])
            actions = np.array([exp[1] for exp in batch])
            rewards = np.array([exp[2] for exp in batch])
            next_states = np.array([exp[3] for exp in batch])
            dones = np.array([exp[4] for exp in batch])
            
            # Calculate importance sampling weights
            total_priority = self.memory.total()
            probs = np.array(priorities) / (total_priority + 1e-6)
            weights = (len(self.memory) * probs) ** (-self.per_beta)
            weights = weights / weights.max()  # Normalize weights
        else:
            # Uniform sampling
            import random
            batch_indices = random.sample(range(len(self.memory)), min(self.batch_size, len(self.memory)))
            batch = [self.memory[i] for i in batch_indices]
            states = np.array([exp[0] for exp in batch])
            actions = np.array([exp[1] for exp in batch])
            rewards = np.array([exp[2] for exp in batch])
            next_states = np.array([exp[3] for exp in batch])
            dones = np.array([exp[4] for exp in batch])
            weights = np.ones(self.batch_size)
        
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
        
        # Train the network with importance sampling weights
        history = self.q_network.fit(
            states, 
            target_q_values, 
            batch_size=self.batch_size,
            epochs=1,
            verbose=0,
            sample_weight=weights
        )
        
        loss = history.history['loss'][0]
        
        # Update priorities in PER
        if self.use_per:
            # Calculate TD-errors for priority updates
            current_q_values = self.q_network.predict(states, verbose=0)
            td_errors = np.abs(target_q_values - current_q_values)
            
            # Update priorities
            for i, idx in enumerate(batch_idx):
                priority = (td_errors[i][actions[i]] + 1e-6) ** self.per_alpha
                self.memory.update(idx, priority)
                self.max_priority = max(self.max_priority, priority)
        
        # Update target network periodically
        self.step_count += 1
        if self.step_count % self.target_update_freq == 0:
            self._update_target_network()
        
        # Decay epsilon and increase beta
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
        
        if self.use_per:
            self.per_beta = min(1.0, self.per_beta + self.per_beta_increment)
        
        return loss
    
    def save(self, filepath: str):
        """
        Save the agent model and parameters with version metadata
        
        :param filepath: Directory to save model
        """
        from datetime import datetime
        
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
            'use_per': self.use_per,
            'per_alpha': self.per_alpha,
            'per_beta': self.per_beta,
            'per_beta_increment': self.per_beta_increment,
            'max_priority': self.max_priority,
            'step_count': self.step_count
        }
        
        with open(os.path.join(filepath, 'agent_params.json'), 'w') as f:
            json.dump(params, f, indent=2)
        
        # Save version metadata
        metadata = {
            'version': self._get_version(),
            'timestamp': datetime.now().isoformat(),
            'hyperparameters': {
                'learning_rate': self.learning_rate,
                'discount_factor': self.discount_factor,
                'epsilon': self.epsilon,
                'epsilon_min': self.epsilon_min,
                'epsilon_decay': self.epsilon_decay,
                'memory_size': self.memory_size,
                'batch_size': self.batch_size,
                'target_update_freq': self.target_update_freq,
                'use_double_dqn': self.use_double_dqn,
                'use_per': self.use_per,
                'per_alpha': self.per_alpha,
                'per_beta': self.per_beta,
                'per_beta_increment': self.per_beta_increment
            },
            'architecture': {
                'state_shape': list(self.state_shape),
                'action_size': self.action_size,
                'use_double_dqn': self.use_double_dqn,
                'use_per': self.use_per
            },
            'training_state': {
                'step_count': self.step_count,
                'memory_size': len(self.memory),
                'epsilon': self.epsilon,
                'per_beta': self.per_beta if self.use_per else None
            }
        }
        
        with open(os.path.join(filepath, 'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _get_version(self) -> str:
        """
        Generate version string based on step count
        
        :return: Version string (e.g., "1.0.1234")
        """
        major = 1
        minor = 0
        patch = self.step_count
        return f"{major}.{minor}.{patch}"
    
    def load(self, filepath: str):
        """
        Load the agent model and parameters
        
        :param filepath: Directory to load model from
        :raises ValueError: If loaded model's input shape doesn't match expected state_shape
        """
        # Load Q-network
        self.q_network = keras.models.load_model(
            os.path.join(filepath, 'q_network.h5')
        )
        
        # Load target network
        self.target_network = keras.models.load_model(
            os.path.join(filepath, 'target_network.h5')
        )
        
        # Validate that loaded model's input shape matches expected state_shape
        model_input_shape = self.q_network.input_shape[1:]  # Skip batch dimension
        expected_shape = self.state_shape
        
        if model_input_shape != expected_shape:
            raise ValueError(
                f"Model input shape mismatch: loaded model expects {model_input_shape}, "
                f"but agent was initialized with state_shape={expected_shape}. "
                f"The model was likely trained with a different feature configuration. "
                f"Please retrain the model or use a model trained with {expected_shape} features."
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
        self.use_per = params.get('use_per', True)
        self.per_alpha = params.get('per_alpha', 0.6)
        self.per_beta = params.get('per_beta', 0.4)
        self.per_beta_increment = params.get('per_beta_increment', 0.001)
        self.max_priority = params.get('max_priority', 1.0)
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
    
    def predict_batch(self, states: list) -> list:
        """
        Batch prediction for multiple states (GPU efficient)
        
        :param states: List of state arrays
        :return: List of Q-value arrays
        """
        if not states:
            return []
        
        # Convert to batch
        batch = np.array(states)
        q_values = self.q_network.predict(batch, verbose=0)
        
        # Return as list of arrays
        return [q_values[i] for i in range(len(states))]
    
    def act_batch(self, states: list, training: bool = True, action_masks: list = None) -> list:
        """
        Choose actions for a batch of states with optional action masking
        
        :param states: List of states
        :param training: Whether in training mode
        :param action_masks: Optional list of binary masks (1=valid, 0=invalid), one per state
        :return: List of selected actions
        """
        if not states:
            return []
        
        # Get Q-values for all states
        q_values_batch = self.predict_batch(states)
        
        actions = []
        for i, q_values in enumerate(q_values_batch):
            action_mask = action_masks[i] if action_masks and i < len(action_masks) else None
            
            if training and np.random.rand() <= self.epsilon:
                # Exploration: sample from valid actions only
                if action_mask is not None:
                    valid_actions = np.where(action_mask == 1)[0]
                    if len(valid_actions) == 0:
                        # Fallback: if all actions masked, return HOLD (action 0)
                        actions.append(0)
                    else:
                        actions.append(int(np.random.choice(valid_actions)))
                else:
                    # Random action (exploration)
                    actions.append(int(np.random.randint(self.action_size)))
            else:
                # Greedy action (exploitation)
                q_values_copy = q_values.copy() if action_mask is not None else q_values
                if action_mask is not None:
                    q_values_copy[action_mask == 0] = -np.inf
                actions.append(int(np.argmax(q_values_copy)))
        
        return actions
