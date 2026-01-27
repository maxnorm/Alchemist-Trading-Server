"""
Equity Tracker
Tracks periodic equity snapshots for performance analysis
"""

import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from database import Database


class EquityTracker:
    """
    Tracks periodic equity snapshots
    Records balance, equity, and drawdown for chart rendering
    """

    def __init__(
        self,
        snapshot_interval_minutes: int = 5,
        db: Optional[Database] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize equity tracker
        :param snapshot_interval_minutes: Interval between snapshots in minutes
        :param db: Database instance
        :param logger: Logger instance
        """
        self.snapshot_interval_minutes = snapshot_interval_minutes
        self.db = db or Database()
        self.logger = logger or logging.getLogger(__name__)
        self._tracking_sessions: Dict[str, Any] = {}  # session_id -> tracking info
        self._tracking_lock = threading.Lock()

    def record_snapshot(
        self,
        model_id: Optional[int],  # None for portfolio-level
        session_id: int,
        balance: float,
        equity: float,
        unrealized_pnl: float = 0.0,
    ) -> None:
        """
        Record an equity snapshot
        :param model_id: Model ID (None for portfolio-level)
        :param session_id: Trading session ID
        :param balance: Account balance
        :param equity: Account equity (balance + unrealized P&L)
        :param unrealized_pnl: Unrealized P&L
        """
        try:
            from sqlalchemy import text
            from sqlalchemy.exc import SQLAlchemyError

            # Calculate drawdown percentage
            # Get high water mark from session
            result = self.db.execute_one(
                "SELECT high_water_mark FROM live_trading_sessions WHERE id = :session_id",
                {"session_id": session_id},
            )
            high_water_mark = result[0] if result else equity

            # Calculate drawdown
            if high_water_mark > 0:
                drawdown_pct = ((high_water_mark - equity) / high_water_mark) * 100
            else:
                drawdown_pct = 0.0

            # Insert snapshot
            query = """
                INSERT INTO equity_curve
                (model_id, session_id, timestamp, equity, balance, drawdown_pct, unrealized_pnl)
                VALUES (:model_id, :session_id, :timestamp, :equity, :balance, :drawdown_pct, :unrealized_pnl)
            """

            params = {
                "model_id": model_id,
                "session_id": session_id,
                "timestamp": datetime.utcnow(),
                "equity": equity,
                "balance": balance,
                "drawdown_pct": drawdown_pct,
                "unrealized_pnl": unrealized_pnl,
            }

            with self.db.execute_query() as conn:
                conn.execute(text(query), params)

            self.logger.debug(
                f"Recorded equity snapshot: session_id={session_id}, "
                f"equity={equity}, balance={balance}, drawdown={drawdown_pct:.2f}%"
            )
        except SQLAlchemyError as e:
            self.logger.error(f"Error recording equity snapshot: {e}", exc_info=True)
            raise

    def get_equity_curve(
        self,
        model_id: Optional[int] = None,
        session_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict]:
        """
        Get equity curve data
        :param model_id: Optional model ID to filter by
        :param session_id: Optional session ID to filter by
        :param start_date: Optional start date filter
        :param end_date: Optional end date filter
        :return: List of equity curve points
        """
        try:
            from sqlalchemy.exc import SQLAlchemyError

            query = "SELECT * FROM equity_curve WHERE 1=1"
            params: Dict[str, Any] = {}

            if model_id is not None:
                query += " AND model_id = :model_id"
                params["model_id"] = model_id
            else:
                # For portfolio-level, model_id should be NULL
                query += " AND model_id IS NULL"

            if session_id:
                query += " AND session_id = :session_id"
                params["session_id"] = session_id

            if start_date:
                query += " AND timestamp >= :start_date"
                params["start_date"] = start_date

            if end_date:
                query += " AND timestamp <= :end_date"
                params["end_date"] = end_date

            query += " ORDER BY timestamp ASC"

            rows = self.db.execute_with_result(query, params if params else None)

            # Convert rows to dictionaries
            curve = []
            for row in rows:
                curve_dict = {
                    "id": row[0],
                    "model_id": row[1],
                    "session_id": row[2],
                    "timestamp": row[3],
                    "equity": float(row[4]) if row[4] else None,
                    "balance": float(row[5]) if row[5] else None,
                    "drawdown_pct": float(row[6]) if row[6] else None,
                    "unrealized_pnl": float(row[7]) if row[7] else None,
                }
                curve.append(curve_dict)

            return curve
        except SQLAlchemyError as e:
            self.logger.error(f"Error getting equity curve: {e}", exc_info=True)
            return []

    def start_tracking(self, model_id: Optional[int], session_id: int) -> None:
        """
        Start tracking a session (for background periodic snapshots)
        :param model_id: Model ID (None for portfolio-level)
        :param session_id: Trading session ID
        """
        with self._tracking_lock:
            self._tracking_sessions[str(session_id)] = {
                "model_id": model_id,
                "session_id": session_id,
                "last_snapshot": datetime.utcnow(),
            }

        self.logger.info(f"Started equity tracking for session {session_id}")

    def stop_tracking(self, session_id: int) -> None:
        """
        Stop tracking a session
        :param session_id: Trading session ID
        """
        with self._tracking_lock:
            session_key = str(session_id)
            if session_key in self._tracking_sessions:
                del self._tracking_sessions[session_key]

        self.logger.info(f"Stopped equity tracking for session {session_id}")

    def should_record_snapshot(self, session_id: int) -> bool:
        """
        Check if it's time to record a snapshot for a session
        :param session_id: Trading session ID
        :return: True if snapshot should be recorded
        """
        with self._tracking_lock:
            session_key = str(session_id)
            if session_key not in self._tracking_sessions:
                return False

            tracking_info = self._tracking_sessions[session_key]
            last_snapshot = tracking_info["last_snapshot"]
            interval = timedelta(minutes=self.snapshot_interval_minutes)

            if datetime.utcnow() - last_snapshot >= interval:
                tracking_info["last_snapshot"] = datetime.utcnow()
                return True

            return False
