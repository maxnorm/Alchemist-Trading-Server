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

        # #region agent log
        try:
            import json as json_log
            import os
            import time

            log_path = r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log"
            with open(log_path, "a") as f:
                f.write(
                    json_log.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "D",
                            "location": "terminal.py:78",
                            "message": "send_order before send_msg",
                            "data": {"order_data": data},
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion
        self.send_msg(json.dumps(data))

        # #region agent log
        try:
            import json as json_log
            import time as _t

            payload = {
                "sessionId": "debug-session",
                "runId": "run-debug",
                "hypothesisId": "H1",
                "location": "terminal.py:send_order",
                "message": "after_send_msg",
                "data": {
                    "socket_fileno": (
                        self._Connection__socket.fileno()
                        if hasattr(self, "_Connection__socket")
                        else None
                    ),
                    "order_type": order_type,
                    "symbol": pair.symbol,
                    "lotsize": lotsize,
                },
                "timestamp": int(_t.time() * 1000),
            }
            try:
                host_log = r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log"
                with open(host_log, "a") as f:
                    f.write(json_log.dumps(payload) + "\n")
            except Exception:
                pass
            try:
                log_path = os.path.join(os.getenv("LOG_DIR", "/app/logs"), "debug.log")
                with open(log_path, "a") as f:
                    f.write(json_log.dumps(payload) + "\n")
            except Exception:
                pass
        except Exception:  # pragma: no cover
            pass
        # #endregion

        # #region agent log
        try:
            import json as json_log
            import os
            import time

            log_path = r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log"
            with open(log_path, "a") as f:
                f.write(
                    json_log.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "D",
                            "location": "terminal.py:87",
                            "message": "send_order after send_msg, before get_response",
                            "data": {},
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion

        try:
            response = await self.get_response()
            # #region agent log
            try:
                import json as json_log
                import os
                import time as _t

                payload = {
                    "sessionId": "debug-session",
                    "runId": "run-debug",
                    "hypothesisId": "H1",
                    "location": "terminal.py:send_order",
                    "message": "got_response",
                    "data": {
                        "has_response": response is not None,
                        "return_code": (
                            response.get("return_code")
                            if isinstance(response, dict)
                            else None
                        ),
                    },
                    "timestamp": int(_t.time() * 1000),
                }
                try:
                    host_log = r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log"
                    with open(host_log, "a") as f:
                        f.write(json_log.dumps(payload) + "\n")
                except Exception:
                    pass
                try:
                    log_path = os.path.join(
                        os.getenv("LOG_DIR", "/app/logs"), "debug.log"
                    )
                    with open(log_path, "a") as f:
                        f.write(json_log.dumps(payload) + "\n")
                except Exception:
                    pass
            except Exception:  # pragma: no cover
                pass
            # #endregion
            # #region agent log
            try:
                import json as json_log
                import os
                import time

                log_path = r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log"
                with open(log_path, "a") as f:
                    f.write(
                        json_log.dumps(
                            {
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "D",
                                "location": "terminal.py:99",
                                "message": "send_order got response",
                                "data": {
                                    "return_code": response.get("return_code"),
                                    "has_ticket": "ticket" in response,
                                    "comment": response.get("comment"),
                                    "full_response": str(response),
                                },
                                "timestamp": int(time.time() * 1000),
                            }
                        )
                        + "\n"
                    )
            except Exception:
                pass
            # #endregion
        except TimeoutError as e:
            # #region agent log
            try:
                import json as json_log
                import os

                log_path = r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log"
                with open(log_path, "a") as f:
                    f.write(
                        json_log.dumps(
                            {
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "E",
                                "location": "terminal.py:108",
                                "message": "TimeoutError in get_response",
                                "data": {"error": str(e)},
                                "timestamp": int(__import__("time").time() * 1000),
                            }
                        )
                        + "\n"
                    )
            except Exception:
                pass
            # #endregion
            raise TimeoutError(
                f"Timeout waiting for order response from MT5 terminal: {e}. "
                f"Order may not have been processed. Check MT5 terminal connection."
            )
        except ConnectionError as e:
            # #region agent log
            try:
                import json as json_log
                import os

                log_path = r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log"
                with open(log_path, "a") as f:
                    f.write(
                        json_log.dumps(
                            {
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "E",
                                "location": "terminal.py:114",
                                "message": "ConnectionError in get_response",
                                "data": {"error": str(e)},
                                "timestamp": int(__import__("time").time() * 1000),
                            }
                        )
                        + "\n"
                    )
            except Exception:
                pass
            # #endregion
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

        # #region agent log
        try:
            import json as json_log
            import os
            import time

            log_path = r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log"
            with open(log_path, "a") as f:
                f.write(
                    json_log.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "D",
                            "location": "terminal.py:135",
                            "message": "Checking return_code",
                            "data": {
                                "return_code": return_code,
                                "expected_executed": TradeRequest.EXECUTED.value,
                                "expected_placed": TradeRequest.PLACED.value,
                                "comment": comment,
                            },
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion

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
            # #region agent log
            try:
                import json as json_log
                import os
                import time

                log_path = r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log"
                with open(log_path, "a") as f:
                    f.write(
                        json_log.dumps(
                            {
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "D",
                                "location": "terminal.py:149",
                                "message": "Trade created successfully",
                                "data": {
                                    "ticket": trade.ticket,
                                    "lotsize": trade.lotsize,
                                    "price": trade.open_price,
                                },
                                "timestamp": int(time.time() * 1000),
                            }
                        )
                        + "\n"
                    )
            except Exception:
                pass
            # #endregion
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
            # #region agent log
            try:
                import json as json_log
                import os
                import time

                log_path = r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log"
                with open(log_path, "a") as f:
                    f.write(
                        json_log.dumps(
                            {
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "D",
                                "location": "terminal.py:167",
                                "message": "Invalid return_code, raising exception",
                                "data": {
                                    "return_code": return_code,
                                    "retcode_desc": retcode_desc,
                                    "comment": comment,
                                    "error_details": error_details,
                                },
                                "timestamp": int(time.time() * 1000),
                            }
                        )
                        + "\n"
                    )
            except Exception:
                pass
            # #endregion
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
