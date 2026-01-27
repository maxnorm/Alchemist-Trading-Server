"""
Unit tests for Reward Normalization
Tests for reward normalizer and integration with trading environment
"""

import pytest
import os
import sys
import numpy as np
from unittest.mock import Mock, MagicMock

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/backend/trading_server/src'))

from environments.reward_normalizer import RewardNormalizer


class TestRewardNormalizer:
    """Tests for RewardNormalizer"""

    def test_normalize_first_reward(self):
        """Test normalization of first reward"""
        normalizer = RewardNormalizer(alpha=0.99, clip_range=(-3.0, 3.0))
        reward = 1.0

        normalized = normalizer.normalize(reward)

        # First reward should initialize statistics
        assert normalized == reward  # First reward sets mean
        stats = normalizer.get_statistics()
        assert stats['mean'] == reward
        assert stats['count'] == 1

    def test_normalize_updates_statistics(self):
        """Test that normalization updates running statistics"""
        normalizer = RewardNormalizer(alpha=0.99, clip_range=(-3.0, 3.0))

        # Normalize multiple rewards
        rewards = [1.0, 2.0, 3.0, 4.0, 5.0]
        normalized_rewards = [normalizer.normalize(r) for r in rewards]

        stats = normalizer.get_statistics()
        assert stats['count'] == len(rewards)
        assert stats['mean'] > 0
        assert stats['std'] > 0

    def test_normalize_clips_extreme_values(self):
        """Test that normalization clips extreme values"""
        normalizer = RewardNormalizer(alpha=0.99, clip_range=(-3.0, 3.0))

        # Normalize rewards to establish statistics
        for _ in range(100):
            normalizer.normalize(1.0)

        # Extreme reward should be clipped
        extreme_reward = 100.0
        normalized = normalizer.normalize(extreme_reward)

        assert -3.0 <= normalized <= 3.0

    def test_normalize_window_based(self):
        """Test window-based normalization"""
        normalizer = RewardNormalizer(
            alpha=0.99,
            clip_range=(-3.0, 3.0),
            window_size=10,
            use_window=True,
        )

        # Normalize rewards
        rewards = [1.0, 2.0, 3.0, 4.0, 5.0] * 3
        normalized_rewards = [normalizer.normalize(r) for r in rewards]

        stats = normalizer.get_statistics()
        assert stats['count'] == len(rewards)

    def test_normalize_stable_distribution(self):
        """Test that normalization produces stable distribution"""
        normalizer = RewardNormalizer(alpha=0.99, clip_range=(-3.0, 3.0))

        # Generate rewards with varying magnitudes
        np.random.seed(42)
        rewards = np.random.normal(0, 10, 1000)  # Large variance

        normalized_rewards = [normalizer.normalize(float(r)) for r in rewards]

        # Normalized rewards should have stable distribution
        normalized_array = np.array(normalized_rewards[-100:])  # Last 100
        assert np.std(normalized_array) < 2.0  # Should be more stable

    def test_detect_distribution_shift(self):
        """Test distribution shift detection"""
        normalizer = RewardNormalizer(alpha=0.99, clip_range=(-3.0, 3.0))

        # Normalize rewards from one distribution
        for _ in range(200):
            normalizer.normalize(1.0)

        # Shift to different distribution
        for _ in range(100):
            normalizer.normalize(10.0)  # Much larger rewards

        # Should detect shift
        shift_detected = normalizer.detect_distribution_shift(window_size=100, threshold=2.0)
        assert shift_detected

    def test_reset(self):
        """Test resetting normalizer"""
        normalizer = RewardNormalizer(alpha=0.99, clip_range=(-3.0, 3.0))

        # Normalize some rewards
        for _ in range(10):
            normalizer.normalize(1.0)

        # Reset
        normalizer.reset()

        stats = normalizer.get_statistics()
        assert stats['count'] == 0
        assert stats['mean'] == 0.0
        assert stats['std'] == 1.0

    def test_get_statistics(self):
        """Test getting statistics"""
        normalizer = RewardNormalizer(alpha=0.99, clip_range=(-3.0, 3.0))

        # Normalize some rewards
        rewards = [1.0, 2.0, 3.0, 4.0, 5.0]
        for r in rewards:
            normalizer.normalize(r)

        stats = normalizer.get_statistics()
        assert 'mean' in stats
        assert 'std' in stats
        assert 'variance' in stats
        assert 'count' in stats
        assert stats['count'] == len(rewards)


class TestRewardNormalizerIntegration:
    """Tests for reward normalizer integration with environment"""

    def test_live_env_with_normalizer(self):
        """Test LiveTradingEnv with reward normalizer"""
        from environments.live_env import LiveTradingEnv
        from unittest.mock import Mock

        # Create mock account and data providers
        account = Mock()
        account.balance = 10000.0
        account.login = "test_account"

        data_provider = Mock()
        data_provider.currency_pair = Mock()
        data_provider.currency_pair.symbol = "EURUSD"
        data_provider.subscribe = Mock()

        # Create normalizer
        normalizer = RewardNormalizer(alpha=0.99, clip_range=(-3.0, 3.0))

        # Create environment with normalizer
        env = LiveTradingEnv(
            account=account,
            data_providers=[data_provider],
            window_size=50,
            reward_normalizer=normalizer,
            use_reward_normalization=True,
        )

        assert env.reward_normalizer is not None
        assert env.use_reward_normalization is True

    def test_live_env_normalizes_rewards(self):
        """Test that LiveTradingEnv normalizes rewards"""
        from environments.live_env import LiveTradingEnv
        from unittest.mock import Mock

        # Create mock account and data providers
        account = Mock()
        account.balance = 10000.0
        account.login = "test_account"

        data_provider = Mock()
        data_provider.currency_pair = Mock()
        data_provider.currency_pair.symbol = "EURUSD"
        data_provider.subscribe = Mock()

        # Create environment with normalization enabled
        env = LiveTradingEnv(
            account=account,
            data_providers=[data_provider],
            window_size=50,
            use_reward_normalization=True,
        )

        # Calculate reward multiple times to establish statistics
        for _ in range(10):
            reward = env.calculate_reward(
                previous_balance=10000.0,
                current_balance=10100.0,
                action=1,
                has_position=False,
            )

        # Check that normalizer has statistics
        stats = env.get_reward_statistics()
        assert 'normalizer' in stats
        assert stats['normalizer']['count'] > 0

    def test_live_env_reward_statistics(self):
        """Test getting reward statistics from environment"""
        from environments.live_env import LiveTradingEnv
        from unittest.mock import Mock

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
            use_reward_normalization=True,
        )

        # Get statistics (should work even without rewards)
        stats = env.get_reward_statistics()
        assert isinstance(stats, dict)
