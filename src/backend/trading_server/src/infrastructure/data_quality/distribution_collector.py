"""
Distribution Collector
Collects and stores feature distributions for drift detection
"""

import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy import text
from utils.logging_config import get_logger
from utils.time_utils import get_utc_time


class DistributionCollector:
    """
    Collects and stores feature distributions for drift detection
    """

    def __init__(self, database=None):
        """
        Initialize distribution collector

        :param database: Database instance (optional, will create if not provided)
        """
        self.logger = get_logger("distribution_collector", "distribution_collector.log")

        # Lazy import database to avoid circular imports
        if database is None:
            try:
                from database import Database

                self.database = Database()
            except Exception as e:
                self.logger.warning(f"Failed to initialize database: {e}")
                self.database = None
        else:
            self.database = database

    def collect_distribution(
        self,
        feature_name: str,
        symbol: str,
        values: np.ndarray,
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        Calculate and store feature distribution statistics

        :param feature_name: Name of the feature
        :param symbol: Trading symbol
        :param values: Feature values as numpy array
        :param timestamp: Timestamp for the distribution (defaults to now)
        :return: True if successful, False otherwise
        """
        if self.database is None:
            self.logger.warning(
                "Database not available, skipping distribution collection"
            )
            return False

        if len(values) == 0:
            self.logger.warning(f"No values provided for {feature_name} ({symbol})")
            return False

        if timestamp is None:
            timestamp = get_utc_time()

        try:
            # Calculate statistics
            mean = float(np.mean(values))
            std = float(np.std(values))
            min_value = float(np.min(values))
            max_value = float(np.max(values))

            # Calculate percentiles
            percentiles_list = [10, 25, 50, 75, 90, 95, 99]
            percentiles_dict = {}
            for p in percentiles_list:
                percentiles_dict[str(p)] = float(np.percentile(values, p))

            sample_size = len(values)

            # Store in database
            import json

            with self.database.execute_query() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO feature_distributions
                        (feature_name, symbol, timestamp, mean, std, min_value,
                         max_value, percentiles, sample_size)
                        VALUES (:feature_name, :symbol, :timestamp, :mean, :std,
                                :min_value, :max_value, :percentiles::jsonb,
                                :sample_size)
                    """
                    ),
                    {
                        "feature_name": feature_name,
                        "symbol": symbol,
                        "timestamp": timestamp,
                        "mean": mean,
                        "std": std,
                        "min_value": min_value,
                        "max_value": max_value,
                        "percentiles": json.dumps(percentiles_dict),
                        "sample_size": sample_size,
                    },
                )

            self.logger.debug(
                f"Collected distribution for {feature_name} ({symbol}): "
                f"mean={mean:.6f}, std={std:.6f}, n={sample_size}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to collect distribution: {e}", exc_info=True)
            return False

    def get_distribution(
        self,
        feature_name: str,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve distributions for a feature within a time range

        :param feature_name: Name of the feature
        :param symbol: Trading symbol
        :param start_time: Start time
        :param end_time: End time
        :return: List of distribution dictionaries
        """
        if self.database is None:
            return []

        try:
            import json

            with self.database.execute_query() as conn:
                result = conn.execute(
                    text(
                        """
                        SELECT feature_name, symbol, timestamp, mean, std,
                               min_value, max_value, percentiles, sample_size
                        FROM feature_distributions
                        WHERE feature_name = :feature_name
                          AND symbol = :symbol
                          AND timestamp >= :start_time
                          AND timestamp <= :end_time
                        ORDER BY timestamp ASC
                    """
                    ),
                    {
                        "feature_name": feature_name,
                        "symbol": symbol,
                        "start_time": start_time,
                        "end_time": end_time,
                    },
                )

                distributions = []
                for row in result:
                    distributions.append(
                        {
                            "feature_name": row[0],
                            "symbol": row[1],
                            "timestamp": row[2],
                            "mean": float(row[3]) if row[3] is not None else None,
                            "std": float(row[4]) if row[4] is not None else None,
                            "min_value": float(row[5]) if row[5] is not None else None,
                            "max_value": float(row[6]) if row[6] is not None else None,
                            "percentiles": json.loads(row[7]) if row[7] else {},
                            "sample_size": row[8],
                        }
                    )

                return distributions

        except Exception as e:
            self.logger.error(f"Failed to get distributions: {e}", exc_info=True)
            return []

    def get_baseline_distribution(
        self,
        feature_name: str,
        symbol: str,
        baseline_days: int = 90,
    ) -> np.ndarray:
        """
        Get baseline distribution values for drift detection

        :param feature_name: Name of the feature
        :param symbol: Trading symbol
        :param baseline_days: Number of days for baseline window
        :return: Array of feature values (mean values from distributions)
        """
        end_time = get_utc_time()
        start_time = end_time - timedelta(days=baseline_days)

        distributions = self.get_distribution(
            feature_name, symbol, start_time, end_time
        )

        if len(distributions) == 0:
            return np.array([])

        # Extract mean values as proxy for feature values
        # In a real implementation, we might store actual sample values
        values = [d["mean"] for d in distributions if d["mean"] is not None]

        return np.array(values)

    def get_current_distribution(
        self,
        feature_name: str,
        symbol: str,
        window_days: int = 30,
    ) -> np.ndarray:
        """
        Get current distribution values for drift detection

        :param feature_name: Name of the feature
        :param symbol: Trading symbol
        :param window_days: Number of days for monitoring window
        :return: Array of feature values (mean values from distributions)
        """
        end_time = get_utc_time()
        start_time = end_time - timedelta(days=window_days)

        distributions = self.get_distribution(
            feature_name, symbol, start_time, end_time
        )

        if len(distributions) == 0:
            return np.array([])

        # Extract mean values as proxy for feature values
        values = [d["mean"] for d in distributions if d["mean"] is not None]

        return np.array(values)
