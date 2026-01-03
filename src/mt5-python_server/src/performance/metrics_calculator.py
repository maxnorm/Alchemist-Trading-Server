"""
Performance Metrics Calculator
Calculates various performance metrics from trade data
"""
import logging
import math
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from database import Database
from .trade_logger import TradeLogger
from .equity_tracker import EquityTracker


class PerformanceMetricsCalculator:
    """
    Calculates performance metrics from trade data
    Supports multiple time periods and caches calculations
    """
    
    def __init__(
        self,
        db: Optional[Database] = None,
        trade_logger: Optional[TradeLogger] = None,
        equity_tracker: Optional[EquityTracker] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize metrics calculator
        :param db: Database instance
        :param trade_logger: TradeLogger instance
        :param equity_tracker: EquityTracker instance
        :param logger: Logger instance
        """
        self.db = db or Database()
        self.trade_logger = trade_logger or TradeLogger(db, logger)
        self.equity_tracker = equity_tracker or EquityTracker(db=db, logger=logger)
        self.logger = logger or logging.getLogger(__name__)
    
    def calculate_win_rate(self, trades: List[Dict]) -> float:
        """
        Calculate win rate (winning trades / total trades)
        :param trades: List of closed trade dictionaries
        :return: Win rate as percentage (0-100)
        """
        if not trades:
            return 0.0
        
        closed_trades = [t for t in trades if t.get('status') == 'closed' and t.get('pnl') is not None]
        if not closed_trades:
            return 0.0
        
        winning_trades = [t for t in closed_trades if t['pnl'] > 0]
        return (len(winning_trades) / len(closed_trades)) * 100.0
    
    def calculate_sharpe_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.0,
        annualized: bool = True
    ) -> float:
        """
        Calculate Sharpe ratio
        :param returns: List of returns (as decimals, e.g., 0.05 for 5%)
        :param risk_free_rate: Risk-free rate (annual)
        :param annualized: Whether to annualize the ratio
        :return: Sharpe ratio
        """
        if not returns or len(returns) < 2:
            return 0.0
        
        mean_return = sum(returns) / len(returns)
        
        # Calculate standard deviation
        variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0:
            return 0.0
        
        # Daily Sharpe ratio
        sharpe = (mean_return - risk_free_rate / 252) / std_dev
        
        # Annualize if requested (assuming daily returns)
        if annualized:
            sharpe *= math.sqrt(252)
        
        return sharpe
    
    def calculate_sortino_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.0
    ) -> float:
        """
        Calculate Sortino ratio (downside deviation only)
        :param returns: List of returns (as decimals)
        :param risk_free_rate: Risk-free rate (annual)
        :return: Sortino ratio
        """
        if not returns or len(returns) < 2:
            return 0.0
        
        mean_return = sum(returns) / len(returns)
        
        # Calculate downside deviation (only negative returns)
        downside_returns = [r for r in returns if r < 0]
        if not downside_returns:
            return float('inf') if mean_return > risk_free_rate / 252 else 0.0
        
        downside_variance = sum(r ** 2 for r in downside_returns) / len(returns)
        downside_dev = math.sqrt(downside_variance)
        
        if downside_dev == 0:
            return 0.0
        
        # Daily Sortino ratio
        sortino = (mean_return - risk_free_rate / 252) / downside_dev
        
        # Annualize (assuming daily returns)
        sortino *= math.sqrt(252)
        
        return sortino
    
    def calculate_max_drawdown(
        self,
        equity_curve: List[Dict]
    ) -> Tuple[float, float]:
        """
        Calculate maximum drawdown
        :param equity_curve: List of equity curve points with 'equity' key
        :return: Tuple of (max_drawdown_amount, max_drawdown_pct)
        """
        if not equity_curve or len(equity_curve) < 2:
            return 0.0, 0.0
        
        peak = equity_curve[0]['equity']
        max_drawdown = 0.0
        max_drawdown_pct = 0.0
        
        for point in equity_curve:
            equity = point['equity']
            if equity > peak:
                peak = equity
            
            drawdown = peak - equity
            drawdown_pct = (drawdown / peak * 100) if peak > 0 else 0.0
            
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                max_drawdown_pct = drawdown_pct
        
        return max_drawdown, max_drawdown_pct
    
    def calculate_profit_factor(self, trades: List[Dict]) -> float:
        """
        Calculate profit factor (gross profit / gross loss)
        :param trades: List of closed trade dictionaries
        :return: Profit factor
        """
        closed_trades = [t for t in trades if t.get('status') == 'closed' and t.get('pnl') is not None]
        if not closed_trades:
            return 0.0
        
        gross_profit = sum(t['pnl'] for t in closed_trades if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in closed_trades if t['pnl'] < 0))
        
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        
        return gross_profit / gross_loss
    
    def calculate_expectancy(self, trades: List[Dict]) -> float:
        """
        Calculate expectancy (expected value per trade)
        :param trades: List of closed trade dictionaries
        :return: Expectancy value
        """
        closed_trades = [t for t in trades if t.get('status') == 'closed' and t.get('pnl') is not None]
        if not closed_trades:
            return 0.0
        
        total_pnl = sum(t['pnl'] for t in closed_trades)
        return total_pnl / len(closed_trades)
    
    def calculate_average_win_loss(self, trades: List[Dict]) -> Tuple[float, float]:
        """
        Calculate average win and average loss
        :param trades: List of closed trade dictionaries
        :return: Tuple of (average_win, average_loss)
        """
        closed_trades = [t for t in trades if t.get('status') == 'closed' and t.get('pnl') is not None]
        if not closed_trades:
            return 0.0, 0.0
        
        winning_trades = [t['pnl'] for t in closed_trades if t['pnl'] > 0]
        losing_trades = [t['pnl'] for t in closed_trades if t['pnl'] < 0]
        
        avg_win = sum(winning_trades) / len(winning_trades) if winning_trades else 0.0
        avg_loss = sum(losing_trades) / len(losing_trades) if losing_trades else 0.0
        
        return avg_win, abs(avg_loss)
    
    def calculate_win_loss_streaks(self, trades: List[Dict]) -> Tuple[int, int]:
        """
        Calculate longest win and loss streaks
        :param trades: List of closed trade dictionaries (ordered by time)
        :return: Tuple of (longest_win_streak, longest_loss_streak)
        """
        closed_trades = [t for t in trades if t.get('status') == 'closed' and t.get('pnl') is not None]
        if not closed_trades:
            return 0, 0
        
        # Sort by opened_at to ensure chronological order
        closed_trades.sort(key=lambda t: t.get('opened_at', ''))
        
        max_win_streak = 0
        max_loss_streak = 0
        current_win_streak = 0
        current_loss_streak = 0
        
        for trade in closed_trades:
            pnl = trade.get('pnl', 0)
            if pnl > 0:
                current_win_streak += 1
                current_loss_streak = 0
                max_win_streak = max(max_win_streak, current_win_streak)
            elif pnl < 0:
                current_loss_streak += 1
                current_win_streak = 0
                max_loss_streak = max(max_loss_streak, current_loss_streak)
            else:
                # Break streak on breakeven
                current_win_streak = 0
                current_loss_streak = 0
        
        return max_win_streak, max_loss_streak
    
    def calculate_recovery_factor(
        self,
        net_profit: float,
        max_drawdown: float
    ) -> float:
        """
        Calculate recovery factor (net profit / max drawdown)
        :param net_profit: Net profit
        :param max_drawdown: Maximum drawdown
        :return: Recovery factor
        """
        if max_drawdown == 0:
            return float('inf') if net_profit > 0 else 0.0
        
        return net_profit / max_drawdown
    
    def calculate_all_metrics(
        self,
        model_id: Optional[int],
        session_id: Optional[int],
        period: str = 'all_time'
    ) -> Dict[str, float]:
        """
        Calculate all performance metrics for a model/session
        :param model_id: Model ID (None for portfolio-level)
        :param session_id: Optional session ID
        :param period: Time period ('realtime', 'daily', 'weekly', 'monthly', 'yearly', 'all_time')
        :return: Dictionary of metric name -> value
        """
        # Get trades for the period
        trades = self.trade_logger.get_trade_history(
            model_id=model_id,
            session_id=session_id
        )
        
        # Filter by period if needed
        if period != 'all_time':
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            
            if period == 'daily':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == 'weekly':
                start_date = now - timedelta(days=7)
            elif period == 'monthly':
                start_date = now - timedelta(days=30)
            elif period == 'yearly':
                start_date = now - timedelta(days=365)
            else:  # realtime
                start_date = now - timedelta(hours=24)
            
            trades = [t for t in trades if t.get('opened_at') and 
                     datetime.fromisoformat(str(t['opened_at'])) >= start_date]
        
        # Get equity curve
        equity_curve = self.equity_tracker.get_equity_curve(
            model_id=model_id,
            session_id=session_id
        )
        
        # Calculate returns from trades
        closed_trades = [t for t in trades if t.get('status') == 'closed' and t.get('pnl') is not None]
        returns = []
        if closed_trades:
            # Calculate returns as percentage of initial balance
            # For simplicity, use P&L as return (can be improved with balance tracking)
            total_pnl = sum(t['pnl'] for t in closed_trades)
            # Approximate return (would need initial balance for accurate calculation)
            returns = [t['pnl'] / 10000.0 for t in closed_trades]  # Normalize to reasonable scale
        
        # Calculate all metrics
        metrics = {
            'win_rate': self.calculate_win_rate(trades),
            'profit_factor': self.calculate_profit_factor(trades),
            'expectancy': self.calculate_expectancy(trades),
        }
        
        if returns:
            metrics['sharpe_ratio'] = self.calculate_sharpe_ratio(returns)
            metrics['sortino_ratio'] = self.calculate_sortino_ratio(returns)
        
        if equity_curve:
            max_dd, max_dd_pct = self.calculate_max_drawdown(equity_curve)
            metrics['max_drawdown'] = max_dd
            metrics['max_drawdown_pct'] = max_dd_pct
        
        avg_win, avg_loss = self.calculate_average_win_loss(trades)
        metrics['average_win'] = avg_win
        metrics['average_loss'] = avg_loss
        
        win_streak, loss_streak = self.calculate_win_loss_streaks(trades)
        metrics['longest_win_streak'] = win_streak
        metrics['longest_loss_streak'] = loss_streak
        
        # Calculate total P&L
        total_pnl = sum(t.get('pnl', 0) for t in closed_trades)
        metrics['total_pnl'] = total_pnl
        
        if max_dd > 0:
            metrics['recovery_factor'] = self.calculate_recovery_factor(total_pnl, max_dd)
        else:
            metrics['recovery_factor'] = 0.0
        
        return metrics
    
    def update_metrics_in_db(
        self,
        model_id: Optional[int],
        session_id: Optional[int],
        period: str,
        metrics: Dict[str, float]
    ) -> None:
        """
        Update metrics in database
        :param model_id: Model ID (None for portfolio-level)
        :param session_id: Optional session ID
        :param period: Time period
        :param metrics: Dictionary of metric name -> value
        """
        try:
            conn = self.db._Database__get_connection()
            cursor = conn.cursor()
            
            for metric_type, value in metrics.items():
                cursor.execute("""
                    INSERT INTO performance_metrics
                    (model_id, session_id, metric_type, value, period, calculated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON DUPLICATE KEY UPDATE
                        value = ?,
                        calculated_at = ?
                """, (
                    model_id, session_id, metric_type, value, period, datetime.utcnow(),
                    value, datetime.utcnow()
                ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.logger.debug(f"Updated metrics in DB for model_id={model_id}, period={period}")
        except Exception as e:
            self.logger.error(f"Error updating metrics in DB: {e}", exc_info=True)
            raise
