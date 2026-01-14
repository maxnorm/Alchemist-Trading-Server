"""
Trading control service
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from typing import List, Optional, cast, Any
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
            "SELECT COUNT(*) FROM orders WHERE state IN ('NEW', 'PARTIALLY_FILLED', 'FILLED')"
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

    # Calculate total equity and balance from MT5 accounts
    total_equity = None
    total_balance = None
    try:
        result = db.execute(
            text("""
                SELECT 
                    COALESCE(SUM(equity), 0) as total_equity,
                    COALESCE(SUM(balance), 0) as total_balance
                FROM mt5_accounts
                WHERE is_active = TRUE
            """)
        )
        row = result.fetchone()
        if row and (row[0] is not None or row[1] is not None):
            total_equity = float(row[0]) if row[0] is not None else None
            total_balance = float(row[1]) if row[1] is not None else None
    except Exception as e:
        logger.warning(f"Failed to get equity/balance: {e}")

    return TradingStatusResponse(
        is_active=len(active_experiments) > 0
        and not kill_switch_active
        and not circuit_breaker_active,
        active_experiments=active_experiments,
        open_positions=open_positions,
        active_positions=open_positions,  # Alias for dashboard compatibility
        kill_switch_active=kill_switch_active,
        circuit_breaker_active=circuit_breaker_active,
        total_equity=total_equity,
        total_balance=total_balance,
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
                breaker_type=row[1],  # Alias for dashboard compatibility
                loss_threshold=float(row[2]) if row[2] else None,
                threshold_value=float(row[2]) if row[2] else None,  # Alias
                current_loss=float(row[3]) if row[3] else None,
                trigger_value=float(row[3]) if row[3] else None,  # Alias
                activated_at=row[4] if row[4] else None,
                triggered_at=row[4] if row[4] else None,  # Alias
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
        # Cast to CursorResult to access rowcount attribute
        cursor_result = cast(CursorResult[Any], result)
        return cursor_result.rowcount > 0
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
                WHERE state IN ('NEW', 'PARTIALLY_FILLED', 'FILLED')
                ORDER BY entry_time DESC
            """
            )
        )
        rows = result.fetchall()

        positions = []
        for row in rows:
            entry_time = row[8]
            entry_price = float(row[5])
            volume = float(row[6])
            symbol = row[3]
            
            # Get current price from latest tick data (if available)
            current_price = None
            unrealized_pnl = None
            unrealized_pnl_pct = None
            
            try:
                price_result = db.execute(
                    text("""
                        SELECT bid, ask
                        FROM tick_data
                        WHERE symbol = :symbol
                        ORDER BY timestamp DESC
                        LIMIT 1
                    """),
                    {"symbol": symbol}
                )
                price_row = price_result.fetchone()
                if price_row:
                    # Use mid price (average of bid/ask)
                    bid = float(price_row[0]) if price_row[0] else None
                    ask = float(price_row[1]) if price_row[1] else None
                    if bid is not None and ask is not None:
                        current_price = (bid + ask) / 2.0
                        
                        # Calculate unrealized P&L
                        order_type = row[4]
                        if current_price and entry_price:
                            if order_type.upper() == 'BUY':
                                unrealized_pnl = (current_price - entry_price) * volume
                            elif order_type.upper() == 'SELL':
                                unrealized_pnl = (entry_price - current_price) * volume
                            
                            if unrealized_pnl is not None and entry_price > 0:
                                unrealized_pnl_pct = (unrealized_pnl / (entry_price * volume)) * 100
            except Exception as e:
                logger.debug(f"Could not get current price for {symbol}: {e}")
            
            positions.append(
                PositionResponse(
                    id=row[0],
                    experiment_id=row[1],
                    account_login=row[2],
                    symbol=symbol,
                    order_type=row[4],
                    entry_price=entry_price,
                    volume=volume,
                    pnl=float(row[7]) if row[7] else None,
                    entry_time=entry_time,
                    opened_at=entry_time.isoformat() if entry_time else None,
                    status=row[9],
                    current_price=current_price,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_pct=unrealized_pnl_pct,
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
        # If no pairs found in database, return fallback list
        if not pairs:
            logger.warning("No currency pairs found in database, using fallback list")
            return ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]
        return pairs
    except Exception as e:
        logger.error(f"Failed to get currency pairs: {e}")
        # Return common pairs as fallback
        return ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]
