"""
Distributed Training Support
Multi-GPU and multi-node training using TensorFlow distribute
"""
import os
import logging
from typing import Optional, Dict, Any
import tensorflow as tf
from tensorflow import keras

from agents.dqn_agent import DQNAgent
from utils.gpu_utils import GPUConfig


class DistributedTrainer:
    """
    Distributed training wrapper for DQN agent
    Supports multi-GPU and multi-node training
    """
    
    def __init__(
        self,
        strategy_type: str = 'mirrored',
        devices: Optional[list] = None,
        cluster_resolver: Optional[tf.distribute.cluster_resolver.ClusterResolver] = None
    ):
        """
        Initialize distributed trainer
        
        :param strategy_type: Strategy type ('mirrored', 'multi_worker', 'parameter_server')
        :param devices: Optional list of device IDs to use
        :param cluster_resolver: Optional cluster resolver for multi-node training
        """
        self.strategy_type = strategy_type
        self.devices = devices
        self.cluster_resolver = cluster_resolver
        self.logger = logging.getLogger(__name__)
        
        # Create distribution strategy
        self.strategy = self._create_strategy()
        
        # Agent will be created within strategy scope
        self.agent: Optional[DQNAgent] = None
    
    def _create_strategy(self) -> tf.distribute.Strategy:
        """
        Create distribution strategy based on configuration
        
        :return: Distribution strategy
        """
        if self.strategy_type == 'mirrored':
            # Multi-GPU on single machine
            if self.devices:
                self.logger.info(f"Using MirroredStrategy with devices: {self.devices}")
                return tf.distribute.MirroredStrategy(devices=self.devices)
            else:
                self.logger.info("Using MirroredStrategy with all available GPUs")
                return tf.distribute.MirroredStrategy()
        
        elif self.strategy_type == 'multi_worker':
            # Multi-node training
            if self.cluster_resolver:
                self.logger.info("Using MultiWorkerMirroredStrategy")
                return tf.distribute.MultiWorkerMirroredStrategy(
                    cluster_resolver=self.cluster_resolver
                )
            else:
                self.logger.warning("MultiWorkerMirroredStrategy requires cluster_resolver")
                return tf.distribute.MirroredStrategy()
        
        elif self.strategy_type == 'parameter_server':
            # Parameter server strategy (for very large models)
            self.logger.info("Using ParameterServerStrategy")
            return tf.distribute.experimental.ParameterServerStrategy(
                cluster_resolver=self.cluster_resolver
            )
        
        else:
            self.logger.warning(f"Unknown strategy type: {self.strategy_type}, using default")
            return tf.distribute.get_strategy()
    
    def create_agent_within_strategy(
        self,
        state_shape: tuple,
        action_size: int,
        **agent_kwargs
    ) -> DQNAgent:
        """
        Create DQN agent within distribution strategy scope
        
        :param state_shape: Shape of state space
        :param action_size: Number of actions
        :param agent_kwargs: Additional arguments for DQNAgent
        :return: DQN agent
        """
        with self.strategy.scope():
            self.agent = DQNAgent(
                state_shape=state_shape,
                action_size=action_size,
                **agent_kwargs
            )
            self.logger.info("Agent created within distribution strategy scope")
        
        return self.agent
    
    def get_strategy(self) -> tf.distribute.Strategy:
        """
        Get the distribution strategy
        
        :return: Distribution strategy
        """
        return self.strategy
    
    def get_num_replicas(self) -> int:
        """
        Get number of replicas (GPUs/workers)
        
        :return: Number of replicas
        """
        return self.strategy.num_replicas_in_sync
    
    def is_distributed(self) -> bool:
        """
        Check if distributed training is enabled
        
        :return: True if distributed
        """
        return self.strategy.num_replicas_in_sync > 1
    
    def get_worker_info(self) -> Dict[str, Any]:
        """
        Get information about workers
        
        :return: Dictionary with worker information
        """
        return {
            'strategy_type': self.strategy_type,
            'num_replicas': self.strategy.num_replicas_in_sync,
            'devices': self.devices,
            'is_distributed': self.is_distributed()
        }


def setup_distributed_training(
    strategy_type: str = 'mirrored',
    devices: Optional[list] = None
) -> DistributedTrainer:
    """
    Setup distributed training (convenience function)
    
    :param strategy_type: Strategy type
    :param devices: Optional device IDs
    :return: DistributedTrainer instance
    """
    # Configure GPU first
    gpu_config = GPUConfig()
    gpu_config.configure_gpu()
    
    # Create distributed trainer
    trainer = DistributedTrainer(strategy_type=strategy_type, devices=devices)
    
    return trainer
