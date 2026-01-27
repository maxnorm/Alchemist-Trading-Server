"""
Agent factory
Creates DQN agents with proper configuration
Supports standard DQN, attention-based DQN, and custom architectures
"""

import os
from typing import Optional, Dict, Any, Tuple, Union, cast

from agents.dqn_agent import DQNAgent
from agents.attention_dqn_agent import AttentionDQNAgent
from environments.base_trading_env import BaseTradingEnv
from domain.config.agent_config import AgentConfig


class AgentFactory:
    """Factory for creating DQN agents"""

    @staticmethod
    def create_agent(
        env: BaseTradingEnv,
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
        if env.observation_space.shape is None:
            raise ValueError("Environment observation space must have a shape")
        state_shape = tuple(int(dim) for dim in env.observation_space.shape)

        if not hasattr(env.action_space, "n"):
            raise ValueError(
                "Environment action space must have 'n' attribute (Discrete space)"
            )
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
            # AttentionDQNAgent accepts any tuple shape
            agent: Union[AttentionDQNAgent, DQNAgent] = AttentionDQNAgent(
                state_shape=state_shape,  # type: ignore[arg-type]
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
            # DQNAgent also expects Tuple[int, int] based on the error
            if len(state_shape) != 2:
                raise ValueError(
                    f"DQNAgent requires 2D state shape, got {len(state_shape)}D"
                )
            state_shape_2d = cast(Tuple[int, int], (state_shape[0], state_shape[1]))
            agent = DQNAgent(
                state_shape=state_shape_2d,
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
        if model_path:
            try:
                # Check if it's a directory (local path) or needs to be downloaded
                if os.path.exists(model_path) and os.path.isdir(model_path):
                    agent.load(model_path)
                else:
                    # If it's an MLflow URI or other format, log warning
                    # The caller should use ModelRegistry.get_model_path() to download first
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Model path {model_path} does not exist locally. "
                        "Use ModelRegistry.get_model_path() to download from MLflow first."
                    )
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Could not load model from {model_path}: {e}")

        return agent
