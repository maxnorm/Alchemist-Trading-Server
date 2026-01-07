"""
Integration tests for training rollback mechanism
Tests full rollback flow with simulated divergence scenarios
"""

import unittest
import os
import tempfile
import shutil
import numpy as np
from unittest.mock import Mock, patch

from agents.dqn_agent import DQNAgent
from application.training.checkpoint_manager import CheckpointManager
from application.training.health_monitor import TrainingHealthMonitor
from application.training.training_loop import TrainingLoop
from application.training.metrics_tracker import MetricsTracker
from application.training.episode_manager import EpisodeManager
from domain.config.training_config import TrainingConfig


class TestTrainingRollback(unittest.TestCase):
    """Test training rollback mechanism"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_manager = CheckpointManager(self.temp_dir, save_freq_steps=1000)
        
        # Create a mock agent
        self.agent = Mock(spec=DQNAgent)
        self.agent.memory = Mock()
        self.agent.memory.__len__ = Mock(return_value=100)
        self.agent.epsilon = 0.1
        self.agent.learning_rate = 0.001
        
        # Mock agent save/load
        self.agent.save = Mock()
        self.agent.load = Mock()
        
        # Mock Q-network
        self.agent.q_network = Mock()
        self.agent.q_network.get_weights = Mock(return_value=[
            np.array([1.0, 2.0, 3.0]),
            np.array([4.0, 5.0, 6.0]),
        ])
        self.agent.q_network.optimizer = Mock()
        self.agent.q_network.optimizer.learning_rate = Mock()
        self.agent.q_network.optimizer.learning_rate.assign = Mock()
        self.agent.get_q_values = Mock(return_value=np.array([10.0, 20.0, 30.0]))

    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_pre_training_checkpoint(self):
        """Test saving pre-training checkpoint"""
        metrics = {
            "average_loss": 0.5,
            "total_reward": 100.0,
        }
        
        checkpoint_path = self.checkpoint_manager.save_pre_training_checkpoint(
            agent=self.agent,
            step=100,
            episode=1,
            metrics=metrics,
            logger=None,
        )
        
        self.assertIsNotNone(checkpoint_path)
        self.assertTrue(os.path.exists(checkpoint_path))
        self.assertTrue(os.path.exists(os.path.join(checkpoint_path, "metadata.json")))
        self.agent.save.assert_called_once_with(checkpoint_path)
        
        # Verify metadata
        import json
        metadata_path = os.path.join(checkpoint_path, "metadata.json")
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        
        self.assertEqual(metadata["step"], 100)
        self.assertEqual(metadata["episode"], 1)
        self.assertEqual(metadata["health_status"], "valid")
        self.assertEqual(metadata["type"], "pre_training")

    def test_rollback_to_checkpoint_success(self):
        """Test successful rollback to checkpoint"""
        # First save a checkpoint
        metrics = {"average_loss": 0.5, "total_reward": 100.0}
        checkpoint_path = self.checkpoint_manager.save_pre_training_checkpoint(
            agent=self.agent,
            step=100,
            episode=1,
            metrics=metrics,
            logger=None,
        )
        
        # Perform rollback
        logger = Mock()
        success = self.checkpoint_manager.rollback_to_checkpoint(
            checkpoint_path=checkpoint_path,
            agent=self.agent,
            logger=logger,
        )
        
        self.assertTrue(success)
        self.agent.load.assert_called_once_with(checkpoint_path)
        logger.info.assert_called()

    def test_rollback_to_checkpoint_failure_missing_metadata(self):
        """Test rollback failure when metadata is missing"""
        # Create checkpoint directory without metadata
        checkpoint_path = os.path.join(self.temp_dir, "test_checkpoint")
        os.makedirs(checkpoint_path, exist_ok=True)
        
        logger = Mock()
        success = self.checkpoint_manager.rollback_to_checkpoint(
            checkpoint_path=checkpoint_path,
            agent=self.agent,
            logger=logger,
        )
        
        self.assertFalse(success)
        logger.error.assert_called()
        self.agent.load.assert_not_called()

    def test_get_latest_safe_checkpoint(self):
        """Test getting latest safe checkpoint"""
        # Save multiple checkpoints
        for step in [100, 200, 300]:
            metrics = {"average_loss": 0.5, "total_reward": 100.0}
            self.checkpoint_manager.save_pre_training_checkpoint(
                agent=self.agent,
                step=step,
                episode=1,
                metrics=metrics,
                logger=None,
            )
        
        latest = self.checkpoint_manager.get_latest_safe_checkpoint()
        self.assertIsNotNone(latest)
        self.assertIn("step300", latest)

    def test_get_latest_safe_checkpoint_none(self):
        """Test getting latest safe checkpoint when none exist"""
        latest = self.checkpoint_manager.get_latest_safe_checkpoint()
        self.assertIsNone(latest)

    def test_rollback_with_gradient_explosion(self):
        """Test rollback triggered by gradient explosion"""
        # Setup health monitor
        config = {
            'divergence_threshold': 5.0,
            'gradient_norm_threshold': 10.0,
        }
        health_monitor = TrainingHealthMonitor(config)
        
        # Simulate gradient explosion
        gradients = [
            np.array([100.0, 200.0, 300.0]),
            np.array([400.0, 500.0, 600.0]),
        ]
        is_diverged, reason, grad_norm = health_monitor.check_gradient_norm(gradients)
        
        self.assertTrue(is_diverged)
        self.assertIn("exceeds threshold", reason)
        self.assertGreater(grad_norm, 10.0)

    def test_rollback_with_nan_propagation(self):
        """Test rollback triggered by NaN propagation"""
        config = {
            'divergence_threshold': 5.0,
            'gradient_norm_threshold': 10.0,
        }
        health_monitor = TrainingHealthMonitor(config)
        
        # Simulate NaN in weights
        weights = [
            np.array([1.0, 2.0, 3.0]),
            np.array([np.nan, 2.0, 3.0]),
        ]
        is_diverged, reason = health_monitor.check_nan(0.5, weights)
        
        self.assertTrue(is_diverged)
        self.assertIn("NaN/Inf detected", reason)

    def test_rollback_with_value_overestimation(self):
        """Test rollback triggered by value overestimation"""
        config = {
            'divergence_threshold': 5.0,
            'gradient_norm_threshold': 10.0,
        }
        health_monitor = TrainingHealthMonitor(config)
        
        # Simulate value overestimation
        q_values = np.array([1e7, 1e6, 1e5])
        is_diverged, reason = health_monitor.check_value_overestimation(q_values, threshold=1e6)
        
        self.assertTrue(is_diverged)
        self.assertIn("Value overestimation", reason)

    def test_rollback_with_high_update_ratio(self):
        """Test rollback triggered by high update-to-data ratio"""
        config = {
            'divergence_threshold': 5.0,
            'gradient_norm_threshold': 10.0,
        }
        health_monitor = TrainingHealthMonitor(config)
        
        # Simulate high update-to-data ratio
        is_diverged, reason = health_monitor.check_update_to_data_ratio(
            update_count=1000,
            data_count=50,  # 20:1 ratio
            max_ratio=10.0
        )
        
        self.assertTrue(is_diverged)
        self.assertIn("Update-to-data ratio", reason)


if __name__ == '__main__':
    unittest.main()
