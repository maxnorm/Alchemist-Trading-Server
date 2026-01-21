"""
ZeroMQ-based MT5 terminal connection for trading.
"""

import time

from codes.terminal_code import Terminal
from codes.trade_request_code import TradeRequest
from models.trade import Trade
from mt5_connection.zeromq_conn import ZeroMQConnection


def generate_new_id():
    """
    Generate a new id for each trading terminal
    by incrementing the last id
    """
    new_id = ZeroMQTerminal.last_id + 1
    ZeroMQTerminal.last_id = new_id
    return new_id


class ZeroMQTerminal:
    """
    MT5 terminal connection for trading operation (ZeroMQ REQ/REP).
    """

    last_id = 0
    __trade_request_executed_code = 10009

    def __init__(self, zmq_conn: ZeroMQConnection):
        self._zmq_conn = zmq_conn
        self.id = generate_new_id()
        self._idle_threshold = 60  # seconds before we proactively ping
        self._account_id = None  # Set by server for disconnect tracking
        self._account_login = None  # Set by server for disconnect tracking

    async def get_all_infos(self):
        """
        Get all the terminal infos

        Expected message format:
            {
                "request": 100
            }
        """
        data = {"request": Terminal.ACCOUNT_INFO.value}
        self._zmq_conn.send_msg(data)
        return await self._zmq_conn.get_response()

    async def ping(self):
        """Lightweight ping to validate connection (ACCOUNT_INFO request)."""
        data = {"request": Terminal.ACCOUNT_INFO.value}
        self._zmq_conn.send_msg(data)
        return await self._zmq_conn.get_response()

    def ping_sync(self):
        """Synchronous wrapper for heartbeat threads."""
        import asyncio

        return asyncio.run(self.ping())

    async def _ensure_connection(self, force_ping: bool = False):
        """Check socket health/idle and ping if stale."""
        if not self.is_alive():
            raise ConnectionError("MT5 socket appears disconnected before send")
        last_recv = self.last_recv_ts()
        now = time.time()
        if force_ping or (last_recv and now - last_recv > self._idle_threshold):
            await self.ping()

    async def send_order(
        self, order_type, pair, lotsize, price=None, sl=None, tp=None, _retry=True
    ):
        """
        Send an order to MT5 terminal
        :param order_type: Order type
        :param pair: Currency pair
        :param lotsize: Lot size
        :param price: Order price (optional if Market Order)
        :param sl: Stop loss (optional)
        :param tp: Take profit (optional)
        """
        await self._ensure_connection()

        data = {
            "request": Terminal.OPEN_ORDER.value,
            "order_type": order_type,
            "symbol": pair.symbol,
            "lotsize": lotsize,
            "price": price,
            "sl": sl,
            "tp": tp,
        }

        self._zmq_conn.send_msg(data)

        try:
            response = await self._zmq_conn.get_response()
        except TimeoutError as exc:
            raise TimeoutError(
                f"Timeout waiting for order response from MT5 terminal: {exc}. "
                f"Order may not have been processed. Check MT5 terminal connection."
            )
        except ConnectionError as exc:
            if _retry:
                await self._ensure_connection(force_ping=True)
                return await self.send_order(
                    order_type, pair, lotsize, price, sl, tp, _retry=False
                )
            raise ConnectionError(
                f"Connection error while waiting for order response: {exc}. "
                f"MT5 terminal connection may be lost."
            )

        return_code = response.get("return_code", -1)
        comment = response.get("comment", "Unknown error")

        if (
            return_code == TradeRequest.EXECUTED.value
            or return_code == TradeRequest.PLACED.value
        ):
            trade = Trade(
                response["ticket"],
                order_type,
                pair,
                response["lotsize"],
                response["price"],
                sl,
                tp,
            )
            return trade

        retcode_desc = self._get_retcode_description(return_code)
        error_details = (
            f"Order failed - Return code: {return_code} ({retcode_desc}), "
            f"Expected: {TradeRequest.EXECUTED.value} (EXECUTED) or {TradeRequest.PLACED.value} (PLACED), "
            f"Comment: {comment}, "
            f"Full response: {response}"
        )
        raise Exception(f"Error while sending order: {error_details}")

    def _get_retcode_description(self, retcode: int) -> str:
        trade_request = TradeRequest.from_code(retcode)
        if trade_request:
            return f"{trade_request.name} - {trade_request.get_description()}"
        return f"Unknown retcode: {retcode}"

    async def close_order(self, trade, lotsize):
        data = {
            "request": Terminal.CLOSE_ORDER.value,
            "ticket": trade.ticket,
            "lotsize": lotsize,
        }

        self._zmq_conn.send_msg(data)
        response = await self._zmq_conn.get_response()
        return response

    def is_alive(self) -> bool:
        return self._zmq_conn.is_alive()

    def last_recv_ts(self):
        return self._zmq_conn.last_recv_ts()
