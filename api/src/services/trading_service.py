"""
Trading control service
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime
from schemas.trading import (
    TradingStatusResponse,
    KillSwitchStatusResponse,
    CircuitBreakerStatusResponse,
    PositionResponse,
)
from config import settings
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_trading_status(db: Session) -> TradingStatusResponse:
    """Get overall trading status"""
    # Get active experiments
    result = db.execute(text("SELECT id FROM experiments WHERE status = 'training'"))
    active_experiments = [row[0] for row in result.fetchall()]

    # Get open positions
    result = db.execute(
        text(
            "SELECT COUNT(*) FROM orders WHERE state IN ('new', 'partially_filled', 'filled')"
        )
    )
    open_positions = result.scalar() or 0

    # Get kill switch status
    kill_switch_active = check_kill_switch_status()

    # Get circuit breaker status (from database if available)
    circuit_breaker_active = False
    try:
        result = db.execute(
            text(
                "SELECT is_active FROM circuit_breaker_status ORDER BY updated_at DESC LIMIT 1"
            )
        )
        row = result.fetchone()
        if row:
            circuit_breaker_active = bool(row[0])
    except Exception:
        # Table might not exist yet
        pass

    return TradingStatusResponse(
        is_active=len(active_experiments) > 0
        and not kill_switch_active
        and not circuit_breaker_active,
        active_experiments=active_experiments,
        open_positions=open_positions,
        kill_switch_active=kill_switch_active,
        circuit_breaker_active=circuit_breaker_active,
    )


def check_kill_switch_status() -> bool:
    """Check if kill switch is active"""
    kill_switch_path = Path(settings.kill_switch_file)
    return kill_switch_path.exists()


def get_kill_switch_status() -> KillSwitchStatusResponse:
    """Get kill switch status"""
    is_active = check_kill_switch_status()
    reason = None
    activated_at = None

    if is_active:
        # Try to read reason from file
        try:
            kill_switch_path = Path(settings.kill_switch_file)
            if kill_switch_path.exists():
                content = kill_switch_path.read_text().strip()
                if content:
                    reason = content
                activated_at = datetime.fromtimestamp(kill_switch_path.stat().st_mtime)
        except Exception as e:
            logger.warning(f"Failed to read kill switch file: {e}")

    return KillSwitchStatusResponse(
        is_active=is_active, reason=reason, activated_at=activated_at
    )


def trigger_kill_switch(reason: str = "API trigger") -> bool:
    """Trigger kill switch"""
    try:
        kill_switch_path = Path(settings.kill_switch_file)
        kill_switch_path.parent.mkdir(parents=True, exist_ok=True)
        kill_switch_path.write_text(reason)
        logger.critical(f"Kill switch triggered via API: {reason}")
        return True
    except Exception as e:
        logger.error(f"Failed to trigger kill switch: {e}")
        return False


def reset_kill_switch() -> bool:
    """Reset kill switch"""
    try:
        kill_switch_path = Path(settings.kill_switch_file)
        if kill_switch_path.exists():
            kill_switch_path.unlink()
            logger.info("Kill switch reset via API")
        return True
    except Exception as e:
        logger.error(f"Failed to reset kill switch: {e}")
        return False


def get_circuit_breaker_status(db: Session) -> CircuitBreakerStatusResponse:
    """Get circuit breaker status"""
    try:
        result = db.execute(
            text(
                """
                SELECT is_active, reason, loss_threshold, current_loss, updated_at
                FROM circuit_breaker_status
                ORDER BY updated_at DESC
                LIMIT 1
            """
            )
        )
        row = result.fetchone()

        if row:
            return CircuitBreakerStatusResponse(
                is_active=bool(row[0]),
                reason=row[1],
                loss_threshold=float(row[2]) if row[2] else None,
                current_loss=float(row[3]) if row[3] else None,
                activated_at=row[4] if row[4] else None,
            )
    except Exception as e:
        logger.warning(f"Failed to get circuit breaker status: {e}")

    return CircuitBreakerStatusResponse(is_active=False)


def reset_circuit_breaker(db: Session) -> bool:
    """Reset circuit breaker"""
    try:
        result = db.execute(
            text(
                """
                UPDATE circuit_breaker_status
                SET is_active = FALSE, reason = NULL, updated_at = NOW()
                WHERE is_active = TRUE
            """
            )
        )
        db.commit()
        return result.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to reset circuit breaker: {e}")
        return False


def get_open_positions(db: Session) -> List[PositionResponse]:
    """Get open positions"""
    try:
        result = db.execute(
            text(
                """
                SELECT id, experiment_id, account_login, symbol, order_type,
                       entry_price, volume, pnl, entry_time, status
                FROM orders
                WHERE state IN ('new', 'partially_filled', 'filled')
                ORDER BY entry_time DESC
            """
            )
        )
        rows = result.fetchall()

        positions = []
        for row in rows:
            positions.append(
                PositionResponse(
                    id=row[0],
                    experiment_id=row[1],
                    account_login=row[2],
                    symbol=row[3],
                    order_type=row[4],
                    entry_price=float(row[5]),
                    volume=float(row[6]),
                    pnl=float(row[7]) if row[7] else None,
                    entry_time=row[8],
                    status=row[9],
                )
            )

        return positions
    except Exception as e:
        logger.error(f"Failed to get open positions: {e}")
        return []


def get_trade_history(
    db: Session, experiment_id: Optional[int] = None, limit: int = 100
) -> List[PositionResponse]:
    """Get trade history"""
    query = """
        SELECT id, experiment_id, account_login, symbol, order_type,
               entry_price, volume, pnl, entry_time, status
        FROM orders
        WHERE 1=1
    """
    params = {}

    if experiment_id:
        query += " AND experiment_id = :experiment_id"
        params["experiment_id"] = experiment_id

    query += " ORDER BY entry_time DESC LIMIT :limit"
    params["limit"] = limit

    try:
        result = db.execute(text(query), params)
        rows = result.fetchall()

        trades = []
        for row in rows:
            trades.append(
                PositionResponse(
                    id=row[0],
                    experiment_id=row[1],
                    account_login=row[2],
                    symbol=row[3],
                    order_type=row[4],
                    entry_price=float(row[5]),
                    volume=float(row[6]),
                    pnl=float(row[7]) if row[7] else None,
                    entry_time=row[8],
                    status=row[9],
                )
            )

        return trades
    except Exception as e:
        logger.error(f"Failed to get trade history: {e}")
        return []


def get_available_currency_pairs(db: Session) -> List[str]:
    """Get available currency pairs from database"""
    try:
        result = db.execute(text("SELECT symbol FROM forex_pairs ORDER BY symbol"))
        pairs = [row[0] for row in result.fetchall()]
        return pairs
    except Exception as e:
        logger.error(f"Failed to get currency pairs: {e}")
        # Return common pairs as fallback
        return ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]
