"""
Session Manager
Manages trading session lifecycle for performance tracking
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict
from database import Database


class SessionManager:
    """
    Manages trading session lifecycle
    Tracks session start/end balances and links models to trading sessions
    """
    
    def __init__(self, db: Optional[Database] = None, logger: Optional[logging.Logger] = None):
        """
        Initialize session manager
        :param db: Database instance
        :param logger: Logger instance
        """
        self.db = db or Database()
        self.logger = logger or logging.getLogger(__name__)
    
    def create_session(
        self,
        model_id: int,
        start_balance: float
    ) -> int:
        """
        Create a new trading session
        :param model_id: Model ID
        :param start_balance: Starting balance
        :return: Session ID
        """
        try:
            conn = self.db._Database__get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO live_trading_sessions 
                (model_id, status, start_balance, current_balance, high_water_mark)
                VALUES (?, 'active', ?, ?, ?)
            """, (model_id, start_balance, start_balance, start_balance))
            
            session_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            conn.close()
            
            self.logger.info(f"Created trading session {session_id} for model {model_id}")
            return session_id
        except Exception as e:
            self.logger.error(f"Error creating session: {e}", exc_info=True)
            raise
    
    def end_session(
        self,
        session_id: int,
        reason: str,
        end_balance: float
    ) -> None:
        """
        End a trading session
        :param session_id: Session ID
        :param reason: Reason for ending (e.g., 'user_stopped', 'kill_switch')
        :param end_balance: Ending balance
        """
        try:
            conn = self.db._Database__get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE live_trading_sessions
                SET status = 'stopped',
                    ended_at = ?,
                    ended_reason = ?,
                    current_balance = ?
                WHERE id = ?
            """, (datetime.utcnow(), reason, end_balance, session_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.logger.info(f"Ended trading session {session_id}: {reason}")
        except Exception as e:
            self.logger.error(f"Error ending session: {e}", exc_info=True)
            raise
    
    def pause_session(self, session_id: int) -> None:
        """
        Pause a trading session
        :param session_id: Session ID
        """
        try:
            conn = self.db._Database__get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE live_trading_sessions
                SET status = 'paused'
                WHERE id = ?
            """, (session_id,))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.logger.info(f"Paused trading session {session_id}")
        except Exception as e:
            self.logger.error(f"Error pausing session: {e}", exc_info=True)
            raise
    
    def resume_session(self, session_id: int) -> None:
        """
        Resume a paused trading session
        :param session_id: Session ID
        """
        try:
            conn = self.db._Database__get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE live_trading_sessions
                SET status = 'active'
                WHERE id = ?
            """, (session_id,))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.logger.info(f"Resumed trading session {session_id}")
        except Exception as e:
            self.logger.error(f"Error resuming session: {e}", exc_info=True)
            raise
    
    def update_balance(
        self,
        session_id: int,
        current_balance: float
    ) -> None:
        """
        Update current balance and high water mark for a session
        :param session_id: Session ID
        :param current_balance: Current balance
        """
        try:
            conn = self.db._Database__get_connection()
            cursor = conn.cursor()
            
            # Get current high water mark
            cursor.execute("""
                SELECT high_water_mark FROM live_trading_sessions WHERE id = ?
            """, (session_id,))
            result = cursor.fetchone()
            high_water_mark = result[0] if result else current_balance
            
            # Update high water mark if current balance is higher
            if current_balance > high_water_mark:
                high_water_mark = current_balance
            
            cursor.execute("""
                UPDATE live_trading_sessions
                SET current_balance = ?,
                    high_water_mark = ?
                WHERE id = ?
            """, (current_balance, high_water_mark, session_id))
            
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            self.logger.error(f"Error updating balance: {e}", exc_info=True)
            raise
    
    def get_active_sessions(
        self,
        model_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Get all active trading sessions
        :param model_id: Optional model ID to filter by
        :return: List of session dictionaries
        """
        try:
            conn = self.db._Database__get_connection()
            cursor = conn.cursor(dictionary=True)
            
            if model_id:
                cursor.execute("""
                    SELECT * FROM live_trading_sessions
                    WHERE status = 'active' AND model_id = ?
                    ORDER BY started_at DESC
                """, (model_id,))
            else:
                cursor.execute("""
                    SELECT * FROM live_trading_sessions
                    WHERE status = 'active'
                    ORDER BY started_at DESC
                """)
            
            sessions = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return sessions
        except Exception as e:
            self.logger.error(f"Error getting active sessions: {e}", exc_info=True)
            return []
    
    def get_session(self, session_id: int) -> Optional[Dict]:
        """
        Get a specific session by ID
        :param session_id: Session ID
        :return: Session dictionary or None
        """
        try:
            conn = self.db._Database__get_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT * FROM live_trading_sessions WHERE id = ?
            """, (session_id,))
            
            session = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return session
        except Exception as e:
            self.logger.error(f"Error getting session: {e}", exc_info=True)
            return None
