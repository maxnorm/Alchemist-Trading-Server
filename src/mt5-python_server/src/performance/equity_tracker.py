"""
Equity Tracker
Tracks periodic equity snapshots for performance analysis
"""

import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict
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
        self._tracking_sessions = {}  # session_id -> tracking info
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
            # Calculate drawdown percentage
            # Get high water mark from session
            conn = self.db._Database__get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT high_water_mark FROM live_trading_sessions WHERE id = ?
            """,
                (session_id,),
            )
            result = cursor.fetchone()
            high_water_mark = result[0] if result else equity

            # Calculate drawdown
            if high_water_mark > 0:
                drawdown_pct = ((high_water_mark - equity) / high_water_mark) * 100
            else:
                drawdown_pct = 0.0

            # Insert snapshot
            cursor.execute(
                """
                INSERT INTO equity_curve
                (model_id, session_id, timestamp, equity, balance, drawdown_pct, unrealized_pnl)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    model_id,
                    session_id,
                    datetime.utcnow(),
                    equity,
                    balance,
                    drawdown_pct,
                    unrealized_pnl,
                ),
            )

            conn.commit()
            cursor.close()
            conn.close()

            self.logger.debug(
                f"Recorded equity snapshot: session_id={session_id}, "
                f"equity={equity}, balance={balance}, drawdown={drawdown_pct:.2f}%"
            )
        except Exception as e:
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
            conn = self.db._Database__get_connection()
            cursor = conn.cursor(dictionary=True)

            query = "SELECT * FROM equity_curve WHERE 1=1"
            params = []

            if model_id is not None:
                query += " AND model_id = ?"
                params.append(model_id)
            else:
                # For portfolio-level, model_id should be NULL
                query += " AND model_id IS NULL"

            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)

            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date)

            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date)

            query += " ORDER BY timestamp ASC"

            cursor.execute(query, tuple(params))
            curve = cursor.fetchall()
            cursor.close()
            conn.close()

            return curve
        except Exception as e:
            self.logger.error(f"Error getting equity curve: {e}", exc_info=True)
            return []

    def start_tracking(self, model_id: Optional[int], session_id: int) -> None:
        """
        Start tracking a session (for background periodic snapshots)
        :param model_id: Model ID (None for portfolio-level)
        :param session_id: Trading session ID
        """
        with self._tracking_lock:
            self._tracking_sessions[session_id] = {
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
            if session_id in self._tracking_sessions:
                del self._tracking_sessions[session_id]

        self.logger.info(f"Stopped equity tracking for session {session_id}")

    def should_record_snapshot(self, session_id: int) -> bool:
        """
        Check if it's time to record a snapshot for a session
        :param session_id: Trading session ID
        :return: True if snapshot should be recorded
        """
        with self._tracking_lock:
            if session_id not in self._tracking_sessions:
                return False

            tracking_info = self._tracking_sessions[session_id]
            last_snapshot = tracking_info["last_snapshot"]
            interval = timedelta(minutes=self.snapshot_interval_minutes)

            if datetime.utcnow() - last_snapshot >= interval:
                tracking_info["last_snapshot"] = datetime.utcnow()
                return True

            return False
