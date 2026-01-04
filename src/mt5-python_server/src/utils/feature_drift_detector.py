"""
Feature Drift Detection using Population Stability Index (PSI)
Detects when feature distributions change significantly from reference distribution
"""

import numpy as np
from typing import Dict
import logging


class FeatureDriftDetector:
    """
    Detect feature distribution drift using PSI (Population Stability Index)

    PSI thresholds:
    - PSI < 0.1: No significant change
    - 0.1 <= PSI < 0.25: Minor change
    - PSI >= 0.25: Significant change (drift detected)
    """

    def __init__(
        self, reference_features: Dict[str, np.ndarray], drift_threshold: float = 0.25
    ):
        """
        Initialize drift detector

        :param reference_features: Dictionary of feature_name -> reference distribution
        :param drift_threshold: PSI threshold for drift detection (default: 0.25)
        """
        self.reference_features = reference_features
        self.drift_threshold = drift_threshold
        self.logger = logging.getLogger(__name__)

    def _calculate_psi(
        self, reference: np.ndarray, current: np.ndarray, n_bins: int = 10
    ) -> float:
        """
        Calculate Population Stability Index (PSI)

        :param reference: Reference distribution
        :param current: Current distribution
        :param n_bins: Number of bins for histogram
        :return: PSI value
        """
        # Remove NaN and Inf values
        reference = reference[np.isfinite(reference)]
        current = current[np.isfinite(current)]

        if len(reference) == 0 or len(current) == 0:
            return 0.0

        # Determine bin edges from reference distribution
        min_val = min(np.min(reference), np.min(current))
        max_val = max(np.max(reference), np.max(current))

        if min_val == max_val:
            return 0.0

        # Create bins
        bin_edges = np.linspace(min_val, max_val, n_bins + 1)

        # Calculate histograms
        ref_hist, _ = np.histogram(reference, bins=bin_edges)
        curr_hist, _ = np.histogram(current, bins=bin_edges)

        # Normalize to probabilities
        ref_probs = ref_hist / (len(reference) + 1e-10)
        curr_probs = curr_hist / (len(current) + 1e-10)

        # Add small epsilon to avoid log(0)
        ref_probs = ref_probs + 1e-10
        curr_probs = curr_probs + 1e-10

        # Calculate PSI
        psi = np.sum((curr_probs - ref_probs) * np.log(curr_probs / ref_probs))

        return float(psi)

    def detect_drift(self, current_features: Dict[str, np.ndarray]) -> Dict[str, bool]:
        """
        Detect drift for each feature

        :param current_features: Dictionary of feature_name -> current distribution
        :return: Dictionary of feature_name -> drift_detected (bool)
        """
        drift_results = {}

        for name, current_values in current_features.items():
            if name not in self.reference_features:
                continue  # Skip features not in reference

            reference_values = self.reference_features[name]

            # Calculate PSI
            psi = self._calculate_psi(reference_values, current_values)

            # Check if drift detected
            drift_detected = psi >= self.drift_threshold

            drift_results[name] = drift_detected

            if drift_detected:
                self.logger.warning(
                    f"Feature drift detected for '{name}': PSI={psi:.4f} "
                    f"(threshold={self.drift_threshold})"
                )

        return drift_results

    def get_drift_scores(
        self, current_features: Dict[str, np.ndarray]
    ) -> Dict[str, float]:
        """
        Get PSI scores for each feature (without threshold check)

        :param current_features: Dictionary of feature_name -> current distribution
        :return: Dictionary of feature_name -> PSI_score
        """
        psi_scores = {}

        for name, current_values in current_features.items():
            if name not in self.reference_features:
                continue

            reference_values = self.reference_features[name]
            psi = self._calculate_psi(reference_values, current_values)
            psi_scores[name] = psi

        return psi_scores

    def update_reference(self, new_reference_features: Dict[str, np.ndarray]):
        """
        Update reference distribution (e.g., after retraining)

        :param new_reference_features: New reference distributions
        """
        self.reference_features = new_reference_features
        self.logger.info("Reference features updated for drift detection")
