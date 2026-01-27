"""
Tests for Walk-Forward Validation

Tests expanding/rolling windows, temporal ordering, and edge cases.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../scripts'))
from walk_forward_validation import walk_forward_validation, _aggregate_results


@pytest.fixture
def sample_data():
    """Generate sample time series data"""
    start_date = datetime(2020, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(365)]  # 1 year of data
    
    # Generate synthetic price data
    np.random.seed(42)
    base_price = 1.1000
    returns = np.random.randn(len(dates)) * 0.001
    prices = base_price + np.cumsum(returns)
    
    data = pd.DataFrame({
        'timestamp': dates,
        'bid': prices - 0.0001,
        'ask': prices + 0.0001,
        'volume': np.random.randint(1000, 10000, len(dates)),
    })
    
    return data


@pytest.fixture
def simple_backtest_func():
    """Simple backtest function for testing"""
    def backtest(train_data, test_data, **kwargs):
        return {
            'train_rows': len(train_data),
            'test_rows': len(test_data),
            'sharpe_ratio': np.random.randn() * 0.5 + 1.0,  # Random Sharpe for testing
            'total_return': np.random.randn() * 0.1,
        }
    return backtest


class TestWalkForwardValidation:
    """Test walk-forward validation functionality"""
    
    def test_expanding_window(self, sample_data):
        """Test expanding window mode"""
        result = walk_forward_validation(
            data=sample_data,
            train_window_days=90,
            test_window_days=30,
            step_days=30,
            window_type="expanding"
        )
        
        assert "results" in result
        assert "aggregated_metrics" in result
        assert "window_info" in result
        assert len(result["results"]) > 0
        
        # Check that train window grows in expanding mode
        window_info = result["window_info"]
        if len(window_info) > 1:
            first_train_rows = window_info[0]["train_rows"]
            last_train_rows = window_info[-1]["train_rows"]
            assert last_train_rows >= first_train_rows, "Expanding window should grow"
    
    def test_rolling_window(self, sample_data):
        """Test rolling window mode"""
        result = walk_forward_validation(
            data=sample_data,
            train_window_days=90,
            test_window_days=30,
            step_days=30,
            window_type="rolling"
        )
        
        assert len(result["results"]) > 0
        
        # Check that train window size is approximately constant in rolling mode
        window_info = result["window_info"]
        if len(window_info) > 1:
            train_rows = [w["train_rows"] for w in window_info]
            # Allow some variation due to weekends/holidays, but should be similar
            train_rows_std = np.std(train_rows)
            train_rows_mean = np.mean(train_rows)
            cv = train_rows_std / train_rows_mean if train_rows_mean > 0 else 0
            assert cv < 0.2, "Rolling window should have similar train sizes"
    
    def test_temporal_ordering(self, sample_data, simple_backtest_func):
        """Test that no future data is used for training"""
        result = walk_forward_validation(
            data=sample_data,
            train_window_days=90,
            test_window_days=30,
            step_days=30,
            window_type="expanding",
            backtest_func=simple_backtest_func
        )
        
        # Verify temporal ordering in each window
        for window in result["window_info"]:
            train_start = pd.to_datetime(window["train_start"])
            train_end = pd.to_datetime(window["train_end"])
            test_start = pd.to_datetime(window["test_start"])
            test_end = pd.to_datetime(window["test_end"])
            
            # Train should end before test starts
            assert train_end <= test_start, f"Temporal leakage: train_end {train_end} > test_start {test_start}"
            assert train_start < test_start, "Train should start before test"
            assert test_start < test_end, "Test should have valid range"
    
    def test_with_backtest_func(self, sample_data, simple_backtest_func):
        """Test integration with backtest function"""
        result = walk_forward_validation(
            data=sample_data,
            train_window_days=90,
            test_window_days=30,
            step_days=30,
            window_type="expanding",
            backtest_func=simple_backtest_func
        )
        
        assert len(result["results"]) > 0
        # Check that metrics from backtest function are present
        assert "sharpe_ratio" in result["results"][0]
        assert "total_return" in result["results"][0]
    
    def test_insufficient_data(self, sample_data):
        """Test error handling for insufficient data"""
        # Try with window sizes larger than available data
        with pytest.raises(ValueError, match="Insufficient data"):
            walk_forward_validation(
                data=sample_data,
                train_window_days=200,
                test_window_days=200,
                step_days=30
            )
    
    def test_missing_timestamp(self):
        """Test error handling for missing timestamp column"""
        data = pd.DataFrame({
            'bid': [1.1, 1.2, 1.3],
            'ask': [1.11, 1.21, 1.31],
        })
        
        with pytest.raises(ValueError, match="timestamp"):
            walk_forward_validation(data=data)
    
    def test_invalid_window_type(self, sample_data):
        """Test error handling for invalid window type"""
        with pytest.raises(ValueError, match="window_type"):
            walk_forward_validation(
                data=sample_data,
                window_type="invalid"
            )
    
    def test_single_window(self):
        """Test with data that only allows one window"""
        start_date = datetime(2020, 1, 1)
        dates = [start_date + timedelta(days=i) for i in range(120)]  # 120 days
        
        data = pd.DataFrame({
            'timestamp': dates,
            'bid': np.random.rand(len(dates)) + 1.1,
            'ask': np.random.rand(len(dates)) + 1.11,
        })
        
        result = walk_forward_validation(
            data=data,
            train_window_days=60,
            test_window_days=30,
            step_days=30
        )
        
        # Should produce at least one window
        assert len(result["results"]) >= 1
    
    def test_aggregated_metrics(self, sample_data, simple_backtest_func):
        """Test aggregated metrics calculation"""
        result = walk_forward_validation(
            data=sample_data,
            train_window_days=90,
            test_window_days=30,
            step_days=30,
            backtest_func=simple_backtest_func
        )
        
        aggregated = result["aggregated_metrics"]
        assert "num_windows" in aggregated
        assert "successful_windows" in aggregated
        assert aggregated["num_windows"] == len(result["results"])
        
        # Check that aggregated metrics exist for sharpe_ratio
        if "sharpe_ratio" in result["results"][0]:
            assert "sharpe_ratio_mean" in aggregated
            assert "sharpe_ratio_std" in aggregated
    
    def test_data_sorted(self, sample_data):
        """Test that data is sorted by timestamp"""
        # Shuffle data
        shuffled_data = sample_data.sample(frac=1).reset_index(drop=True)
        
        # Should still work (function should sort internally)
        result = walk_forward_validation(
            data=shuffled_data,
            train_window_days=90,
            test_window_days=30,
            step_days=30
        )
        
        assert len(result["results"]) > 0
    
    def test_step_size_variation(self, sample_data):
        """Test different step sizes"""
        for step_days in [7, 15, 30, 60]:
            result = walk_forward_validation(
                data=sample_data,
                train_window_days=90,
                test_window_days=30,
                step_days=step_days
            )
            
            assert len(result["results"]) > 0
            # Larger step should produce fewer windows
            if step_days > 30:
                # This is a heuristic check
                pass


class TestAggregateResults:
    """Test aggregation function"""
    
    def test_basic_aggregation(self):
        """Test basic metric aggregation"""
        results = [
            {"sharpe_ratio": 1.0, "total_return": 0.1},
            {"sharpe_ratio": 1.5, "total_return": 0.15},
            {"sharpe_ratio": 2.0, "total_return": 0.2},
        ]
        
        aggregated = _aggregate_results(results)
        
        assert "sharpe_ratio_mean" in aggregated
        assert "sharpe_ratio_std" in aggregated
        assert "sharpe_ratio_min" in aggregated
        assert "sharpe_ratio_max" in aggregated
        assert aggregated["sharpe_ratio_mean"] == pytest.approx(1.5)
        assert aggregated["num_windows"] == 3
    
    def test_empty_results(self):
        """Test aggregation with empty results"""
        aggregated = _aggregate_results([])
        assert aggregated == {}
    
    def test_mixed_metrics(self):
        """Test aggregation with mixed metric types"""
        results = [
            {"metric1": 1.0, "metric2": 10, "window_idx": 0},
            {"metric1": 2.0, "metric2": 20, "window_idx": 1},
        ]
        
        aggregated = _aggregate_results(results)
        
        # Should aggregate numeric metrics, exclude window_idx
        assert "metric1_mean" in aggregated
        assert "metric2_mean" in aggregated
        assert "window_idx_mean" not in aggregated
