"""
Stress tests for slippage models under adverse market conditions.

Tests performance degradation under:
- Widened spreads (5x normal)
- High volatility (3x normal)
- Low liquidity (reduced market depth)
"""
import pytest
import numpy as np
import pandas as pd
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/trading_server/src'))

from environments.slippage_models import (
    MarketImpactSlippage,
    VolumeBasedSlippage,
    VolatilitySlippage,
    SpreadSlippage,
    TransactionCosts,
    create_slippage_model
)


class TestSlippageStressScenarios:
    """Stress tests for slippage models"""
    
    @pytest.fixture
    def baseline_config(self):
        """Baseline normal market conditions"""
        return {
            'spread_pct': 0.0001,  # 1 pip
            'volatility': 0.01,     # 1% daily volatility
            'market_depth': 1000.0, # Normal liquidity
            'price': 1.0850
        }
    
    @pytest.fixture
    def stress_config(self):
        """Stress market conditions"""
        return {
            'spread_pct': 0.0005,   # 5x normal (5 pips)
            'volatility': 0.03,      # 3x normal (3% daily volatility)
            'market_depth': 200.0,   # 5x lower liquidity
            'price': 1.0850
        }
    
    def test_market_impact_stress_widened_spread(self, baseline_config, stress_config):
        """Test market impact with 5x widened spread"""
        model = MarketImpactSlippage(base_impact=0.0001, market_depth=baseline_config['market_depth'])
        
        # Baseline execution
        baseline_price = model.apply(
            baseline_config['price'],
            quantity=50,
            is_buy=True,
            volatility=baseline_config['volatility']
        )
        
        # Stress execution (same model, but market conditions changed)
        # Note: Spread affects base price, not slippage model directly
        # This test verifies model still works under stress
        stress_price = model.apply(
            stress_config['price'],
            quantity=50,
            is_buy=True,
            volatility=stress_config['volatility'],
            market_depth=stress_config['market_depth']
        )
        
        # Impact should be higher under stress (lower depth, higher vol)
        baseline_impact = abs(baseline_price - baseline_config['price']) / baseline_config['price']
        stress_impact = abs(stress_price - stress_config['price']) / stress_config['price']
        
        assert stress_impact > baseline_impact
    
    def test_market_impact_stress_high_volatility(self, baseline_config, stress_config):
        """Test market impact with 3x volatility"""
        model = MarketImpactSlippage(
            base_impact=0.0001,
            volatility_multiplier=1.0,
            baseline_volatility=baseline_config['volatility']
        )
        
        baseline_price = model.apply(
            baseline_config['price'],
            quantity=50,
            is_buy=True,
            volatility=baseline_config['volatility']
        )
        
        high_vol_price = model.apply(
            baseline_config['price'],
            quantity=50,
            is_buy=True,
            volatility=stress_config['volatility']
        )
        
        # Higher volatility should increase impact
        assert high_vol_price > baseline_price
    
    def test_market_impact_stress_low_liquidity(self, baseline_config, stress_config):
        """Test market impact with reduced market depth"""
        model = MarketImpactSlippage(base_impact=0.0001)
        
        baseline_price = model.apply(
            baseline_config['price'],
            quantity=50,
            is_buy=True,
            market_depth=baseline_config['market_depth']
        )
        
        low_liquidity_price = model.apply(
            baseline_config['price'],
            quantity=50,
            is_buy=True,
            market_depth=stress_config['market_depth']
        )
        
        # Lower liquidity should increase impact
        assert low_liquidity_price > baseline_price
    
    def test_combined_stress_scenario(self, baseline_config, stress_config):
        """Test all stress factors combined"""
        model = MarketImpactSlippage(
            base_impact=0.0001,
            volatility_multiplier=1.0,
            baseline_volatility=baseline_config['volatility']
        )
        
        baseline_price = model.apply(
            baseline_config['price'],
            quantity=50,
            is_buy=True,
            volatility=baseline_config['volatility'],
            market_depth=baseline_config['market_depth']
        )
        
        # Combined stress: high vol + low liquidity
        stress_price = model.apply(
            baseline_config['price'],
            quantity=50,
            is_buy=True,
            volatility=stress_config['volatility'],
            market_depth=stress_config['market_depth']
        )
        
        baseline_impact = abs(baseline_price - baseline_config['price']) / baseline_config['price']
        stress_impact = abs(stress_price - baseline_config['price']) / baseline_config['price']
        
        # Combined stress should have significantly higher impact
        assert stress_impact > baseline_impact * 1.5  # At least 50% more impact
    
    def test_performance_degradation_realistic(self, baseline_config, stress_config):
        """
        Test that performance degradation is realistic, not catastrophic.
        
        Under stress, costs should increase but not make trading impossible.
        """
        model = MarketImpactSlippage(
            base_impact=0.0005,  # Increased to get more noticeable impact
            max_impact=0.01,  # 1% max impact cap
            volatility_multiplier=1.0,
            baseline_volatility=baseline_config['volatility']
        )
        
        # Large order under stress
        stress_price = model.apply(
            baseline_config['price'],
            quantity=200,  # Large order
            is_buy=True,
            volatility=stress_config['volatility'],
            market_depth=stress_config['market_depth']
        )
        
        impact_pct = abs(stress_price - baseline_config['price']) / baseline_config['price']
        
        # Impact should be significant but not catastrophic
        # Should be less than 1% (max_impact cap)
        assert impact_pct < 0.01
        # But should be noticeable (more than 0.05%)
        assert impact_pct > 0.0005


class TestTransactionCostsStress:
    """Stress tests for TransactionCosts with slippage models"""
    
    def test_transaction_costs_stress_scenario(self):
        """Test TransactionCosts with stress market conditions"""
        slippage = MarketImpactSlippage(
            base_impact=0.0001,
            volatility_multiplier=1.0,
            baseline_volatility=0.01
        )
        
        costs = TransactionCosts(
            spread_pct=0.0005,  # 5x normal spread
            commission_pct=0.0001,
            slippage_model=slippage
        )
        
        price = 1.0850
        quantity = 50
        
        # Normal conditions
        normal_exec, normal_cost = costs.calculate_total_cost(
            price, quantity, is_buy=True,
            volatility=0.01,
            market_depth=1000.0
        )
        
        # Stress conditions
        stress_exec, stress_cost = costs.calculate_total_cost(
            price, quantity, is_buy=True,
            volatility=0.03,  # 3x volatility
            market_depth=200.0  # 5x lower liquidity
        )
        
        # Stress should have higher costs
        assert stress_cost > normal_cost
        
        # But costs should be realistic (not more than 2% of trade value)
        trade_value = price * quantity
        assert stress_cost / trade_value < 0.02


class TestBacktestStressIntegration:
    """Integration tests simulating backtest performance under stress"""
    
    def test_backtest_performance_degradation(self):
        """
        Simulate how backtest performance degrades under stress.
        
        This test verifies that stress conditions produce realistic
        (not catastrophic) performance degradation.
        """
        # Simulate a series of trades
        model = MarketImpactSlippage(
            base_impact=0.0001,
            volatility_multiplier=1.0,
            baseline_volatility=0.01
        )
        
        prices = [1.0850 + i * 0.0001 for i in range(100)]  # Price series
        quantities = [50] * 100  # Same size trades
        
        # Normal conditions
        normal_costs = []
        for price in prices:
            exec_price = model.apply(
                price, quantity=50, is_buy=True,
                volatility=0.01, market_depth=1000.0
            )
            cost = abs(exec_price - price) * 50
            normal_costs.append(cost)
        
        # Stress conditions
        stress_costs = []
        for price in prices:
            exec_price = model.apply(
                price, quantity=50, is_buy=True,
                volatility=0.03, market_depth=200.0
            )
            cost = abs(exec_price - price) * 50
            stress_costs.append(cost)
        
        normal_total = sum(normal_costs)
        stress_total = sum(stress_costs)
        
        # Stress should increase costs
        assert stress_total > normal_total
        
        # But degradation should be realistic
        # Under severe stress (3x vol + 5x lower liquidity), 5-10x degradation is realistic
        degradation_ratio = stress_total / normal_total
        assert degradation_ratio < 10.0  # Allow for realistic stress scenarios
        assert degradation_ratio > 1.2  # At least 20% increase
