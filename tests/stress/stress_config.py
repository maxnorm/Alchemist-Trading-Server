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
