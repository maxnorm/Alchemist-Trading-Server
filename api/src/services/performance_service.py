"""
Performance metrics service
Business logic for performance tracking
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict, Any
from schemas.performance import (
    PortfolioPerformanceResponse,
    EquityCurveResponse,
    EquityCurvePoint,
    ModelPerformanceResponse,
    PerformanceBreakdownResponse,
    AllocationResponse,
)
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def get_portfolio_performance(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    period: str = "all_time",
) -> PortfolioPerformanceResponse:
    """Get portfolio performance summary (aggregated across all models)"""
    # Get metrics from performance_metrics table (portfolio-level has model_id = NULL)
    query = """
        SELECT 
            metric_type,
            value
        FROM performance_metrics
        WHERE model_id IS NULL AND period = :period
    """

    metrics = {}
    try:
        result = db.execute(text(query), {"period": period})
        for row in result.fetchall():
            metrics[row[0]] = float(row[1])
    except Exception as e:
        logger.warning(f"Failed to get portfolio metrics: {e}")

    # Get trade counts from model_trades
    query = """
        SELECT 
            COUNT(*) as total_trades,
            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
            SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
            SUM(pnl) as total_pnl
        FROM model_trades
        WHERE status = 'closed' AND pnl IS NOT NULL
    """
    params = {}

    if start_date:
        query += " AND closed_at >= :start_date"
        params["start_date"] = start_date

    if end_date:
        query += " AND closed_at <= :end_date"
        params["end_date"] = end_date

    try:
        result = db.execute(text(query), params)
        row = result.fetchone()

        total_trades = int(row[0]) if row and row[0] else 0
        winning_trades = int(row[1]) if row and row[1] else 0
        losing_trades = int(row[2]) if row and row[2] else 0
        total_pnl = float(row[3]) if row and row[3] else 0.0

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

        # Calculate profit factor and expectancy from trades
        profit_factor = metrics.get("profit_factor")
        expectancy = metrics.get("expectancy")

        # Calculate total_pnl_pct if we have starting balance
        total_pnl_pct = None
        if start_date or period != "all_time":
            # Try to get starting balance from first trade or session
            start_balance_query = """
                SELECT start_balance FROM live_trading_sessions
                ORDER BY started_at ASC LIMIT 1
            """
            try:
                start_result = db.execute(text(start_balance_query))
                start_row = start_result.fetchone()
                if start_row and start_row[0] and start_row[0] > 0:
                    total_pnl_pct = (total_pnl / float(start_row[0])) * 100
            except Exception:
                pass

        return PortfolioPerformanceResponse(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            sharpe_ratio=metrics.get("sharpe_ratio"),
            max_drawdown=metrics.get("max_drawdown"),
            max_drawdown_pct=metrics.get("max_drawdown_pct"),
            profit_factor=profit_factor,
            expectancy=expectancy,
            period_start=start_date,
            period_end=end_date,
        )
    except Exception as e:
        logger.error(f"Failed to get portfolio performance: {e}")
        return PortfolioPerformanceResponse(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_pnl=0.0,
        )


def get_portfolio_equity_curve(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> EquityCurveResponse:
    """Get portfolio equity curve (model_id = NULL)"""
    query = """
        SELECT timestamp, balance, equity, drawdown_pct
        FROM equity_curve
        WHERE model_id IS NULL
    """
    params = {}

    if start_date:
        query += " AND timestamp >= :start_date"
        params["start_date"] = start_date

    if end_date:
        query += " AND timestamp <= :end_date"
        params["end_date"] = end_date

    query += " ORDER BY timestamp ASC"

    try:
        result = db.execute(text(query), params)
        rows = result.fetchall()

        data = [
            EquityCurvePoint(
                timestamp=row[0], balance=float(row[1]), equity=float(row[2])
            )
            for row in rows
        ]

        return EquityCurveResponse(data=data, total_points=len(data))
    except Exception as e:
        logger.warning(f"Failed to get portfolio equity curve: {e}")
        return EquityCurveResponse(data=[], total_points=0)


def list_model_performance(db: Session) -> List[ModelPerformanceResponse]:
    """List all model performance summaries"""
    query = """
        SELECT DISTINCT m.id, m.name, m.version
        FROM models m
        JOIN live_trading_sessions lts ON m.id = lts.model_id
        WHERE lts.status = 'active'
    """

    try:
        result = db.execute(text(query))
        models = result.fetchall()

        performances = []
        for model_row in models:
            model_id = model_row[0]
            perf = get_model_performance(db, model_id, "all_time")
            if perf:
                performances.append(perf)

        return performances
    except Exception as e:
        logger.error(f"Failed to list model performance: {e}")
        return []


def get_model_performance(
    db: Session, model_id: int, period: str = "all_time"
) -> Optional[ModelPerformanceResponse]:
    """Get model performance"""
    # Get metrics from performance_metrics table
    query = """
        SELECT 
            metric_type,
            value
        FROM performance_metrics
        WHERE model_id = :model_id AND period = :period
    """

    metrics = {}
    try:
        result = db.execute(text(query), {"model_id": model_id, "period": period})
        for row in result.fetchall():
            metrics[row[0]] = float(row[1])
    except Exception as e:
        logger.warning(f"Failed to get model metrics: {e}")

    # Get trade statistics
    query = """
        SELECT 
            COUNT(*) as total_trades,
            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
            SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
            SUM(pnl) as total_pnl
        FROM model_trades
        WHERE model_id = :model_id AND status = 'closed' AND pnl IS NOT NULL
    """

    try:
        result = db.execute(text(query), {"model_id": model_id})
        row = result.fetchone()

        if row and row[0]:
            total_trades = int(row[0])
            winning_trades = int(row[1]) if row[1] else 0
            losing_trades = int(row[2]) if row[2] else 0
            total_pnl = float(row[3]) if row[3] else 0.0
            win_rate = (
                (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
            )

            # Get model version
            version_query = "SELECT version FROM models WHERE id = :model_id"
            version_result = db.execute(text(version_query), {"model_id": model_id})
            version_row = version_result.fetchone()
            model_version = version_row[0] if version_row else f"model_{model_id}"

            return ModelPerformanceResponse(
                model_version=model_version,
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                win_rate=win_rate,
                total_pnl=total_pnl,
                sharpe_ratio=metrics.get("sharpe_ratio"),
                max_drawdown=metrics.get("max_drawdown"),
                max_drawdown_pct=metrics.get("max_drawdown_pct"),
            )
    except Exception as e:
        logger.error(f"Failed to get model performance: {e}")

    return None


def get_model_equity_curve(
    db: Session,
    model_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> EquityCurveResponse:
    """Get model equity curve"""
    query = """
        SELECT timestamp, balance, equity, drawdown_pct
        FROM equity_curve
        WHERE model_id = :model_id
    """
    params = {"model_id": model_id}

    if start_date:
        query += " AND timestamp >= :start_date"
        params["start_date"] = start_date

    if end_date:
        query += " AND timestamp <= :end_date"
        params["end_date"] = end_date

    query += " ORDER BY timestamp ASC"

    try:
        result = db.execute(text(query), params)
        rows = result.fetchall()

        data = [
            EquityCurvePoint(
                timestamp=row[0], balance=float(row[1]), equity=float(row[2])
            )
            for row in rows
        ]

        # Get model version
        version_query = "SELECT version FROM models WHERE id = :model_id"
        version_result = db.execute(text(version_query), {"model_id": model_id})
        version_row = version_result.fetchone()
        model_version = version_row[0] if version_row else f"model_{model_id}"

        return EquityCurveResponse(
            model_version=model_version, data=data, total_points=len(data)
        )
    except Exception as e:
        logger.warning(f"Failed to get model equity curve: {e}")
        return EquityCurveResponse(
            model_version=f"model_{model_id}", data=[], total_points=0
        )


def get_model_trades(
    db: Session,
    model_id: int,
    limit: int = 100,
    offset: int = 0,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> tuple[List[Dict[str, Any]], int]:
    """Get model trade history with pagination"""
    # Count total
    count_query = """
        SELECT COUNT(*) 
        FROM model_trades
        WHERE model_id = :model_id
    """
    params = {"model_id": model_id}

    if start_date:
        count_query += " AND opened_at >= :start_date"
        params["start_date"] = start_date

    if end_date:
        count_query += " AND opened_at <= :end_date"
        params["end_date"] = end_date

    try:
        count_result = db.execute(text(count_query), params)
        total = count_result.scalar() or 0
    except Exception as e:
        logger.warning(f"Failed to count trades: {e}")
        total = 0

    # Get trades
    query = """
        SELECT 
            id, session_id, model_id, order_uuid, symbol, action, entry_price,
            exit_price, volume, pnl, pnl_pips, commission, swap, status,
            opened_at, closed_at, duration_seconds
        FROM model_trades
        WHERE model_id = :model_id
    """

    if start_date:
        query += " AND opened_at >= :start_date"

    if end_date:
        query += " AND opened_at <= :end_date"

    query += " ORDER BY opened_at DESC LIMIT :limit OFFSET :offset"
    params.update({"limit": limit, "offset": offset})

    try:
        result = db.execute(text(query), params)
        rows = result.fetchall()

        trades = []
        for row in rows:
            # Map to frontend Trade interface
            status = row[13].upper() if row[13] else "OPEN"
            trades.append(
                {
                    "id": row[0],
                    "session_id": row[1],
                    "model_id": row[2],
                    "order_uuid": row[3],
                    "symbol": row[4],
                    "order_type": row[5],  # 'BUY' or 'SELL'
                    "entry_price": float(row[6]) if row[6] else None,
                    "exit_price": float(row[7]) if row[7] else None,
                    "volume": float(row[8]),
                    "pnl": float(row[9]) if row[9] else None,
                    "pnl_pips": float(row[10]) if row[10] else None,
                    "pnl_pct": None,  # Can be calculated if needed
                    "commission": float(row[11]) if row[11] else 0.0,
                    "swap": float(row[12]) if row[12] else 0.0,
                    "status": "CLOSED" if status == "CLOSED" else "OPEN",
                    "entry_time": row[14].isoformat() if row[14] else None,
                    "exit_time": row[15].isoformat() if row[15] else None,
                    "duration_seconds": row[16] if row[16] else None,
                }
            )

        return trades, total
    except Exception as e:
        logger.warning(f"Failed to get model trades: {e}")
        return [], 0


def get_model_statistics(
    db: Session, model_id: int, period: str = "all_time"
) -> Dict[str, Any]:
    """Get detailed model statistics"""
    # Get all metrics
    query = """
        SELECT metric_type, value
        FROM performance_metrics
        WHERE model_id = :model_id AND period = :period
    """

    stats = {}
    try:
        result = db.execute(text(query), {"model_id": model_id, "period": period})
        for row in result.fetchall():
            stats[row[0]] = float(row[1])
    except Exception as e:
        logger.warning(f"Failed to get model statistics: {e}")

    # Get additional trade statistics
    query = """
        SELECT 
            AVG(duration_seconds) as avg_duration,
            MIN(duration_seconds) as min_duration,
            MAX(duration_seconds) as max_duration
        FROM model_trades
        WHERE model_id = :model_id AND status = 'closed' AND duration_seconds IS NOT NULL
    """

    try:
        result = db.execute(text(query), {"model_id": model_id})
        row = result.fetchone()
        if row:
            stats["avg_duration_seconds"] = float(row[0]) if row[0] else None
            stats["min_duration_seconds"] = int(row[1]) if row[1] else None
            stats["max_duration_seconds"] = int(row[2]) if row[2] else None
    except Exception as e:
        logger.warning(f"Failed to get duration stats: {e}")

    return stats


def get_model_comparison(db: Session, model_id: int) -> Dict[str, Any]:
    """Compare paper vs live trading performance"""
    # Get paper trading metrics (sessions with specific status or from paper accounts)
    # This is a simplified version - in production, you'd distinguish paper vs live sessions
    paper_query = """
        SELECT 
            metric_type,
            value
        FROM performance_metrics
        WHERE model_id = :model_id AND period = 'all_time'
        LIMIT 1
    """

    # For now, return a placeholder structure
    # In Phase 7, this will properly distinguish paper vs live sessions
    return {
        "paper": {
            "sharpe_ratio": None,
            "win_rate": None,
            "profit_factor": None,
            "avg_trade": None,
        },
        "live": {
            "sharpe_ratio": None,
            "win_rate": None,
            "profit_factor": None,
            "avg_trade": None,
        },
        "difference": {
            "sharpe_ratio": None,
            "win_rate": None,
            "profit_factor": None,
            "avg_trade": None,
        },
    }


def get_performance_breakdown(
    db: Session, period: str = "day"
) -> List[PerformanceBreakdownResponse]:
    """Get P&L breakdown by period"""
    if period == "day":
        date_format = "DATE(closed_at)"
    elif period == "week":
        date_format = "YEARWEEK(closed_at)"
    elif period == "month":
        date_format = "DATE_FORMAT(closed_at, '%Y-%m')"
    else:
        date_format = "DATE(closed_at)"

    query = f"""
        SELECT 
            {date_format} as period,
            SUM(pnl) as pnl,
            COUNT(*) as trades,
            AVG(CASE WHEN pnl > 0 THEN 1.0 ELSE 0.0 END) * 100 as win_rate
        FROM model_trades
        WHERE status = 'closed' AND pnl IS NOT NULL
        GROUP BY {date_format}
        ORDER BY period DESC
        LIMIT 30
    """

    try:
        result = db.execute(text(query))
        rows = result.fetchall()

        breakdown = []
        for row in rows:
            breakdown.append(
                PerformanceBreakdownResponse(
                    period=str(row[0]),
                    pnl=float(row[1]) or 0.0,
                    trades=int(row[2]) or 0,
                    win_rate=float(row[3]) or 0.0,
                )
            )

        return breakdown
    except Exception as e:
        logger.warning(f"Failed to get performance breakdown: {e}")
        return []


def get_allocation(db: Session) -> AllocationResponse:
    """Get allocation by pair/model"""
    # By pair (from open positions)
    query = """
        SELECT symbol, SUM(volume * entry_price) as total_value
        FROM model_trades
        WHERE status = 'open'
        GROUP BY symbol
    """

    by_pair = {}
    try:
        result = db.execute(text(query))
        for row in result.fetchall():
            by_pair[row[0]] = float(row[1]) if row[1] else 0.0
    except Exception as e:
        logger.warning(f"Failed to get allocation by pair: {e}")

    # By model
    query = """
        SELECT m.id, SUM(mt.volume * mt.entry_price) as total_value
        FROM model_trades mt
        JOIN models m ON mt.model_id = m.id
        WHERE mt.status = 'open'
        GROUP BY m.id
    """

    by_model = {}
    try:
        result = db.execute(text(query))
        for row in result.fetchall():
            model_id = row[0]
            # Get model version
            version_query = "SELECT version FROM models WHERE id = :model_id"
            version_result = db.execute(text(version_query), {"model_id": model_id})
            version_row = version_result.fetchone()
            model_version = version_row[0] if version_row else f"model_{model_id}"
            by_model[model_version] = float(row[1]) if row[1] else 0.0
    except Exception as e:
        logger.warning(f"Failed to get allocation by model: {e}")

    return AllocationResponse(by_pair=by_pair, by_model=by_model)


def get_realtime_metrics(db: Session) -> Dict[str, Any]:
    """Get real-time performance metrics for all active models"""
    query = """
        SELECT 
            m.id,
            m.version,
            lts.current_balance,
            lts.start_balance,
            (lts.current_balance - lts.start_balance) as pnl
        FROM models m
        JOIN live_trading_sessions lts ON m.id = lts.model_id
        WHERE lts.status = 'active'
    """

    try:
        result = db.execute(text(query))
        models = []
        for row in result.fetchall():
            models.append(
                {
                    "model_id": row[0],
                    "model_version": row[1],
                    "current_balance": float(row[2]),
                    "start_balance": float(row[3]),
                    "pnl": float(row[4]),
                }
            )

        return {"models": models, "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Failed to get realtime metrics: {e}")
        return {"models": [], "timestamp": datetime.utcnow().isoformat()}


def export_portfolio_report(
    db: Session,
    format: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Export portfolio report (placeholder - actual implementation would generate PDF/CSV)"""
    # This is a placeholder - actual implementation would use libraries like reportlab for PDF
    # or csv module for CSV
    return {
        "format": format,
        "message": "Export functionality not yet implemented",
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
    }


def export_model_report(db: Session, model_id: int, format: str) -> Dict[str, Any]:
    """Export model report (placeholder - actual implementation would generate PDF/CSV)"""
    return {
        "format": format,
        "model_id": model_id,
        "message": "Export functionality not yet implemented",
    }
