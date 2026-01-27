"""
Unit tests for Market Impact Slippage Models
"""
import pytest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/backend/trading_server/src'))

from environments.slippage_models import (
    MarketImpactSlippage,
    VolumeBasedSlippage,
    create_slippage_model
)


class TestMarketImpactSlippage:
    """Tests for MarketImpactSlippage class"""
    
    def test_market_impact_increases_with_order_size(self):
        """Test that larger orders have more impact"""
        model = MarketImpactSlippage(base_impact=0.0001, market_depth=1000.0)
        price = 100.0
        
        small_order = model.apply(price, quantity=10, is_buy=True, market_depth=1000)
        large_order = model.apply(price, quantity=100, is_buy=True, market_depth=1000)
        
        assert large_order > small_order
    
    def test_market_impact_increases_with_volatility(self):
        """Test that higher volatility increases impact"""
        model = MarketImpactSlippage(
            base_impact=0.0001,
            volatility_multiplier=1.0,
            baseline_volatility=0.01
        )
        price = 100.0
        
        normal_vol = model.apply(price, quantity=50, is_buy=True, volatility=0.01)
        high_vol = model.apply(price, quantity=50, is_buy=True, volatility=0.03)
        
        assert high_vol > normal_vol
    
    def test_market_impact_respects_market_depth(self):
        """Test that lower market depth increases impact"""
        model = MarketImpactSlippage(base_impact=0.0001)
        price = 100.0
        quantity = 50
        
        high_depth = model.apply(price, quantity=quantity, is_buy=True, market_depth=10000)
        low_depth = model.apply(price, quantity=quantity, is_buy=True, market_depth=100)
        
        assert low_depth > high_depth
    
    def test_market_impact_buy_vs_sell(self):
        """Test that buys increase price, sells decrease price"""
        model = MarketImpactSlippage(base_impact=0.0001)
        price = 100.0
        
        buy_price = model.apply(price, quantity=50, is_buy=True)
        sell_price = model.apply(price, quantity=50, is_buy=False)
        
        assert buy_price > price
        assert sell_price < price
    
    def test_market_impact_respects_bounds(self):
        """Test that impact is clamped to min/max"""
        model = MarketImpactSlippage(
            base_impact=0.0001,
            min_impact=0.0,
            max_impact=0.001  # 0.1% cap
        )
        price = 100.0
        
        # Very large order should be capped
        result = model.apply(price, quantity=100000, is_buy=True, market_depth=1)
        impact = abs(result - price) / price
        
        assert impact <= 0.001
    
    def test_market_impact_square_root_scaling(self):
        """Test that impact scales with square root of participation"""
        model = MarketImpactSlippage(base_impact=0.0001, market_depth=1000.0)
        price = 100.0
        
        # Order size 10: participation = 0.01, sqrt = 0.1
        impact_10 = model.apply(price, quantity=10, is_buy=True) - price
        
        # Order size 100: participation = 0.1, sqrt = 0.316
        impact_100 = model.apply(price, quantity=100, is_buy=True) - price
        
        # Impact should increase but not linearly (square root)
        assert impact_100 > impact_10
        # Verify it's roughly square root relationship (impact_100 / impact_10 ≈ sqrt(10))
        ratio = impact_100 / impact_10
        assert 2.0 < ratio < 4.0  # sqrt(10) ≈ 3.16


class TestVolumeBasedSlippageEnhancement:
    """Tests for enhanced VolumeBasedSlippage with volatility"""
    
    def test_volume_slippage_with_volatility(self):
        """Test that VolumeBasedSlippage can use volatility adjustment"""
        # Use smaller impact_coefficient and higher max_slippage to avoid clamping
        model = VolumeBasedSlippage(impact_coefficient=0.01, max_slippage=0.1)
        price = 100.0
        
        normal = model.apply(price, quantity=50, is_buy=True, volume=1000, volatility=0.01, volatility_multiplier=1.0, baseline_volatility=0.01)
        high_vol = model.apply(price, quantity=50, is_buy=True, volume=1000, volatility=0.03, volatility_multiplier=1.0, baseline_volatility=0.01)
        
        assert high_vol > normal
    
    def test_volume_slippage_backward_compatible(self):
        """Test that VolumeBasedSlippage works without volatility (backward compatibility)"""
        model = VolumeBasedSlippage(impact_coefficient=0.1)
        price = 100.0
        
        # Should work without volatility parameter
        result = model.apply(price, quantity=50, is_buy=True, volume=1000)
        assert result > price


class TestFactoryFunction:
    """Tests for factory function with market_impact type"""
    
    def test_create_market_impact_model(self):
        """Test factory can create MarketImpactSlippage"""
        model = create_slippage_model("market_impact", base_impact=0.0001)
        assert isinstance(model, MarketImpactSlippage)
    
    def test_factory_with_kwargs(self):
        """Test factory passes kwargs to MarketImpactSlippage"""
        model = create_slippage_model(
            "market_impact",
            base_impact=0.0002,
            market_depth=2000.0
        )
        assert model.base_impact == 0.0002
        assert model.market_depth == 2000.0
