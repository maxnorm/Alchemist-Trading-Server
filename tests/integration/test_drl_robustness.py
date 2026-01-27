"""
Integration tests for DRL Robustness features
Tests adaptive learning rates, reward normalization, and reward monitoring together
"""

import pytest
import os
import sys
import numpy as np
from unittest.mock import Mock, MagicMock

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/backend/trading_server/src'))

from agents.dqn_agent import DQNAgent
from agents.learning_rate_scheduler import ReduceLROnPlateauScheduler
from environments.live_env import LiveTradingEnv
from environments.reward_normalizer import RewardNormalizer
from environments.reward_monitor import RewardMonitor


class TestDRLRobustnessIntegration:
    """Integration tests for DRL robustness features"""

    def test_agent_with_scheduler_and_normalized_rewards(self):
        """Test DQN agent with scheduler and normalized rewards in environment"""
        # Create scheduler
        scheduler = ReduceLROnPlateauScheduler(
            factor=0.5, patience=5, min_lr=1e-6, monitor='loss', mode='min'
        )

        # Create agent with scheduler
        agent = DQNAgent(
            state_shape=(50, 15),
            action_size=4,
            learning_rate=0.001,
            learning_rate_scheduler=scheduler,
            batch_size=32,
            memory_size=1000,
        )

        # Create normalizer and monitor
        normalizer = RewardNormalizer(alpha=0.99, clip_range=(-3.0, 3.0))
        monitor = RewardMonitor(window_size=100, anomaly_threshold=3.0)

        # Create mock account and data providers
        account = Mock()
        account.balance = 10000.0
        account.login = "test_account"

        data_provider = Mock()
        data_provider.currency_pair = Mock()
        data_provider.currency_pair.symbol = "EURUSD"
        data_provider.subscribe = Mock()

        # Create environment with normalizer and monitor
        env = LiveTradingEnv(
            account=account,
            data_providers=[data_provider],
            window_size=50,
            reward_normalizer=normalizer,
            use_reward_normalization=True,
            reward_monitor=monitor,
            use_reward_monitoring=True,
        )

        # Verify all components are configured
        assert agent.learning_rate_scheduler is not None
        assert env.reward_normalizer is not None
        assert env.reward_monitor is not None

    def test_training_with_adaptive_learning_and_normalization(self):
        """Test training loop with adaptive learning and reward normalization"""
        # Create scheduler
        scheduler = ReduceLROnPlateauScheduler(
            factor=0.5, patience=3, min_lr=1e-6, monitor='loss', mode='min'
        )

        # Create agent
        agent = DQNAgent(
            state_shape=(50, 15),
            action_size=4,
            learning_rate=0.001,
            learning_rate_scheduler=scheduler,
            batch_size=32,
            memory_size=1000,
        )

        # Create environment components
        normalizer = RewardNormalizer(alpha=0.99, clip_range=(-3.0, 3.0))
        monitor = RewardMonitor(window_size=100, anomaly_threshold=3.0)

        # Create mock account and data providers
        account = Mock()
        account.balance = 10000.0
        account.login = "test_account"

        data_provider = Mock()
        data_provider.currency_pair = Mock()
        data_provider.currency_pair.symbol = "EURUSD"
        data_provider.subscribe = Mock()

        env = LiveTradingEnv(
            account=account,
            data_providers=[data_provider],
            window_size=50,
            reward_normalizer=normalizer,
            use_reward_normalization=True,
            reward_monitor=monitor,
            use_reward_monitoring=True,
        )

        # Simulate training loop
        state = np.random.randn(50, 15)
        initial_lr = agent.learning_rate

        # Add experiences
        for i in range(200):
            action = agent.act(state, training=True)
            reward = env.calculate_reward(
                previous_balance=10000.0,
                current_balance=10000.0 + np.random.randn() * 100,
                action=action,
                has_position=False,
            )
            next_state = np.random.randn(50, 15)
            agent.remember(state, action, reward, next_state, False)
            state = next_state

        # Train multiple times
        losses = []
        for _ in range(10):
            loss = agent.replay()
            if loss > 0:
                losses.append(loss)
                agent.update_learning_rate(loss)

        # Verify learning rate was updated
        lr_history = agent.get_learning_rate_history()
        assert len(lr_history) > 0

        # Verify reward statistics
        reward_stats = env.get_reward_statistics()
        assert 'normalizer' in reward_stats
        assert 'monitor' in reward_stats

    def test_reward_monitor_detects_anomalies(self):
        """Test that reward monitor detects anomalies"""
        monitor = RewardMonitor(window_size=100, anomaly_threshold=3.0)

        # Normal rewards
        for _ in range(50):
            monitor.update(1.0, components={'sharpe_reward': 0.5})

        # Anomalous reward
        monitor.update(100.0, components={'sharpe_reward': 50.0})

        stats = monitor.get_statistics()
        assert stats['anomaly_count'] > 0

    def test_reward_monitor_detects_hacking(self):
        """Test that reward monitor detects reward hacking"""
        monitor = RewardMonitor(window_size=100, anomaly_threshold=3.0)

        # Simulate reward hacking: agent exploits transaction_penalty
        for _ in range(100):
            monitor.update(
                0.1,
                components={
                    'sharpe_reward': 0.01,
                    'drawdown_penalty': 0.01,
                    'volatility_penalty': 0.01,
                    'transaction_penalty': -0.95,  # Dominates
                    'action_penalty': 0.01,
                },
            )

        is_hacking, component = monitor.detect_reward_hacking(component_threshold=0.8)
        assert is_hacking
        assert component == 'transaction_penalty'

    def test_reward_monitor_detects_distribution_shift(self):
        """Test that reward monitor detects distribution shifts"""
        monitor = RewardMonitor(window_size=100, anomaly_threshold=3.0)

        # First distribution
        for _ in range(100):
            monitor.update(1.0)

        # Shift to different distribution
        for _ in range(100):
            monitor.update(10.0)

        shift_detected = monitor.detect_distribution_shift(window_size=50, threshold=2.0)
        assert shift_detected

    def test_all_components_work_together(self):
        """Test that all robustness components work together"""
        # Create all components
        scheduler = ReduceLROnPlateauScheduler(factor=0.5, patience=5)
        normalizer = RewardNormalizer(alpha=0.99, clip_range=(-3.0, 3.0))
        monitor = RewardMonitor(window_size=100, anomaly_threshold=3.0)

        # Create agent
        agent = DQNAgent(
            state_shape=(50, 15),
            action_size=4,
            learning_rate=0.001,
            learning_rate_scheduler=scheduler,
            batch_size=32,
            memory_size=1000,
        )

        # Create mock account and data providers
        account = Mock()
        account.balance = 10000.0
        account.login = "test_account"

        data_provider = Mock()
        data_provider.currency_pair = Mock()
        data_provider.currency_pair.symbol = "EURUSD"
        data_provider.subscribe = Mock()

        # Create environment
        env = LiveTradingEnv(
            account=account,
            data_providers=[data_provider],
            window_size=50,
            reward_normalizer=normalizer,
            use_reward_normalization=True,
            reward_monitor=monitor,
            use_reward_monitoring=True,
        )

        # Simulate training
        state = np.random.randn(50, 15)
        for i in range(100):
            action = agent.act(state, training=True)
            reward = env.calculate_reward(
                previous_balance=10000.0,
                current_balance=10000.0 + np.random.randn() * 50,
                action=action,
                has_position=False,
            )
            next_state = np.random.randn(50, 15)
            agent.remember(state, action, reward, next_state, False)
            state = next_state

        # Train
        for _ in range(5):
            loss = agent.replay()
            if loss > 0:
                agent.update_learning_rate(loss)

        # Verify all components are working
        assert len(agent.get_learning_rate_history()) > 0
        stats = env.get_reward_statistics()
        assert 'normalizer' in stats
        assert 'monitor' in stats
        assert stats['normalizer']['count'] > 0
        assert stats['monitor']['reward_count'] > 0
