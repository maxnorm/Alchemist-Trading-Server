"""
Unit tests for TrainingHealthMonitor
Tests each health check independently with synthetic data
"""

import unittest
import numpy as np
from application.training.health_monitor import TrainingHealthMonitor


class TestTrainingHealthMonitor(unittest.TestCase):
    """Test TrainingHealthMonitor health checks"""

    def setUp(self):
        """Set up test fixtures"""
        config = {
            'divergence_threshold': 5.0,
            'gradient_norm_threshold': 10.0,
        }
        self.monitor = TrainingHealthMonitor(config)

    def test_check_loss_trend_no_divergence(self):
        """Test loss trend check with normal loss values"""
        # Add normal loss values
        for i in range(15):
            self.monitor.loss_history.append(0.5 + i * 0.01)
        
        is_diverged, reason = self.monitor.check_loss_trend(0.65)
        self.assertFalse(is_diverged)
        self.assertEqual(reason, "")

    def test_check_loss_trend_divergence(self):
        """Test loss trend check with exponential increase"""
        # Add losses that increase exponentially
        losses = [0.1, 0.2, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0]
        for loss in losses:
            self.monitor.loss_history.append(loss)
        
        is_diverged, reason = self.monitor.check_loss_trend(128.0)
        self.assertTrue(is_diverged)
        self.assertIn("Loss increased", reason)
        self.assertIn("divergence threshold", reason)

    def test_check_nan_in_loss(self):
        """Test NaN detection in loss value"""
        is_diverged, reason = self.monitor.check_nan(np.nan, None)
        self.assertTrue(is_diverged)
        self.assertIn("NaN/Inf detected in loss", reason)

    def test_check_nan_in_loss_inf(self):
        """Test Inf detection in loss value"""
        is_diverged, reason = self.monitor.check_nan(np.inf, None)
        self.assertTrue(is_diverged)
        self.assertIn("NaN/Inf detected in loss", reason)

    def test_check_nan_in_weights(self):
        """Test NaN detection in model weights"""
        weights = [
            np.array([1.0, 2.0, 3.0]),
            np.array([np.nan, 2.0, 3.0]),
            np.array([1.0, 2.0, 3.0]),
        ]
        is_diverged, reason = self.monitor.check_nan(0.5, weights)
        self.assertTrue(is_diverged)
        self.assertIn("NaN/Inf detected in model weights", reason)

    def test_check_nan_no_issue(self):
        """Test NaN check with valid values"""
        weights = [
            np.array([1.0, 2.0, 3.0]),
            np.array([4.0, 5.0, 6.0]),
        ]
        is_diverged, reason = self.monitor.check_nan(0.5, weights)
        self.assertFalse(is_diverged)
        self.assertEqual(reason, "")

    def test_check_gradient_norm_explosion(self):
        """Test gradient norm check with exploding gradients"""
        gradients = [
            np.array([100.0, 200.0, 300.0]),
            np.array([400.0, 500.0, 600.0]),
        ]
        is_diverged, reason, grad_norm = self.monitor.check_gradient_norm(gradients)
        self.assertTrue(is_diverged)
        self.assertIn("exceeds threshold", reason)
        self.assertIsNotNone(grad_norm)

    def test_check_gradient_norm_nan(self):
        """Test gradient norm check with NaN gradients"""
        gradients = [
            np.array([1.0, 2.0, 3.0]),
            np.array([np.nan, 2.0, 3.0]),
        ]
        is_diverged, reason, grad_norm = self.monitor.check_gradient_norm(gradients)
        self.assertTrue(is_diverged)
        self.assertIn("NaN/Inf in gradient norm", reason)

    def test_check_gradient_norm_normal(self):
        """Test gradient norm check with normal gradients"""
        gradients = [
            np.array([0.1, 0.2, 0.3]),
            np.array([0.4, 0.5, 0.6]),
        ]
        is_diverged, reason, grad_norm = self.monitor.check_gradient_norm(gradients)
        self.assertFalse(is_diverged)
        self.assertIsNotNone(grad_norm)
        self.assertLess(grad_norm, 10.0)

    def test_check_gradient_norm_preservation(self):
        """Test gradient norm preservation mechanism"""
        # First check sets initial norm
        gradients1 = [np.array([0.5, 0.5, 0.5])]
        is_diverged1, reason1, norm1 = self.monitor.check_gradient_norm(gradients1, preserve_initial_norm=True)
        self.assertFalse(is_diverged1)
        self.assertIsNotNone(self.monitor.initial_gradient_norm)
        
        # Second check with doubled norm should suggest LR adjustment
        gradients2 = [np.array([1.0, 1.0, 1.0])]
        is_diverged2, reason2, norm2 = self.monitor.check_gradient_norm(gradients2, preserve_initial_norm=True)
        self.assertFalse(is_diverged2)  # Not diverged, but suggests adjustment
        self.assertIn("suggest LR adjustment", reason2)
        self.assertLess(self.monitor.adaptive_lr_factor, 1.0)

    def test_check_value_overestimation(self):
        """Test value overestimation detection"""
        q_values = np.array([1e7, 1e6, 1e5])  # Very large Q-values
        is_diverged, reason = self.monitor.check_value_overestimation(q_values, threshold=1e6)
        self.assertTrue(is_diverged)
        self.assertIn("Value overestimation detected", reason)

    def test_check_value_overestimation_nan(self):
        """Test value overestimation with NaN Q-values"""
        q_values = np.array([np.nan, 1.0, 2.0])
        is_diverged, reason = self.monitor.check_value_overestimation(q_values)
        self.assertTrue(is_diverged)
        self.assertIn("NaN/Inf in Q-values", reason)

    def test_check_value_overestimation_normal(self):
        """Test value overestimation with normal Q-values"""
        q_values = np.array([10.0, 20.0, 30.0])
        is_diverged, reason = self.monitor.check_value_overestimation(q_values, threshold=1e6)
        self.assertFalse(is_diverged)
        self.assertEqual(reason, "")

    def test_check_update_to_data_ratio_high(self):
        """Test update-to-data ratio check with high ratio"""
        is_diverged, reason = self.monitor.check_update_to_data_ratio(
            update_count=1000,
            data_count=50,  # 20:1 ratio
            max_ratio=10.0
        )
        self.assertTrue(is_diverged)
        self.assertIn("Update-to-data ratio", reason)
        self.assertIn("exceeds threshold", reason)

    def test_check_update_to_data_ratio_normal(self):
        """Test update-to-data ratio check with normal ratio"""
        is_diverged, reason = self.monitor.check_update_to_data_ratio(
            update_count=100,
            data_count=50,  # 2:1 ratio
            max_ratio=10.0
        )
        self.assertFalse(is_diverged)
        self.assertEqual(reason, "")

    def test_check_update_to_data_ratio_zero_data(self):
        """Test update-to-data ratio with zero data count"""
        is_diverged, reason = self.monitor.check_update_to_data_ratio(
            update_count=100,
            data_count=0,
            max_ratio=10.0
        )
        self.assertFalse(is_diverged)
        self.assertEqual(reason, "")

    def test_gradient_norm_none(self):
        """Test gradient norm check with None gradients"""
        is_diverged, reason, grad_norm = self.monitor.check_gradient_norm(None)
        self.assertFalse(is_diverged)
        self.assertEqual(reason, "")
        self.assertIsNone(grad_norm)

    def test_value_overestimation_empty(self):
        """Test value overestimation with empty Q-values"""
        is_diverged, reason = self.monitor.check_value_overestimation(np.array([]))
        self.assertFalse(is_diverged)
        self.assertEqual(reason, "")


if __name__ == '__main__':
    unittest.main()
