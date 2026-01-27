"""
Trade Logger
Logs trade entries and exits for performance tracking
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
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
            query = """
                INSERT INTO model_trades
                (session_id, model_id, order_uuid, symbol, action, entry_price, volume,
                 commission, swap, status, opened_at)
                VALUES (:session_id, :model_id, :order_uuid, :symbol, :action, :entry_price,
                        :volume, :commission, :swap, 'open', :opened_at)
                RETURNING id
            """

            params = {
                "session_id": session_id,
                "model_id": model_id,
                "order_uuid": order_uuid,
                "symbol": symbol,
                "action": action,
                "entry_price": entry_price,
                "volume": volume,
                "commission": commission,
                "swap": swap,
                "opened_at": datetime.utcnow(),
            }

            result = self.db.execute_one(query, params)
            if result:
                trade_id = result[0]
                self.logger.info(
                    f"Logged trade entry: trade_id={trade_id}, session_id={session_id}, "
                    f"symbol={symbol}, action={action}, price={entry_price}, volume={volume}"
                )
                return trade_id
            raise RuntimeError("Failed to log trade entry")
        except SQLAlchemyError as e:
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
            query = """
                UPDATE model_trades
                SET exit_price = :exit_price,
                    pnl = :pnl,
                    pnl_pips = :pnl_pips,
                    duration_seconds = :duration_seconds,
                    status = 'closed',
                    closed_at = :closed_at
                WHERE id = :trade_id
            """

            params = {
                "exit_price": exit_price,
                "pnl": pnl,
                "pnl_pips": pnl_pips,
                "duration_seconds": duration_seconds,
                "closed_at": datetime.utcnow(),
                "trade_id": trade_id,
            }

            with self.db.execute_query() as conn:
                conn.execute(text(query), params)

            self.logger.info(
                f"Logged trade exit: trade_id={trade_id}, exit_price={exit_price}, "
                f"pnl={pnl}, pnl_pips={pnl_pips}, duration={duration_seconds}s"
            )
        except SQLAlchemyError as e:
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
            query = "SELECT * FROM model_trades WHERE status = 'open'"
            params = {}

            if session_id:
                query += " AND session_id = :session_id"
                params["session_id"] = session_id

            if model_id:
                query += " AND model_id = :model_id"
                params["model_id"] = model_id

            query += " ORDER BY opened_at DESC"

            rows = self.db.execute_with_result(query, params if params else None)

            # Convert rows to dictionaries
            trades = []
            for row in rows:
                trade_dict = {
                    "id": row[0],
                    "session_id": row[1],
                    "model_id": row[2],
                    "order_uuid": row[3],
                    "symbol": row[4],
                    "action": row[5],
                    "entry_price": float(row[6]) if row[6] else None,
                    "exit_price": float(row[7]) if row[7] else None,
                    "volume": float(row[8]) if row[8] else None,
                    "commission": float(row[9]) if row[9] else None,
                    "swap": float(row[10]) if row[10] else None,
                    "pnl": float(row[11]) if row[11] else None,
                    "pnl_pips": float(row[12]) if row[12] else None,
                    "duration_seconds": row[13],
                    "status": row[14],
                    "opened_at": row[15],
                    "closed_at": row[16],
                }
                trades.append(trade_dict)

            return trades
        except SQLAlchemyError as e:
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
            query = "SELECT * FROM model_trades WHERE 1=1"
            params: Dict[str, Any] = {}

            if model_id:
                query += " AND model_id = :model_id"
                params["model_id"] = model_id

            if session_id:
                query += " AND session_id = :session_id"
                params["session_id"] = session_id

            if start_date:
                query += " AND opened_at >= :start_date"
                params["start_date"] = start_date

            if end_date:
                query += " AND opened_at <= :end_date"
                params["end_date"] = end_date

            query += " ORDER BY opened_at DESC LIMIT :limit OFFSET :offset"
            params["limit"] = limit
            params["offset"] = offset

            rows = self.db.execute_with_result(query, params)

            # Convert rows to dictionaries
            trades = []
            for row in rows:
                trade_dict = {
                    "id": row[0],
                    "session_id": row[1],
                    "model_id": row[2],
                    "order_uuid": row[3],
                    "symbol": row[4],
                    "action": row[5],
                    "entry_price": float(row[6]) if row[6] else None,
                    "exit_price": float(row[7]) if row[7] else None,
                    "volume": float(row[8]) if row[8] else None,
                    "commission": float(row[9]) if row[9] else None,
                    "swap": float(row[10]) if row[10] else None,
                    "pnl": float(row[11]) if row[11] else None,
                    "pnl_pips": float(row[12]) if row[12] else None,
                    "duration_seconds": row[13],
                    "status": row[14],
                    "opened_at": row[15],
                    "closed_at": row[16],
                }
                trades.append(trade_dict)

            return trades
        except SQLAlchemyError as e:
            self.logger.error(f"Error getting trade history: {e}", exc_info=True)
            return []

    def get_trade_by_uuid(self, order_uuid: str) -> Optional[Dict]:
        """
        Get a trade by order UUID
        :param order_uuid: Order UUID from OMS
        :return: Trade dictionary or None
        """
        try:
            query = """
                SELECT * FROM model_trades WHERE order_uuid = :order_uuid
            """

            params = {"order_uuid": order_uuid}
            row = self.db.execute_one(query, params)

            if row:
                trade_dict = {
                    "id": row[0],
                    "session_id": row[1],
                    "model_id": row[2],
                    "order_uuid": row[3],
                    "symbol": row[4],
                    "action": row[5],
                    "entry_price": float(row[6]) if row[6] else None,
                    "exit_price": float(row[7]) if row[7] else None,
                    "volume": float(row[8]) if row[8] else None,
                    "commission": float(row[9]) if row[9] else None,
                    "swap": float(row[10]) if row[10] else None,
                    "pnl": float(row[11]) if row[11] else None,
                    "pnl_pips": float(row[12]) if row[12] else None,
                    "duration_seconds": row[13],
                    "status": row[14],
                    "opened_at": row[15],
                    "closed_at": row[16],
                }
                return trade_dict
            return None
        except SQLAlchemyError as e:
            self.logger.error(f"Error getting trade by UUID: {e}", exc_info=True)
            return None
