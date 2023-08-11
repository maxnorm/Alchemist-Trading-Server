import asyncio

from codes.order_type import OrderType
from models.currency_pair import CurrencyPair
from mt5_connection.terminal import MT5Terminal
from utils.time_utils import print_with_datetime


class Account:
    """
    Class for an account
    """

    def __init__(self, login, terminal: MT5Terminal):
        self.login = login
        self.__terminal = terminal
        self.current_trade = {}

        self.currency = None
        self.leverage = None
        self.balance = None
        self.equity = None
        self.profit = None
        self.margin = None
        self.margin_free = None

        self.__set_account_infos()

        gbpjpy = CurrencyPair('GBPJPY', 3)

        trade = self.send_order(OrderType.BUY, gbpjpy, 0.02)
        self.close_order(trade.ticket, 0.01)

    def set_terminal(self, terminal: MT5Terminal):
        """
        Set the terminal for the account
        :param terminal: Terminal to set
        """
        self.__terminal = terminal
        self.__set_account_infos()

    def send_order(self, order_type, pair, lotsize, price=None, sl=None, tp=None):
        """
        Send an order to MT5 terminal
        :param order_type: Order type
        :param pair: Currency pair
        :param lotsize: Lot size
        :param price: Order price (optional if Market Order)
        :param sl: Stop loss (optional)
        :param tp: Take profit (optional)
        """
        try:
            trade = asyncio.run(self.__terminal.send_order(order_type, pair, lotsize, price, sl, tp))
            self.current_trade[trade.ticket] = trade
            return trade
        except Exception as e:
            print_with_datetime(f"Account {self.login} | {e}.\n"
                                f"[ORDER:{order_type}|PAIR:{pair}|LOTSIZE:{lotsize}|PRICE:{price}|SL:{sl}|TP:{tp}]")

    def close_order(self, ticket, lotsize=None):
        """
        Close an order
        :param ticket: Ticket of the order
        :param lotsize: Lot size to close (optional for partial close)
        """
        try:
            trade = self.current_trade[ticket]

            if lotsize is None:
                lotsize = trade.lotsize

            result = asyncio.run(self.__terminal.close_order(trade, lotsize))

            if trade.lotsize == result['order']['lotsize']:
                trade.close(result['order']['close_price'])
                self.current_trade.pop(ticket)
                print(f"Trade closed: {trade.ticket}")
            else:
                trade.update_lotsize(result['order']['lotsize'])
                print(f"Trade partially closed: {trade.ticket}. New lotsize: {trade.lotsize}")

            self.__update_account_infos(result['account'])
        except Exception as e:
            print_with_datetime(f"Account {self.login} | {e}.\n"
                                f"[TICKET:{ticket}]")

    def __set_account_infos(self):
        """
        Set the account infos by getting them from the terminal
        """
        infos = asyncio.run(self.__terminal.get_all_infos())

        self.currency = infos['currency']
        self.leverage = infos['leverage']
        self.balance = infos['balance']
        self.equity = infos['equity']
        self.profit = infos['profit']
        self.margin = infos['margin']
        self.margin_free = infos['margin_free']

    def __update_account_infos(self, infos):
        """
        Update the account infos by getting them from the terminal
        """
        self.balance = infos['balance']
        self.equity = infos['equity']
        self.profit = infos['profit']
        self.margin = infos['margin']
        self.margin_free = infos['margin_free']
