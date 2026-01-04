"""
Trade Logger
Logs trade entries and exits for performance tracking
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from database import Database


class TradeLogger:
    """
    Logs trade entries and exits
    Tracks open positions and calculates P&L
    """

    def __init__(
        self, db: Optional[Database] = None, logger: Optional[logging.Logger] = None
    ):
        """
        Initialize trade logger
        :param db: Database instance
        :param logger: Logger instance
        """
        self.db = db or Database()
        self.logger = logger or logging.getLogger(__name__)

    def log_trade_entry(
        self,
        session_id: int,
        model_id: int,
        order_uuid: str,
        symbol: str,
        action: str,  # 'BUY' or 'SELL'
        entry_price: float,
        volume: float,
        commission: float = 0.0,
        swap: float = 0.0,
    ) -> int:
        """
        Log a trade entry (position opened)
        :param session_id: Trading session ID
        :param model_id: Model ID
        :param order_uuid: Unique order UUID from OMS
        :param symbol: Currency pair symbol
        :param action: 'BUY' or 'SELL'
        :param entry_price: Entry price
        :param volume: Trade volume (lots)
        :param commission: Commission paid
        :param swap: Swap paid/received
        :return: Trade ID
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO model_trades
                (session_id, model_id, order_uuid, symbol, action, entry_price, volume,
                 commission, swap, status, opened_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)
            """,
                (
                    session_id,
                    model_id,
                    order_uuid,
                    symbol,
                    action,
                    entry_price,
                    volume,
                    commission,
                    swap,
                    datetime.utcnow(),
                ),
            )

            trade_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            conn.close()

            self.logger.info(
                f"Logged trade entry: trade_id={trade_id}, session_id={session_id}, "
                f"symbol={symbol}, action={action}, price={entry_price}, volume={volume}"
            )
            return trade_id
        except Exception as e:
            self.logger.error(f"Error logging trade entry: {e}", exc_info=True)
            raise

    def log_trade_exit(
        self,
        trade_id: int,
        exit_price: float,
        pnl: float,
        pnl_pips: float,
        duration_seconds: int,
    ) -> None:
        """
        Log a trade exit (position closed)
        :param trade_id: Trade ID from entry
        :param exit_price: Exit price
        :param pnl: Profit/loss amount
        :param pnl_pips: Profit/loss in pips
        :param duration_seconds: Trade duration in seconds
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE model_trades
                SET exit_price = ?,
                    pnl = ?,
                    pnl_pips = ?,
                    duration_seconds = ?,
                    status = 'closed',
                    closed_at = ?
                WHERE id = ?
            """,
                (
                    exit_price,
                    pnl,
                    pnl_pips,
                    duration_seconds,
                    datetime.utcnow(),
                    trade_id,
                ),
            )

            conn.commit()
            cursor.close()
            conn.close()

            self.logger.info(
                f"Logged trade exit: trade_id={trade_id}, exit_price={exit_price}, "
                f"pnl={pnl}, pnl_pips={pnl_pips}, duration={duration_seconds}s"
            )
        except Exception as e:
            self.logger.error(f"Error logging trade exit: {e}", exc_info=True)
            raise

    def get_open_trades(
        self, session_id: Optional[int] = None, model_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Get all open trades
        :param session_id: Optional session ID to filter by
        :param model_id: Optional model ID to filter by
        :return: List of open trade dictionaries
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor(dictionary=True)

            query = "SELECT * FROM model_trades WHERE status = 'open'"
            params = []

            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)

            if model_id:
                query += " AND model_id = ?"
                params.append(model_id)

            query += " ORDER BY opened_at DESC"

            cursor.execute(query, tuple(params))
            trades = cursor.fetchall()
            cursor.close()
            conn.close()

            return trades
        except Exception as e:
            self.logger.error(f"Error getting open trades: {e}", exc_info=True)
            return []

    def get_trade_history(
        self,
        model_id: Optional[int] = None,
        session_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """
        Get trade history with filtering and pagination
        :param model_id: Optional model ID to filter by
        :param session_id: Optional session ID to filter by
        :param start_date: Optional start date filter
        :param end_date: Optional end date filter
        :param limit: Maximum number of trades to return
        :param offset: Offset for pagination
        :return: List of trade dictionaries
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor(dictionary=True)

            query = "SELECT * FROM model_trades WHERE 1=1"
            params: List[Any] = []

            if model_id:
                query += " AND model_id = ?"
                params.append(model_id)

            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)

            if start_date:
                query += " AND opened_at >= ?"
                params.append(start_date)

            if end_date:
                query += " AND opened_at <= ?"
                params.append(end_date)

            query += " ORDER BY opened_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, tuple(params))
            trades = cursor.fetchall()
            cursor.close()
            conn.close()

            return trades
        except Exception as e:
            self.logger.error(f"Error getting trade history: {e}", exc_info=True)
            return []

    def get_trade_by_uuid(self, order_uuid: str) -> Optional[Dict]:
        """
        Get a trade by order UUID
        :param order_uuid: Order UUID from OMS
        :return: Trade dictionary or None
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT * FROM model_trades WHERE order_uuid = ?
            """,
                (order_uuid,),
            )

            trade = cursor.fetchone()
            cursor.close()
            conn.close()

            return trade
        except Exception as e:
            self.logger.error(f"Error getting trade by UUID: {e}", exc_info=True)
            return None
