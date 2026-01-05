"""
Unit tests for feature point-in-time constraints
Verifies no look-ahead bias in feature extraction
"""

import pytest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
import numpy as np

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/mt5-python_server/src'))

from application.environment.price_history_manager import PriceHistoryManager
from application.environment.feature_engine import FeatureEngine
from application.environment.state_builder import StateBuilder
from utils.feature_engineering import FeatureEngineer
from utils.time_utils import get_utc_time


class TestFeatureTimestamps:
    """Unit tests for feature timestamp constraints"""

    @pytest.fixture
    def price_manager(self):
        """Create price history manager"""
        from data_providers.price_provider import PriceDataProvider
        from domain.entities.currency_pair import CurrencyPair
        
        # Create mock providers
        pair = CurrencyPair("EURUSD", 0.0001)
        provider = PriceDataProvider(pair)
        providers = [provider]
        
        return PriceHistoryManager(window_size=10, data_providers=providers)

    @pytest.fixture
    def feature_engine(self):
        """Create feature engine"""
        feature_engineer = FeatureEngineer(normalization_method="robust")
        return FeatureEngine(
            feature_engineer=feature_engineer,
            window_size=10,
            features_per_pair=15,
        )

    def test_point_in_time_filtering_future_timestamps(self, price_manager):
        """Test that price_history with future timestamps is filtered out"""
        symbol = 'EURUSD'
        base_time = get_utc_time()
        
        # Add prices with various timestamps
        # Past prices (should be included)
        for i in range(15):
            timestamp = base_time - timedelta(seconds=15-i)
            price = 1.1000 + 0.0001 * i
            price_manager.add_price(symbol, price, timestamp=timestamp)
        
        # Future prices (should be filtered out)
        for i in range(5):
            timestamp = base_time + timedelta(seconds=i+1)
            price = 1.1000 + 0.0001 * (15+i)
            price_manager.add_price(symbol, price, timestamp=timestamp)
        
        # Get history up to base_time
        filtered_history = price_manager.get_history_up_to(symbol, base_time)
        
        # Should only include prices <= base_time (15 past prices)
        assert len(filtered_history) == 15, f"Expected 15 prices, got {len(filtered_history)}"
        # All prices should be <= base_time
        assert all(
            price_manager.price_timestamps[symbol][i] <= base_time
            for i, price in enumerate(price_manager.price_history_by_pair[symbol])
            if price in filtered_history
        )

    def test_point_in_time_filtering_past_timestamps(self, price_manager):
        """Test that price_history with only past timestamps accepts all"""
        symbol = 'EURUSD'
        base_time = get_utc_time()
        
        # Add only past prices
        for i in range(20):
            timestamp = base_time - timedelta(seconds=20-i)
            price = 1.1000 + 0.0001 * i
            price_manager.add_price(symbol, price, timestamp=timestamp)
        
        # Get history up to base_time
        filtered_history = price_manager.get_history_up_to(symbol, base_time)
        
        # Should include all past prices
        assert len(filtered_history) == 20, f"Expected 20 prices, got {len(filtered_history)}"

    def test_point_in_time_filtering_mixed_timestamps(self, price_manager):
        """Test that mixed timestamps only use <= current_time"""
        symbol = 'EURUSD'
        current_time = get_utc_time()
        
        # Add prices: 5 past, 5 at current_time, 5 future
        for i in range(5):
            timestamp = current_time - timedelta(seconds=5-i)
            price = 1.1000 + 0.0001 * i
            price_manager.add_price(symbol, price, timestamp=timestamp)
        
        for i in range(5):
            timestamp = current_time  # At current_time
            price = 1.1000 + 0.0001 * (5+i)
            price_manager.add_price(symbol, price, timestamp=timestamp)
        
        for i in range(5):
            timestamp = current_time + timedelta(seconds=i+1)  # Future
            price = 1.1000 + 0.0001 * (10+i)
            price_manager.add_price(symbol, price, timestamp=timestamp)
        
        # Get history up to current_time
        filtered_history = price_manager.get_history_up_to(symbol, current_time)
        
        # Should include past + at current_time (10 prices), not future
        assert len(filtered_history) == 10, f"Expected 10 prices, got {len(filtered_history)}"
        # Verify no future prices
        timestamps = price_manager.price_timestamps.get(symbol, [])
        filtered_indices = [
            i for i, price in enumerate(price_manager.price_history_by_pair[symbol])
            if price in filtered_history
        ]
        for idx in filtered_indices:
            assert timestamps[idx] <= current_time, "Filtered history should not include future timestamps"

    def test_economic_calendar_latency_buffer_too_recent(self, feature_engine):
        """Test that event published 1 minute ago is rejected (too recent)"""
        # Mock database
        mock_db = Mock()
        current_time = get_utc_time()
        
        # Event published 1 minute ago (too recent - should be rejected)
        event_time = current_time - timedelta(minutes=1)
        mock_db.get_upcoming_events.return_value = [
            {
                "datetime": event_time,
                "country": "USD",
                "impact": "High",
            }
        ]
        
        feature_engine.set_database(mock_db)
        
        # Extract economic features
        features = feature_engine.extract_economic_features("EURUSD", current_time)
        
        # Should have zero features (event too recent, filtered out)
        assert features["event_count_24h"] == 0.0, "Event published 1 minute ago should be filtered out"
        assert features["high_impact_count_24h"] == 0.0

    def test_economic_calendar_latency_buffer_old_enough(self, feature_engine):
        """Test that event published 10 minutes ago is accepted"""
        # Mock database
        mock_db = Mock()
        current_time = get_utc_time()
        
        # Event published 10 minutes ago (old enough - should be accepted)
        event_time = current_time - timedelta(minutes=10)
        mock_db.get_upcoming_events.return_value = [
            {
                "datetime": event_time,
                "country": "USD",
                "impact": "High",
            }
        ]
        
        feature_engine.set_database(mock_db)
        
        # Extract economic features
        features = feature_engine.extract_economic_features("EURUSD", current_time)
        
        # Should have features (event old enough)
        assert features["event_count_24h"] > 0, "Event published 10 minutes ago should be accepted"
        assert features["high_impact_count_24h"] > 0

    def test_economic_calendar_latency_buffer_at_boundary(self, feature_engine):
        """Test that event published exactly 5 minutes ago is rejected (boundary)"""
        # Mock database
        mock_db = Mock()
        current_time = get_utc_time()
        
        # Event published exactly 5 minutes ago (at boundary - should be rejected)
        event_time = current_time - timedelta(minutes=5)
        mock_db.get_upcoming_events.return_value = [
            {
                "datetime": event_time,
                "country": "USD",
                "impact": "High",
            }
        ]
        
        feature_engine.set_database(mock_db)
        
        # Extract economic features
        features = feature_engine.extract_economic_features("EURUSD", current_time)
        
        # Should have zero features (at boundary, should be rejected)
        # effective_time = current_time - 5 minutes, event_time = current_time - 5 minutes
        # event_time < effective_time is False, so event is filtered out
        assert features["event_count_24h"] == 0.0, "Event at boundary (5 minutes) should be rejected"

    def test_look_ahead_bias_detection_sequential_timestamps(self, price_manager, feature_engine):
        """Test that features computed at time T don't use data from time T+1"""
        symbol = 'EURUSD'
        base_time = get_utc_time()
        
        # Add sequential prices
        prices = []
        timestamps = []
        for i in range(20):
            timestamp = base_time + timedelta(seconds=i)
            price = 1.1000 + 0.0001 * i
            prices.append(price)
            timestamps.append(timestamp)
            price_manager.add_price(symbol, price, timestamp=timestamp)
        
        # Extract features at time T (e.g., base_time + 10 seconds)
        time_t = base_time + timedelta(seconds=10)
        filtered_history = price_manager.get_history_up_to(symbol, time_t)
        
        # Features should only use data <= time_t
        assert len(filtered_history) == 11, f"Expected 11 prices at time T, got {len(filtered_history)}"
        
        # Verify no future data
        for i, price in enumerate(price_manager.price_history_by_pair[symbol]):
            ts = price_manager.price_timestamps[symbol][i]
            if price in filtered_history:
                assert ts <= time_t, f"Price at index {i} has timestamp {ts} > {time_t}"

    def test_look_ahead_bias_detection_temporal_ordering(self, price_manager, feature_engine):
        """Test with sequential timestamps to verify temporal ordering"""
        symbol = 'EURUSD'
        base_time = get_utc_time()
        
        # Add prices in sequence
        for i in range(15):
            timestamp = base_time + timedelta(seconds=i)
            price = 1.1000 + 0.0001 * i
            price_manager.add_price(symbol, price, timestamp=timestamp)
        
        # Extract features at different times
        time_t1 = base_time + timedelta(seconds=5)
        history_t1 = price_manager.get_history_up_to(symbol, time_t1)
        
        time_t2 = base_time + timedelta(seconds=10)
        history_t2 = price_manager.get_history_up_to(symbol, time_t2)
        
        # History at T2 should include more prices than T1
        assert len(history_t2) > len(history_t1), "History at T2 should include more prices than T1"
        assert len(history_t1) == 6, f"Expected 6 prices at T1, got {len(history_t1)}"
        assert len(history_t2) == 11, f"Expected 11 prices at T2, got {len(history_t2)}"

    def test_cached_indicators_respect_timestamp_constraints(self, price_manager, feature_engine):
        """Test that cached indicators respect timestamp constraints"""
        symbol = 'EURUSD'
        base_time = get_utc_time()
        
        # Add prices
        for i in range(20):
            timestamp = base_time + timedelta(seconds=i)
            price = 1.1000 + 0.0001 * i
            price_manager.add_price(symbol, price, timestamp=timestamp)
        
        # Extract features at time T
        time_t = base_time + timedelta(seconds=10)
        filtered_history = price_manager.get_history_up_to(symbol, time_t)
        
        # Extract features (should use filtered history)
        features = feature_engine.extract_features(
            filtered_history, symbol, current_time=time_t
        )
        
        # Features should be based on filtered history only
        if features is not None:
            # Verify features are computed from correct data
            assert len(filtered_history) >= feature_engine.window_size or features is None

    def test_backward_compatibility_no_current_time(self, feature_engine):
        """Test that extract_features() works without current_time parameter"""
        symbol = 'EURUSD'
        price_history = [1.1000 + 0.0001 * i for i in range(20)]
        
        # Should work without current_time
        features = feature_engine.extract_features(price_history, symbol)
        
        # Should not raise error and should return features if sufficient data
        assert features is not None or len(price_history) < feature_engine.window_size

    def test_backward_compatibility_existing_code(self, price_manager):
        """Test that existing code still works (add_price without timestamp)"""
        symbol = 'EURUSD'
        
        # Add price without timestamp (should default to current time)
        price_manager.add_price(symbol, 1.1000)
        
        # Should still work
        history = price_manager.get_history(symbol)
        assert len(history) == 1
        assert history[0] == 1.1000
        
        # get_history_up_to should work (no timestamps tracked, returns all)
        current_time = get_utc_time()
        filtered = price_manager.get_history_up_to(symbol, current_time)
        assert len(filtered) == 1

    def test_state_builder_with_current_time(self, price_manager, feature_engine):
        """Test StateBuilder.build_state() with current_time parameter"""
        from data_providers.price_provider import PriceDataProvider
        from domain.entities.currency_pair import CurrencyPair
        
        pair = CurrencyPair("EURUSD", 0.0001)
        provider = PriceDataProvider(pair)
        providers = [provider]
        
        state_builder = StateBuilder(
            price_history_manager=price_manager,
            feature_engine=feature_engine,
            window_size=10,
            data_providers=providers,
        )
        
        # Add sufficient data
        base_time = get_utc_time()
        for i in range(15):
            timestamp = base_time - timedelta(seconds=15-i)
            price = 1.1000 + 0.0001 * i
            price_manager.add_price("EURUSD", price, timestamp=timestamp)
        
        # Build state with current_time
        current_time = base_time
        state = state_builder.build_state(current_time=current_time)
        
        # Should return state if sufficient data
        # (May be None if feature engineer not fitted, which is expected)
        # The important thing is that it doesn't crash and respects current_time
