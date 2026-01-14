"""
Class for the trading interaction between MT5 and Python
"""

import json
import time
from codes.terminal_code import Terminal
from codes.trade_request_code import TradeRequest
from models.trade import Trade
from mt5_connection.conn import Connection


def generate_new_id():
    """
    Generate a new id for each trading terminal
    by incrementing the last id
    """
    new_id = MT5Terminal.last_id + 1
    MT5Terminal.last_id = new_id
    return new_id


class MT5Terminal(Connection):
    """
    MT5 terminal connection for trading operation
    """

    last_id = 0
    __trade_request_executed_code = 10009

    def __init__(self, socket, stop_char="\n", verbose=False, console_lock=None):
        super().__init__(socket, stop_char, verbose, console_lock)
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
        self.send_msg(json.dumps(data))
        return await self.get_response()

    def __del__(self):
        """Cleanup on terminal deletion - notify server of disconnect"""
        try:
            # Notify server of disconnect if account_id is set
            if hasattr(self, "_account_id") and self._account_id:
                # Try to import and call disconnect handler
                try:
                    # sys and os not used in this context

                    # Find server instance (this is a bit hacky but necessary)
                    # The server should handle cleanup via its own tracking
                    pass  # Server will detect disconnect via socket errors
                except Exception:
                    pass
        except Exception:
            pass
        # Call parent cleanup
        try:
            super().__del__()
        except Exception:
            pass

    async def ping(self):
        """Lightweight ping to validate connection (ACCOUNT_INFO request)."""
        data = {"request": Terminal.ACCOUNT_INFO.value}
        self.send_msg(json.dumps(data))
        return await self.get_response()

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

        Expected message format exemple:
            {
                "request": 101,\n
                "order_type": 0,\n
                "symbol": "EURUSD",\n
                "lotsize": 0.01,\n
                "price": 1.12345,\n
                "sl": 1.12345,\n
                "tp": 1.12345
            }
        """
        # Ensure connection is healthy or ping if stale
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

        self.send_msg(json.dumps(data))

        try:
            response = await self.get_response()
        except TimeoutError as e:
            raise TimeoutError(
                f"Timeout waiting for order response from MT5 terminal: {e}. "
                f"Order may not have been processed. Check MT5 terminal connection."
            )
        except ConnectionError as e:
            # Retry once after a forced ping if allowed
            if _retry:
                await self._ensure_connection(force_ping=True)
                return await self.send_order(
                    order_type, pair, lotsize, price, sl, tp, _retry=False
                )
            raise ConnectionError(
                f"Connection error while waiting for order response: {e}. "
                f"MT5 terminal connection may be lost."
            )

        return_code = response.get("return_code", -1)
        comment = response.get("comment", "Unknown error")

        # Accept both EXECUTED (10009) for market orders and PLACED (10008) for pending orders
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
        else:
            # Get human-readable retcode description
            retcode_desc = self._get_retcode_description(return_code)

            # Log full response for debugging
            error_details = (
                f"Order failed - Return code: {return_code} ({retcode_desc}), "
                f"Expected: {TradeRequest.EXECUTED.value} (EXECUTED) or {TradeRequest.PLACED.value} (PLACED), "
                f"Comment: {comment}, "
                f"Full response: {response}"
            )
            raise Exception(f"Error while sending order: {error_details}")

    def _get_retcode_description(self, retcode: int) -> str:
        """
        Get human-readable description for MT5 retcode
        :param retcode: MT5 return code
        :return: Description string with constant name and description
        """
        trade_request = TradeRequest.from_code(retcode)
        if trade_request:
            return f"{trade_request.name} - {trade_request.get_description()}"
        return f"Unknown retcode: {retcode}"

    async def close_order(self, trade, lotsize):
        """
        Close an order
        :param trade: Trade to close
        :param lotsize: Lot size to close (optional for partial close)
        """

        data = {
            "request": Terminal.CLOSE_ORDER.value,
            "ticket": trade.ticket,
            "lotsize": lotsize,
        }

        self.send_msg(json.dumps(data))
        response = await self.get_response()

        print(response)

        if response["return_code"] == TradeRequest.EXECUTED.value:
            return response
        else:
            raise Exception(f"Error while closing order: {response['comment']}")
