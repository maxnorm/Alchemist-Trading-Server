"""
Feature engine
Extracts features from price history
"""
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from utils.technical_indicators import TechnicalIndicators
from utils.feature_engineering import FeatureEngineer


class FeatureEngine:
    """Extracts features from price history"""
    
    def __init__(
        self,
        feature_engineer: FeatureEngineer,
        window_size: int,
        features_per_pair: int
    ):
        """
        Initialize feature engine
        :param feature_engineer: Feature engineer instance
        :param window_size: Window size for features
        :param features_per_pair: Number of features per pair
        """
        self.feature_engineer = feature_engineer
        self.window_size = window_size
        self.features_per_pair = features_per_pair
        
        # Indicator cache for performance
        self.indicator_cache: Dict[str, Dict[str, np.ndarray]] = {}
        self.last_calculated_length: Dict[str, int] = {}
        
        # Economic calendar database (optional)
        self.database = None
    
    def extract_features(
        self,
        price_history: List[float],
        symbol: str
    ) -> Optional[np.ndarray]:
        """
        Extract features from price history for a single pair
        :param price_history: List of prices
        :param symbol: Currency pair symbol
        :return: Feature matrix or None if insufficient data
        """
        if len(price_history) < self.window_size:
            return None
        
        # Get recent window
        prices = np.array(price_history[-self.window_size:])
        
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
        pair_features = {
            'price': prices,
            **indicators
        }
        
        # Fit feature engineer if not fitted
        if not self.feature_engineer.is_fitted:
            try:
                clean_features = {k: np.nan_to_num(v) for k, v in indicators.items()}
                clean_features['price'] = prices
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
                    padding = np.zeros((self.window_size - pair_feature_matrix.shape[0], pair_feature_matrix.shape[1]))
                    pair_feature_matrix = np.vstack([padding, pair_feature_matrix])
                elif pair_feature_matrix.shape[0] > self.window_size:
                    # Take last window_size
                    pair_feature_matrix = pair_feature_matrix[-self.window_size:]
            
            return pair_feature_matrix
        
        return None
    
    def set_database(self, database):
        """
        Set database instance for economic calendar queries
        :param database: Database instance
        """
        self.database = database
    
    def extract_economic_features(self, symbol: str, current_time: datetime) -> Dict[str, float]:
        """
        Extract economic calendar features for a symbol
        :param symbol: Currency pair symbol
        :param current_time: Current datetime
        :return: Dictionary of economic features
        """
        if self.database is None:
            # Return zero features if no database
            return {
                'event_count_24h': 0.0,
                'high_impact_count_24h': 0.0,
                'medium_impact_count_24h': 0.0,
                'low_impact_count_24h': 0.0,
                'time_to_next_event': 24.0,  # Default to 24 hours if no events
                'next_event_impact': 0.0
            }
        
        try:
            # Get events for next 24 hours
            events = self.database.get_upcoming_events(hours_ahead=24)
            
            # Extract base currency from symbol (first 3 chars)
            base_currency = symbol[:3]
            
            # Filter events relevant to this currency pair
            relevant_events = [
                e for e in events 
                if e['country'] == base_currency or e['country'] in ['USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'NZD']
            ]
            
            # Calculate features
            event_count_24h = len(relevant_events)
            high_impact_count = sum(1 for e in relevant_events if e['impact'] == 'High')
            medium_impact_count = sum(1 for e in relevant_events if e['impact'] == 'Medium')
            low_impact_count = sum(1 for e in relevant_events if e['impact'] == 'Low')
            
            # Time to next event
            if relevant_events:
                next_event_time = relevant_events[0]['datetime']
                if isinstance(next_event_time, str):
                    next_event_time = datetime.fromisoformat(next_event_time.replace('Z', '+00:00'))
                time_to_next = (next_event_time - current_time).total_seconds() / 3600.0
                time_to_next = max(0.0, min(24.0, time_to_next))  # Clamp to 0-24 hours
                next_event_impact = 1.0 if relevant_events[0]['impact'] == 'High' else (0.5 if relevant_events[0]['impact'] == 'Medium' else 0.25)
            else:
                time_to_next = 24.0
                next_event_impact = 0.0
            
            return {
                'event_count_24h': float(event_count_24h),
                'high_impact_count_24h': float(high_impact_count),
                'medium_impact_count_24h': float(medium_impact_count),
                'low_impact_count_24h': float(low_impact_count),
                'time_to_next_event': time_to_next,
                'next_event_impact': next_event_impact
            }
        except Exception as e:
            # Return zero features on error
            return {
                'event_count_24h': 0.0,
                'high_impact_count_24h': 0.0,
                'medium_impact_count_24h': 0.0,
                'low_impact_count_24h': 0.0,
                'time_to_next_event': 24.0,
                'next_event_impact': 0.0
            }
    
    def extract_features_for_all_pairs(
        self,
        price_histories: Dict[str, List[float]],
        data_providers
    ) -> Optional[np.ndarray]:
        """
        Extract features for all pairs
        Optimized with pre-allocation and vectorized operations
        :param price_histories: Dictionary of symbol -> price history
        :param data_providers: List of data providers
        :return: Combined feature matrix or None if insufficient data
        """
        n_pairs = len(data_providers)
        if n_pairs == 0:
            return None
        
        # Pre-allocate list for better memory efficiency
        all_pair_features = []
        
        for provider in data_providers:
            symbol = provider.currency_pair.symbol
            
            # Get price history for this pair
            if symbol not in price_histories:
                return None
            
            price_history = price_histories[symbol]
            if len(price_history) < self.window_size:
                return None
            
            # Extract features for this pair
            pair_features = self.extract_features(price_history, symbol)
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
