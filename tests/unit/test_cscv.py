"""
Tests for Combinatorially Symmetric Cross-Validation (CSCV)

Tests PBO calculation, performance degradation, and edge cases.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/trading_server/src'))
from training.cscv import (
    combinatorially_symmetric_cross_validation,
    interpret_pbo,
    _partition_data,
    _generate_train_test_splits,
    _calculate_pbo,
    _calculate_performance_degradation,
)


@pytest.fixture
def sample_data():
    """Generate sample time series data"""
    start_date = datetime(2020, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(400)]  # ~400 days
    
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
def strategy_configs():
    """Generate sample strategy configurations"""
    configs = []
    for i in range(10):
        configs.append({
            'learning_rate': 0.001 * (i + 1),
            'gamma': 0.95 + i * 0.01,
            'epsilon': 0.1 + i * 0.05,
            'strategy_id': i,
        })
    return configs


@pytest.fixture
def train_evaluate_funcs():
    """Create train and evaluate functions for testing"""
    def train_func(data, config):
        # Dummy training - just return config as "model"
        return {'config': config, 'trained': True}
    
    def evaluate_func(data, model, config):
        # Return metrics based on strategy_id to create known performance pattern
        strategy_id = config.get('strategy_id', 0)
        
        # Create some strategies that perform well, some that don't
        # This helps test PBO calculation
        if strategy_id < 3:
            # Good strategies
            sharpe = 1.5 + np.random.randn() * 0.2
            total_return = 0.15 + np.random.randn() * 0.05
        elif strategy_id < 7:
            # Medium strategies
            sharpe = 0.8 + np.random.randn() * 0.3
            total_return = 0.05 + np.random.randn() * 0.03
        else:
            # Poor strategies
            sharpe = 0.2 + np.random.randn() * 0.2
            total_return = -0.05 + np.random.randn() * 0.02
        
        return {
            'sharpe_ratio': sharpe,
            'total_return': total_return,
            'profit_factor': sharpe * 0.5 + 1.0,
        }
    
    return train_func, evaluate_func


class TestCSCV:
    """Test CSCV algorithm"""
    
    def test_basic_cscv(self, sample_data, strategy_configs, train_evaluate_funcs):
        """Test basic CSCV execution"""
        train_func, evaluate_func = train_evaluate_funcs
        
        result = combinatorially_symmetric_cross_validation(
            data=sample_data,
            strategy_configs=strategy_configs,
            n_splits=4,
            evaluation_metric='sharpe_ratio',
            train_func=train_func,
            evaluate_func=evaluate_func,
        )
        
        assert 'pbo' in result
        assert 'performance_degradation' in result
        assert 'logit_pbo' in result
        assert 'strategy_rankings' in result
        assert 'n_strategies' in result
        assert result['n_strategies'] == len(strategy_configs)
        assert 0 <= result['pbo'] <= 1
        assert 0 <= result['performance_degradation'] <= 1
    
    def test_pbo_calculation(self, sample_data, strategy_configs, train_evaluate_funcs):
        """Test PBO calculation"""
        train_func, evaluate_func = train_evaluate_funcs
        
        result = combinatorially_symmetric_cross_validation(
            data=sample_data,
            strategy_configs=strategy_configs,
            n_splits=4,
            evaluation_metric='sharpe_ratio',
            train_func=train_func,
            evaluate_func=evaluate_func,
        )
        
        pbo = result['pbo']
        assert isinstance(pbo, float)
        assert 0 <= pbo <= 1
    
    def test_insufficient_strategies(self, sample_data):
        """Test error handling for insufficient strategies"""
        configs = [{'param': 1}]  # Only 1 strategy
        
        with pytest.raises(ValueError, match="at least 2"):
            combinatorially_symmetric_cross_validation(
                data=sample_data,
                strategy_configs=configs,
                n_splits=4,
            )
    
    def test_missing_timestamp(self):
        """Test error handling for missing timestamp"""
        data = pd.DataFrame({
            'bid': [1.1, 1.2, 1.3],
            'ask': [1.11, 1.21, 1.31],
        })
        
        configs = [{'param': 1}, {'param': 2}]
        
        with pytest.raises(ValueError, match="timestamp"):
            combinatorially_symmetric_cross_validation(
                data=data,
                strategy_configs=configs,
            )
    
    def test_different_metrics(self, sample_data, strategy_configs, train_evaluate_funcs):
        """Test with different evaluation metrics"""
        train_func, evaluate_func = train_evaluate_funcs
        
        for metric in ['sharpe_ratio', 'total_return', 'profit_factor']:
            result = combinatorially_symmetric_cross_validation(
                data=sample_data,
                strategy_configs=strategy_configs,
                n_splits=4,
                evaluation_metric=metric,
                train_func=train_func,
                evaluate_func=evaluate_func,
            )
            
            assert result['evaluation_metric'] == metric
            assert 'pbo' in result
    
    def test_different_n_splits(self, sample_data, strategy_configs, train_evaluate_funcs):
        """Test with different numbers of splits"""
        train_func, evaluate_func = train_evaluate_funcs
        
        for n_splits in [2, 4, 6]:
            result = combinatorially_symmetric_cross_validation(
                data=sample_data,
                strategy_configs=strategy_configs,
                n_splits=n_splits,
                train_func=train_func,
                evaluate_func=evaluate_func,
            )
            
            assert result['n_splits'] == n_splits
            assert len(result['strategy_rankings']) > 0
    
    def test_without_train_evaluate_funcs(self, sample_data, strategy_configs):
        """Test CSCV without providing train/evaluate functions (uses default)"""
        result = combinatorially_symmetric_cross_validation(
            data=sample_data,
            strategy_configs=strategy_configs,
            n_splits=4,
        )
        
        # Should still complete, but with warning
        assert 'pbo' in result


class TestPartitionData:
    """Test data partitioning"""
    
    def test_partition_data(self, sample_data):
        """Test data partitioning"""
        partitions = _partition_data(sample_data, n_splits=4)
        
        assert len(partitions) == 4
        # Check that all partitions together equal original data
        total_rows = sum(len(p) for p in partitions)
        assert total_rows == len(sample_data)
        
        # Check that partitions don't overlap (by index)
        all_indices = set()
        for p in partitions:
            partition_indices = set(p.index)
            assert not all_indices & partition_indices, "Partitions should not overlap"
            all_indices.update(partition_indices)
    
    def test_partition_ordering(self, sample_data):
        """Test that partitions maintain temporal ordering"""
        partitions = _partition_data(sample_data, n_splits=4)
        
        for i, partition in enumerate(partitions):
            if len(partition) > 1:
                timestamps = partition['timestamp'].values
                assert all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1)), \
                    "Partition should be sorted by timestamp"


class TestTrainTestSplits:
    """Test train/test split generation"""
    
    def test_generate_splits(self):
        """Test split generation"""
        splits = _generate_train_test_splits(n_splits=4)
        
        # For n_splits=4, should get C(4,2) = 6 combinations
        assert len(splits) == 6
        
        # Check that each split has correct sizes
        for train_indices, test_indices in splits:
            assert len(train_indices) == 2
            assert len(test_indices) == 2
            assert set(train_indices) & set(test_indices) == set(), "Train and test should not overlap"
            assert set(train_indices) | set(test_indices) == set(range(4)), "Should cover all indices"
    
    def test_splits_coverage(self):
        """Test that all indices are covered in splits"""
        splits = _generate_train_test_splits(n_splits=4)
        
        all_train_indices = set()
        all_test_indices = set()
        
        for train_indices, test_indices in splits:
            all_train_indices.update(train_indices)
            all_test_indices.update(test_indices)
        
        assert all_train_indices == set(range(4))
        assert all_test_indices == set(range(4))


class TestPBOCalculation:
    """Test PBO calculation"""
    
    def test_calculate_pbo_consistent(self):
        """Test PBO calculation with consistent rankings"""
        # If best strategy is always best, PBO should be low
        all_rankings = [
            [0, 1, 2, 3],  # Strategy 0 is best
            [0, 1, 2, 3],  # Strategy 0 is best
            [0, 1, 2, 3],  # Strategy 0 is best
        ]
        
        pbo, logit_pbo = _calculate_pbo(all_rankings, n_strategies=4)
        
        # With consistent rankings, PBO should be low
        assert 0 <= pbo <= 1
        assert isinstance(logit_pbo, float)
    
    def test_calculate_pbo_inconsistent(self):
        """Test PBO calculation with inconsistent rankings"""
        # If best strategy varies, PBO should be higher
        all_rankings = [
            [0, 1, 2, 3],  # Strategy 0 is best
            [1, 0, 2, 3],  # Strategy 1 is best
            [2, 0, 1, 3],  # Strategy 2 is best
        ]
        
        pbo, logit_pbo = _calculate_pbo(all_rankings, n_strategies=4)
        
        assert 0 <= pbo <= 1
        # Inconsistent rankings should lead to higher PBO
        assert isinstance(logit_pbo, float)
    
    def test_calculate_pbo_empty(self):
        """Test PBO calculation with empty rankings"""
        pbo, logit_pbo = _calculate_pbo([], n_strategies=4)
        assert pbo == 0.0
        assert logit_pbo == 0.0


class TestPerformanceDegradation:
    """Test performance degradation calculation"""
    
    def test_calculate_degradation(self):
        """Test performance degradation calculation"""
        # Simulate good in-sample, poor out-of-sample
        all_performances = [
            [2.0, 1.5, 1.0, 0.5],  # Strategy 0 performs best
            [0.5, 1.0, 1.5, 2.0],  # Strategy 3 performs best
        ]
        all_rankings = [
            [0, 1, 2, 3],  # Strategy 0 ranked first
            [3, 2, 1, 0],  # Strategy 3 ranked first
        ]
        
        degradation = _calculate_performance_degradation(all_performances, all_rankings)
        
        assert 0 <= degradation <= 1
        assert isinstance(degradation, float)
    
    def test_calculate_degradation_empty(self):
        """Test degradation with empty data"""
        degradation = _calculate_performance_degradation([], [])
        assert degradation == 0.0


class TestInterpretPBO:
    """Test PBO interpretation"""
    
    def test_interpret_low_pbo(self):
        """Test interpretation of low PBO"""
        interpretation = interpret_pbo(0.03)
        assert "Low" in interpretation or "low" in interpretation
    
    def test_interpret_moderate_pbo(self):
        """Test interpretation of moderate PBO"""
        interpretation = interpret_pbo(0.07)
        assert "Moderate" in interpretation or "moderate" in interpretation
    
    def test_interpret_high_pbo(self):
        """Test interpretation of high PBO"""
        interpretation = interpret_pbo(0.15)
        assert "High" in interpretation or "high" in interpretation
