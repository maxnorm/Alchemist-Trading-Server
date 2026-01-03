"""
Paper Trading Environment

Real-time paper trading environment that:
- Uses live data from data providers
- Simulates order execution with realistic slippage
- Tracks simulated P&L
- Does NOT execute real trades

Perfect for model validation before production deployment.
"""

import time
import numpy as np
from typing import Optional, Dict, List, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque

from environments.base_trading_env import BaseTradingEnv
from environments.slippage_models import SlippageModel, FixedSlippage

if TYPE_CHECKING:
    from data_providers.base_provider import DataProvider


@dataclass
class SimulatedPosition:
    """Simulated position for paper trading"""
    symbol: str
    side: str  # 'long' or 'short'
    quantity: float
    entry_price: float
    entry_time: datetime
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    
    def update_price(self, bid: float, ask: float) -> None:
        """Update current price and unrealized P&L"""
        if self.side == 'long':
            self.current_price = bid
            self.unrealized_pnl = (bid - self.entry_price) * self.quantity
        else:
            self.current_price = ask
            self.unrealized_pnl = (self.entry_price - ask) * self.quantity


@dataclass
class SimulatedTrade:
    """Completed simulated trade"""
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    duration_seconds: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'side': self.side,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'quantity': self.quantity,
            'entry_time': self.entry_time.isoformat(),
            'exit_time': self.exit_time.isoformat(),
            'pnl': self.pnl,
            'duration_seconds': self.duration_seconds
        }


class PaperTradingEnv(BaseTradingEnv):
    """
    Paper trading environment with real-time data.
    
    Uses live data feeds but simulates all executions.
    Useful for model validation without risking real capital.
    
    Features:
    - Real-time price updates from data providers
    - Simulated execution with slippage
    - Position and P&L tracking
    - Latency simulation (optional)
    - Performance metrics calculation
    
    Usage:
        # Create with data providers
        providers = [PriceProvider(pair) for pair in currency_pairs]
        
        env = PaperTradingEnv(
            data_providers=providers,
            initial_balance=10000.0,
            transaction_cost=0.0001,
            slippage_model=FixedSlippage(0.0001)
        )
        
        # Run trading loop
        state, info = env.reset()
        
        while True:
            action = agent.act(state)
            state, reward, done, truncated, info = env.step(action)
            
            # Paper trading doesn't have a natural end
            # Use external signals to stop (e.g., time-based)
            if should_stop():
                break
        
        # Get performance
        metrics = env.get_performance_metrics()
    """
    
    def __init__(
        self,
        data_providers: List['DataProvider'],
        window_size: int = 50,
        initial_balance: float = 10000.0,
        transaction_cost: float = 0.0001,
        slippage_model: SlippageModel = None,
        position_size_pct: float = 0.1,
        simulate_latency: bool = True,
        latency_ms: int = 50,
        max_history: int = 1000
    ):
        """
        Initialize paper trading environment.
        
        Args:
            data_providers: List of data providers for price feeds
            window_size: Observation window size
            initial_balance: Starting simulated balance
            transaction_cost: Transaction cost as fraction
            slippage_model: Model for simulating execution slippage
            position_size_pct: Default position size as fraction of balance
            simulate_latency: Whether to simulate network latency
            latency_ms: Simulated latency in milliseconds
            max_history: Maximum price history to keep
        """
        n_pairs = len(data_providers)
        action_size = (n_pairs * 3) + 1  # +1 for global HOLD
        
        super().__init__(
            window_size=window_size,
            price_shape=15,  # Standard feature count
            action_size=action_size
        )
        
        self.data_providers = data_providers
        self.initial_balance = initial_balance
        self.transaction_cost = transaction_cost
        self.slippage_model = slippage_model or FixedSlippage()
        self.position_size_pct = position_size_pct
        self.simulate_latency = simulate_latency
        self.latency_ms = latency_ms
        self.max_history = max_history
        
        # Simulated state
        self.simulated_balance = initial_balance
        self.simulated_positions: Dict[str, SimulatedPosition] = {}
        self.simulated_trades: List[SimulatedTrade] = []
        self.equity_history: List[Tuple[datetime, float]] = []
        
        # Price history for state building
        self.price_history: Dict[str, deque] = {
            p.currency_pair.symbol: deque(maxlen=max_history)
            for p in data_providers
        }
        
        # Statistics
        self.step_count = 0
        self.start_time: Optional[datetime] = None
    
    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Reset paper trading state"""
        super().reset(seed=seed)
        
        self.simulated_balance = self.initial_balance
        self.simulated_positions = {}
        self.simulated_trades = []
        self.equity_history = [(datetime.now(), self.initial_balance)]
        self.step_count = 0
        self.start_time = datetime.now()
        
        # Clear price history
        for symbol in self.price_history:
            self.price_history[symbol].clear()
        
        info = {
            'simulated_balance': self.simulated_balance,
            'start_time': self.start_time.isoformat()
        }
        
        return self.get_state(), info
    
    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """
        Execute one step with simulated trading.
        
        Args:
            action: Action to take
            
        Returns:
            Tuple of (observation, reward, terminated, truncated, info)
        """
        # Simulate network latency
        if self.simulate_latency:
            time.sleep(self.latency_ms / 1000)
        
        # Update positions with current prices
        self._update_positions()
        
        # Calculate equity before action
        old_equity = self._calculate_equity()
        
        # Execute simulated action
        self._execute_simulated_action(action)
        
        # Calculate new equity
        new_equity = self._calculate_equity()
        
        # Record equity
        self.equity_history.append((datetime.now(), new_equity))
        
        # Calculate reward
        if old_equity > 0:
            reward = (new_equity - old_equity) / old_equity
        else:
            reward = 0.0
        
        self.step_count += 1
        
        info = {
            'simulated_balance': self.simulated_balance,
            'simulated_equity': new_equity,
            'positions': {
                sym: {'side': p.side, 'quantity': p.quantity, 'unrealized_pnl': p.unrealized_pnl}
                for sym, p in self.simulated_positions.items()
            },
            'step_count': self.step_count,
            'trade_count': len(self.simulated_trades)
        }
        
        # Paper trading never terminates on its own
        return self.get_state(), reward, False, False, info
    
    def get_state(self) -> np.ndarray:
        """Get current state from live data providers"""
        if not self.data_providers:
            return np.zeros(self.observation_space.shape, dtype=np.float32)
        
        # Collect data from all providers
        all_features = []
        
        for provider in self.data_providers:
            symbol = provider.currency_pair.symbol
            
            # Get current data
            try:
                current_data = provider.get_current_data()
                if current_data:
                    self.price_history[symbol].append({
                        'timestamp': datetime.now(),
                        'bid': current_data.get('bid', 0),
                        'ask': current_data.get('ask', 0),
                        'volume': current_data.get('volume', 0)
                    })
            except Exception:
                pass
        
        # Build state from history
        # Use the first provider's history as the main timeline
        if self.data_providers:
            main_symbol = self.data_providers[0].currency_pair.symbol
            history = list(self.price_history[main_symbol])
        else:
            history = []
        
        if len(history) < self.window_size:
            # Not enough data yet
            return np.zeros(self.observation_space.shape, dtype=np.float32)
        
        # Take last window_size entries
        window = history[-self.window_size:]
        
        features = []
        for entry in window:
            row_features = [
                entry['bid'],
                entry['ask'],
                entry['volume'],
                1.0 if self.simulated_positions else 0.0,
            ]
            
            # Pad to match expected feature size
            while len(row_features) < self.observation_space.shape[1]:
                row_features.append(0.0)
            
            features.append(row_features[:self.observation_space.shape[1]])
        
        return np.array(features, dtype=np.float32)
    
    def _execute_simulated_action(self, action: int) -> None:
        """Execute action in simulation"""
        if action == 0:  # Global HOLD
            return
        
        # Decode action
        pair_index, action_type = self.decode_action(action)
        
        if pair_index is None or pair_index >= len(self.data_providers):
            return
        
        provider = self.data_providers[pair_index]
        symbol = provider.currency_pair.symbol
        
        # Get current data
        try:
            current_data = provider.get_current_data()
            if not current_data:
                return
        except Exception:
            return
        
        from domain.action_type import ActionType
        
        if action_type == ActionType.BUY:
            self._open_simulated_position(symbol, 'long', current_data)
        elif action_type == ActionType.SELL:
            self._open_simulated_position(symbol, 'short', current_data)
        elif action_type == ActionType.CLOSE:
            self._close_simulated_position(symbol, current_data)
    
    def _open_simulated_position(
        self,
        symbol: str,
        side: str,
        data: Dict
    ) -> None:
        """Open a simulated position"""
        if symbol in self.simulated_positions:
            return  # Already have a position
        
        price = data['ask'] if side == 'long' else data['bid']
        fill_price = self.slippage_model.apply(
            price,
            quantity=1.0,
            is_buy=(side == 'long'),
            volume=data.get('volume', 1000)
        )
        
        # Calculate position size
        position_value = self.simulated_balance * self.position_size_pct
        quantity = position_value / fill_price
        
        # Deduct transaction cost
        cost = fill_price * quantity * self.transaction_cost
        self.simulated_balance -= cost
        
        self.simulated_positions[symbol] = SimulatedPosition(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=fill_price,
            entry_time=datetime.now(),
            current_price=fill_price
        )
    
    def _close_simulated_position(self, symbol: str, data: Dict) -> float:
        """Close a simulated position"""
        if symbol not in self.simulated_positions:
            return 0.0
        
        position = self.simulated_positions[symbol]
        
        # Calculate exit price with slippage
        if position.side == 'long':
            price = data['bid']
            fill_price = self.slippage_model.apply(
                price, quantity=position.quantity, is_buy=False
            )
            pnl = (fill_price - position.entry_price) * position.quantity
        else:
            price = data['ask']
            fill_price = self.slippage_model.apply(
                price, quantity=position.quantity, is_buy=True
            )
            pnl = (position.entry_price - fill_price) * position.quantity
        
        # Deduct transaction cost
        cost = fill_price * position.quantity * self.transaction_cost
        net_pnl = pnl - cost
        
        self.simulated_balance += net_pnl
        
        # Record trade
        exit_time = datetime.now()
        trade = SimulatedTrade(
            symbol=symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=fill_price,
            quantity=position.quantity,
            entry_time=position.entry_time,
            exit_time=exit_time,
            pnl=net_pnl,
            duration_seconds=(exit_time - position.entry_time).total_seconds()
        )
        self.simulated_trades.append(trade)
        
        del self.simulated_positions[symbol]
        return net_pnl
    
    def _update_positions(self) -> None:
        """Update all positions with current prices"""
        for symbol, position in self.simulated_positions.items():
            # Find provider for this symbol
            provider = next(
                (p for p in self.data_providers if p.currency_pair.symbol == symbol),
                None
            )
            
            if provider:
                try:
                    data = provider.get_current_data()
                    if data:
                        position.update_price(data['bid'], data['ask'])
                except Exception:
                    pass
    
    def _calculate_equity(self) -> float:
        """Calculate total simulated equity"""
        equity = self.simulated_balance
        
        for position in self.simulated_positions.values():
            equity += position.unrealized_pnl
        
        return equity
    
    def get_trade_history(self) -> List[Dict]:
        """Get completed trades"""
        return [t.to_dict() for t in self.simulated_trades]
    
    def get_equity_curve(self) -> List[Tuple[str, float]]:
        """Get equity curve with timestamps"""
        return [(t.isoformat(), e) for t, e in self.equity_history]
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Calculate performance metrics from paper trading"""
        if not self.simulated_trades:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'profit_factor': 0.0,
                'days_traded': 0
            }
        
        pnls = [t.pnl for t in self.simulated_trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        win_rate = len(wins) / len(pnls) if pnls else 0.0
        total_pnl = sum(pnls)
        
        # Profit factor
        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Sharpe ratio from equity curve
        if len(self.equity_history) > 1:
            equities = [e for _, e in self.equity_history]
            returns = np.diff(equities) / equities[:-1]
            sharpe_ratio = np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(252)
        else:
            sharpe_ratio = 0.0
        
        # Max drawdown
        max_drawdown = self._calculate_max_drawdown()
        
        # Days traded
        if self.start_time:
            days_traded = (datetime.now() - self.start_time).days
        else:
            days_traded = 0
        
        return {
            'total_trades': len(self.simulated_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': np.mean(pnls) if pnls else 0.0,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'days_traded': days_traded,
            'final_balance': self.simulated_balance,
            'final_equity': self._calculate_equity(),
            'total_return': (self._calculate_equity() - self.initial_balance) / self.initial_balance
        }
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown"""
        if len(self.equity_history) == 0:
            return 0.0
        
        equities = [e for _, e in self.equity_history]
        peak = equities[0]
        max_dd = 0.0
        
        for equity in equities:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def close_all_positions(self) -> int:
        """Close all open positions (e.g., at end of paper trading)"""
        closed = 0
        
        for symbol in list(self.simulated_positions.keys()):
            # Find provider
            provider = next(
                (p for p in self.data_providers if p.currency_pair.symbol == symbol),
                None
            )
            
            if provider:
                try:
                    data = provider.get_current_data()
                    if data:
                        self._close_simulated_position(symbol, data)
                        closed += 1
                except Exception:
                    pass
        
        return closed
    
    def update_session_metrics(
        self,
        session_manager=None,
        session_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update paper trading session metrics in the database.
        
        This method should be called periodically during paper trading to sync
        metrics with the PaperTradingSessionManager.
        
        Args:
            session_manager: Optional PaperTradingSessionManager instance
            session_id: Optional session ID to update
            
        Returns:
            Dictionary of current metrics
        """
        metrics = self.get_performance_metrics()
        
        if session_manager and session_id:
            try:
                # Calculate winning trades
                winning_trades = sum(1 for t in self.simulated_trades if t.pnl > 0)
                
                # Update session in database
                session_manager.update_session_metrics(
                    session_id=session_id,
                    balance=self.simulated_balance,
                    total_trades=len(self.simulated_trades),
                    winning_trades=winning_trades,
                    pnl=metrics.get('total_pnl', 0.0)
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to update session metrics: {e}")
        
        return metrics
    
    def end_session_and_store_results(
        self,
        session_manager=None,
        session_id: Optional[int] = None,
        model_registry=None,
        model_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        End paper trading session and store results.
        
        This method should be called when paper trading is complete.
        It closes all positions, calculates final metrics, and stores results
        in both the session manager and model registry.
        
        Args:
            session_manager: Optional PaperTradingSessionManager instance
            session_id: Optional session ID to end
            model_registry: Optional ModelRegistry instance
            model_id: Optional model ID to store results for
            
        Returns:
            Final metrics dictionary
        """
        # Close all positions
        self.close_all_positions()
        
        # Get final metrics
        final_metrics = self.get_performance_metrics()
        
        # End session in database
        if session_manager and session_id:
            try:
                session_manager.end_session(session_id, final_metrics)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to end session: {e}")
        
        # Store results in model registry
        if model_registry and model_id:
            try:
                # Format results for model registry
                results = {
                    'total_trades': final_metrics.get('total_trades', 0),
                    'winning_trades': sum(1 for t in self.simulated_trades if t.pnl > 0),
                    'win_rate': final_metrics.get('win_rate', 0.0),
                    'pnl': final_metrics.get('total_pnl', 0.0),
                    'sharpe_ratio': final_metrics.get('sharpe_ratio'),
                    'max_drawdown': final_metrics.get('max_drawdown'),
                    'days_traded': final_metrics.get('days_traded', 0),
                    'trade_count': final_metrics.get('total_trades', 0)
                }
                
                model_registry.store_paper_trading_results(model_id, results)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to store results in model registry: {e}")
        
        return final_metrics
