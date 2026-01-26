"""
Unit tests for FeatureEngine feature filtering

Tests for filtering features in FeatureEngine based on selected feature names.
"""

import pytest
import os
import sys
import numpy as np
from unittest.mock import Mock, MagicMock, patch

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/trading_server/src'))

from application.environment.feature_engine import FeatureEngine
from utils.feature_engineering import FeatureEngineer


class TestFeatureEngineFiltering:
    """Tests for FeatureEngine feature filtering"""

    @pytest.fixture
    def feature_engine(self):
        """Create FeatureEngine instance"""
        feature_engineer = FeatureEngineer(normalization_method="robust")
        return FeatureEngine(
            feature_engineer=feature_engineer,
            window_size=50,
            features_per_pair=15,
            database=None,
            feature_registry=None,
            auto_register=False
        )

    def test_filter_features_basic(self, feature_engine):
        """Test basic feature filtering"""
        # Initialize feature list first
        feature_engine._initialize_versioning()
        original_list = feature_engine.feature_list.copy()

        # Filter to only RSI and SMA features
        selected_features = ["rsi_14_EURUSD", "sma_20_EURUSD"]
        feature_engine.filter_features(selected_features)

        assert feature_engine.selected_features == selected_features
        assert feature_engine._filtered_indicators is not None
        assert "rsi" in feature_engine._filtered_indicators
        assert "sma_20" in feature_engine._filtered_indicators

    def test_filter_features_empty_list(self, feature_engine):
        """Test that empty feature list doesn't filter"""
        feature_engine._initialize_versioning()
        original_list = feature_engine.feature_list.copy()

        feature_engine.filter_features([])

        assert feature_engine.selected_features == []
        assert feature_engine._filtered_indicators is None

    def test_filter_features_none(self, feature_engine):
        """Test that None doesn't filter"""
        feature_engine._initialize_versioning()
        original_list = feature_engine.feature_list.copy()

        # Should not raise error
        feature_engine.filter_features(None)

        assert feature_engine.selected_features is None

    def test_filter_features_unknown_indicators(self, feature_engine):
        """Test filtering with unknown indicator names"""
        feature_engine._initialize_versioning()

        # Use features that don't match known indicators
        selected_features = ["unknown_feature_EURUSD", "another_unknown_GBPUSD"]
        feature_engine.filter_features(selected_features)

        # Should log warning but not fail
        assert feature_engine.selected_features == selected_features
        # Should keep all indicators if none matched
        assert feature_engine._filtered_indicators is None

    def test_filter_features_mixed_known_unknown(self, feature_engine):
        """Test filtering with mix of known and unknown features"""
        feature_engine._initialize_versioning()

        selected_features = ["rsi_14_EURUSD", "unknown_feature_EURUSD"]
        feature_engine.filter_features(selected_features)

        assert feature_engine.selected_features == selected_features
        # Should filter to known indicators
        assert feature_engine._filtered_indicators is not None
        assert "rsi" in feature_engine._filtered_indicators

    def test_filter_features_price_included(self, feature_engine):
        """Test that price is included when price-related features are selected"""
        feature_engine._initialize_versioning()

        selected_features = ["price_bid_EURUSD", "rsi_14_EURUSD"]
        feature_engine.filter_features(selected_features)

        assert "price" in feature_engine._filtered_indicators

    def test_filter_features_multiple_symbols(self, feature_engine):
        """Test filtering with features from multiple symbols"""
        feature_engine._initialize_versioning()

        selected_features = ["rsi_14_EURUSD", "sma_20_GBPUSD", "macd_EURUSD"]
        feature_engine.filter_features(selected_features)

        assert feature_engine.selected_features == selected_features
        assert "rsi" in feature_engine._filtered_indicators
        assert "sma_20" in feature_engine._filtered_indicators
        assert "macd" in feature_engine._filtered_indicators

    def test_filter_features_feature_list_updated(self, feature_engine):
        """Test that feature_list is updated after filtering"""
        feature_engine._initialize_versioning()
        original_list = feature_engine.feature_list.copy()
        assert len(original_list) > 0

        selected_features = ["rsi_14_EURUSD", "sma_20_EURUSD"]
        feature_engine.filter_features(selected_features)

        # Feature list should be filtered
        assert len(feature_engine.feature_list) <= len(original_list)
        # Should only contain selected indicators
        for feature in feature_engine.feature_list:
            assert feature in feature_engine._filtered_indicators or feature_engine._filtered_indicators is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
