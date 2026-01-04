"""
State builder
Builds state vectors from price data
"""

import numpy as np
import logging
from typing import Optional, List

from data_providers.price_provider import PriceDataProvider
from application.environment.price_history_manager import PriceHistoryManager
from application.environment.feature_engine import FeatureEngine


class StateBuilder:
    """Builds state vectors from data"""

    def __init__(
        self,
        price_history_manager: PriceHistoryManager,
        feature_engine: FeatureEngine,
        window_size: int,
        data_providers: List[PriceDataProvider],
    ):
        """
        Initialize state builder
        :param price_history_manager: Price history manager
        :param feature_engine: Feature engine
        :param window_size: Window size for state
        :param data_providers: List of data providers
        """
        self.price_manager = price_history_manager
        self.feature_engine = feature_engine
        self.window_size = window_size
        self.data_providers = data_providers

    def build_state(self) -> Optional[np.ndarray]:
        """
        Build state vector from current data
        Optimized with pre-allocation and vectorized operations
        :return: State array or None if insufficient data
        """
        logger = logging.getLogger(__name__)
        max_staleness = 60  # seconds

        # Check data availability with staleness tolerance
        for provider in self.data_providers:
            symbol = provider.currency_pair.symbol

            if not self.price_manager.has_sufficient_data(symbol):
                return None  # Still need sufficient data

            staleness = self.price_manager.get_data_staleness(symbol)
            if staleness is not None and staleness > max_staleness:
                logger.warning(
                    f"Stale data for {symbol}: {staleness:.1f}s old (max: {max_staleness}s)"
                )
                # Continue with stale data but log warning

        # Get price histories
        price_histories = self.price_manager.get_all_histories()

        # Extract features for all pairs
        state = self.feature_engine.extract_features_for_all_pairs(
            price_histories, self.data_providers
        )

        if state is None:
            return None

        # Economic calendar features - DISABLED
        # TODO: Re-enable when new scraping methods are implemented
        # # Add economic calendar features
        # # Get economic features for the primary currency pair (first provider)
        # if self.data_providers:
        #     primary_symbol = self.data_providers[0].currency_pair.symbol
        #     current_time = datetime.utcnow()
        #     economic_features = self.feature_engine.extract_economic_features(primary_symbol, current_time)
        #
        #     # Convert to array and repeat across time window
        #     economic_array = np.array([
        #         economic_features['event_count_24h'],
        #         economic_features['high_impact_count_24h'],
        #         economic_features['medium_impact_count_24h'],
        #         economic_features['low_impact_count_24h'],
        #         economic_features['time_to_next_event'],
        #         economic_features['next_event_impact']
        #     ], dtype=np.float32)
        #
        #     # Repeat economic features across time window
        #     economic_features_matrix = np.tile(economic_array, (self.window_size, 1))
        #
        #     # Concatenate economic features to state
        #     state = np.hstack([state, economic_features_matrix])

        return state

    def _has_sufficient_data(self) -> bool:
        """
        Check if sufficient data for all pairs
        :return: True if sufficient data
        """
        if not self.data_providers:
            return False

        for provider in self.data_providers:
            symbol = provider.currency_pair.symbol
            if not self.price_manager.has_sufficient_data(symbol):
                return False

        return True

    def get_data_status(self) -> List[str]:
        """
        Get data status for all pairs
        :return: List of status strings
        """
        return self.price_manager.get_data_status()
