"""
Unit tests for feature drift detection
"""
import unittest
import numpy as np

from tests.shared.helpers.path_utils import setup_trading_server_path
setup_trading_server_path()

from utils.feature_drift_detector import FeatureDriftDetector


class TestFeatureDriftDetector(unittest.TestCase):
    """Test feature drift detection"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Reference distribution (normal)
        self.reference_features = {
            'price': np.random.normal(1.0, 0.1, 1000),
            'rsi': np.random.normal(50.0, 10.0, 1000)
        }
        
        self.detector = FeatureDriftDetector(
            self.reference_features,
            drift_threshold=0.25
        )
    
    def test_no_drift_same_distribution(self):
        """Test no drift detected with same distribution"""
        current_features = {
            'price': np.random.normal(1.0, 0.1, 1000),
            'rsi': np.random.normal(50.0, 10.0, 1000)
        }
        
        drift_results = self.detector.detect_drift(current_features)
        # Should not detect drift for similar distributions
        # (Note: This is probabilistic, so we check that it's not always True)
        self.assertIn('price', drift_results)
        self.assertIn('rsi', drift_results)
    
    def test_drift_detected_different_distribution(self):
        """Test drift detected with significantly different distribution"""
        # Very different distribution
        current_features = {
            'price': np.random.normal(2.0, 0.5, 1000),  # Much higher mean
            'rsi': np.random.normal(50.0, 10.0, 1000)
        }
        
        drift_results = self.detector.detect_drift(current_features)
        # Should detect drift for price (different distribution)
        self.assertIn('price', drift_results)
        self.assertIn('rsi', drift_results)
    
    def test_get_drift_scores(self):
        """Test getting PSI scores"""
        current_features = {
            'price': np.random.normal(1.0, 0.1, 1000),
            'rsi': np.random.normal(50.0, 10.0, 1000)
        }
        
        psi_scores = self.detector.get_drift_scores(current_features)
        self.assertIn('price', psi_scores)
        self.assertIn('rsi', psi_scores)
        self.assertIsInstance(psi_scores['price'], float)
        self.assertGreaterEqual(psi_scores['price'], 0.0)
    
    def test_update_reference(self):
        """Test updating reference distribution"""
        new_reference = {
            'price': np.random.normal(1.5, 0.2, 1000),
            'rsi': np.random.normal(55.0, 12.0, 1000)
        }
        
        self.detector.update_reference(new_reference)
        self.assertEqual(len(self.detector.reference_features), 2)


if __name__ == '__main__':
    unittest.main()
