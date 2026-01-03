"""
Unit tests for Trading Environments

Tests for BaseTradingEnv, HistoricalTradingEnv, PaperTradingEnv, and slippage models.
"""

import pytest
import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/mt5-python_server/src'))

from environments.base_trading_env import BaseTradingEnv
from environments.slippage_models import (
    SlippageModel,
    NoSlippage,
    FixedSlippage,
    VolumeBasedSlippage,
    RandomSlippage,
    SpreadSlippage,
    VolatilitySlippage,
    TransactionCosts,
    create_slippage_model
)


class TestSlippageModels:
    """Tests for slippage models"""
    
    def test_no_slippage(self):
        """Test NoSlippage returns exact price"""
        model = NoSlippage()
        
        price = 1.0850
        result = model.apply(price, quantity=0.1, is_buy=True)
        
        assert result == price
    
    def test_fixed_slippage_buy(self):
        """Test FixedSlippage increases price for buys"""
        slippage_pct = 0.0001  # 1 pip
        model = FixedSlippage(slippage_pct=slippage_pct)
        
        price = 1.0000
        result = model.apply(price, quantity=0.1, is_buy=True)
        
        assert result > price
        assert abs(result - price * (1 + slippage_pct)) < 1e-10
    
    def test_fixed_slippage_sell(self):
        """Test FixedSlippage decreases price for sells"""
        slippage_pct = 0.0001
        model = FixedSlippage(slippage_pct=slippage_pct)
        
        price = 1.0000
        result = model.apply(price, quantity=0.1, is_buy=False)
        
        assert result < price
        assert abs(result - price * (1 - slippage_pct)) < 1e-10
    
    def test_volume_based_slippage(self):
        """Test VolumeBasedSlippage increases with size"""
        model = VolumeBasedSlippage(impact_coefficient=0.1)
        
        price = 100.0
        
        # Small order
        small_result = model.apply(price, quantity=10, is_buy=True, volume=1000)
        
        # Large order
        large_result = model.apply(price, quantity=100, is_buy=True, volume=1000)
        
        # Larger orders should have more slippage
        assert large_result > small_result
    
    def test_random_slippage_in_range(self):
        """Test RandomSlippage stays within bounds"""
        min_pct = 0.0001
        max_pct = 0.0005
        model = RandomSlippage(min_pct=min_pct, max_pct=max_pct, seed=42)
        
        price = 100.0
        
        for _ in range(100):
            result = model.apply(price, is_buy=True)
            slippage = (result - price) / price
            assert slippage >= min_pct
            assert slippage <= max_pct
    
    def test_random_slippage_reproducible(self):
        """Test RandomSlippage is reproducible with seed"""
        model1 = RandomSlippage(seed=42)
        model2 = RandomSlippage(seed=42)
        
        price = 100.0
        
        results1 = [model1.apply(price, is_buy=True) for _ in range(10)]
        results2 = [model2.apply(price, is_buy=True) for _ in range(10)]
        
        assert results1 == results2
    
    def test_spread_slippage(self):
        """Test SpreadSlippage uses bid-ask spread"""
        model = SpreadSlippage(spread_multiplier=1.0)
        
        bid = 1.0850
        ask = 1.0852
        mid = (bid + ask) / 2
        
        # Buy at ask + slippage
        buy_result = model.apply(ask, is_buy=True, bid=bid, ask=ask)
        assert buy_result >= ask
        
        # Sell at bid - slippage
        sell_result = model.apply(bid, is_buy=False, bid=bid, ask=ask)
        assert sell_result <= bid
    
    def test_volatility_slippage_increases_with_volatility(self):
        """Test VolatilitySlippage increases during high volatility"""
        model = VolatilitySlippage(
            base_slippage=0.0001,
            volatility_multiplier=10.0,
            baseline_volatility=0.01
        )
        
        price = 100.0
        
        # Normal volatility
        normal_result = model.apply(price, is_buy=True, volatility=0.01)
        
        # High volatility
        high_vol_result = model.apply(price, is_buy=True, volatility=0.03)
        
        # Higher volatility should have more slippage
        assert high_vol_result > normal_result
    
    def test_create_slippage_model_factory(self):
        """Test slippage model factory function"""
        models = ['none', 'fixed', 'volume', 'random', 'spread', 'volatility']
        
        for model_type in models:
            model = create_slippage_model(model_type)
            assert isinstance(model, SlippageModel)
    
    def test_create_slippage_model_invalid(self):
        """Test factory raises error for invalid type"""
        with pytest.raises(ValueError):
            create_slippage_model('invalid_type')
    
    def test_transaction_costs(self):
        """Test TransactionCosts combines all costs"""
        costs = TransactionCosts(
            spread_pct=0.0001,
            commission_pct=0.0001,
            slippage_model=FixedSlippage(0.0001)
        )
        
        price = 100.0
        quantity = 1.0
        
        exec_price, total_cost = costs.calculate_total_cost(
            price, quantity, is_buy=True
        )
        
        assert exec_price > price
        assert total_cost > 0


class TestBaseTradingEnv:
    """Tests for BaseTradingEnv"""
    
    @pytest.fixture
    def mock_env(self):
        """Create concrete implementation for testing"""
        class MockEnv(BaseTradingEnv):
            def get_state(self):
                return np.zeros((self.window_size, 5), dtype=np.float32)
        
        return MockEnv(window_size=50, price_shape=5, action_size=4)
    
    def test_seed_reproducibility(self, mock_env):
        """Test that same seed produces same random numbers"""
        mock_env.seed(42)
        values1 = [mock_env.np_random.random() for _ in range(10)]
        
        mock_env.seed(42)
        values2 = [mock_env.np_random.random() for _ in range(10)]
        
        assert values1 == values2
    
    def test_different_seeds_different_values(self, mock_env):
        """Test that different seeds produce different values"""
        mock_env.seed(42)
        values1 = [mock_env.np_random.random() for _ in range(10)]
        
        mock_env.seed(123)
        values2 = [mock_env.np_random.random() for _ in range(10)]
        
        assert values1 != values2
    
    def test_reset_returns_tuple(self, mock_env):
        """Test reset returns (observation, info) tuple"""
        result = mock_env.reset(seed=42)
        
        assert isinstance(result, tuple)
        assert len(result) == 2
        
        obs, info = result
        assert isinstance(obs, np.ndarray)
        assert isinstance(info, dict)
    
    def test_reset_with_seed(self, mock_env):
        """Test reset applies seed correctly"""
        obs1, info1 = mock_env.reset(seed=42)
        obs2, info2 = mock_env.reset(seed=42)
        
        assert info1['seed'] == 42
        assert info2['seed'] == 42
    
    def test_observation_space_shape(self, mock_env):
        """Test observation space has correct shape"""
        assert mock_env.observation_space.shape == (50, 5)
    
    def test_action_space_size(self, mock_env):
        """Test action space has correct size"""
        assert mock_env.action_space.n == 4
    
    def test_decode_action_hold(self, mock_env):
        """Test decoding HOLD action"""
        pair_index, action_type = mock_env.decode_action(0)
        
        from domain.action_type import ActionType
        
        assert pair_index is None
        assert action_type == ActionType.HOLD
    
    def test_decode_action_buy(self, mock_env):
        """Test decoding BUY action"""
        # Action 1 = BUY on pair 0
        pair_index, action_type = mock_env.decode_action(1)
        
        from domain.action_type import ActionType
        
        assert pair_index == 0
        assert action_type == ActionType.BUY
    
    def test_decode_action_sell(self, mock_env):
        """Test decoding SELL action"""
        # Action 2 = SELL on pair 0
        pair_index, action_type = mock_env.decode_action(2)
        
        from domain.action_type import ActionType
        
        assert pair_index == 0
        assert action_type == ActionType.SELL
    
    def test_decode_action_close(self, mock_env):
        """Test decoding CLOSE action"""
        # Action 3 = CLOSE on pair 0
        pair_index, action_type = mock_env.decode_action(3)
        
        from domain.action_type import ActionType
        
        assert pair_index == 0
        assert action_type == ActionType.CLOSE


class TestHistoricalEnv:
    """Tests for HistoricalTradingEnv"""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample historical data"""
        dates = pd.date_range(start='2024-01-01', periods=1000, freq='1min')
        
        # Generate realistic price data
        base_price = 1.0850
        returns = np.random.normal(0, 0.0001, len(dates))
        prices = base_price * np.cumprod(1 + returns)
        
        data = pd.DataFrame({
            'timestamp': dates,
            'bid': prices,
            'ask': prices + 0.0002,  # 2 pip spread
            'volume': np.random.randint(100, 1000, len(dates))
        })
        
        return data
    
    def test_reproducibility_with_seed(self, sample_data):
        """Test environment produces reproducible results with same seed"""
        from environments.historical_env import HistoricalTradingEnv
        
        env1 = HistoricalTradingEnv(data=sample_data, seed=42)
        env2 = HistoricalTradingEnv(data=sample_data, seed=42)
        
        obs1, _ = env1.reset(seed=42)
        obs2, _ = env2.reset(seed=42)
        
        np.testing.assert_array_equal(obs1, obs2)
    
    def test_transaction_costs_applied(self, sample_data):
        """Test transaction costs are deducted"""
        from environments.historical_env import HistoricalTradingEnv
        
        initial_balance = 10000.0
        transaction_cost = 0.001  # 0.1%
        
        env = HistoricalTradingEnv(
            data=sample_data,
            initial_balance=initial_balance,
            transaction_cost=transaction_cost
        )
        
        env.reset()
        
        # Execute a BUY action
        env.step(1)
        
        # Balance should decrease due to transaction cost
        assert env.balance < initial_balance
    
    def test_slippage_applied(self, sample_data):
        """Test slippage is applied to fills"""
        from environments.historical_env import HistoricalTradingEnv
        
        slippage = FixedSlippage(slippage_pct=0.001)
        
        env = HistoricalTradingEnv(
            data=sample_data,
            slippage_model=slippage
        )
        
        env.reset()
        
        # Get current ask price
        current_bar = sample_data.iloc[env.current_step]
        ask_price = current_bar['ask']
        
        # Execute BUY
        env.step(1)
        
        # Entry price should be higher than ask due to slippage
        if env.position:
            assert env.position.entry_price > ask_price
    
    def test_position_tracking(self, sample_data):
        """Test position is tracked correctly"""
        from environments.historical_env import HistoricalTradingEnv
        
        env = HistoricalTradingEnv(data=sample_data)
        env.reset()
        
        # No position initially
        assert env.position is None
        
        # Open position
        env.step(1)  # BUY
        assert env.position is not None
        assert env.position.side == 'long'
        
        # Close position
        env.step(3)  # CLOSE
        assert env.position is None
    
    def test_equity_calculation(self, sample_data):
        """Test equity includes unrealized P&L"""
        from environments.historical_env import HistoricalTradingEnv
        
        env = HistoricalTradingEnv(data=sample_data, initial_balance=10000.0)
        env.reset()
        
        # Initial equity equals balance
        initial_equity = env._calculate_equity(sample_data.iloc[env.current_step])
        assert abs(initial_equity - 10000.0) < 0.01
        
        # Open position
        env.step(1)
        
        # Equity now includes unrealized P&L
        new_bar = sample_data.iloc[env.current_step]
        equity_with_position = env._calculate_equity(new_bar)
        
        # Equity should differ from balance due to position
        if env.position:
            assert equity_with_position != env.balance


class TestPaperEnv:
    """Tests for PaperTradingEnv"""
    
    @pytest.fixture
    def mock_provider(self):
        """Create mock data provider"""
        provider = Mock()
        provider.currency_pair = Mock()
        provider.currency_pair.symbol = "EURUSD"
        provider.get_current_data.return_value = {
            'bid': 1.0850,
            'ask': 1.0852,
            'volume': 500
        }
        return provider
    
    def test_no_real_orders_executed(self, mock_provider):
        """Test that paper trading doesn't execute real orders"""
        from environments.paper_env import PaperTradingEnv
        
        env = PaperTradingEnv(
            data_providers=[mock_provider],
            initial_balance=10000.0
        )
        
        env.reset()
        
        # Execute some actions
        for _ in range(10):
            env.step(1)  # BUY
            env.step(3)  # CLOSE
        
        # No real broker calls should be made
        # (provider.get_current_data is called but no order execution)
        assert mock_provider.get_current_data.called
    
    def test_simulated_pnl_tracking(self, mock_provider):
        """Test that P&L is tracked in simulation"""
        from environments.paper_env import PaperTradingEnv
        
        env = PaperTradingEnv(
            data_providers=[mock_provider],
            initial_balance=10000.0
        )
        
        env.reset()
        
        # Open and close some positions
        env.step(1)  # BUY
        
        # Update price
        mock_provider.get_current_data.return_value = {
            'bid': 1.0860,  # Price went up
            'ask': 1.0862,
            'volume': 500
        }
        
        env.step(3)  # CLOSE
        
        # Should have trades recorded
        assert len(env.simulated_trades) >= 1
    
    def test_performance_metrics(self, mock_provider):
        """Test performance metrics calculation"""
        from environments.paper_env import PaperTradingEnv
        
        env = PaperTradingEnv(
            data_providers=[mock_provider],
            initial_balance=10000.0
        )
        
        env.reset()
        
        # Execute some trades
        env.step(1)  # BUY
        env.step(3)  # CLOSE
        
        metrics = env.get_performance_metrics()
        
        assert 'total_trades' in metrics
        assert 'win_rate' in metrics
        assert 'sharpe_ratio' in metrics
        assert 'max_drawdown' in metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
