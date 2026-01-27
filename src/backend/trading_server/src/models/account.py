from typing import Dict, Any, Optional

from trading.brokers.base import IBrokerAdapter
from utils.time_utils import print_with_datetime
from domain.entities.account_info import AccountInfo
from application.trading.trade_executor import TradeExecutor
from mt5_connection.zeromq_terminal import ZeroMQTerminal
from infrastructure.db_integration import get_account_from_db


class Account:
    """
    Class for an account
    """

    def __init__(
        self,
        login,
        broker_adapter: Optional[IBrokerAdapter] = None,
        terminal: Optional[ZeroMQTerminal] = None,
    ):
        """
        Initialize account

        :param login: Account login ID
        :param broker_adapter: IBrokerAdapter instance (preferred)
        :param terminal: ZeroMQTerminal instance
        """
        self.login = login

        # Use broker_adapter if provided, otherwise create from terminal
        if broker_adapter:
            self.broker_adapter = broker_adapter
        elif terminal:
            # Create adapter from terminal for backward compatibility
            from trading.brokers.mt5_adapter import MT5BrokerAdapter

            self.broker_adapter = MT5BrokerAdapter.from_terminal(terminal)
        else:
            raise ValueError("Either broker_adapter or terminal must be provided")

        self.trade_executor = TradeExecutor(broker_adapter=self.broker_adapter)
        self.current_trade: Dict[str, Any] = {}

        # Cache for account type (lazy-loaded from database)
        self._account_type: Optional[str] = None

        # Initialize account info
        self.info = self._fetch_account_info()
        print(self)

    def set_terminal(self, terminal: ZeroMQTerminal):
        """
        Set the terminal for the account
        :param terminal: Terminal to set
        """
        from trading.brokers.mt5_adapter import MT5BrokerAdapter

        self.broker_adapter = MT5BrokerAdapter.from_terminal(terminal)
        self.trade_executor = TradeExecutor(broker_adapter=self.broker_adapter)
        self.update_info()

    def set_broker_adapter(self, broker_adapter: IBrokerAdapter):
        """
        Set the broker adapter for the account
        :param broker_adapter: Broker adapter to set
        """
        self.broker_adapter = broker_adapter
        self.trade_executor = TradeExecutor(broker_adapter=broker_adapter)
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
        trade = self.trade_executor.send_order(order_type, pair, lotsize, price, sl, tp)
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
        Fetch account information from broker adapter
        :return: AccountInfo instance
        """
        account_info = self.broker_adapter.get_account_info()
        # Ensure login matches
        return (
            account_info.update(login=self.login)
            if account_info.login != self.login
            else account_info
        )

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

    @property
    def account_type(self) -> Optional[str]:
        """
        Get account type from database ('demo' or 'live')
        Caches result to avoid repeated database queries

        :return: Account type string ('demo' or 'live') or None if not found in database
        """
        if self._account_type is None:
            self._account_type = self._get_account_type_from_db()
        return self._account_type

    def _get_account_type_from_db(self) -> Optional[str]:
        """
        Get account type from database

        :return: Account type string ('demo' or 'live') or None if not found
        """
        try:
            account_data = get_account_from_db(self.login)
            if account_data:
                return account_data.get("account_type")
            return None
        except Exception as e:
            print_with_datetime(
                f"Error getting account type for account {self.login}: {e}"
            )
            return None

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
