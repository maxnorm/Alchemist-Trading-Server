"""
Agent factory
Creates DQN agents with proper configuration
Supports standard DQN, attention-based DQN, and custom architectures
"""

import os
from typing import Optional, Dict, Any

from agents.dqn_agent import DQNAgent
from agents.attention_dqn_agent import AttentionDQNAgent
from environments.live_env import LiveTradingEnv
from domain.config.agent_config import AgentConfig


class AgentFactory:
    """Factory for creating DQN agents"""

    @staticmethod
    def create_agent(
        env: LiveTradingEnv,
        config: Optional[AgentConfig] = None,
        model_path: Optional[str] = None,
        use_attention: bool = False,
        architecture_config: Optional[Dict[str, Any]] = None,
        attention_config: Optional[Dict[str, Any]] = None,
    ) -> DQNAgent:
        """
        Create a DQN agent

        :param env: Trading environment
        :param config: Agent configuration (uses default if not provided)
        :param model_path: Optional path to pre-trained model
        :param use_attention: Whether to use attention-based agent
        :param architecture_config: Optional architecture configuration
        :param attention_config: Optional attention configuration
        :return: Configured DQN agent
        """
        # Extract state shape and action size from environment
        state_shape = tuple(int(dim) for dim in env.observation_space.shape)
        action_size = int(env.action_space.n)

        # Use provided config or default for live trading
        if config is None:
            config = AgentConfig.for_live_trading()

        # Load architecture config from file if path provided
        if architecture_config is None:
            arch_config_path = os.getenv("AI_ARCHITECTURE_CONFIG")
            if arch_config_path and os.path.exists(arch_config_path):
                import json

                with open(arch_config_path, "r") as f:
                    arch_data = json.load(f)
                    architecture_config = arch_data.get("architecture", {})

        # Create agent with configuration
        if use_attention:
            agent = AttentionDQNAgent(
                state_shape=state_shape,
                action_size=action_size,
                learning_rate=config.learning_rate,
                discount_factor=config.discount_factor,
                epsilon=config.epsilon,
                epsilon_min=config.epsilon_min,
                epsilon_decay=config.epsilon_decay,
                memory_size=config.memory_size,
                batch_size=config.batch_size,
                target_update_freq=config.target_update_freq,
                use_double_dqn=config.use_double_dqn,
                use_per=getattr(config, "use_per", True),
                per_alpha=getattr(config, "per_alpha", 0.6),
                per_beta=getattr(config, "per_beta", 0.4),
                per_beta_increment=getattr(config, "per_beta_increment", 0.001),
                attention_config=attention_config,
                architecture_config=architecture_config,
            )
        else:
            agent = DQNAgent(
                state_shape=state_shape,
                action_size=action_size,
                learning_rate=config.learning_rate,
                discount_factor=config.discount_factor,
                epsilon=config.epsilon,
                epsilon_min=config.epsilon_min,
                epsilon_decay=config.epsilon_decay,
                memory_size=config.memory_size,
                batch_size=config.batch_size,
                target_update_freq=config.target_update_freq,
                use_double_dqn=config.use_double_dqn,
                use_per=getattr(config, "use_per", True),
                per_alpha=getattr(config, "per_alpha", 0.6),
                per_beta=getattr(config, "per_beta", 0.4),
                per_beta_increment=getattr(config, "per_beta_increment", 0.001),
                architecture_config=architecture_config,
            )

        # Load pre-trained model if path provided
        if model_path and os.path.exists(model_path):
            try:
                agent.load(model_path)
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Could not load model from {model_path}: {e}")

        return agent
