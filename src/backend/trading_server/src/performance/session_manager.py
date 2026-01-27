"""
Session Manager
Manages trading session lifecycle for performance tracking
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from database import Database


class SessionManager:
    """
    Manages trading session lifecycle
    Tracks session start/end balances and links models to trading sessions
    """

    def __init__(
        self, db: Optional[Database] = None, logger: Optional[logging.Logger] = None
    ):
        """
        Initialize session manager
        :param db: Database instance
        :param logger: Logger instance
        """
        self.db = db or Database()
        self.logger = logger or logging.getLogger(__name__)

    def create_session(self, model_id: int, start_balance: float) -> int:
        """
        Create a new trading session
        :param model_id: Model ID
        :param start_balance: Starting balance
        :return: Session ID
        """
        try:
            query = """
                INSERT INTO live_trading_sessions
                (model_id, status, start_balance, current_balance, high_water_mark)
                VALUES (:model_id, 'active', :start_balance, :current_balance, :high_water_mark)
                RETURNING id
            """

            params = {
                "model_id": model_id,
                "start_balance": start_balance,
                "current_balance": start_balance,
                "high_water_mark": start_balance,
            }

            result = self.db.execute_one(query, params)
            if result:
                session_id = result[0]
                self.logger.info(
                    f"Created trading session {session_id} for model {model_id}"
                )
                return session_id
            raise RuntimeError("Failed to create trading session")
        except SQLAlchemyError as e:
            self.logger.error(f"Error creating session: {e}", exc_info=True)
            raise

    def end_session(self, session_id: int, reason: str, end_balance: float) -> None:
        """
        End a trading session
        :param session_id: Session ID
        :param reason: Reason for ending (e.g., 'user_stopped', 'kill_switch')
        :param end_balance: Ending balance
        """
        try:
            query = """
                UPDATE live_trading_sessions
                SET status = 'stopped',
                    ended_at = :ended_at,
                    ended_reason = :ended_reason,
                    current_balance = :current_balance
                WHERE id = :session_id
            """

            params = {
                "ended_at": datetime.utcnow(),
                "ended_reason": reason,
                "current_balance": end_balance,
                "session_id": session_id,
            }

            with self.db.execute_query() as conn:
                conn.execute(text(query), params)

            self.logger.info(f"Ended trading session {session_id}: {reason}")
        except SQLAlchemyError as e:
            self.logger.error(f"Error ending session: {e}", exc_info=True)
            raise

    def pause_session(self, session_id: int) -> None:
        """
        Pause a trading session
        :param session_id: Session ID
        """
        try:
            query = """
                UPDATE live_trading_sessions
                SET status = 'paused'
                WHERE id = :session_id
            """

            params = {"session_id": session_id}

            with self.db.execute_query() as conn:
                conn.execute(text(query), params)

            self.logger.info(f"Paused trading session {session_id}")
        except SQLAlchemyError as e:
            self.logger.error(f"Error pausing session: {e}", exc_info=True)
            raise

    def resume_session(self, session_id: int) -> None:
        """
        Resume a paused trading session
        :param session_id: Session ID
        """
        try:
            query = """
                UPDATE live_trading_sessions
                SET status = 'active'
                WHERE id = :session_id
            """

            params = {"session_id": session_id}

            with self.db.execute_query() as conn:
                conn.execute(text(query), params)

            self.logger.info(f"Resumed trading session {session_id}")
        except SQLAlchemyError as e:
            self.logger.error(f"Error resuming session: {e}", exc_info=True)
            raise

    def update_balance(self, session_id: int, current_balance: float) -> None:
        """
        Update current balance and high water mark for a session
        :param session_id: Session ID
        :param current_balance: Current balance
        """
        try:
            # Get current high water mark
            result = self.db.execute_one(
                "SELECT high_water_mark FROM live_trading_sessions WHERE id = :session_id",
                {"session_id": session_id},
            )
            high_water_mark = result[0] if result else current_balance

            # Update high water mark if current balance is higher
            if current_balance > high_water_mark:
                high_water_mark = current_balance

            query = """
                UPDATE live_trading_sessions
                SET current_balance = :current_balance,
                    high_water_mark = :high_water_mark
                WHERE id = :session_id
            """

            params = {
                "current_balance": current_balance,
                "high_water_mark": high_water_mark,
                "session_id": session_id,
            }

            with self.db.execute_query() as conn:
                conn.execute(text(query), params)
        except SQLAlchemyError as e:
            self.logger.error(f"Error updating balance: {e}", exc_info=True)
            raise

    def get_active_sessions(self, model_id: Optional[int] = None) -> List[Dict]:
        """
        Get all active trading sessions
        :param model_id: Optional model ID to filter by
        :return: List of session dictionaries
        """
        try:
            if model_id:
                query = """
                    SELECT * FROM live_trading_sessions
                    WHERE status = 'active' AND model_id = :model_id
                    ORDER BY started_at DESC
                """
                params = {"model_id": model_id}
            else:
                query = """
                    SELECT * FROM live_trading_sessions
                    WHERE status = 'active'
                    ORDER BY started_at DESC
                """
                params = None

            rows = self.db.execute_with_result(query, params)

            # Convert rows to dictionaries (assuming standard column order)
            sessions = []
            for row in rows:
                session_dict = {
                    "id": row[0],
                    "model_id": row[1],
                    "status": row[2],
                    "start_balance": float(row[3]) if row[3] else None,
                    "current_balance": float(row[4]) if row[4] else None,
                    "high_water_mark": float(row[5]) if row[5] else None,
                    "started_at": row[6],
                    "ended_at": row[7],
                    "ended_reason": row[8],
                }
                sessions.append(session_dict)

            return sessions
        except SQLAlchemyError as e:
            self.logger.error(f"Error getting active sessions: {e}", exc_info=True)
            return []

    def get_session(self, session_id: int) -> Optional[Dict]:
        """
        Get a specific session by ID
        :param session_id: Session ID
        :return: Session dictionary or None
        """
        try:
            query = """
                SELECT * FROM live_trading_sessions WHERE id = :session_id
            """

            params = {"session_id": session_id}
            row = self.db.execute_one(query, params)

            if row:
                session_dict = {
                    "id": row[0],
                    "model_id": row[1],
                    "status": row[2],
                    "start_balance": float(row[3]) if row[3] else None,
                    "current_balance": float(row[4]) if row[4] else None,
                    "high_water_mark": float(row[5]) if row[5] else None,
                    "started_at": row[6],
                    "ended_at": row[7],
                    "ended_reason": row[8],
                }
                return session_dict
            return None
        except SQLAlchemyError as e:
            self.logger.error(f"Error getting session: {e}", exc_info=True)
            return None
