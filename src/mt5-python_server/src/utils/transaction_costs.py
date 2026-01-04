"""
Transaction Cost and Slippage Modeling
Implements realistic transaction cost calculation including spread, commission, and slippage
Based on industry best practices for algorithmic trading
"""

import numpy as np
from typing import Optional
from models.currency_pair import CurrencyPair


class TransactionCostModel:
    """
    Model transaction costs and slippage for realistic trading simulation

    Components:
    1. Spread Cost: Bid-ask spread (paid on entry)
    2. Commission: Broker commission (entry + exit)
    3. Slippage: Market impact based on volatility and order size

    Based on best practices:
    - Granular cost analysis
    - Volatility-based slippage
    - Order size impact
    - Market condition awareness
    """

    def __init__(
        self,
        spread_pct: float = 0.0001,  # 0.01% = 1 pip for EUR/USD
        commission_pct: float = 0.0001,  # 0.01% per trade
        base_slippage_pct: float = 0.0002,  # 0.02% base slippage
        volatility_slippage_factor: float = 2.0,  # Multiplier for volatility
        order_size_impact_factor: float = 0.5,  # Impact of large orders
        contract_size: int = 100000,  # Standard lot size in units
    ):
        """
        Initialize transaction cost model

        :param spread_pct: Bid-ask spread as percentage (default: 0.01%)
        :param commission_pct: Commission per trade as percentage (default: 0.01%)
        :param base_slippage_pct: Base slippage percentage (default: 0.02%)
        :param volatility_slippage_factor: Multiplier for volatility-based slippage
        :param order_size_impact_factor: Impact factor for large orders
        :param contract_size: Contract size per lot (default: 100,000 for standard lot)
        """
        self.spread_pct = spread_pct
        self.commission_pct = commission_pct
        self.base_slippage_pct = base_slippage_pct
        self.volatility_slippage_factor = volatility_slippage_factor
        self.order_size_impact_factor = order_size_impact_factor
        self.contract_size = contract_size

    def calculate_spread_cost(
        self,
        entry_price: float,
        lot_size: float,
        is_long: bool,
        pair: Optional[CurrencyPair] = None,
    ) -> float:
        """
        Calculate spread cost (bid-ask spread)
        For long positions: pay ask price (higher)
        For short positions: pay bid price (lower, but spread still applies on exit)

        :param entry_price: Entry price
        :param lot_size: Position size in lots
        :param is_long: True for long position, False for short
        :param pair: Currency pair (optional, for actual spread if available)
        :return: Spread cost in account currency
        """
        # If we have actual bid/ask, use real spread
        if pair and pair.bid is not None and pair.ask is not None:
            actual_spread = pair.ask - pair.bid
            spread_pct = (
                actual_spread / pair.mid_price
                if pair.mid_price > 0
                else self.spread_pct
            )
        else:
            # Use configured spread percentage
            spread_pct = self.spread_pct

        # Spread cost = spread percentage * price * lot size * contract size
        spread_cost = entry_price * spread_pct * lot_size * self.contract_size

        return spread_cost

    def calculate_commission(
        self, entry_price: float, exit_price: float, lot_size: float
    ) -> float:
        """
        Calculate commission cost (entry + exit)

        :param entry_price: Entry price
        :param exit_price: Exit price
        :param lot_size: Position size in lots
        :return: Commission cost in account currency
        """
        # Commission on entry
        entry_commission = (
            entry_price * self.commission_pct * lot_size * self.contract_size
        )

        # Commission on exit
        exit_commission = (
            exit_price * self.commission_pct * lot_size * self.contract_size
        )

        total_commission = entry_commission + exit_commission

        return total_commission

    def calculate_slippage(
        self,
        entry_price: float,
        lot_size: float,
        volatility: Optional[float] = None,
        is_long: bool = True,
    ) -> float:
        """
        Calculate slippage based on market conditions

        Slippage factors:
        1. Base slippage (market impact)
        2. Volatility-based slippage (higher volatility = more slippage)
        3. Order size impact (larger orders = more slippage)

        :param entry_price: Entry price
        :param lot_size: Position size in lots
        :param volatility: Current volatility (optional, for volatility-based slippage)
        :param is_long: True for long position, False for short
        :return: Slippage cost in account currency
        """
        # Base slippage
        base_slippage = (
            entry_price * self.base_slippage_pct * lot_size * self.contract_size
        )

        # Volatility-based slippage
        volatility_slippage = 0.0
        if volatility is not None and volatility > 0:
            # Higher volatility = more slippage
            # Normalize volatility (assuming daily volatility, annualize if needed)
            # Typical forex daily volatility: 0.005-0.015 (0.5%-1.5%)
            normalized_vol = min(volatility, 0.05)  # Cap at 5% for safety
            volatility_slippage = (
                entry_price
                * normalized_vol
                * self.volatility_slippage_factor
                * self.base_slippage_pct
                * lot_size
                * self.contract_size
            )

        # Order size impact (larger orders have more market impact)
        # Standard lot = 1.0, micro lot = 0.01
        # Impact increases with order size, but with diminishing returns
        size_impact = np.log1p(lot_size * 10) * self.order_size_impact_factor
        size_slippage = base_slippage * size_impact

        total_slippage = base_slippage + volatility_slippage + size_slippage

        return total_slippage

    def calculate_entry_cost(
        self,
        entry_price: float,
        lot_size: float,
        is_long: bool,
        pair: Optional[CurrencyPair] = None,
        volatility: Optional[float] = None,
    ) -> dict:
        """
        Calculate total cost for entering a position

        :param entry_price: Entry price
        :param lot_size: Position size in lots
        :param is_long: True for long position, False for short
        :param pair: Currency pair (for actual spread)
        :param volatility: Current volatility (for slippage calculation)
        :return: Dictionary with cost breakdown
        """
        spread_cost = self.calculate_spread_cost(entry_price, lot_size, is_long, pair)
        entry_commission = (
            entry_price * self.commission_pct * lot_size * self.contract_size
        )
        slippage = self.calculate_slippage(entry_price, lot_size, volatility, is_long)

        total_entry_cost = spread_cost + entry_commission + slippage

        return {
            "spread_cost": spread_cost,
            "entry_commission": entry_commission,
            "slippage": slippage,
            "total_entry_cost": total_entry_cost,
            "entry_cost_pct": (
                total_entry_cost / (entry_price * lot_size * self.contract_size)
                if entry_price > 0
                else 0.0
            ),
        }

    def calculate_exit_cost(
        self,
        exit_price: float,
        lot_size: float,
        is_long: bool,
        pair: Optional[CurrencyPair] = None,
        volatility: Optional[float] = None,
    ) -> dict:
        """
        Calculate total cost for exiting a position

        :param exit_price: Exit price
        :param lot_size: Position size in lots
        :param is_long: True for long position, False for short
        :param pair: Currency pair (for actual spread)
        :param volatility: Current volatility (for slippage calculation)
        :return: Dictionary with cost breakdown
        """
        # For exit, spread applies (opposite direction)
        spread_cost = self.calculate_spread_cost(
            exit_price, lot_size, not is_long, pair
        )
        exit_commission = (
            exit_price * self.commission_pct * lot_size * self.contract_size
        )
        slippage = self.calculate_slippage(
            exit_price, lot_size, volatility, not is_long
        )

        total_exit_cost = spread_cost + exit_commission + slippage

        return {
            "spread_cost": spread_cost,
            "exit_commission": exit_commission,
            "slippage": slippage,
            "total_exit_cost": total_exit_cost,
            "exit_cost_pct": (
                total_exit_cost / (exit_price * lot_size * self.contract_size)
                if exit_price > 0
                else 0.0
            ),
        }

    def calculate_round_trip_cost(
        self,
        entry_price: float,
        exit_price: float,
        lot_size: float,
        is_long: bool,
        pair: Optional[CurrencyPair] = None,
        volatility: Optional[float] = None,
    ) -> dict:
        """
        Calculate total round-trip transaction cost (entry + exit)

        This is the most comprehensive method, accounting for all costs

        :param entry_price: Entry price
        :param exit_price: Exit price
        :param lot_size: Position size in lots
        :param is_long: True for long position, False for short
        :param pair: Currency pair (for actual spread)
        :param volatility: Current volatility (for slippage calculation)
        :return: Dictionary with complete cost breakdown
        """
        entry_costs = self.calculate_entry_cost(
            entry_price, lot_size, is_long, pair, volatility
        )
        exit_costs = self.calculate_exit_cost(
            exit_price, lot_size, is_long, pair, volatility
        )

        total_cost = entry_costs["total_entry_cost"] + exit_costs["total_exit_cost"]

        # Calculate as percentage of trade value
        trade_value = entry_price * lot_size * self.contract_size
        total_cost_pct = total_cost / trade_value if trade_value > 0 else 0.0

        return {
            "entry_costs": entry_costs,
            "exit_costs": exit_costs,
            "total_cost": total_cost,
            "total_cost_pct": total_cost_pct,
            "spread_cost": entry_costs["spread_cost"] + exit_costs["spread_cost"],
            "commission": entry_costs["entry_commission"]
            + exit_costs["exit_commission"],
            "slippage": entry_costs["slippage"] + exit_costs["slippage"],
        }

    def calculate_cost_for_action(
        self,
        action: int,
        entry_price: float,
        exit_price: Optional[float],
        lot_size: float,
        is_long: bool,
        pair: Optional[CurrencyPair] = None,
        volatility: Optional[float] = None,
    ) -> float:
        """
        Calculate transaction cost for a specific action

        :param action: Action taken (0=Hold, 1=Buy, 2=Sell, 3=Close)
        :param entry_price: Entry price (or current price for close)
        :param exit_price: Exit price (for close action, None otherwise)
        :param lot_size: Position size in lots
        :param is_long: True for long position, False for short
        :param pair: Currency pair
        :param volatility: Current volatility
        :return: Total transaction cost as absolute value
        """
        if action == 0:  # Hold - no cost
            return 0.0

        elif action in [1, 2]:  # Buy or Sell - entry cost only
            costs = self.calculate_entry_cost(
                entry_price, lot_size, is_long, pair, volatility
            )
            return costs["total_entry_cost"]

        elif action == 3:  # Close - exit cost only
            if exit_price is None:
                exit_price = entry_price  # Use current price if exit price not provided
            costs = self.calculate_exit_cost(
                exit_price, lot_size, is_long, pair, volatility
            )
            return costs["total_exit_cost"]

        return 0.0

    def estimate_cost_percentage(
        self, entry_price: float, lot_size: float, volatility: Optional[float] = None
    ) -> float:
        """
        Estimate total transaction cost as percentage of trade value
        Useful for quick cost estimation without full calculation

        :param entry_price: Entry price
        :param lot_size: Position size in lots
        :param volatility: Current volatility (optional)
        :return: Estimated cost as percentage
        """
        # Base costs
        base_cost_pct = (
            self.spread_pct + (2 * self.commission_pct) + (2 * self.base_slippage_pct)
        )

        # Add volatility adjustment
        if volatility is not None:
            normalized_vol = min(volatility, 0.05)
            volatility_adjustment = (
                normalized_vol
                * self.volatility_slippage_factor
                * self.base_slippage_pct
            )
            base_cost_pct += volatility_adjustment

        # Add size impact
        size_impact = (
            np.log1p(lot_size * 10)
            * self.order_size_impact_factor
            * self.base_slippage_pct
        )
        base_cost_pct += size_impact

        return base_cost_pct
