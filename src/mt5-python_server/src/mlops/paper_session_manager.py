"""
Paper Trading Session Manager

Manages paper trading sessions for model validation.
Tracks session metrics in real-time and calculates validation metrics.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PaperSession:
    """Paper trading session data"""

    id: int
    model_id: int
    status: str  # running, completed, stopped
    start_balance: float
    current_balance: float
    total_trades: int
    winning_trades: int
    pnl: float
    sharpe_ratio: Optional[float]
    max_drawdown: Optional[float]
    started_at: datetime
    ended_at: Optional[datetime]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "model_id": self.model_id,
            "status": self.status,
            "start_balance": self.start_balance,
            "current_balance": self.current_balance,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "pnl": self.pnl,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }


class PaperTradingSessionManager:
    """
    Manages paper trading sessions for model validation.

    Responsibilities:
    - Create paper trading sessions
    - Track session metrics in real-time
    - Calculate validation metrics
    - Link sessions to models
    """

    def __init__(self, database):
        """
        Initialize paper trading session manager

        :param database: Database instance
        """
        self.db = database

    def create_session(
        self, model_id: int, start_balance: float
    ) -> Optional[PaperSession]:
        """
        Create a new paper trading session

        :param model_id: Model ID
        :param start_balance: Starting balance for paper trading
        :return: PaperSession instance
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO paper_trading_sessions (
                    model_id, status, start_balance, current_balance, started_at
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                (model_id, "running", start_balance, start_balance, datetime.now()),
            )

            session_id = cursor.lastrowid
            conn.commit()
            cursor.close()

            logger.info(
                f"Created paper trading session {session_id} for model {model_id}"
            )

            return self.get_session(session_id)

        except Exception as e:
            logger.error(f"Error creating paper trading session: {e}", exc_info=True)
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def get_session(self, session_id: int) -> Optional[PaperSession]:
        """
        Get session by ID

        :param session_id: Session ID
        :return: PaperSession instance or None
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, model_id, status, start_balance, current_balance,
                       total_trades, winning_trades, pnl, sharpe_ratio, max_drawdown,
                       started_at, ended_at
                FROM paper_trading_sessions
                WHERE id = %s
                """,
                (session_id,),
            )

            row = cursor.fetchone()
            cursor.close()

            if not row:
                return None

            (
                id_val,
                model_id,
                status,
                start_balance,
                current_balance,
                total_trades,
                winning_trades,
                pnl,
                sharpe_ratio,
                max_drawdown,
                started_at,
                ended_at,
            ) = row

            return PaperSession(
                id=id_val,
                model_id=model_id,
                status=status,
                start_balance=start_balance,
                current_balance=current_balance,
                total_trades=total_trades or 0,
                winning_trades=winning_trades or 0,
                pnl=pnl or 0.0,
                sharpe_ratio=float(sharpe_ratio) if sharpe_ratio else None,
                max_drawdown=float(max_drawdown) if max_drawdown else None,
                started_at=started_at,
                ended_at=ended_at,
            )

        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}", exc_info=True)
            return None
        finally:
            if conn:
                conn.close()

    def update_session_metrics(
        self,
        session_id: int,
        balance: Optional[float] = None,
        total_trades: Optional[int] = None,
        winning_trades: Optional[int] = None,
        pnl: Optional[float] = None,
    ) -> bool:
        """
        Update session metrics in real-time

        :param session_id: Session ID
        :param balance: Current balance
        :param total_trades: Total number of trades
        :param winning_trades: Number of winning trades
        :param pnl: Current P&L
        :return: True if successful
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Build update query dynamically
            updates = []
            params = []

            if balance is not None:
                updates.append("current_balance = %s")
                params.append(balance)

            if total_trades is not None:
                updates.append("total_trades = %s")
                params.append(total_trades)

            if winning_trades is not None:
                updates.append("winning_trades = %s")
                params.append(winning_trades)

            if pnl is not None:
                updates.append("pnl = %s")
                params.append(pnl)

            if not updates:
                return True  # Nothing to update

            params.append(session_id)

            cursor.execute(
                f"UPDATE paper_trading_sessions SET {', '.join(updates)} WHERE id = %s",
                params,
            )

            conn.commit()
            cursor.close()

            return True

        except Exception as e:
            logger.error(f"Error updating session metrics: {e}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def end_session(
        self, session_id: int, final_metrics: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        End a paper trading session and calculate final metrics

        :param session_id: Session ID
        :param final_metrics: Optional final metrics dictionary
        :return: Final metrics dictionary
        """
        conn = None
        try:
            session = self.get_session(session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")

            if session.status != "running":
                logger.warning(
                    f"Session {session_id} is not running, status: {session.status}"
                )
                return session.to_dict()

            # Calculate metrics if not provided
            if not final_metrics:
                final_metrics = self._calculate_metrics(session)

            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE paper_trading_sessions
                SET status = 'completed',
                    current_balance = %s,
                    total_trades = %s,
                    winning_trades = %s,
                    pnl = %s,
                    sharpe_ratio = %s,
                    max_drawdown = %s,
                    ended_at = %s
                WHERE id = %s
                """,
                (
                    final_metrics.get("current_balance", session.current_balance),
                    final_metrics.get("total_trades", session.total_trades),
                    final_metrics.get("winning_trades", session.winning_trades),
                    final_metrics.get("pnl", session.pnl),
                    final_metrics.get("sharpe_ratio"),
                    final_metrics.get("max_drawdown"),
                    datetime.now(),
                    session_id,
                ),
            )

            conn.commit()
            cursor.close()

            logger.info(f"Ended paper trading session {session_id}")

            # Return updated session
            session = self.get_session(session_id)
            if session is None:
                raise ValueError(f"Session {session_id} not found after ending")
            return session.to_dict()

        except Exception as e:
            logger.error(f"Error ending session: {e}", exc_info=True)
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def stop_session(self, session_id: int) -> bool:
        """
        Stop a running session (mark as stopped, not completed)

        :param session_id: Session ID
        :return: True if successful
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE paper_trading_sessions
                SET status = 'stopped', ended_at = %s
                WHERE id = %s AND status = 'running'
                """,
                (datetime.now(), session_id),
            )

            conn.commit()
            cursor.close()

            logger.info(f"Stopped paper trading session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error stopping session: {e}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def get_session_metrics(self, session_id: int) -> Dict[str, Any]:
        """
        Get current session metrics

        :param session_id: Session ID
        :return: Metrics dictionary
        """
        session = self.get_session(session_id)
        if not session:
            return {}

        return session.to_dict()

    def get_sessions_by_model(self, model_id: int) -> List[PaperSession]:
        """
        Get all sessions for a model

        :param model_id: Model ID
        :return: List of PaperSession instances
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, model_id, status, start_balance, current_balance,
                       total_trades, winning_trades, pnl, sharpe_ratio, max_drawdown,
                       started_at, ended_at
                FROM paper_trading_sessions
                WHERE model_id = %s
                ORDER BY started_at DESC
                """,
                (model_id,),
            )

            rows = cursor.fetchall()
            cursor.close()

            sessions = []
            for row in rows:
                (
                    id_val,
                    model_id,
                    status,
                    start_balance,
                    current_balance,
                    total_trades,
                    winning_trades,
                    pnl,
                    sharpe_ratio,
                    max_drawdown,
                    started_at,
                    ended_at,
                ) = row

                sessions.append(
                    PaperSession(
                        id=id_val,
                        model_id=model_id,
                        status=status,
                        start_balance=start_balance,
                        current_balance=current_balance,
                        total_trades=total_trades or 0,
                        winning_trades=winning_trades or 0,
                        pnl=pnl or 0.0,
                        sharpe_ratio=float(sharpe_ratio) if sharpe_ratio else None,
                        max_drawdown=float(max_drawdown) if max_drawdown else None,
                        started_at=started_at,
                        ended_at=ended_at,
                    )
                )

            return sessions

        except Exception as e:
            logger.error(
                f"Error getting sessions for model {model_id}: {e}", exc_info=True
            )
            return []
        finally:
            if conn:
                conn.close()

    def validate_session(
        self, session_id: int, criteria: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate a session against criteria

        :param session_id: Session ID
        :param criteria: Optional validation criteria (uses defaults if not provided)
        :return: Validation result dictionary
        """
        session = self.get_session(session_id)
        if not session:
            return {"valid": False, "error": "Session not found"}

        if session.status != "completed":
            return {"valid": False, "error": "Session must be completed to validate"}

        # Default criteria
        if not criteria:
            criteria = {
                "min_trades": 100,
                "min_win_rate": 0.45,
                "min_sharpe_ratio": 1.0,
                "max_drawdown": 0.10,
            }

        # Calculate win rate
        win_rate = (
            session.winning_trades / session.total_trades
            if session.total_trades > 0
            else 0.0
        )

        # Validation checks
        checks = {
            "min_trades": session.total_trades >= criteria.get("min_trades", 0),
            "min_win_rate": win_rate >= criteria.get("min_win_rate", 0),
            "min_sharpe_ratio": (session.sharpe_ratio or 0)
            >= criteria.get("min_sharpe_ratio", 0),
            "max_drawdown": (session.max_drawdown or 1.0)
            <= criteria.get("max_drawdown", 1.0),
        }

        valid = all(checks.values())

        return {
            "valid": valid,
            "checks": checks,
            "metrics": {
                "total_trades": session.total_trades,
                "win_rate": win_rate,
                "sharpe_ratio": session.sharpe_ratio,
                "max_drawdown": session.max_drawdown,
                "pnl": session.pnl,
            },
        }

    def _calculate_metrics(self, session: PaperSession) -> Dict[str, float]:
        """
        Calculate metrics from session data

        :param session: PaperSession instance
        :return: Metrics dictionary
        """
        # This is a placeholder - in practice, metrics would be calculated
        # from trade history or equity curve data
        return {
            "current_balance": session.current_balance,
            "total_trades": session.total_trades,
            "winning_trades": session.winning_trades,
            "pnl": session.pnl,
            "sharpe_ratio": (
                session.sharpe_ratio if session.sharpe_ratio is not None else 0.0
            ),
            "max_drawdown": (
                session.max_drawdown if session.max_drawdown is not None else 0.0
            ),
        }
