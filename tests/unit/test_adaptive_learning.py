"""
Unit tests for Adaptive Learning Rate Schedulers
Tests for learning rate scheduler implementations and DQN agent integration
"""

import pytest
import os
import sys
import numpy as np
from unittest.mock import Mock, MagicMock
from tensorflow import keras

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/mt5-python_server/src'))

from agents.learning_rate_scheduler import (
    BaseLearningRateScheduler,
    ReduceLROnPlateauScheduler,
    CosineAnnealingScheduler,
    AdaptiveScheduler,
    create_scheduler,
)


class TestReduceLROnPlateauScheduler:
    """Tests for ReduceLROnPlateau scheduler"""

    def test_reduce_on_plateau_decreases_lr(self):
        """Test that learning rate decreases when metric plateaus"""
        scheduler = ReduceLROnPlateauScheduler(
            factor=0.5, patience=3, min_lr=1e-6, monitor='loss', mode='min'
        )
        optimizer = keras.optimizers.Adam(learning_rate=0.001)

        # Initial loss
        initial_lr = scheduler.get_current_lr(optimizer)
        assert initial_lr == 0.001

        # Simulate plateau: loss doesn't improve for patience steps
        scheduler.step(0.5, optimizer)  # Best loss
        scheduler.step(0.6, optimizer)  # Worse
        scheduler.step(0.7, optimizer)  # Worse
        scheduler.step(0.8, optimizer)  # Worse - should trigger reduction

        new_lr = scheduler.get_current_lr(optimizer)
        assert new_lr < initial_lr
        assert new_lr == 0.0005  # 0.001 * 0.5

    def test_reduce_on_plateau_resets_on_improvement(self):
        """Test that patience resets when metric improves"""
        scheduler = ReduceLROnPlateauScheduler(
            factor=0.5, patience=3, min_lr=1e-6, monitor='loss', mode='min'
        )
        optimizer = keras.optimizers.Adam(learning_rate=0.001)

        # Set best loss
        scheduler.step(0.5, optimizer)  # Best loss
        scheduler.step(0.6, optimizer)  # Worse
        scheduler.step(0.4, optimizer)  # Better - should reset patience

        # Should not reduce yet
        lr = scheduler.get_current_lr(optimizer)
        assert lr == 0.001

    def test_reduce_on_plateau_respects_min_lr(self):
        """Test that learning rate doesn't go below minimum"""
        scheduler = ReduceLROnPlateauScheduler(
            factor=0.5, patience=1, min_lr=1e-4, monitor='loss', mode='min'
        )
        optimizer = keras.optimizers.Adam(learning_rate=1e-4)

        # Try to reduce below minimum
        scheduler.step(0.5, optimizer)
        scheduler.step(0.6, optimizer)  # Should trigger reduction

        lr = scheduler.get_current_lr(optimizer)
        assert lr >= 1e-4

    def test_reduce_on_plateau_max_mode(self):
        """Test reduce on plateau with max mode (for reward maximization)"""
        scheduler = ReduceLROnPlateauScheduler(
            factor=0.5, patience=3, min_lr=1e-6, monitor='reward', mode='max'
        )
        optimizer = keras.optimizers.Adam(learning_rate=0.001)

        # Set best reward
        scheduler.step(1.0, optimizer)  # Best reward
        scheduler.step(0.9, optimizer)  # Worse
        scheduler.step(0.8, optimizer)  # Worse
        scheduler.step(0.7, optimizer)  # Worse - should trigger reduction

        new_lr = scheduler.get_current_lr(optimizer)
        assert new_lr < 0.001


class TestCosineAnnealingScheduler:
    """Tests for CosineAnnealing scheduler"""

    def test_cosine_annealing_cycles(self):
        """Test that cosine annealing cycles correctly"""
        scheduler = CosineAnnealingScheduler(T_max=10, eta_min=1e-6, initial_lr=0.001)
        optimizer = keras.optimizers.Adam(learning_rate=0.001)

        # First step
        lr1 = scheduler.step(0.5, optimizer)
        assert lr1 > 1e-6
        assert lr1 <= 0.001

        # After T_max steps, should return to near initial
        for _ in range(10):
            scheduler.step(0.5, optimizer)

        # Should be near initial after full cycle
        lr_after_cycle = scheduler.get_current_lr(optimizer)
        assert abs(lr_after_cycle - 0.001) < 0.0001

    def test_cosine_annealing_respects_min_lr(self):
        """Test that cosine annealing respects minimum learning rate"""
        scheduler = CosineAnnealingScheduler(T_max=10, eta_min=1e-4, initial_lr=0.001)
        optimizer = keras.optimizers.Adam(learning_rate=0.001)

        # Step to minimum (middle of cycle)
        for _ in range(5):
            scheduler.step(0.5, optimizer)

        lr = scheduler.get_current_lr(optimizer)
        assert lr >= 1e-4


class TestAdaptiveScheduler:
    """Tests for Adaptive scheduler"""

    def test_adaptive_scheduler_combines_strategies(self):
        """Test that adaptive scheduler combines plateau and cosine"""
        plateau = ReduceLROnPlateauScheduler(factor=0.5, patience=3)
        cosine = CosineAnnealingScheduler(T_max=10, eta_min=1e-6)
        scheduler = AdaptiveScheduler(
            reduce_on_plateau=plateau,
            cosine_annealing=cosine,
            primary_strategy='plateau',
        )
        optimizer = keras.optimizers.Adam(learning_rate=0.001)

        # Should work with both strategies
        lr = scheduler.step(0.5, optimizer)
        assert lr > 0


class TestSchedulerFactory:
    """Tests for scheduler factory function"""

    def test_create_reduce_on_plateau(self):
        """Test creating reduce on plateau scheduler"""
        scheduler = create_scheduler(
            'reduce_on_plateau', factor=0.5, patience=10
        )
        assert isinstance(scheduler, ReduceLROnPlateauScheduler)

    def test_create_cosine_annealing(self):
        """Test creating cosine annealing scheduler"""
        scheduler = create_scheduler('cosine_annealing', T_max=100)
        assert isinstance(scheduler, CosineAnnealingScheduler)

    def test_create_adaptive(self):
        """Test creating adaptive scheduler"""
        scheduler = create_scheduler('adaptive')
        assert isinstance(scheduler, AdaptiveScheduler)

    def test_create_invalid_type(self):
        """Test that invalid scheduler type raises error"""
        with pytest.raises(ValueError):
            create_scheduler('invalid_type')


class TestDQNAgentIntegration:
    """Tests for DQN agent integration with learning rate scheduler"""

    def test_dqn_agent_with_scheduler(self):
        """Test DQN agent with learning rate scheduler"""
        from agents.dqn_agent import DQNAgent

        scheduler = ReduceLROnPlateauScheduler(factor=0.5, patience=3)
        agent = DQNAgent(
            state_shape=(50, 15),
            action_size=4,
            learning_rate=0.001,
            learning_rate_scheduler=scheduler,
        )

        assert agent.learning_rate_scheduler is not None
        assert agent.learning_rate == 0.001

    def test_dqn_agent_scheduler_config(self):
        """Test DQN agent with scheduler config"""
        from agents.dqn_agent import DQNAgent

        scheduler_config = {
            'type': 'reduce_on_plateau',
            'factor': 0.5,
            'patience': 10,
        }
        agent = DQNAgent(
            state_shape=(50, 15),
            action_size=4,
            learning_rate=0.001,
            scheduler_config=scheduler_config,
        )

        assert agent.learning_rate_scheduler is not None
        assert isinstance(agent.learning_rate_scheduler, ReduceLROnPlateauScheduler)

    def test_dqn_agent_update_learning_rate(self):
        """Test that DQN agent updates learning rate during training"""
        from agents.dqn_agent import DQNAgent

        scheduler = ReduceLROnPlateauScheduler(factor=0.5, patience=2)
        agent = DQNAgent(
            state_shape=(50, 15),
            action_size=4,
            learning_rate=0.001,
            learning_rate_scheduler=scheduler,
            batch_size=32,
            memory_size=1000,
        )

        initial_lr = agent.learning_rate

        # Add experiences and train
        state = np.random.randn(50, 15)
        for i in range(100):
            agent.remember(state, 0, 0.1, state, False)

        # Train multiple times to trigger scheduler
        for _ in range(5):
            loss = agent.replay()
            if loss > 0:
                # Update learning rate with scheduler
                agent.update_learning_rate(loss)

        # Check that learning rate history is tracked
        lr_history = agent.get_learning_rate_history()
        assert len(lr_history) > 0
