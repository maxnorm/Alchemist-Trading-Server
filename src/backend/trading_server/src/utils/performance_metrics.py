"""
Performance Metrics Calculator
Calculates risk-adjusted performance metrics for trading agents
"""

import numpy as np
from collections import deque
from typing import Deque, List, Optional


class PerformanceMetrics:
    """
    Calculate various performance metrics for trading evaluation

    Metrics include:
    - Sharpe Ratio: Risk-adjusted return metric
    - Sortino Ratio: Downside-adjusted return metric
    - Calmar Ratio: Return to max drawdown ratio
    - Volatility: Standard deviation of returns
    - Drawdown: Peak-to-trough decline
    """

    def __init__(self, window_size: int = 252):
        """
        Initialize metrics calculator
        :param window_size: Rolling window for calculations (default: 252 = 1 year of trading days)
        """
        self.window_size = window_size
        self.returns_history: Deque[float] = deque(maxlen=window_size)
        self.balance_history: Deque[float] = deque(maxlen=window_size)
        self.initial_balance: Optional[float] = None
        self.max_balance: Optional[float] = None
        self.max_drawdown = 0.0
        self.peak_balance: Optional[float] = None

        # For profit factor calculation
        self.gross_profit = 0.0
        self.gross_loss = 0.0
        self.trade_returns: List[float] = []  # Store individual trade returns

    def update(self, current_balance: float, previous_balance: float):
        """
        Update metrics with new balance
        :param current_balance: Current account balance
        :param previous_balance: Previous account balance
        """
        # Initialize on first update
        if self.initial_balance is None:
            self.initial_balance = current_balance
            self.max_balance = current_balance
            self.peak_balance = current_balance

        # Calculate return
        if previous_balance > 0:
            return_pct = (current_balance - previous_balance) / previous_balance
            self.returns_history.append(return_pct)

            # Track profit/loss for profit factor
            profit_loss = current_balance - previous_balance
            if profit_loss > 0:
                self.gross_profit += profit_loss
            elif profit_loss < 0:
                self.gross_loss += abs(profit_loss)

            # Store trade return
            self.trade_returns.append(return_pct)

        # Update balance history
        self.balance_history.append(current_balance)

        # Update peak balance and drawdown
        if self.peak_balance is not None and current_balance > self.peak_balance:
            self.peak_balance = current_balance
            self.max_balance = current_balance

        # Calculate current drawdown
        if self.peak_balance is not None and self.peak_balance > 0:
            current_drawdown = (self.peak_balance - current_balance) / self.peak_balance
            if current_drawdown > self.max_drawdown:
                self.max_drawdown = current_drawdown

    def sharpe_ratio(
        self, risk_free_rate: float = 0.0, annualized: bool = True
    ) -> float:
        """
        Calculate Sharpe Ratio
        Formula: (Mean Return - Risk-Free Rate) / Standard Deviation of Returns

        :param risk_free_rate: Risk-free rate (default: 0.0)
        :param annualized: Whether to annualize the ratio (default: True)
        :return: Sharpe ratio
        """
        if len(self.returns_history) < 2:
            return 0.0

        returns = np.array(self.returns_history)
        excess_returns = returns - risk_free_rate

        if np.std(excess_returns) == 0:
            return 0.0

        sharpe = np.mean(excess_returns) / np.std(excess_returns)

        if annualized:
            # Annualize: multiply by sqrt(252) for daily returns
            # Assuming daily returns (can be adjusted if different frequency)
            sharpe *= np.sqrt(252)

        return sharpe

    def sortino_ratio(
        self, risk_free_rate: float = 0.0, annualized: bool = True
    ) -> float:
        """
        Calculate Sortino Ratio (uses downside deviation instead of total volatility)
        Formula: (Mean Return - Risk-Free Rate) / Downside Deviation

        :param risk_free_rate: Risk-free rate
        :param annualized: Whether to annualize
        :return: Sortino ratio
        """
        if len(self.returns_history) < 2:
            return 0.0

        returns = np.array(self.returns_history)
        excess_returns = returns - risk_free_rate
        downside_returns = excess_returns[excess_returns < 0]

        if len(downside_returns) == 0 or np.std(downside_returns) == 0:
            return 0.0

        sortino = np.mean(excess_returns) / np.std(downside_returns)

        if annualized:
            sortino *= np.sqrt(252)

        return sortino

    def calmar_ratio(self, annualized: bool = True) -> float:
        """
        Calculate Calmar Ratio (Annual Return / Maximum Drawdown)

        :param annualized: Whether to annualize return
        :return: Calmar ratio
        """
        if len(self.returns_history) == 0 or self.max_drawdown == 0:
            return 0.0

        mean_return = np.mean(self.returns_history)

        if annualized:
            # Annualize return (assuming daily returns)
            annual_return = mean_return * 252
        else:
            annual_return = mean_return

        if self.max_drawdown == 0:
            return float("inf") if annual_return > 0 else 0.0

        return float(annual_return / self.max_drawdown)

    def volatility(self, annualized: bool = True) -> float:
        """
        Calculate volatility (standard deviation of returns)

        :param annualized: Whether to annualize volatility
        :return: Volatility
        """
        if len(self.returns_history) < 2:
            return 0.0

        vol = np.std(self.returns_history)

        if annualized:
            # Annualize volatility (assuming daily returns)
            vol *= np.sqrt(252)

        return float(vol)

    def current_drawdown(self) -> float:
        """
        Get current drawdown percentage
        :return: Current drawdown as fraction (0.0 to 1.0)
        """
        if len(self.balance_history) == 0 or self.peak_balance is None:
            return 0.0

        current_balance = self.balance_history[-1]
        if self.peak_balance == 0:
            return 0.0

        return (self.peak_balance - current_balance) / self.peak_balance

    def mean_return(self) -> float:
        """Get mean return"""
        if len(self.returns_history) == 0:
            return 0.0
        return float(np.mean(self.returns_history))

    def total_return(self) -> float:
        """Get total return since initialization"""
        if self.initial_balance is None or len(self.balance_history) == 0:
            return 0.0

        current_balance = self.balance_history[-1]
        if self.initial_balance == 0:
            return 0.0

        return (current_balance - self.initial_balance) / self.initial_balance

    def get_all_metrics(self, risk_free_rate: float = 0.0) -> dict:
        """
        Get all performance metrics
        :param risk_free_rate: Risk-free rate for Sharpe/Sortino calculations
        :return: Dictionary of all metrics
        """
        return {
            "sharpe_ratio": self.sharpe_ratio(risk_free_rate),
            "sortino_ratio": self.sortino_ratio(risk_free_rate),
            "calmar_ratio": self.calmar_ratio(),
            "volatility": self.volatility(),
            "max_drawdown": self.max_drawdown,
            "current_drawdown": self.current_drawdown(),
            "mean_return": self.mean_return(),
            "total_return": self.total_return(),
            "profit_factor": self.profit_factor(),
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "num_returns": len(self.returns_history),
        }

    def profit_factor(self) -> float:
        """
        Calculate Profit Factor
        Formula: Gross Profit / Gross Loss

        :return: Profit factor (infinity if no losses, 0 if no profits)
        """
        if self.gross_loss == 0:
            return float("inf") if self.gross_profit > 0 else 0.0
        return self.gross_profit / abs(self.gross_loss)

    def reset(self):
        """Reset all metrics (useful for new episodes)"""
        self.returns_history.clear()
        self.balance_history.clear()
        self.max_drawdown = 0.0
        self.peak_balance = None
        self.gross_profit = 0.0
        self.gross_loss = 0.0
        self.trade_returns.clear()
        # Keep initial_balance and max_balance for overall tracking

    # Static methods for standalone calculations (as per roadmap)
    @staticmethod
    def calculate_sharpe_ratio(
        returns: np.ndarray, risk_free_rate: float = 0.0
    ) -> float:
        """
        Calculate Sharpe Ratio from returns array
        Formula: (Mean Return - Risk-Free Rate) / Standard Deviation of Returns

        :param returns: Array of returns
        :param risk_free_rate: Risk-free rate (default: 0.0)
        :return: Sharpe ratio (annualized)
        """
        if len(returns) < 2:
            return 0.0

        excess_returns = returns - risk_free_rate

        if np.std(excess_returns) == 0:
            return 0.0

        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)

    @staticmethod
    def calculate_sortino_ratio(
        returns: np.ndarray, risk_free_rate: float = 0.0
    ) -> float:
        """
        Calculate Sortino Ratio from returns array
        Formula: (Mean Return - Risk-Free Rate) / Downside Deviation

        :param returns: Array of returns
        :param risk_free_rate: Risk-free rate (default: 0.0)
        :return: Sortino ratio (annualized)
        """
        if len(returns) < 2:
            return 0.0

        excess_returns = returns - risk_free_rate
        downside_returns = excess_returns[excess_returns < 0]

        if len(downside_returns) == 0 or np.std(downside_returns) == 0:
            return 0.0

        return np.mean(excess_returns) / np.std(downside_returns) * np.sqrt(252)

    @staticmethod
    def calculate_calmar_ratio(returns: np.ndarray, max_drawdown: float) -> float:
        """
        Calculate Calmar Ratio from returns and max drawdown
        Formula: Annual Return / Maximum Drawdown

        :param returns: Array of returns
        :param max_drawdown: Maximum drawdown (as positive value)
        :return: Calmar ratio
        """
        if len(returns) == 0 or abs(max_drawdown) == 0:
            return 0.0

        annual_return = np.mean(returns) * 252

        if abs(max_drawdown) == 0:
            return float("inf") if annual_return > 0 else 0.0

        return annual_return / abs(max_drawdown)

    @staticmethod
    def calculate_profit_factor(gross_profit: float, gross_loss: float) -> float:
        """
        Calculate Profit Factor
        Formula: Gross Profit / Gross Loss

        :param gross_profit: Total gross profit
        :param gross_loss: Total gross loss (as positive value)
        :return: Profit factor (infinity if no losses, 0 if no profits)
        """
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / abs(gross_loss)
