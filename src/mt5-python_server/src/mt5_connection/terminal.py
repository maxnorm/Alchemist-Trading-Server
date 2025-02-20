"""
Class for the trading interaction between MT5 and Python
"""
import json
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

    def __init__(self, socket, stop_char='\n', verbose=False, console_lock=None):
        super().__init__(socket, stop_char, verbose, console_lock)
        self.id = generate_new_id()

    async def get_all_infos(self):
        """
        Get all the terminal infos

        Expected message format:
            {
                "request": 100
            }
        """
        data = {
            'request': Terminal.ACCOUNT_INFO.value
        }
        self.send_msg(json.dumps(data))
        return await self.get_response()

    async def send_order(self, order_type, pair, lotsize, price=None, sl=None, tp=None):
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
        data = {
            'request': Terminal.OPEN_ORDER.value,
            'order_type': order_type,
            'symbol': pair.symbol,
            'lotsize': lotsize,
            'price': price,
            'sl': sl,
            'tp': tp
        }
        self.send_msg(json.dumps(data))
        response = await self.get_response()

        if response['return_code'] == TradeRequest.EXECUTED.value:
            trade = Trade(
                response['ticket'],
                order_type,
                pair,
                response['lotsize'],
                response['price'],
                sl,
                tp
            )
            return trade
        else:
            raise Exception(f"Error while sending order: {response['comment']}")

    async def close_order(self, trade, lotsize):
        """
        Close an order
        :param trade: Trade to close
        :param lotsize: Lot size to close (optional for partial close)
        """

        data = {
            'request': Terminal.CLOSE_ORDER.value,
            'ticket': trade.ticket,
            'lotsize': lotsize,
        }

        self.send_msg(json.dumps(data))
        response = await self.get_response()

        print(response)

        if response['return_code'] == TradeRequest.EXECUTED.value:
            return response
        else:
            raise Exception(f"Error while closing order: {response['comment']}")
