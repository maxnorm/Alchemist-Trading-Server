"""
State builder
Builds state vectors from price data
"""

import numpy as np
import logging
from typing import Optional, List, Dict
from datetime import datetime

from connectors.base import IDataSourceConnector
from application.environment.price_history_manager import PriceHistoryManager
from application.environment.feature_engine import FeatureEngine


class StateBuilder:
    """Builds state vectors from data"""

    def __init__(
        self,
        price_history_manager: PriceHistoryManager,
        feature_engine: FeatureEngine,
        window_size: int,
        connectors: List[IDataSourceConnector],
    ):
        """
        Initialize state builder
        :param price_history_manager: Price history manager
        :param feature_engine: Feature engine
        :param window_size: Window size for state
        :param connectors: List of data source connectors
        """
        self.price_manager = price_history_manager
        self.feature_engine = feature_engine
        self.window_size = window_size
        self.connectors = connectors

    def build_state(
        self, 
        current_time: Optional[datetime] = None,
        mode: str = 'training',
        include_latency: bool = True
    ) -> Optional[np.ndarray]:
        """
        Build state vector from current data with latency awareness and point-in-time constraint
        
        :param current_time: Current datetime for point-in-time constraint (defaults to now)
        :param mode: 'training' (point-in-time) or 'live' (real-time)
        :param include_latency: Include latency features in state
        :return: State array or None if insufficient data
        """
        if current_time is None:
            from utils.time_utils import get_utc_time
            current_time = get_utc_time()
        
        logger = logging.getLogger(__name__)
        max_staleness = 60  # seconds

        # Check data availability with staleness tolerance
        for connector in self.connectors:
            symbol = connector.config.symbol

            if not self.price_manager.has_sufficient_data(symbol):
                return None  # Still need sufficient data

            staleness = self.price_manager.get_data_staleness(symbol)
            if staleness is not None and staleness > max_staleness:
                logger.warning(
                    f"Stale data for {symbol}: {staleness:.1f}s old (max: {max_staleness}s)"
                )
                # Continue with stale data but log warning

        # Get price histories with point-in-time filtering
        # Use query_by='receive_time' for point-in-time training (what was available)
        query_by = 'receive_time' if mode == 'training' else 'receive_time'
        price_histories = {}
        for connector in self.connectors:
            symbol = connector.config.symbol
            # Use get_history_up_to() for point-in-time filtering
            filtered_history = self.price_manager.get_history_up_to(symbol, current_time, query_by=query_by)
            if len(filtered_history) >= self.window_size:
                # Extract prices from (event_time, price, receive_time) tuples for feature extraction
                # Features are extracted from event_time data (for patterns)
                price_list = [price for _, price, _ in filtered_history]
                price_histories[symbol] = price_list
            else:
                # Not enough filtered data
                return None

        # Extract features for all pairs (from event_time data for patterns)
        state = self.feature_engine.extract_features_for_all_pairs(
            price_histories, self.connectors, current_time=current_time
        )

        if state is None:
            return None

        # Add latency features if requested
        if include_latency:
            # Get full history with timestamps for latency calculation
            full_histories = {}
            for connector in self.connectors:
                symbol = connector.config.symbol
                full_histories[symbol] = self.price_manager.get_history_up_to(
                    symbol, current_time, query_by=query_by
                )
            
            latency_features = self._calculate_latency_features(full_histories, current_time)
            if latency_features is not None:
                state = np.hstack([state, latency_features])

        return state
    
    def _calculate_latency_features(
        self,
        price_histories: Dict[str, List[tuple[datetime, float, Optional[datetime]]]],
        current_time: datetime
    ) -> Optional[np.ndarray]:
        """
        Calculate latency features for each symbol
        
        Features per symbol:
        - avg_latency: Average latency (normalized 0-1, 300s = 1.0)
        - max_latency: Maximum latency (normalized 0-1)
        - latency_trend: Increasing/decreasing (-1 to 1)
        - data_freshness: How fresh is latest data (0-1, 0=fresh, 1=stale)
        
        :param price_histories: Dictionary of symbol -> list of (event_time, price, receive_time) tuples
        :param current_time: Current time for staleness calculation
        :return: Numpy array of latency features or None if insufficient data
        """
        latency_features = []
        
        for connector in self.connectors:
            symbol = connector.config.symbol
            history = price_histories.get(symbol, [])
            
            if not history:
                # No data - high latency
                latency_features.extend([1.0, 1.0, 0.0, 1.0])
                continue
            
            # Get latest tick with receive_time
            latest_tick = history[-1]
            event_time = latest_tick[0]
            receive_time = latest_tick[2] if len(latest_tick) > 2 else current_time
            
            # Calculate current latency
            if receive_time is not None:
                latency = (receive_time - event_time).total_seconds()
            else:
                latency = (current_time - event_time).total_seconds()
            
            # Calculate average/max from recent ticks
            recent_latencies = []
            for tick in history[-10:]:  # Last 10 ticks
                if len(tick) > 2:
                    tick_event_time = tick[0]
                    tick_receive_time = tick[2]
                    if tick_receive_time is not None:
                        tick_latency = (tick_receive_time - tick_event_time).total_seconds()
                        recent_latencies.append(tick_latency)
            
            avg_latency = np.mean(recent_latencies) if recent_latencies else latency
            max_latency = np.max(recent_latencies) if recent_latencies else latency
            
            # Normalize (0-1 scale, 300s = 1.0)
            avg_latency_norm = min(1.0, avg_latency / 300.0)
            max_latency_norm = min(1.0, max_latency / 300.0)
            
            # Latency trend
            if len(recent_latencies) >= 2:
                trend = 1.0 if recent_latencies[-1] > recent_latencies[0] else -1.0
            else:
                trend = 0.0
            
            # Data freshness (0 = fresh, 1 = stale)
            freshness = min(1.0, latency / 300.0)
            
            latency_features.extend([avg_latency_norm, max_latency_norm, trend, freshness])
        
        return np.array(latency_features, dtype=np.float32)

    def _has_sufficient_data(self) -> bool:
        """
        Check if sufficient data for all pairs
        :return: True if sufficient data
        """
        if not self.connectors:
            return False

        for connector in self.connectors:
            symbol = connector.config.symbol
            if not self.price_manager.has_sufficient_data(symbol):
                return False

        return True

    def get_data_status(self) -> List[str]:
        """
        Get data status for all pairs
        :return: List of status strings
        """
        return self.price_manager.get_data_status()
