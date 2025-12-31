"""
Attention-based DQN Agent
Extends DQN with multi-head attention mechanisms
"""
import numpy as np
from typing import Optional, Tuple, Dict, List
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

from agents.dqn_agent import DQNAgent


class AttentionDQNAgent(DQNAgent):
    """
    DQN Agent with attention mechanisms
    Uses multi-head self-attention to focus on important time steps
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
        attention_config: Optional[Dict] = None,
        architecture_config: Optional[Dict] = None
    ):
        """
        Initialize Attention DQN Agent
        
        :param attention_config: Configuration for attention mechanism
            - num_heads: Number of attention heads (default: 8)
            - key_dim: Dimension of key/query (default: 64)
            - use_cross_attention: Use cross-pair attention (default: False)
        """
        # Attention configuration
        self.attention_config = attention_config or {}
        self.num_heads = self.attention_config.get('num_heads', 8)
        self.key_dim = self.attention_config.get('key_dim', 64)
        self.use_cross_attention = self.attention_config.get('use_cross_attention', False)
        
        # Initialize parent with architecture config
        super().__init__(
            state_shape=state_shape,
            action_size=action_size,
            learning_rate=learning_rate,
            discount_factor=discount_factor,
            epsilon=epsilon,
            epsilon_min=epsilon_min,
            epsilon_decay=epsilon_decay,
            memory_size=memory_size,
            batch_size=batch_size,
            target_update_freq=target_update_freq,
            use_double_dqn=use_double_dqn,
            use_per=use_per,
            per_alpha=per_alpha,
            per_beta=per_beta,
            per_beta_increment=per_beta_increment,
            architecture_config=architecture_config
        )
    
    def _build_model(self) -> keras.Model:
        """
        Build the Q-network model with attention mechanisms
        
        :return: Compiled Keras model
        """
        window_size, n_features = self.state_shape
        
        # Get architecture parameters
        n_lstm_layers = self.architecture_config.get('n_lstm_layers', 2)
        lstm_units = self.architecture_config.get('lstm_units', [128, 64])
        dense_units = self.architecture_config.get('dense_units', [64, 32])
        dropout_rate = self.architecture_config.get('dropout_rate', 0.2)
        activation = self.architecture_config.get('activation', 'relu')
        
        # Ensure we have enough LSTM units
        if len(lstm_units) < n_lstm_layers:
            lstm_units = lstm_units + [lstm_units[-1]] * (n_lstm_layers - len(lstm_units))
        
        # Input layer
        inputs = layers.Input(shape=(window_size, n_features))
        
        # LSTM layers (keep sequences for attention)
        x = inputs
        for i in range(n_lstm_layers - 1):
            x = layers.LSTM(lstm_units[i], return_sequences=True, activation=activation)(x)
            x = layers.BatchNormalization()(x)
            x = layers.Dropout(dropout_rate)(x)
        
        # Last LSTM layer (keep sequences for attention)
        lstm_out = layers.LSTM(lstm_units[-1], return_sequences=True, activation=activation)(x)
        lstm_out = layers.BatchNormalization()(lstm_out)
        
        # Multi-head self-attention
        attention_out = layers.MultiHeadAttention(
            num_heads=self.num_heads,
            key_dim=self.key_dim
        )(lstm_out, lstm_out)
        
        attention_out = layers.BatchNormalization()(attention_out)
        attention_out = layers.Dropout(dropout_rate)(attention_out)
        
        # Combine LSTM and attention outputs
        combined = layers.Concatenate(axis=-1)([lstm_out, attention_out])
        
        # Global average pooling to reduce sequence dimension
        pooled = layers.GlobalAveragePooling1D()(combined)
        
        # Dense layers
        x = pooled
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
    
    def get_attention_weights(self, state: np.ndarray) -> np.ndarray:
        """
        Get attention weights for a given state (for interpretability)
        
        :param state: Current state
        :return: Attention weights
        """
        # This would require a separate model that outputs attention weights
        # For now, return placeholder
        # In a full implementation, you'd create a model that outputs attention weights
        state = np.expand_dims(state, axis=0)
        # Note: This is a simplified version. Full implementation would
        # require extracting attention weights from the model
        return np.ones((state.shape[1], state.shape[1])) / state.shape[1]
