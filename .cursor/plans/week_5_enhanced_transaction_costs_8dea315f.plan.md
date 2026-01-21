---
name: Week 5 Enhanced Transaction Costs
overview: Implement market impact modeling with volatility adjustment and market depth, enhance existing VolumeBasedSlippage, and create a stress testing framework for slippage models under adverse market conditions.
todos:
  - id: market_impact_class
    content: Create MarketImpactSlippage class with square-root model, volatility adjustment, and market depth in slippage_models.py
    status: pending
  - id: enhance_volume_slippage
    content: Enhance VolumeBasedSlippage.apply() to accept optional volatility parameter for backward-compatible volatility adjustment
    status: pending
  - id: update_factory
    content: Update create_slippage_model() factory function to support 'market_impact' type
    status: pending
    dependencies:
      - market_impact_class
  - id: unit_tests_market_impact
    content: Create tests/unit/test_market_impact.py with comprehensive tests for MarketImpactSlippage and enhanced VolumeBasedSlippage
    status: pending
    dependencies:
      - market_impact_class
      - enhance_volume_slippage
      - update_factory
  - id: stress_test_suite
    content: Create tests/stress/test_slippage_models.py with stress scenarios (widened spreads, high volatility, low liquidity)
    status: pending
    dependencies:
      - market_impact_class
  - id: stress_integration_test
    content: Add integration test simulating backtest performance degradation under stress conditions
    status: pending
    dependencies:
      - stress_test_suite
---

# Week 5: Enhanced Transaction Costs

## Overview

Week 5 focuses on improving transaction cost realism by implementing comprehensive market impact modeling and creating a stress testing framework. This addresses the P1 issue of incomplete transaction cost modeling identified in the audit.

## Task 5.1: Market Impact Modeling (Days 14-16)

### Current State Analysis

- `VolumeBasedSlippage` exists with square-root model (`impact = coefficient * sqrt(quantity/market_volume)`) but lacks volatility adjustment
- `VolatilitySlippage` exists as separate model but doesn't combine with volume-based impact
- No market depth consideration in existing models
- Environments use slippage via `slippage_model.apply(price, quantity, is_buy, **kwargs)` pattern

### Implementation Steps

#### Step 1: Create MarketImpactSlippage Class

**File:** `src/mt5-python_server/src/environments/slippage_models.py`

Add new class after `VolatilitySlippage` (around line 305):

```python
class MarketImpactSlippage(SlippageModel):
    """
    Comprehensive market impact model combining:
  - Square-root model for order size impact
  - Volatility adjustment factor
  - Market depth consideration
    
    Based on Almgren & Chriss (2000) square-root model with enhancements.
    
    Formula: impact = base_impact * sqrt(quantity/market_depth) * volatility_factor
    """
    
    def __init__(
        self,
        base_impact: float = 0.0001,  # 1 pip base impact
        market_depth: float = 1000.0,  # Default market depth
        volatility_multiplier: float = 1.0,
        baseline_volatility: float = 0.01,
        min_impact: float = 0.0,
        max_impact: float = 0.01,
    ):
        """
        Initialize market impact slippage model.
        
        Args:
            base_impact: Base impact coefficient (1 pip = 0.0001 for forex)
            market_depth: Typical market depth (liquidity available)
            volatility_multiplier: How much volatility affects impact
            baseline_volatility: Normal volatility level for scaling
            min_impact: Minimum impact floor
            max_impact: Maximum impact cap
        """
        self.base_impact = base_impact
        self.market_depth = market_depth
        self.volatility_multiplier = volatility_multiplier
        self.baseline_volatility = baseline_volatility
        self.min_impact = min_impact
        self.max_impact = max_impact
    
    def apply(
        self,
        price: float,
        quantity: float = 1.0,
        is_buy: bool = True,
        market_depth: Optional[float] = None,
        volatility: Optional[float] = None,
        **kwargs,
    ) -> float:
        """
        Apply market impact slippage.
        
        Args:
            market_depth: Current market depth (overrides default)
            volatility: Current volatility (for adjustment)
        """
        # Use provided market depth or default
        depth = market_depth if market_depth and market_depth > 0 else self.market_depth
        
        # Calculate size factor using square-root model
        participation_rate = min(quantity / depth, 1.0)  # Cap at 1.0
        size_factor = np.sqrt(participation_rate)
        
        # Volatility adjustment
        current_vol = volatility if volatility and volatility > 0 else self.baseline_volatility
        vol_ratio = current_vol / self.baseline_volatility
        vol_factor = 1.0 + self.volatility_multiplier * (vol_ratio - 1.0)
        vol_factor = max(0.1, vol_factor)  # Prevent negative or zero factors
        
        # Calculate total impact
        impact = self.base_impact * size_factor * vol_factor
        
        # Clamp to min/max bounds
        impact = max(self.min_impact, min(self.max_impact, impact))
        
        if is_buy:
            return price * (1 + impact)
        else:
            return price * (1 - impact)
    
    def get_description(self) -> str:
        return f"Market impact slippage (base={self.base_impact:.4%}, depth={self.market_depth})"
```

#### Step 2: Enhance VolumeBasedSlippage with Volatility Adjustment

**File:** `src/mt5-python_server/src/environments/slippage_models.py`

Modify `VolumeBasedSlippage.apply()` method (around line 125) to accept and use volatility:

```python
def apply(
    self,
    price: float,
    quantity: float = 1.0,
    is_buy: bool = True,
    volume: Optional[float] = None,
    volatility: Optional[float] = None,  # NEW: Add volatility parameter
    volatility_multiplier: float = 1.0,  # NEW: Volatility adjustment strength
    baseline_volatility: float = 0.01,   # NEW: Normal volatility level
    **kwargs,
) -> float:
    """
    Apply volume-based slippage with optional volatility adjustment.
    
    Args:
        volume: Market volume (required for accurate calculation)
        volatility: Current volatility (optional, for enhanced realism)
        volatility_multiplier: How much volatility affects slippage (default: no adjustment)
        baseline_volatility: Normal volatility level for scaling
    """
    # Default volume if not provided
    market_volume = volume if volume and volume > 0 else 1000.0

    # Calculate participation rate
    participation_rate = quantity / market_volume

    # Square-root market impact
    impact = self.impact_coefficient * np.sqrt(participation_rate)
    
    # NEW: Volatility adjustment (if volatility provided)
    if volatility and volatility > 0:
        vol_ratio = volatility / baseline_volatility
        vol_factor = 1.0 + volatility_multiplier * (vol_ratio - 1.0)
        vol_factor = max(0.1, vol_factor)  # Prevent negative factors
        impact = impact * vol_factor

    # Clamp to min/max
    impact = max(self.min_slippage, min(self.max_slippage, impact))

    if is_buy:
        return price * (1 + impact)
    else:
        return price * (1 - impact)
```

#### Step 3: Update Factory Function

**File:** `src/mt5-python_server/src/environments/slippage_models.py`

Add `MarketImpactSlippage` to factory function (around line 357):

```python
def create_slippage_model(model_type: str = "fixed", **kwargs) -> SlippageModel:
    """
    Factory function to create slippage models.
    
    Args:
        model_type: Type of model ("none", "fixed", "volume", "random", "spread", "volatility", "market_impact")
        **kwargs: Model-specific parameters
    
    Returns:
        SlippageModel instance
    """
    models = {
        "none": NoSlippage,
        "fixed": FixedSlippage,
        "volume": VolumeBasedSlippage,
        "random": RandomSlippage,
        "spread": SpreadSlippage,
        "volatility": VolatilitySlippage,
        "market_impact": MarketImpactSlippage,  # NEW
    }
    # ... rest of function
```

#### Step 4: Create Unit Tests for Market Impact

**File:** `tests/unit/test_market_impact.py` (NEW)

Create comprehensive tests:

```python
"""
Unit tests for Market Impact Slippage Models
"""
import pytest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/mt5-python_server/src'))

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
        model = VolumeBasedSlippage(impact_coefficient=0.1)
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
```

### Success Criteria for Task 5.1

- [ ] `MarketImpactSlippage` class implemented with square-root model, volatility adjustment, and market depth
- [ ] `VolumeBasedSlippage` enhanced to accept optional volatility parameter (backward compatible)
- [ ] Factory function updated to support "market_impact" type
- [ ] All unit tests pass
- [ ] Market impact scales correctly with order size (square root)
- [ ] Market impact increases with volatility
- [ ] Market impact increases with lower market depth

---

## Task 5.2: Stress Testing Framework (Days 16-17)

### Implementation Steps

#### Step 1: Create Stress Test Suite

**File:** `tests/stress/test_slippage_models.py` (NEW)

Create comprehensive stress test scenarios:

```python
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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/mt5-python_server/src'))

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
            base_impact=0.0001,
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
        # But should be noticeable (more than 0.1%)
        assert impact_pct > 0.001


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
        
        # But degradation should be realistic (not more than 3x)
        degradation_ratio = stress_total / normal_total
        assert degradation_ratio < 3.0
        assert degradation_ratio > 1.2  # At least 20% increase
```

#### Step 2: Create Stress Test Configuration

**File:** `tests/stress/stress_config.py` (NEW - optional helper)

```python
"""
Configuration for stress test scenarios
"""
from dataclasses import dataclass


@dataclass
class StressConfig:
    """Stress test market conditions"""
    spread_multiplier: float = 5.0  # 5x normal spread
    volatility_multiplier: float = 3.0  # 3x normal volatility
    liquidity_multiplier: float = 0.2  # 1/5th normal liquidity (5x lower)
    
    @classmethod
    def from_baseline(cls, baseline_spread: float, baseline_vol: float, baseline_depth: float):
        """Create stress config from baseline values"""
        return cls(
            spread_pct=baseline_spread * cls.spread_multiplier,
            volatility=baseline_vol * cls.volatility_multiplier,
            market_depth=baseline_depth * cls.liquidity_multiplier
        )
```

### Success Criteria for Task 5.2

- [ ] Stress test suite created with scenarios for:
                - Widened spreads (5x normal)
                - High volatility (3x normal)
                - Low liquidity (reduced market depth)
- [ ] Tests verify performance degradation is realistic (not catastrophic)
- [ ] Integration test simulates backtest performance under stress
- [ ] All stress tests pass
- [ ] Performance degradation ratio is between 1.2x and 3.0x under stress

---

## Testing Strategy

### Unit Tests

- Market impact scaling with order size (square root)
- Volatility adjustment correctness
- Market depth impact
- Bounds enforcement (min/max impact)
- Backward compatibility for enhanced VolumeBasedSlippage

### Stress Tests

- Individual stress factors (spread, volatility, liquidity)
- Combined stress scenarios
- Realistic performance degradation verification
- Integration with TransactionCosts

### Test Execution

```bash
# Run unit tests
pytest tests/unit/test_market_impact.py -v

# Run stress tests
pytest tests/stress/test_slippage_models.py -v

# Run all slippage-related tests
pytest tests/unit/test_market_impact.py tests/stress/test_slippage_models.py tests/unit/test_environments.py::TestSlippageModels -v
```

## Dependencies

- **Week 4 completed**: Observability baseline (for monitoring stress test metrics)
- **Existing code**: `slippage_models.py`, `test_environments.py`
- **No blocking dependencies**: Can proceed independently

## Files to Modify/Create

### Modify

- `src/mt5-python_server/src/environments/slippage_models.py`
                - Add `MarketImpactSlippage` class
                - Enhance `VolumeBasedSlippage.apply()` with volatility
                - Update `create_slippage_model()` factory

### Create

- `tests/unit/test_market_impact.py` - Unit tests for market impact
- `tests/stress/test_slippage_models.py` - Stress test suite
- `tests/stress/stress_config.py` - Optional stress test configuration helper

## Success Metrics

- Market impact scales with square root of order size
- Volatility adjustment increases impact during high volatility
- Market depth consideration reduces impact with higher liquidity
- Stress tests verify realistic (not catastrophic) performance degradation
- All tests pass with 100% coverage of new code

## References

- Almgren & Chriss (2000): Square-root market impact model
- Audit plan Section 3.2.3: Execution Realism recommendations
- Audit plan Section 6.4: Cost/Slippage Modeling implementation details