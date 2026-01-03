"""
Historical Backtesting Environment

Event-driven backtesting environment that replays historical data
for offline training and strategy validation.

Features:
- Replays tick/bar data chronologically
- Realistic slippage and transaction cost modeling
- Trade history tracking
- Performance metrics calculation
- Reproducible via seeding
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

from environments.base_trading_env import BaseTradingEnv
from environments.slippage_models import SlippageModel, FixedSlippage


@dataclass
class Trade:
    """Represents a completed trade"""

    entry_time: datetime
    exit_time: Optional[datetime]
    symbol: str
    side: str  # 'long' or 'short'
    entry_price: float
    exit_price: Optional[float]
    quantity: float
    pnl: float = 0.0
    commission: float = 0.0
    slippage_cost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "pnl": self.pnl,
            "commission": self.commission,
            "slippage_cost": self.slippage_cost,
        }


@dataclass
class Position:
    """Represents an open position"""

    symbol: str
    side: str  # 'long' or 'short'
    quantity: float
    entry_price: float
    entry_time: datetime


class HistoricalTradingEnv(BaseTradingEnv):
    """
    Historical backtesting environment.

    Replays historical data for offline training and validation.
    Supports realistic transaction costs and slippage modeling.

    Usage:
        # Load historical data
        data = pd.read_parquet("data/ticks.parquet")

        # Create environment
        env = HistoricalTradingEnv(
            data=data,
            window_size=50,
            initial_balance=10000.0,
            transaction_cost=0.0001,
            slippage_model=FixedSlippage(0.0001),
            seed=42
        )

        # Run episode
        state, info = env.reset()
        done = False

        while not done:
            action = agent.act(state)
            state, reward, done, truncated, info = env.step(action)

        # Get results
        metrics = env.get_performance_metrics()
        trades = env.get_trade_history()
    """

    def __init__(
        self,
        data: pd.DataFrame,
        window_size: int = 50,
        initial_balance: float = 10000.0,
        transaction_cost: float = 0.0001,
        slippage_model: SlippageModel = None,
        position_size_pct: float = 0.1,
        max_positions: int = 1,
        seed: Optional[int] = None,
    ):
        """
        Initialize historical backtesting environment.

        Args:
            data: DataFrame with columns [timestamp, bid, ask, volume] + optional features
                  Must be sorted by timestamp
            window_size: Number of past observations for state
            initial_balance: Starting account balance
            transaction_cost: Transaction cost as fraction (e.g., 0.0001 = 1 pip)
            slippage_model: Model for realistic fill prices
            position_size_pct: Position size as fraction of balance
            max_positions: Maximum concurrent positions
            seed: Random seed for reproducibility
        """
        # Validate data
        required_columns = ["bid", "ask"]
        for col in required_columns:
            if col not in data.columns:
                raise ValueError(f"Data must contain column: {col}")

        # Determine feature columns
        self.feature_columns = [
            c
            for c in data.columns
            if c not in ["timestamp", "bid", "ask", "volume", "symbol"]
        ]

        # Calculate observation size: bid, ask, volume, position_indicator + features
        n_base_features = 4  # bid, ask, volume, position
        n_features = n_base_features + len(self.feature_columns)

        super().__init__(
            window_size=window_size,
            price_shape=n_features,
            action_size=4,  # HOLD, BUY, SELL, CLOSE
            seed=seed,
        )

        # Store data
        self.data = data.reset_index(drop=True)
        self.n_steps = len(self.data)

        # Configuration
        self.initial_balance = initial_balance
        self.transaction_cost = transaction_cost
        self.slippage_model = slippage_model or FixedSlippage()
        self.position_size_pct = position_size_pct
        self.max_positions = max_positions

        # State tracking
        self.balance = initial_balance
        self.equity_history: List[float] = []
        self.position: Optional[Position] = None
        self.trade_history: List[Trade] = []
        self.current_step = window_size

    def reset(
        self, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Reset environment to initial state.

        Args:
            seed: Random seed for reproducibility
            options: Optional configuration (can include 'start_step')

        Returns:
            Tuple of (observation, info)
        """
        # Call parent reset for seeding
        super().reset(seed=seed)

        # Reset state
        self.balance = self.initial_balance
        self.equity_history = [self.initial_balance]
        self.position = None
        self.trade_history = []

        # Set start position
        if options and "start_step" in options:
            self.current_step = max(self.window_size, options["start_step"])
        else:
            self.current_step = self.window_size

        info = {"balance": self.balance, "step": self.current_step, "seed": self._seed}

        return self.get_state(), info

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """
        Execute one step in the environment.

        Args:
            action: Action to take (0=HOLD, 1=BUY, 2=SELL, 3=CLOSE)

        Returns:
            Tuple of (observation, reward, terminated, truncated, info)
        """
        # Get current bar data
        if self.current_step >= len(self.data):
            return self.get_state(), 0.0, True, False, {"error": "Data exhausted"}

        current_bar = self.data.iloc[self.current_step]

        # Calculate equity before action
        old_equity = self._calculate_equity(current_bar)

        # Execute action
        self._execute_action(action, current_bar)

        # Move to next step
        self.current_step += 1

        # Check termination
        terminated = self.current_step >= len(self.data) - 1 or self.balance <= 0
        truncated = False

        # Get new bar for reward calculation
        if not terminated:
            new_bar = self.data.iloc[self.current_step]
            new_equity = self._calculate_equity(new_bar)
        else:
            new_equity = self._calculate_equity(current_bar)

        # Record equity
        self.equity_history.append(new_equity)

        # Calculate reward as equity change (percentage)
        if old_equity > 0:
            reward = (new_equity - old_equity) / old_equity
        else:
            reward = 0.0

        info = {
            "balance": self.balance,
            "equity": new_equity,
            "position": self._position_to_dict(),
            "step": self.current_step,
            "total_trades": len(self.trade_history),
        }

        return self.get_state(), reward, terminated, truncated, info

    def get_state(self) -> np.ndarray:
        """
        Get current observation.

        Returns:
            State array of shape (window_size, n_features)
        """
        if self.current_step < self.window_size:
            # Not enough data yet
            return np.zeros(self.observation_space.shape, dtype=np.float32)

        start_idx = self.current_step - self.window_size
        end_idx = self.current_step

        window = self.data.iloc[start_idx:end_idx]

        # Build feature array
        features = []
        for _, row in window.iterrows():
            row_features = [
                row["bid"],
                row["ask"],
                row.get("volume", 0),
                1.0 if self.position is not None else 0.0,
            ]

            # Add additional features
            for col in self.feature_columns:
                row_features.append(row[col])

            features.append(row_features)

        return np.array(features, dtype=np.float32)

    def _execute_action(self, action: int, bar: pd.Series) -> None:
        """Execute trading action"""
        timestamp = bar.get("timestamp", datetime.now())
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif hasattr(timestamp, "to_pydatetime"):
            timestamp = timestamp.to_pydatetime()

        if action == 0:  # HOLD
            return

        elif action == 1:  # BUY (open long)
            if self.position is None:
                fill_price = self.slippage_model.apply(
                    bar["ask"],
                    quantity=1.0,
                    is_buy=True,
                    volume=bar.get("volume", 1000),
                )

                # Calculate position size
                position_value = self.balance * self.position_size_pct
                quantity = position_value / fill_price

                # Deduct transaction cost
                cost = fill_price * quantity * self.transaction_cost
                self.balance -= cost

                self.position = Position(
                    symbol=bar.get("symbol", "UNKNOWN"),
                    side="long",
                    quantity=quantity,
                    entry_price=fill_price,
                    entry_time=timestamp,
                )

        elif action == 2:  # SELL (open short)
            if self.position is None:
                fill_price = self.slippage_model.apply(
                    bar["bid"],
                    quantity=1.0,
                    is_buy=False,
                    volume=bar.get("volume", 1000),
                )

                # Calculate position size
                position_value = self.balance * self.position_size_pct
                quantity = position_value / fill_price

                # Deduct transaction cost
                cost = fill_price * quantity * self.transaction_cost
                self.balance -= cost

                self.position = Position(
                    symbol=bar.get("symbol", "UNKNOWN"),
                    side="short",
                    quantity=quantity,
                    entry_price=fill_price,
                    entry_time=timestamp,
                )

        elif action == 3:  # CLOSE
            if self.position is not None:
                self._close_position(bar, timestamp)

    def _close_position(self, bar: pd.Series, timestamp: datetime) -> float:
        """Close current position and return P&L"""
        if self.position is None:
            return 0.0

        # Calculate exit price with slippage
        if self.position.side == "long":
            exit_price = self.slippage_model.apply(
                bar["bid"],
                quantity=self.position.quantity,
                is_buy=False,
                volume=bar.get("volume", 1000),
            )
            pnl = (exit_price - self.position.entry_price) * self.position.quantity
        else:
            exit_price = self.slippage_model.apply(
                bar["ask"],
                quantity=self.position.quantity,
                is_buy=True,
                volume=bar.get("volume", 1000),
            )
            pnl = (self.position.entry_price - exit_price) * self.position.quantity

        # Deduct transaction cost
        cost = exit_price * self.position.quantity * self.transaction_cost
        net_pnl = pnl - cost

        # Update balance
        self.balance += net_pnl

        # Record trade
        trade = Trade(
            entry_time=self.position.entry_time,
            exit_time=timestamp,
            symbol=self.position.symbol,
            side=self.position.side,
            entry_price=self.position.entry_price,
            exit_price=exit_price,
            quantity=self.position.quantity,
            pnl=net_pnl,
            commission=cost,
        )
        self.trade_history.append(trade)

        self.position = None
        return net_pnl

    def _calculate_equity(self, bar: pd.Series) -> float:
        """Calculate current equity (balance + unrealized P&L)"""
        if self.position is None:
            return self.balance

        if self.position.side == "long":
            unrealized = (
                bar["bid"] - self.position.entry_price
            ) * self.position.quantity
        else:
            unrealized = (
                self.position.entry_price - bar["ask"]
            ) * self.position.quantity

        return self.balance + unrealized

    def _position_to_dict(self) -> Optional[Dict]:
        """Convert position to dictionary"""
        if self.position is None:
            return None
        return {
            "symbol": self.position.symbol,
            "side": self.position.side,
            "quantity": self.position.quantity,
            "entry_price": self.position.entry_price,
        }

    def get_trade_history(self) -> List[Dict]:
        """Get list of completed trades"""
        return [t.to_dict() for t in self.trade_history]

    def get_equity_curve(self) -> np.ndarray:
        """Get equity curve as array"""
        return np.array(self.equity_history)

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Calculate comprehensive performance metrics.

        Returns:
            Dictionary of performance metrics
        """
        if not self.trade_history:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "profit_factor": 0.0,
            }

        # Trade statistics
        pnls = [t.pnl for t in self.trade_history]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        win_rate = len(wins) / len(pnls) if pnls else 0.0

        # P&L statistics
        total_pnl = sum(pnls)
        avg_pnl = np.mean(pnls) if pnls else 0.0
        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = np.mean(losses) if losses else 0.0

        # Profit factor
        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # Returns for Sharpe ratio
        equity = np.array(self.equity_history)
        if len(equity) > 1:
            returns = np.diff(equity) / equity[:-1]
            sharpe_ratio = np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(252)
        else:
            sharpe_ratio = 0.0

        # Max drawdown
        max_drawdown = self._calculate_max_drawdown()

        return {
            "total_trades": len(self.trade_history),
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_pnl": avg_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "final_balance": self.balance,
            "total_return": (self.balance - self.initial_balance)
            / self.initial_balance,
        }

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from equity curve"""
        equity = np.array(self.equity_history)
        if len(equity) == 0:
            return 0.0

        peak = equity[0]
        max_dd = 0.0

        for e in equity:
            if e > peak:
                peak = e
            dd = (peak - e) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

        return max_dd
