"""
Celery tasks for drift detection
Runs drift detection periodically for all features
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from celery import Task
from utils.logging_config import get_logger

# Import Celery app
try:
    from infrastructure.data_pipeline.celery_app import celery_app

    CELERY_AVAILABLE = True
except ImportError:
    celery_app = None
    CELERY_AVAILABLE = False

logger = get_logger("drift_detection_tasks", "drift_detection_tasks.log")


if CELERY_AVAILABLE:

    @celery_app.task(name="drift_detection.detect_drift_for_all_features", bind=True)
    def detect_drift_for_all_features(self: Task) -> Dict[str, Any]:
        """
        Run drift detection for all features

        :return: Dictionary with drift detection results
        """
        if celery_app is None:
            logger.error("Celery app not available")
            return {"error": "Celery app not available"}

        try:
            from infrastructure.data_quality.drift_detector import (
                DistributionDriftDetector,
            )
            from infrastructure.data_quality.distribution_collector import (
                DistributionCollector,
            )
            from database import Database

            database = Database()
            drift_detector = DistributionDriftDetector()
            distribution_collector = DistributionCollector(database)

            # Get all unique feature/symbol combinations from distributions
            # For now, we'll use a predefined list of features
            # In production, this would query the database
            features_to_check = [
                ("price", "EURUSD"),
                ("rsi", "EURUSD"),
                ("macd", "EURUSD"),
                ("bollinger_upper", "EURUSD"),
                ("bollinger_lower", "EURUSD"),
                # Add more features as needed
            ]

            results = []
            for feature_name, symbol in features_to_check:
                try:
                    result = detect_drift_for_feature(
                        feature_name,
                        symbol,
                        database,
                        drift_detector,
                        distribution_collector,
                    )
                    results.append(result)
                except Exception as e:
                    logger.error(
                        f"Error detecting drift for {feature_name} ({symbol}): {e}"
                    )
                    results.append(
                        {
                            "feature_name": feature_name,
                            "symbol": symbol,
                            "error": str(e),
                        }
                    )

            return {
                "total_features_checked": len(features_to_check),
                "results": results,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error in drift detection task: {e}", exc_info=True)
            return {"error": str(e)}

else:

    def detect_drift_for_all_features(self: Task) -> Dict[str, Any]:
        """Placeholder when Celery not available"""
        return {"error": "Celery not available"}


if CELERY_AVAILABLE:

    @celery_app.task(name="drift_detection.detect_drift_for_feature", bind=True)
    def detect_drift_for_feature_task(
        self: Task,
        feature_name: str,
        symbol: str,
    ) -> Dict[str, Any]:
        """
        Run drift detection for a specific feature

        :param feature_name: Name of the feature
        :param symbol: Trading symbol
        :return: Drift detection results
        """
        if celery_app is None:
            logger.error("Celery app not available")
            return {"error": "Celery app not available"}

        try:
            from infrastructure.data_quality.drift_detector import (
                DistributionDriftDetector,
            )
            from infrastructure.data_quality.distribution_collector import (
                DistributionCollector,
            )
            from database import Database

            database = Database()
            drift_detector = DistributionDriftDetector()
            distribution_collector = DistributionCollector(database)

            return detect_drift_for_feature(
                feature_name, symbol, database, drift_detector, distribution_collector
            )

        except Exception as e:
            logger.error(
                f"Error in drift detection task for {feature_name} ({symbol}): {e}",
                exc_info=True,
            )
            return {"error": str(e)}

else:

    def detect_drift_for_feature_task(
        self: Task,
        feature_name: str,
        symbol: str,
    ) -> Dict[str, Any]:
        """Placeholder when Celery not available"""
        return {"error": "Celery not available"}


def detect_drift_for_feature(
    feature_name: str,
    symbol: str,
    database,
    drift_detector: Optional[Any] = None,
    distribution_collector: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Helper function to detect drift for a feature

    :param feature_name: Name of the feature
    :param symbol: Trading symbol
    :param database: Database instance
    :param drift_detector: DriftDetector instance (optional)
    :param distribution_collector: DistributionCollector instance (optional)
    :return: Drift detection results
    """
    try:
        if drift_detector is None:
            from infrastructure.data_quality.drift_detector import (
                DistributionDriftDetector,
            )

            drift_detector = DistributionDriftDetector()

        if distribution_collector is None:
            from infrastructure.data_quality.distribution_collector import (
                DistributionCollector,
            )

            distribution_collector = DistributionCollector(database)

        # Get baseline and current distributions
        baseline_data = distribution_collector.get_baseline_distribution(
            feature_name, symbol
        )
        current_data = distribution_collector.get_current_distribution(
            feature_name, symbol
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
        result = drift_detector.detect_drift(
            feature_name, baseline_data, current_data, method="both"
        )

        # Store drift detection result in database
        store_drift_detection(feature_name, symbol, result, database)

        # Update Prometheus metrics
        update_drift_metrics(feature_name, symbol, result)

        return result

    except Exception as e:
        logger.error(
            f"Error detecting drift for {feature_name} ({symbol}): {e}", exc_info=True
        )
        return {
            "feature_name": feature_name,
            "symbol": symbol,
            "error": str(e),
        }


def store_drift_detection(
    feature_name: str,
    symbol: str,
    result: Dict[str, Any],
    database,
) -> None:
    """
    Store drift detection result in database

    :param feature_name: Name of the feature
    :param symbol: Trading symbol
    :param result: Drift detection result dictionary
    :param database: Database instance
    """
    try:
        from sqlalchemy import text
        from datetime import datetime

        detection_time = datetime.utcnow()
        psi_score = result.get("psi_score")
        ks_statistic = result.get("ks_statistic")
        ks_pvalue = result.get("ks_pvalue")
        drift_severity = result.get("drift_severity", "none")
        drift_detected = result.get("drift_detected", False)

        # Calculate baseline and current window times
        baseline_window_days = 90
        monitoring_window_days = 30
        end_time = detection_time
        current_window_start = end_time - timedelta(days=monitoring_window_days)
        current_window_end = end_time
        baseline_window_end = current_window_start
        baseline_window_start = baseline_window_end - timedelta(
            days=baseline_window_days
        )

        baseline_size = result.get("baseline_size")
        current_size = result.get("current_size")
        baseline_mean = result.get("baseline_mean")
        baseline_std = result.get("baseline_std")
        current_mean = result.get("current_mean")
        current_std = result.get("current_std")
        mean_change_pct = result.get("mean_change_pct")
        std_change_pct = result.get("std_change_pct")

        with database.execute_query() as conn:
            conn.execute(
                text("""
                    INSERT INTO drift_detections
                    (feature_name, symbol, detection_time, psi_score, ks_statistic,
                     ks_pvalue, drift_severity, drift_detected,
                     baseline_window_start, baseline_window_end,
                     current_window_start, current_window_end,
                     baseline_size, current_size, baseline_mean, baseline_std,
                     current_mean, current_std, mean_change_pct, std_change_pct)
                    VALUES (:feature_name, :symbol, :detection_time, :psi_score,
                            :ks_statistic, :ks_pvalue, :drift_severity, :drift_detected,
                            :baseline_window_start, :baseline_window_end,
                            :current_window_start, :current_window_end,
                            :baseline_size, :current_size, :baseline_mean, :baseline_std, :current_mean, :current_std,
                            :mean_change_pct, :std_change_pct)
                """),
                {
                    "feature_name": feature_name,
                    "symbol": symbol,
                    "detection_time": detection_time,
                    "psi_score": psi_score,
                    "ks_statistic": ks_statistic,
                    "ks_pvalue": ks_pvalue,
                    "drift_severity": drift_severity,
                    "drift_detected": drift_detected,
                    "baseline_window_start": baseline_window_start,
                    "baseline_window_end": baseline_window_end,
                    "current_window_start": current_window_start,
                    "current_window_end": current_window_end,
                    "baseline_size": baseline_size,
                    "current_size": current_size,
                    "baseline_mean": baseline_mean,
                    "baseline_std": baseline_std,
                    "current_mean": current_mean,
                    "current_std": current_std,
                    "mean_change_pct": mean_change_pct,
                    "std_change_pct": std_change_pct,
                },
            )

        logger.debug(
            f"Stored drift detection for {feature_name} ({symbol}): {drift_severity}"
        )

    except Exception as e:
        logger.warning(f"Failed to store drift detection: {e}")


def update_drift_metrics(
    feature_name: str,
    symbol: str,
    result: Dict[str, Any],
) -> None:
    """
    Update Prometheus metrics for drift detection

    :param feature_name: Name of the feature
    :param symbol: Trading symbol
    :param result: Drift detection result dictionary
    """
    try:
        from monitoring.metrics import (
            data_drift_psi_score,
            data_drift_ks_statistic,
            data_drift_detections_total,
            data_drift_alerts_total,
        )

        psi_score = result.get("psi_score")
        ks_statistic = result.get("ks_statistic")
        drift_severity = result.get("drift_severity", "none")
        drift_detected = result.get("drift_detected", False)

        if psi_score is not None:
            data_drift_psi_score.labels(feature_name=feature_name, symbol=symbol).set(
                psi_score
            )

        if ks_statistic is not None:
            data_drift_ks_statistic.labels(
                feature_name=feature_name, symbol=symbol
            ).set(ks_statistic)

        # Increment detection counter
        data_drift_detections_total.labels(
            feature_name=feature_name, symbol=symbol, severity=drift_severity
        ).inc()

        # Increment alert counter if drift detected
        if drift_detected and drift_severity in ["minor", "major"]:
            data_drift_alerts_total.labels(
                feature_name=feature_name, symbol=symbol, severity=drift_severity
            ).inc()

    except Exception as e:
        logger.debug(f"Failed to update drift metrics: {e}")
