"""
Distribution Drift Detector
Implements KS test and PSI for feature drift detection
"""

import numpy as np
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from scipy import stats
from utils.logging_config import get_logger


class DistributionDriftDetector:
    """
    Detects distribution drift in features using statistical tests

    Methods:
    - Kolmogorov-Smirnov (KS) test: Compare distributions
    - Population Stability Index (PSI): Measure feature drift
    - Statistical Process Control (SPC): Track mean/std changes
    """

    def __init__(
        self,
        psi_threshold_minor: float = 0.1,
        psi_threshold_major: float = 0.25,
        ks_pvalue_threshold: float = 0.05,
        baseline_window_days: int = 90,
        monitoring_window_days: int = 30,
    ):
        """
        Initialize drift detector

        :param psi_threshold_minor: PSI threshold for minor drift (default: 0.1)
        :param psi_threshold_major: PSI threshold for major drift (default: 0.25)
        :param ks_pvalue_threshold: KS test p-value threshold (default: 0.05)
        :param baseline_window_days: Baseline window in days (default: 90)
        :param monitoring_window_days: Monitoring window in days (default: 30)
        """
        self.psi_threshold_minor = psi_threshold_minor
        self.psi_threshold_major = psi_threshold_major
        self.ks_pvalue_threshold = ks_pvalue_threshold
        self.baseline_window_days = baseline_window_days
        self.monitoring_window_days = monitoring_window_days
        self.logger = get_logger("drift_detector", "drift_detector.log")

    def calculate_psi(
        self, baseline: np.ndarray, current: np.ndarray, bins: int = 10
    ) -> float:
        """
        Calculate Population Stability Index (PSI)

        PSI interpretation:
        - < 0.1: No significant drift
        - 0.1 - 0.25: Minor drift
        - > 0.25: Major drift

        :param baseline: Baseline data array
        :param current: Current data array
        :param bins: Number of bins for histogram (default: 10)
        :return: PSI score
        """
        if len(baseline) == 0 or len(current) == 0:
            return 0.0

        # Determine bin edges from combined data
        combined = np.concatenate([baseline, current])
        min_val = np.min(combined)
        max_val = np.max(combined)

        # Handle case where all values are the same
        if min_val == max_val:
            return 0.0

        # Create bins
        bin_edges = np.linspace(min_val, max_val, bins + 1)

        # Calculate histograms
        baseline_hist, _ = np.histogram(baseline, bins=bin_edges)
        current_hist, _ = np.histogram(current, bins=bin_edges)

        # Normalize to probabilities
        baseline_prob = baseline_hist / len(baseline)
        current_prob = current_hist / len(current)

        # Add small epsilon to avoid log(0)
        epsilon = 1e-10
        baseline_prob = baseline_prob + epsilon
        current_prob = current_prob + epsilon

        # Normalize again after adding epsilon
        baseline_prob = baseline_prob / baseline_prob.sum()
        current_prob = current_prob / current_prob.sum()

        # Calculate PSI
        psi = np.sum(
            (current_prob - baseline_prob) * np.log(current_prob / baseline_prob)
        )

        return float(psi)

    def calculate_ks_statistic(
        self, baseline: np.ndarray, current: np.ndarray
    ) -> Tuple[float, float]:
        """
        Calculate Kolmogorov-Smirnov test statistic and p-value

        :param baseline: Baseline data array
        :param current: Current data array
        :return: Tuple of (KS statistic, p-value)
        """
        if len(baseline) == 0 or len(current) == 0:
            return (0.0, 1.0)

        # Perform KS test
        statistic, pvalue = stats.ks_2samp(baseline, current)

        return (float(statistic), float(pvalue))

    def detect_drift(
        self,
        feature_name: str,
        baseline_data: np.ndarray,
        current_data: np.ndarray,
        method: str = "both",
    ) -> Dict[str, Any]:
        """
        Detect drift between baseline and current data

        :param feature_name: Name of the feature
        :param baseline_data: Baseline data array
        :param current_data: Current data array
        :param method: Detection method ('ks', 'psi', or 'both')
        :return: Dictionary with drift detection results
        """
        if len(baseline_data) == 0 or len(current_data) == 0:
            return {
                "feature_name": feature_name,
                "drift_detected": False,
                "method": method,
                "error": "Insufficient data",
            }

        # Convert to numpy arrays if needed
        baseline = np.array(baseline_data)
        current = np.array(current_data)

        results = {
            "feature_name": feature_name,
            "method": method,
            "baseline_size": len(baseline),
            "current_size": len(current),
        }

        # Calculate PSI
        if method in ["psi", "both"]:
            psi_score = self.calculate_psi(baseline, current)
            results["psi_score"] = psi_score

            # Determine drift severity based on PSI
            if psi_score >= self.psi_threshold_major:
                results["drift_severity"] = "major"
                results["drift_detected"] = True
            elif psi_score >= self.psi_threshold_minor:
                results["drift_severity"] = "minor"
                results["drift_detected"] = True
            else:
                results["drift_severity"] = "none"
                results["drift_detected"] = False

        # Calculate KS test
        if method in ["ks", "both"]:
            ks_statistic, ks_pvalue = self.calculate_ks_statistic(baseline, current)
            results["ks_statistic"] = ks_statistic
            results["ks_pvalue"] = ks_pvalue

            # Determine drift based on p-value
            if ks_pvalue < self.ks_pvalue_threshold:
                if "drift_detected" not in results:
                    results["drift_detected"] = True
                elif not results["drift_detected"]:
                    # If PSI didn't detect drift but KS did, mark as detected
                    results["drift_detected"] = True
                    if "drift_severity" not in results:
                        results["drift_severity"] = "minor"
            else:
                if "drift_detected" not in results:
                    results["drift_detected"] = False

        # Calculate basic statistics
        results["baseline_mean"] = float(np.mean(baseline))
        results["baseline_std"] = float(np.std(baseline))
        results["current_mean"] = float(np.mean(current))
        results["current_std"] = float(np.std(current))

        # Calculate mean/std change
        baseline_mean = float(results["baseline_mean"])
        current_mean = float(results["current_mean"])
        baseline_std = float(results["baseline_std"])
        current_std = float(results["current_std"])
        mean_change_pct = (
            abs(current_mean - baseline_mean) / max(abs(baseline_mean), 1e-10) * 100
        )
        std_change_pct = (
            abs(current_std - baseline_std) / max(abs(baseline_std), 1e-10) * 100
        )

        results["mean_change_pct"] = mean_change_pct
        results["std_change_pct"] = std_change_pct

        return results

    def monitor_feature(
        self,
        feature_name: str,
        symbol: str,
        window_days: Optional[int] = None,
        baseline_days: Optional[int] = None,
        database=None,
    ) -> Dict[str, Any]:
        """
        Monitor feature over time using database

        :param feature_name: Name of the feature
        :param symbol: Trading symbol
        :param window_days: Monitoring window in days (default: from config)
        :param baseline_days: Baseline window in days (default: from config)
        :param database: Database instance for querying feature distributions
        :return: Drift detection results
        """
        if database is None:
            return {
                "feature_name": feature_name,
                "symbol": symbol,
                "error": "Database not provided",
            }

        window_days = window_days or self.monitoring_window_days
        baseline_days = baseline_days or self.baseline_window_days

        # Calculate time windows
        end_time = datetime.utcnow()
        current_start = end_time - timedelta(days=window_days)
        baseline_end = current_start
        baseline_start = baseline_end - timedelta(days=baseline_days)

        # Query baseline data
        baseline_data = self._get_feature_data(
            database, feature_name, symbol, baseline_start, baseline_end
        )

        # Query current data
        current_data = self._get_feature_data(
            database, feature_name, symbol, current_start, end_time
        )

        if len(baseline_data) == 0 or len(current_data) == 0:
            return {
                "feature_name": feature_name,
                "symbol": symbol,
                "drift_detected": False,
                "error": "Insufficient data",
                "baseline_size": len(baseline_data),
                "current_size": len(current_data),
            }

        # Detect drift
        return self.detect_drift(
            feature_name, baseline_data, current_data, method="both"
        )

    def _get_feature_data(
        self,
        database,
        feature_name: str,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
    ) -> np.ndarray:
        """
        Get feature data from database

        :param database: Database instance
        :param feature_name: Feature name
        :param symbol: Trading symbol
        :param start_time: Start time
        :param end_time: End time
        :return: Feature values as numpy array
        """
        # This method should query the feature_distributions table
        # For now, return empty array - will be implemented when database integration is done
        try:
            # Query feature distributions table
            # Assuming database has a method to query feature distributions
            if hasattr(database, "get_feature_distributions"):
                distributions = database.get_feature_distributions(
                    feature_name=feature_name,
                    symbol=symbol,
                    start_time=start_time,
                    end_time=end_time,
                )
                # Extract mean values or sample values
                # For now, we'll use mean values as a proxy
                values = [
                    d.get("mean") for d in distributions if d.get("mean") is not None
                ]
                return np.array(values)
            else:
                self.logger.warning(
                    "Database does not have get_feature_distributions method"
                )
                return np.array([])
        except Exception as e:
            self.logger.error(f"Error getting feature data: {e}")
            return np.array([])

    def get_drift_report(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        database=None,
    ) -> Dict[str, Any]:
        """
        Generate drift report for all features

        :param symbol: Trading symbol
        :param start_time: Start time
        :param end_time: End time
        :param database: Database instance
        :return: Drift report
        """
        if database is None:
            return {"error": "Database not provided"}

        # This would query all features and generate a comprehensive report
        # For now, return a placeholder
        return {
            "symbol": symbol,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "features_checked": 0,
            "drifts_detected": 0,
            "report": [],
        }
