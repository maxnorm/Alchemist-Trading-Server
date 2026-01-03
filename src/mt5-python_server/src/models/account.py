import asyncio

from mt5_connection.terminal import MT5Terminal
from utils.time_utils import print_with_datetime
from domain.entities.account_info import AccountInfo
from application.trading.trade_executor import TradeExecutor


class Account:
    """
    Class for an account
    """

    def __init__(self, login, terminal: MT5Terminal):
        self.login = login
        self.trade_executor = TradeExecutor(terminal)
        self.current_trade = {}

        # Initialize account info
        self.info = self._fetch_account_info()
        print(self)

    def set_terminal(self, terminal: MT5Terminal):
        """
        Set the terminal for the account
        :param terminal: Terminal to set
        """
        self.trade_executor = TradeExecutor(terminal)
        self.update_info()

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
        # #region agent log
        try:
            import json as json_log

            log_path = r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log"
            with open(log_path, "a") as f:
                f.write(
                    json_log.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "B",
                            "location": "account.py:35",
                            "message": "Account.send_order entry",
                            "data": {
                                "order_type": order_type,
                                "symbol": pair.symbol,
                                "lotsize": lotsize,
                            },
                            "timestamp": int(__import__("time").time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion
        trade = self.trade_executor.send_order(order_type, pair, lotsize, price, sl, tp)
        # #region agent log
        try:
            import json as json_log

            log_path = r"c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log"
            with open(log_path, "a") as f:
                f.write(
                    json_log.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "B",
                            "location": "account.py:45",
                            "message": "Account.send_order after trade_executor",
                            "data": {
                                "trade_is_none": trade is None,
                                "trade_ticket": trade.ticket if trade else None,
                            },
                            "timestamp": int(__import__("time").time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion
        if trade:
            self.current_trade[trade.ticket] = trade
        return trade

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

            result = self.trade_executor.close_order(trade, lotsize)

            if result:
                if trade.lotsize == result["order"]["lotsize"]:
                    trade.close(result["order"]["close_price"])
                    self.current_trade.pop(ticket)
                    print(f"Trade closed: {trade.ticket}")
                else:
                    trade.update_lotsize(result["order"]["lotsize"])
                    print(
                        f"Trade partially closed: {trade.ticket}. New lotsize: {trade.lotsize}"
                    )

                # Update account info from result
                if "account" in result:
                    self._update_from_dict(result["account"])
        except Exception as e:
            print_with_datetime(f"Account {self.login} | {e}.\n[TICKET:{ticket}]")

    def update_info(self):
        """Update account information from terminal"""
        self.info = self._fetch_account_info()

    def _fetch_account_info(self) -> AccountInfo:
        """
        Fetch account information from terminal
        :return: AccountInfo instance
        """
        infos = asyncio.run(self.trade_executor.terminal.get_all_infos())
        return AccountInfo.from_dict({"login": self.login, **infos})

    def _update_from_dict(self, infos: dict):
        """
        Update account info from dictionary
        :param infos: Dictionary with account data
        """
        self.info = self.info.update(
            balance=infos.get("balance", self.info.balance),
            equity=infos.get("equity", self.info.equity),
            profit=infos.get("profit", self.info.profit),
            margin=infos.get("margin", self.info.margin),
            margin_free=infos.get("margin_free", self.info.margin_free),
        )

    # Properties for backward compatibility
    @property
    def currency(self):
        return self.info.currency

    @property
    def leverage(self):
        return self.info.leverage

    @property
    def balance(self):
        return self.info.balance

    @property
    def equity(self):
        return self.info.equity

    @property
    def profit(self):
        return self.info.profit

    @property
    def margin(self):
        return self.info.margin

    @property
    def margin_free(self):
        return self.info.margin_free

    def __str__(self):
        return (
            f"Account {self.login}\n"
            f"Currency: {self.info.currency}\n"
            f"Leverage: {self.info.leverage}\n"
            f"Balance: {self.info.balance}\n"
            f"Equity: {self.info.equity}\n"
            f"Profit: {self.info.profit}\n"
            f"Margin: {self.info.margin}\n"
            f"Margin Free: {self.info.margin_free}"
        )
