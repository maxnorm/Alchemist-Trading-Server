"""
Feature engine
Extracts features from price history
"""

import numpy as np
import time
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
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

        # Feature filtering
        self.selected_features: Optional[List[str]] = None
        self._filtered_indicators: Optional[set] = None

        # Initialize version tracking
        self._initialize_versioning()

        # Initialize distribution collector for drift detection (optional)
        self.distribution_collector = None
        self.collect_distributions = False
        if self.collect_distributions:
            try:
                from infrastructure.data_quality.distribution_collector import (
                    DistributionCollector,
                )

                self.distribution_collector = DistributionCollector(database)
                logger.info("Distribution collection enabled for drift detection")
            except Exception as e:
                logger.warning(f"Failed to initialize distribution collector: {e}")
                self.distribution_collector = None

        # Track last distribution collection time (collect every 5 minutes)
        self._last_distribution_collection: Dict[str, datetime] = {}
        self._distribution_collection_interval = timedelta(minutes=5)

    def extract_features(
        self,
        price_history: List[float],
        symbol: str,
        current_time: Optional[datetime] = None,
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

        # Filter indicators if feature filtering is enabled
        if self._filtered_indicators is not None:
            # Only keep indicators that are in the filtered set
            indicators = {
                k: v for k, v in indicators.items() if k in self._filtered_indicators
            }
            # Note: "price" is not in indicators dict (it comes from TechnicalIndicators),
            # but we always include it in pair_features below since it's needed for feature engineering

        # Combine features
        # Always include price - it's the base data for all indicators
        # If filtering is enabled and price is not selected, it will be filtered out later
        # by the feature engineer transform step
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

            # Collect distributions for drift detection (periodically)
            if self.distribution_collector and current_time:
                self._collect_feature_distributions(
                    symbol,
                    pair_features,
                    current_time,
                )

            return pair_feature_matrix

        # Record duration even if extraction failed
        duration = time.time() - start_time
        feature_extraction_duration.observe(duration)

        return None

    def _collect_feature_distributions(
        self, symbol: str, pair_features, current_time: float
    ) -> None:
        """
        Internal helper to forward feature distributions to the optional
        DistributionCollector used for drift detection.

        This is intentionally conservative: if the collector or features are
        unavailable, the method is a no-op rather than raising.
        """
        if not self.distribution_collector or pair_features is None:
            return

        # Current implementation relies on the distribution collector's own API.
        # To avoid introducing behavioural changes here, we keep this as a
        # no-op hook that can be wired to the collector when its interface is
        # extended to support feature matrices directly.
        return

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
                pipeline_hash = self.feature_registry.compute_pipeline_hash(
                    feature_files
                )
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
                existing_version = self.feature_registry.get_pipeline_by_hash(
                    pipeline_hash
                )
                if existing_version:
                    self.pipeline_version = existing_version.version
                    logger.info(
                        f"Using existing pipeline version: {self.pipeline_version}"
                    )
                elif self.auto_register:
                    # Auto-register new version
                    code_commit = self.feature_registry.get_git_commit()
                    # Generate semantic version
                    latest = self.feature_registry.get_latest_version()
                    if latest:
                        # Increment patch version
                        try:
                            version_parts = latest.version.lstrip("v").split(".")
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
                    logger.info(
                        f"Auto-registered new pipeline version: {self.pipeline_version}"
                    )
            else:
                # No registry, use hash as version
                self.pipeline_version = f"hash_{pipeline_hash[:8]}"
                logger.debug(
                    f"Using hash-based version (no registry): {self.pipeline_version}"
                )

        except Exception as e:
            logger.warning(
                f"Failed to initialize feature versioning: {e}", exc_info=True
            )
            # Fallback to hash-based version
            self.pipeline_version = "unknown"

    def _get_feature_code_files(self) -> List[str]:
        """
        Get list of feature computation code files for hashing.

        :return: List of file paths
        """
        # Get the base directory (assuming we're in src/backend/trading_server/src)
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
            "sma_20",
            "sma_50",
            "ema_12",
            "ema_26",
            "rsi",
            "macd",
            "macd_signal",
            "macd_histogram",
            "bb_upper",
            "bb_middle",
            "bb_lower",
            "bb_width",
            "price_change",
            "price_change_pct",
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

            # Add news sentiment features
            news_features = [
                "news_sentiment_1h",
                "news_sentiment_24h",
                "news_volume_24h",
                "high_impact_news_count_24h",
            ]
            features.extend(news_features)

            # Add macro indicator features
            macro_features = [
                "fed_funds_rate",
                "unemployment_rate",
                "cpi_yoy",
                "gdp_growth_rate",
                "interest_rate_differential",
                "ecb_rate",
                "world_bank_gdp_growth",
            ]
            features.extend(macro_features)

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
            "feature_definitions": self._feature_definitions
            or self._get_feature_definitions(),
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
                e
                for e in events
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

    def extract_news_features(
        self, symbol: str, current_time: datetime
    ) -> Dict[str, float]:
        """
        Extract news sentiment features for a symbol
        Point-in-time safe: only uses news published before current_time

        :param symbol: Currency pair symbol
        :param current_time: Current datetime (point-in-time constraint)
        :return: Dictionary of news features
        """
        if self.database is None:
            return {
                "news_sentiment_1h": 0.0,
                "news_sentiment_24h": 0.0,
                "news_volume_24h": 0.0,
                "high_impact_news_count_24h": 0.0,
            }

        try:
            from datetime import timedelta

            # Point-in-time constraint: only use news published before current_time
            # Apply latency buffer: only use news published at least 5 minutes ago
            LATENCY_BUFFER_MINUTES = 5
            effective_time = current_time - timedelta(minutes=LATENCY_BUFFER_MINUTES)

            # Get news from last 24 hours (point-in-time safe)
            start_time = effective_time - timedelta(hours=24)
            news_articles = self.database.get_news_by_timeframe(
                start_time=start_time, end_time=effective_time, symbol=symbol
            )

            # Also get general news (symbol=None) that might affect the pair
            general_news = self.database.get_news_by_timeframe(
                start_time=start_time, end_time=effective_time, symbol=None
            )

            # Combine and filter by symbol relevance
            all_news = news_articles + general_news

            # Get news from last 1 hour
            one_hour_ago = effective_time - timedelta(hours=1)
            recent_news = [
                n
                for n in all_news
                if n["timestamp"] >= one_hour_ago and n["timestamp"] <= effective_time
            ]

            # Calculate features
            # 1-hour sentiment
            if recent_news:
                sentiment_scores_1h = [
                    n.get("sentiment_score", 0.0)
                    for n in recent_news
                    if n.get("sentiment_score") is not None
                ]
                news_sentiment_1h = (
                    sum(sentiment_scores_1h) / len(sentiment_scores_1h)
                    if sentiment_scores_1h
                    else 0.0
                )
            else:
                news_sentiment_1h = 0.0

            # 24-hour sentiment
            if all_news:
                sentiment_scores_24h = [
                    n.get("sentiment_score", 0.0)
                    for n in all_news
                    if n.get("sentiment_score") is not None
                ]
                news_sentiment_24h = (
                    sum(sentiment_scores_24h) / len(sentiment_scores_24h)
                    if sentiment_scores_24h
                    else 0.0
                )
            else:
                news_sentiment_24h = 0.0

            # News volume (24 hours)
            news_volume_24h = float(len(all_news))

            # High impact news count (24 hours)
            # High impact = sentiment_score > 0.5 or < -0.5
            high_impact_news = [
                n
                for n in all_news
                if n.get("sentiment_score") is not None
                and abs(n.get("sentiment_score", 0.0)) > 0.5
            ]
            high_impact_news_count_24h = float(len(high_impact_news))

            return {
                "news_sentiment_1h": news_sentiment_1h,
                "news_sentiment_24h": news_sentiment_24h,
                "news_volume_24h": news_volume_24h,
                "high_impact_news_count_24h": high_impact_news_count_24h,
            }

        except Exception as e:
            logger.warning(f"Error extracting news features: {e}", exc_info=True)
            return {
                "news_sentiment_1h": 0.0,
                "news_sentiment_24h": 0.0,
                "news_volume_24h": 0.0,
                "high_impact_news_count_24h": 0.0,
            }

    def extract_macro_features(
        self, symbol: str, current_time: datetime
    ) -> Dict[str, float]:
        """
        Extract macroeconomic indicator features for a symbol
        Point-in-time safe: only uses indicators published before current_time

        :param symbol: Currency pair symbol
        :param current_time: Current datetime (point-in-time constraint)
        :return: Dictionary of macro features
        """
        if self.database is None:
            return {
                "fed_funds_rate": 0.0,
                "unemployment_rate": 0.0,
                "cpi_yoy": 0.0,
                "gdp_growth_rate": 0.0,
                "interest_rate_differential": 0.0,
                "ecb_rate": 0.0,
                "world_bank_gdp_growth": 0.0,
            }

        try:
            from datetime import timedelta

            # Point-in-time constraint: only use indicators published before current_time
            # Apply latency buffer
            LATENCY_BUFFER_MINUTES = 5
            effective_time = current_time - timedelta(minutes=LATENCY_BUFFER_MINUTES)

            # Extract base and quote currencies
            base_currency = symbol[:3]
            quote_currency = symbol[3:]

            # Get latest indicators (point-in-time safe)
            def get_latest_indicator(series_id: str) -> Optional[float]:
                """Get latest indicator value before effective_time"""
                indicators = self.database.get_economic_indicators(
                    series_id=series_id,
                    start_time=None,
                    end_time=effective_time,
                )
                if indicators:
                    # Sort by timestamp descending and get most recent
                    indicators.sort(key=lambda x: x["timestamp"], reverse=True)
                    return indicators[0]["value"]
                return None

            # US indicators (FRED)
            fed_funds_rate = get_latest_indicator("FEDFUNDS") or 0.0
            unemployment_rate = get_latest_indicator("UNRATE") or 0.0
            cpi_yoy = get_latest_indicator("CPIAUCSL") or 0.0
            gdp_growth_rate = get_latest_indicator("GDP") or 0.0

            # ECB rate
            ecb_rate = get_latest_indicator("FM.M.U2.EUR.HSTA") or 0.0

            # World Bank GDP growth (for base currency country)
            # Map currency to country code
            country_map = {
                "USD": "USA",
                "EUR": "EUU",
                "GBP": "GBR",
                "JPY": "JPN",
                "AUD": "AUS",
                "CAD": "CAN",
                "CHF": "CHE",
                "NZD": "NZL",
            }
            base_country = country_map.get(base_currency, "USA")
            world_bank_series = f"NY.GDP.MKTP.KD.ZG_{base_country}"
            world_bank_gdp_growth = get_latest_indicator(world_bank_series) or 0.0

            # Interest rate differential
            # Get base currency interest rate (simplified - would need more mapping)
            base_rate = 0.0
            quote_rate = 0.0

            if base_currency == "USD":
                base_rate = fed_funds_rate
            elif base_currency == "EUR":
                base_rate = ecb_rate

            if quote_currency == "USD":
                quote_rate = fed_funds_rate
            elif quote_currency == "EUR":
                quote_rate = ecb_rate

            interest_rate_differential = base_rate - quote_rate

            return {
                "fed_funds_rate": float(fed_funds_rate),
                "unemployment_rate": float(unemployment_rate),
                "cpi_yoy": float(cpi_yoy),
                "gdp_growth_rate": float(gdp_growth_rate),
                "interest_rate_differential": float(interest_rate_differential),
                "ecb_rate": float(ecb_rate),
                "world_bank_gdp_growth": float(world_bank_gdp_growth),
            }

        except Exception as e:
            logger.warning(f"Error extracting macro features: {e}", exc_info=True)
            return {
                "fed_funds_rate": 0.0,
                "unemployment_rate": 0.0,
                "cpi_yoy": 0.0,
                "gdp_growth_rate": 0.0,
                "interest_rate_differential": 0.0,
                "ecb_rate": 0.0,
                "world_bank_gdp_growth": 0.0,
            }

    def extract_features_for_all_pairs(
        self,
        price_histories: Dict[str, List[float]],
        connectors,
        current_time: Optional[datetime] = None,
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
            pair_features = self.extract_features(
                price_history, symbol, current_time=current_time
            )
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

    def filter_features(self, feature_names: List[str]) -> None:
        """
        Filter feature engine to only use specified features.

        This method filters which technical indicators are computed and which features
        are included in the feature list. Features are expected to be named with
        symbol suffix (e.g., "rsi_14_EURUSD", "price_bid_EURUSD").

        :param feature_names: List of feature names to keep (e.g., ["rsi_14_EURUSD", "sma_20_GBPUSD"])
        """
        if not feature_names:
            return

        self.selected_features = feature_names

        # Extract base indicator names from selected features
        # Features are named as {indicator}_{symbol} or {field}_{symbol}
        # For technical indicators, we need to map back to base names
        # e.g., "rsi_14_EURUSD" -> "rsi", "sma_20_EURUSD" -> "sma_20"
        base_indicator_map = {
            "rsi": "rsi",
            "rsi_14": "rsi",
            "sma_20": "sma_20",
            "sma_50": "sma_50",
            "ema_12": "ema_12",
            "ema_26": "ema_26",
            "macd": "macd",
            "macd_signal": "macd_signal",
            "macd_histogram": "macd_histogram",
            "bb_upper": "bb_upper",
            "bb_middle": "bb_middle",
            "bb_lower": "bb_lower",
            "bb_width": "bb_width",
            "price_change": "price_change",
            "price_change_pct": "price_change_pct",
            "price": "price",
        }

        # Determine which indicators to compute
        selected_indicators = set()
        for feature_name in feature_names:
            # Try to match base indicator name
            # Feature names might be: "rsi_14_EURUSD", "rsi_EURUSD", or just "rsi"
            parts = feature_name.split("_")

            # Check if it starts with a known indicator
            for base_name, indicator_key in base_indicator_map.items():
                if (
                    feature_name.startswith(base_name + "_")
                    or feature_name == base_name
                ):
                    selected_indicators.add(indicator_key)
                    break
                # Also check for patterns like "rsi_14" -> "rsi"
                if len(parts) >= 2:
                    potential_base = "_".join(parts[:2])  # e.g., "rsi_14"
                    if potential_base in base_indicator_map:
                        selected_indicators.add(base_indicator_map[potential_base])
                        break
                    potential_base = parts[0]  # e.g., "rsi"
                    if potential_base in base_indicator_map:
                        selected_indicators.add(base_indicator_map[potential_base])
                        break

            # Always include price if any price-related feature is selected
            if "price" in feature_name.lower():
                selected_indicators.add("price")

        # If no indicators matched, keep all (backward compatibility)
        if not selected_indicators:
            logger.warning(
                f"Could not match any indicators from selected features: {feature_names}. "
                "Using all indicators."
            )
            self._filtered_indicators = None
        else:
            self._filtered_indicators = selected_indicators
            logger.info(
                f"Filtered to compute only indicators: {sorted(selected_indicators)}"
            )

        # Filter feature_list to only include selected base features
        # This is used for metadata/versioning
        if self.feature_list:
            # Keep features that match selected indicators
            # Use self._filtered_indicators which was just set above
            filtered_list = []
            for base_feature in self.feature_list:
                if (
                    self._filtered_indicators is None
                    or base_feature in self._filtered_indicators
                ):
                    filtered_list.append(base_feature)
            self.feature_list = filtered_list
