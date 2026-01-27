"""
Slippage Models for Realistic Backtesting

Provides various models to simulate market impact and slippage
for more realistic backtesting.

Models:
- NoSlippage: No price impact (ideal execution)
- FixedSlippage: Fixed percentage slippage
- VolumeBasedSlippage: Slippage based on order size vs market volume
- RandomSlippage: Random slippage for robustness testing
- SpreadSlippage: Slippage based on bid-ask spread
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import numpy as np


class SlippageModel(ABC):
    """Abstract base class for slippage models"""

    @abstractmethod
    def apply(
        self, price: float, quantity: float = 1.0, is_buy: bool = True, **kwargs
    ) -> float:
        """
        Apply slippage to a price.

        Args:
            price: Base price (bid or ask depending on side)
            quantity: Order quantity
            is_buy: True for buy orders, False for sell orders
            **kwargs: Additional parameters (e.g., volume, volatility)

        Returns:
            Adjusted price after slippage
        """
        pass

    def get_description(self) -> str:
        """Get human-readable description of the model"""
        return self.__class__.__name__


class NoSlippage(SlippageModel):
    """
    No slippage model - ideal execution at quoted price.

    Useful for baseline comparisons or when slippage is negligible.
    """

    def apply(
        self, price: float, quantity: float = 1.0, is_buy: bool = True, **kwargs
    ) -> float:
        return price

    def get_description(self) -> str:
        return "No slippage - ideal execution"


class FixedSlippage(SlippageModel):
    """
    Fixed percentage slippage model.

    Applies a constant percentage slippage to all orders.
    Simple but may not reflect real market conditions.
    """

    def __init__(self, slippage_pct: float = 0.0001):
        """
        Initialize fixed slippage model.

        Args:
            slippage_pct: Slippage as a decimal (0.0001 = 1 pip for forex)
        """
        self.slippage_pct = slippage_pct

    def apply(
        self, price: float, quantity: float = 1.0, is_buy: bool = True, **kwargs
    ) -> float:
        """
        Apply fixed slippage.

        Buys execute at higher prices, sells at lower prices.
        """
        if is_buy:
            return price * (1 + self.slippage_pct)
        else:
            return price * (1 - self.slippage_pct)

    def get_description(self) -> str:
        return f"Fixed slippage: {self.slippage_pct:.4%}"


class VolumeBasedSlippage(SlippageModel):
    """
    Volume-based slippage model.

    Slippage increases with order size relative to market volume.
    Uses a square-root market impact model commonly used in finance.

    Formula: slippage = impact_coefficient * sqrt(order_size / market_volume)
    """

    def __init__(
        self,
        impact_coefficient: float = 0.1,
        min_slippage: float = 0.0,
        max_slippage: float = 0.01,
    ):
        """
        Initialize volume-based slippage model.

        Args:
            impact_coefficient: Market impact coefficient
            min_slippage: Minimum slippage (floor)
            max_slippage: Maximum slippage (cap)
        """
        self.impact_coefficient = impact_coefficient
        self.min_slippage = min_slippage
        self.max_slippage = max_slippage

    def apply(
        self,
        price: float,
        quantity: float = 1.0,
        is_buy: bool = True,
        volume: Optional[float] = None,
        volatility: Optional[float] = None,  # NEW: Add volatility parameter
        volatility_multiplier: float = 1.0,  # NEW: Volatility adjustment strength
        baseline_volatility: float = 0.01,  # NEW: Normal volatility level
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

    def get_description(self) -> str:
        return f"Volume-based slippage (coefficient={self.impact_coefficient})"


class RandomSlippage(SlippageModel):
    """
    Random slippage model.

    Applies random slippage within a range for robustness testing.
    Useful for Monte Carlo simulations.
    """

    def __init__(
        self, min_pct: float = 0.0, max_pct: float = 0.0002, seed: Optional[int] = None
    ):
        """
        Initialize random slippage model.

        Args:
            min_pct: Minimum slippage percentage
            max_pct: Maximum slippage percentage
            seed: Random seed for reproducibility
        """
        self.min_pct = min_pct
        self.max_pct = max_pct
        self.rng = np.random.default_rng(seed)

    def apply(
        self, price: float, quantity: float = 1.0, is_buy: bool = True, **kwargs
    ) -> float:
        """Apply random slippage"""
        slippage = self.rng.uniform(self.min_pct, self.max_pct)

        if is_buy:
            return price * (1 + slippage)
        else:
            return price * (1 - slippage)

    def set_seed(self, seed: int) -> None:
        """Set random seed for reproducibility"""
        self.rng = np.random.default_rng(seed)

    def get_description(self) -> str:
        return f"Random slippage: {self.min_pct:.4%} - {self.max_pct:.4%}"


class SpreadSlippage(SlippageModel):
    """
    Spread-based slippage model.

    Uses the bid-ask spread to determine slippage.
    More realistic for forex markets where spread varies.
    """

    def __init__(self, spread_multiplier: float = 1.0):
        """
        Initialize spread-based slippage model.

        Args:
            spread_multiplier: Multiplier for the spread (1.0 = use full spread)
        """
        self.spread_multiplier = spread_multiplier

    def apply(
        self,
        price: float,
        quantity: float = 1.0,
        is_buy: bool = True,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
        **kwargs,
    ) -> float:
        """
        Apply spread-based slippage.

        For buys: execute at ask + portion of spread
        For sells: execute at bid - portion of spread
        """
        if bid is None or ask is None:
            # Fallback to fixed slippage if no spread data
            slippage = 0.0001
        else:
            spread = ask - bid
            slippage = (spread * self.spread_multiplier) / price

        if is_buy:
            return price * (1 + slippage / 2)
        else:
            return price * (1 - slippage / 2)

    def get_description(self) -> str:
        return f"Spread-based slippage (multiplier={self.spread_multiplier})"


class VolatilitySlippage(SlippageModel):
    """
    Volatility-based slippage model.

    Slippage increases during high volatility periods.
    Useful for stress testing.
    """

    def __init__(
        self,
        base_slippage: float = 0.0001,
        volatility_multiplier: float = 10.0,
        baseline_volatility: float = 0.01,
    ):
        """
        Initialize volatility-based slippage model.

        Args:
            base_slippage: Base slippage percentage
            volatility_multiplier: How much volatility affects slippage
            baseline_volatility: Normal volatility level
        """
        self.base_slippage = base_slippage
        self.volatility_multiplier = volatility_multiplier
        self.baseline_volatility = baseline_volatility

    def apply(
        self,
        price: float,
        quantity: float = 1.0,
        is_buy: bool = True,
        volatility: Optional[float] = None,
        **kwargs,
    ) -> float:
        """Apply volatility-based slippage"""
        current_vol = (
            volatility if volatility and volatility > 0 else self.baseline_volatility
        )

        # Calculate volatility ratio
        vol_ratio = current_vol / self.baseline_volatility

        # Calculate slippage with volatility adjustment
        slippage = self.base_slippage * (
            1 + self.volatility_multiplier * (vol_ratio - 1)
        )
        slippage = max(0, slippage)  # Ensure non-negative

        if is_buy:
            return price * (1 + slippage)
        else:
            return price * (1 - slippage)

    def get_description(self) -> str:
        return f"Volatility-based slippage (base={self.base_slippage:.4%})"


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
        current_vol = (
            volatility if volatility and volatility > 0 else self.baseline_volatility
        )
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


@dataclass
class TransactionCosts:
    """
    Complete transaction cost model including:
    - Spread
    - Commission
    - Slippage
    """

    spread_pct: float = 0.0001  # Bid-ask spread as percentage
    commission_pct: float = 0.0  # Commission as percentage
    slippage_model: Optional[SlippageModel] = None

    def calculate_total_cost(
        self, price: float, quantity: float, is_buy: bool = True, **kwargs
    ) -> tuple[float, float]:
        """
        Calculate total transaction cost.

        Returns:
            Tuple of (execution_price, total_cost)
        """
        # Start with spread cost
        if is_buy:
            base_price = price * (1 + self.spread_pct / 2)
        else:
            base_price = price * (1 - self.spread_pct / 2)

        # Apply slippage
        if self.slippage_model:
            exec_price = self.slippage_model.apply(
                base_price, quantity, is_buy, **kwargs
            )
        else:
            exec_price = base_price

        # Calculate value
        value = exec_price * quantity

        # Add commission
        commission = value * self.commission_pct

        # Total cost is the deviation from mid price plus commission
        mid_price = price
        price_impact = abs(exec_price - mid_price) * quantity
        total_cost = price_impact + commission

        return exec_price, total_cost


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

    if model_type not in models:
        raise ValueError(
            f"Unknown slippage model: {model_type}. Available: {list(models.keys())}"
        )

    return models[model_type](**kwargs)
