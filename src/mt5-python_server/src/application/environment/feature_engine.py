"""
Feature engine
Extracts features from price history
"""

import numpy as np
import time
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from utils.technical_indicators import TechnicalIndicators
from utils.feature_engineering import FeatureEngineer
from monitoring.metrics import feature_extraction_duration

logger = logging.getLogger(__name__)


class FeatureEngine:
    """Extracts features from price history"""

    def __init__(
        self,
        feature_engineer: FeatureEngineer,
        window_size: int,
        features_per_pair: int,
        database=None,
        feature_registry=None,
        auto_register: bool = True,
    ):
        """
        Initialize feature engine
        :param feature_engineer: Feature engineer instance
        :param window_size: Window size for features
        :param features_per_pair: Number of features per pair
        :param database: Optional database instance for feature registry
        :param feature_registry: Optional FeatureRegistry instance
        :param auto_register: Whether to auto-register pipeline version (default: True)
        """
        self.feature_engineer = feature_engineer
        self.window_size = window_size
        self.features_per_pair = features_per_pair

        # Indicator cache for performance
        self.indicator_cache: Dict[str, Dict[str, np.ndarray]] = {}
        self.last_calculated_length: Dict[str, int] = {}

        # Economic calendar database (optional)
        self.database = database
        
        # Feature versioning
        self.feature_registry = feature_registry
        self.auto_register = auto_register
        self.pipeline_version: Optional[str] = None
        self.feature_list: List[str] = []
        self._feature_definitions: Optional[Dict[str, Any]] = None
        
        # Initialize version tracking
        self._initialize_versioning()

    def extract_features(
        self, price_history: List[float], symbol: str, current_time: Optional[datetime] = None
    ) -> Optional[np.ndarray]:
        """
        Extract features from price history for a single pair
        :param price_history: List of prices (should already be filtered by point-in-time if current_time is provided)
        :param symbol: Currency pair symbol
        :param current_time: Current datetime for point-in-time constraint (optional, for defensive checks)
        :return: Feature matrix or None if insufficient data
        """
        start_time = time.time()
        
        if len(price_history) < self.window_size:
            return None
        
        # Point-in-time constraint: filter price_history to only include data <= current_time
        # Note: The actual filtering happens in PriceHistoryManager.get_history_up_to()
        # This parameter is for explicit point-in-time awareness and defensive checks
        if current_time is not None:
            # Price history should already be filtered by caller using PriceHistoryManager.get_history_up_to()
            # We add this parameter for explicit point-in-time awareness
            pass

        # Get recent window
        prices = np.array(price_history[-self.window_size :])

        # Check if we can use cached indicators
        current_length = len(price_history)
        last_length = self.last_calculated_length.get(symbol, 0)

        # If no new prices, return cached indicators
        if current_length == last_length and symbol in self.indicator_cache:
            indicators = self.indicator_cache[symbol].copy()
        else:
            # Calculate indicators (full calculation)
            indicators = TechnicalIndicators.calculate_all_indicators(prices)
            # Update cache
            self.indicator_cache[symbol] = {k: v.copy() for k, v in indicators.items()}
            self.last_calculated_length[symbol] = current_length

        # Combine features
        pair_features = {"price": prices, **indicators}

        # Fit feature engineer if not fitted
        if not self.feature_engineer.is_fitted:
            try:
                clean_features = {k: np.nan_to_num(v) for k, v in indicators.items()}
                clean_features["price"] = prices
                self.feature_engineer.fit(clean_features)
            except Exception:
                # If fitting fails, defer and wait for more data
                return None

        # Transform features
        if self.feature_engineer.is_fitted:
            pair_feature_matrix = self.feature_engineer.transform(pair_features)

            # Ensure correct shape (window_size, n_features_per_pair)
            if len(pair_feature_matrix.shape) == 2:
                if pair_feature_matrix.shape[0] < self.window_size:
                    # Pad with zeros
                    padding = np.zeros(
                        (
                            self.window_size - pair_feature_matrix.shape[0],
                            pair_feature_matrix.shape[1],
                        )
                    )
                    pair_feature_matrix = np.vstack([padding, pair_feature_matrix])
                elif pair_feature_matrix.shape[0] > self.window_size:
                    # Take last window_size
                    pair_feature_matrix = pair_feature_matrix[-self.window_size :]

            # Record feature extraction duration
            duration = time.time() - start_time
            feature_extraction_duration.observe(duration)
            
            return pair_feature_matrix

        # Record duration even if extraction failed
        duration = time.time() - start_time
        feature_extraction_duration.observe(duration)
        
        return None

    def set_database(self, database):
        """
        Set database instance for economic calendar queries
        :param database: Database instance
        """
        self.database = database
        # Re-initialize versioning if registry wasn't set before
        if self.feature_registry is None and database is not None:
            try:
                from mlops.feature_registry import FeatureRegistry
                self.feature_registry = FeatureRegistry(database)
                self._initialize_versioning()
            except Exception as e:
                logger.warning(f"Failed to initialize feature registry: {e}")
    
    def _initialize_versioning(self):
        """
        Initialize feature pipeline versioning.
        Computes pipeline hash, generates feature list, and optionally registers version.
        """
        try:
            # Get feature computation code files
            feature_files = self._get_feature_code_files()
            
            # Compute pipeline hash
            if self.feature_registry:
                pipeline_hash = self.feature_registry.compute_pipeline_hash(feature_files)
            else:
                # Fallback: compute hash directly
                import hashlib
                hasher = hashlib.sha256()
                for file_path in sorted(feature_files):
                    try:
                        with open(file_path, "rb") as f:
                            hasher.update(f.read())
                    except FileNotFoundError:
                        hasher.update(file_path.encode())
                pipeline_hash = hasher.hexdigest()
            
            # Generate feature list from technical indicators
            self.feature_list = self._generate_feature_list()
            
            # Generate feature definitions
            self._feature_definitions = self._get_feature_definitions()
            
            # Check if this pipeline version already exists
            if self.feature_registry:
                existing_version = self.feature_registry.get_pipeline_by_hash(pipeline_hash)
                if existing_version:
                    self.pipeline_version = existing_version.version
                    logger.info(f"Using existing pipeline version: {self.pipeline_version}")
                elif self.auto_register:
                    # Auto-register new version
                    code_commit = self.feature_registry.get_git_commit()
                    # Generate semantic version
                    latest = self.feature_registry.get_latest_version()
                    if latest:
                        # Increment patch version
                        try:
                            version_parts = latest.version.lstrip('v').split('.')
                            if len(version_parts) == 3:
                                major, minor, patch = map(int, version_parts)
                                new_version = f"v{major}.{minor}.{patch + 1}"
                            else:
                                new_version = "v1.0.0"
                        except (ValueError, IndexError):
                            new_version = "v1.0.0"
                    else:
                        new_version = "v1.0.0"
                    
                    registered = self.feature_registry.register_pipeline(
                        version=new_version,
                        pipeline_hash=pipeline_hash,
                        feature_list=self.feature_list,
                        feature_definitions=self._feature_definitions,
                        code_commit=code_commit,
                    )
                    self.pipeline_version = registered.version
                    logger.info(f"Auto-registered new pipeline version: {self.pipeline_version}")
            else:
                # No registry, use hash as version
                self.pipeline_version = f"hash_{pipeline_hash[:8]}"
                logger.debug(f"Using hash-based version (no registry): {self.pipeline_version}")
                
        except Exception as e:
            logger.warning(f"Failed to initialize feature versioning: {e}", exc_info=True)
            # Fallback to hash-based version
            self.pipeline_version = "unknown"
    
    def _get_feature_code_files(self) -> List[str]:
        """
        Get list of feature computation code files for hashing.
        
        :return: List of file paths
        """
        # Get the base directory (assuming we're in src/mt5-python_server/src)
        base_dir = Path(__file__).parent.parent.parent
        
        feature_files = [
            str(base_dir / "application" / "environment" / "feature_engine.py"),
            str(base_dir / "utils" / "technical_indicators.py"),
            str(base_dir / "utils" / "feature_engineering.py"),
        ]
        
        # Filter to only existing files
        return [f for f in feature_files if os.path.exists(f)]
    
    def _generate_feature_list(self) -> List[str]:
        """
        Generate list of feature names computed by this pipeline.
        
        :return: List of feature names
        """
        # Get features from technical indicators
        features = ["price"]  # Base price feature
        
        # Add technical indicator features
        # These match what TechnicalIndicators.calculate_all_indicators returns
        indicator_features = [
            "sma_20", "sma_50",
            "ema_12", "ema_26",
            "rsi",
            "macd", "macd_signal", "macd_histogram",
            "bb_upper", "bb_middle", "bb_lower", "bb_width",
            "price_change", "price_change_pct",
        ]
        features.extend(indicator_features)
        
        # Add economic calendar features (if database is available)
        if self.database is not None:
            economic_features = [
                "event_count_24h",
                "high_impact_count_24h",
                "medium_impact_count_24h",
                "low_impact_count_24h",
                "time_to_next_event",
                "next_event_impact",
            ]
            features.extend(economic_features)
        
        return features
    
    def _get_feature_definitions(self) -> Dict[str, Any]:
        """
        Get feature definitions and metadata.
        
        :return: Dictionary of feature metadata
        """
        definitions = {
            "window_size": self.window_size,
            "features_per_pair": self.features_per_pair,
            "normalization_method": self.feature_engineer.normalization_method,
            "technical_indicators": {
                "sma_periods": [20, 50],
                "ema_periods": [12, 26],
                "rsi_period": 14,
                "macd_params": {"fast": 12, "slow": 26, "signal": 9},
                "bollinger_params": {"period": 20, "num_std": 2.0},
            },
            "economic_calendar": {
                "enabled": self.database is not None,
                "lookahead_hours": 24,
                "latency_buffer_minutes": 5,
            },
        }
        
        return definitions
    
    def get_pipeline_metadata(self) -> Dict[str, Any]:
        """
        Export feature pipeline metadata for versioning.
        
        :return: Dictionary with pipeline metadata
        """
        return {
            "version": self.pipeline_version,
            "features": self.feature_list,
            "parameters": {
                "window_size": self.window_size,
                "features_per_pair": self.features_per_pair,
                "normalization_method": self.feature_engineer.normalization_method,
            },
            "feature_definitions": self._feature_definitions or self._get_feature_definitions(),
        }

    def extract_economic_features(
        self, symbol: str, current_time: datetime
    ) -> Dict[str, float]:
        """
        Extract economic calendar features for a symbol
        :param symbol: Currency pair symbol
        :param current_time: Current datetime (point-in-time constraint)
        :return: Dictionary of economic features
        """
        if self.database is None:
            # Return zero features if no database
            return {
                "event_count_24h": 0.0,
                "high_impact_count_24h": 0.0,
                "medium_impact_count_24h": 0.0,
                "low_impact_count_24h": 0.0,
                "time_to_next_event": 24.0,  # Default to 24 hours if no events
                "next_event_impact": 0.0,
            }

        try:
            # Apply latency buffer: only use events published at least 5 minutes ago
            LATENCY_BUFFER_MINUTES = 5
            from datetime import timedelta
            effective_time = current_time - timedelta(minutes=LATENCY_BUFFER_MINUTES)
            
            # Get events for next 24 hours
            events = self.database.get_upcoming_events(hours_ahead=24)
            
            # Filter events to only include those published before effective_time
            # This prevents look-ahead bias by only using events that would have been available
            available_events = [
                e for e in events
                if self._parse_event_datetime(e.get("datetime")) < effective_time
            ]

            # Extract base currency from symbol (first 3 chars)
            base_currency = symbol[:3]

            # Filter events relevant to this currency pair (using available_events instead of events)
            relevant_events = [
                e
                for e in available_events
                if e["country"] == base_currency
                or e["country"]
                in ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]
            ]

            # Calculate features
            event_count_24h = len(relevant_events)
            high_impact_count = sum(1 for e in relevant_events if e["impact"] == "High")
            medium_impact_count = sum(
                1 for e in relevant_events if e["impact"] == "Medium"
            )
            low_impact_count = sum(1 for e in relevant_events if e["impact"] == "Low")

            # Time to next event
            if relevant_events:
                next_event_time = relevant_events[0]["datetime"]
                if isinstance(next_event_time, str):
                    next_event_time = datetime.fromisoformat(
                        next_event_time.replace("Z", "+00:00")
                    )
                time_to_next = (next_event_time - current_time).total_seconds() / 3600.0
                time_to_next = max(0.0, min(24.0, time_to_next))  # Clamp to 0-24 hours
                next_event_impact = (
                    1.0
                    if relevant_events[0]["impact"] == "High"
                    else (0.5 if relevant_events[0]["impact"] == "Medium" else 0.25)
                )
            else:
                time_to_next = 24.0
                next_event_impact = 0.0

            return {
                "event_count_24h": float(event_count_24h),
                "high_impact_count_24h": float(high_impact_count),
                "medium_impact_count_24h": float(medium_impact_count),
                "low_impact_count_24h": float(low_impact_count),
                "time_to_next_event": time_to_next,
                "next_event_impact": next_event_impact,
            }
        except Exception:
            # Return zero features on error
            return {
                "event_count_24h": 0.0,
                "high_impact_count_24h": 0.0,
                "medium_impact_count_24h": 0.0,
                "low_impact_count_24h": 0.0,
                "time_to_next_event": 24.0,
                "next_event_impact": 0.0,
            }

    def _parse_event_datetime(self, dt_value: Any) -> datetime:
        """
        Parse event datetime from various formats
        
        :param dt_value: Datetime value (string or datetime object)
        :return: Parsed datetime
        """
        if isinstance(dt_value, datetime):
            return dt_value
        
        if isinstance(dt_value, str):
            # Try ISO format
            try:
                return datetime.fromisoformat(dt_value.replace("Z", "+00:00"))
            except ValueError:
                pass
            # Try standard format: "YYYY-MM-DD HH:MM:SS"
            try:
                return datetime.strptime(dt_value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        
        # Fallback: return current time if parsing fails
        return datetime.utcnow()

    def extract_features_for_all_pairs(
        self, price_histories: Dict[str, List[float]], connectors, current_time: Optional[datetime] = None
    ) -> Optional[np.ndarray]:
        """
        Extract features for all pairs
        Optimized with pre-allocation and vectorized operations
        :param price_histories: Dictionary of symbol -> price history (should be filtered by point-in-time)
        :param connectors: List of data source connectors
        :param current_time: Current datetime for point-in-time constraint (optional)
        :return: Combined feature matrix or None if insufficient data
        """
        n_pairs = len(connectors)
        if n_pairs == 0:
            return None

        # Pre-allocate list for better memory efficiency
        all_pair_features = []

        for connector in connectors:
            symbol = connector.config.symbol

            # Get price history for this pair
            if symbol not in price_histories:
                return None

            price_history = price_histories[symbol]
            if len(price_history) < self.window_size:
                return None

            # Extract features for this pair (includes indicator calculation)
            pair_features = self.extract_features(price_history, symbol, current_time=current_time)
            if pair_features is None:
                return None

            all_pair_features.append(pair_features)

        # Stack features from all pairs horizontally using vectorized operation
        # Result shape: (window_size, n_pairs * n_features_per_pair)
        if all_pair_features:
            # Use np.hstack for efficient horizontal concatenation
            combined_features = np.hstack(all_pair_features)
            return combined_features.astype(np.float32)

        return None
