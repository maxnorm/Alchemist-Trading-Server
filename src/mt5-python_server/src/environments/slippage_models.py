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
        **kwargs,
    ) -> float:
        """
        Apply volume-based slippage.

        Args:
            volume: Market volume (required for accurate calculation)
        """
        # Default volume if not provided
        market_volume = volume if volume and volume > 0 else 1000.0

        # Calculate participation rate
        participation_rate = quantity / market_volume

        # Square-root market impact
        impact = self.impact_coefficient * np.sqrt(participation_rate)

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
        model_type: Type of model ("none", "fixed", "volume", "random", "spread", "volatility")
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
    }

    if model_type not in models:
        raise ValueError(
            f"Unknown slippage model: {model_type}. Available: {list(models.keys())}"
        )

    return models[model_type](**kwargs)
