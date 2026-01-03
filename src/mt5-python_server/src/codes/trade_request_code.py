"""
Enum for the return code for trade request
Based on MQL5 documentation: https://www.mql5.com/en/docs/constants/errorswarnings/enum_trade_return_codes
"""
from enum import IntEnum


class TradeRequest(IntEnum):
    """
    Enum for the return code for trade request
    Complete list of MT5 trade server return codes
    """
    # Success codes
    PLACED = 10008  # Order placed
    EXECUTED = 10009  # Request completed
    DONE_PARTIAL = 10010  # Only part of the request was completed
    
    # Error codes
    REQUOTE = 10004  # Requote
    REJECT = 10006  # Request rejected
    CANCEL = 10007  # Request canceled by trader
    ERROR = 10011  # Request processing error
    TIMEOUT = 10012  # Request canceled by timeout
    INVALID = 10013  # Invalid request
    INVALID_VOLUME = 10014  # Invalid volume in the request
    INVALID_PRICE = 10015  # Invalid price in the request
    INVALID_STOPS = 10016  # Invalid stops in the request
    TRADE_DISABLED = 10017  # Trade is disabled
    MARKET_CLOSED = 10018  # Market is closed
    NO_MONEY = 10019  # There is not enough money to complete the request
    PRICE_CHANGED = 10020  # Prices changed
    PRICE_OFF = 10021  # Price off
    INVALID_EXPIRATION = 10022  # Invalid expiration
    ORDER_CHANGED = 10023  # Order changed
    TOO_MANY_REQUESTS = 10024  # Too many requests
    NO_CHANGES = 10025  # No changes
    SERVER_DISABLES_AT = 10026  # Server disables AT
    CLIENT_DISABLES_AT = 10027  # Client disables AT
    LOCKED = 10028  # Locked
    FROZEN = 10029  # Frozen
    INVALID_FILL = 10030  # Invalid order filling type
    CONNECTION = 10031  # No connection with the trade server
    ONLY_REAL = 10032  # Operation is allowed only for live accounts
    LIMIT_ORDERS = 10033  # The number of pending orders has reached the limit
    LIMIT_VOLUME = 10034  # The volume of orders and positions for the symbol has reached the limit
    INVALID_ORDER = 10035  # Incorrect or prohibited order type
    POSITION_CLOSED = 10036  # Position with the specified POSITION_IDENTIFIER has already been closed
    INVALID_CLOSE_VOLUME = 10038  # A close volume exceeds the current position volume
    CLOSE_ORDER_EXIST = 10039  # A close order already exists for a specified position
    LIMIT_POSITIONS = 10040  # The number of open positions simultaneously present on an account can be limited
    REJECT_CANCEL = 10041  # The pending order activation request is rejected, the order is canceled
    LONG_ONLY = 10042  # The request is rejected, because the "Only long positions are allowed" rule is set
    SHORT_ONLY = 10043  # The request is rejected, because the "Only short positions are allowed" rule is set
    CLOSE_ONLY = 10044  # The request is rejected, because the "Only position closing is allowed" rule is set
    FIFO_CLOSE = 10045  # The request is rejected, because "Position closing is allowed only by FIFO rule" flag is set
    HEDGE_PROHIBITED = 10046  # The request is rejected, because the "Opposite positions on a single symbol are disabled" rule is set
    
    def get_description(self) -> str:
        """
        Get human-readable description for the retcode
        :return: Description string
        """
        descriptions = {
            TradeRequest.REQUOTE: "Requote",
            TradeRequest.REJECT: "Request rejected",
            TradeRequest.CANCEL: "Request canceled by trader",
            TradeRequest.PLACED: "Order placed",
            TradeRequest.EXECUTED: "Request completed",
            TradeRequest.DONE_PARTIAL: "Only part of the request was completed",
            TradeRequest.ERROR: "Request processing error",
            TradeRequest.TIMEOUT: "Request canceled by timeout",
            TradeRequest.INVALID: "Invalid request",
            TradeRequest.INVALID_VOLUME: "Invalid volume in the request",
            TradeRequest.INVALID_PRICE: "Invalid price in the request",
            TradeRequest.INVALID_STOPS: "Invalid stops in the request",
            TradeRequest.TRADE_DISABLED: "Trade is disabled",
            TradeRequest.MARKET_CLOSED: "Market is closed",
            TradeRequest.NO_MONEY: "There is not enough money to complete the request",
            TradeRequest.PRICE_CHANGED: "Prices changed",
            TradeRequest.PRICE_OFF: "Price off",
            TradeRequest.INVALID_EXPIRATION: "Invalid expiration",
            TradeRequest.ORDER_CHANGED: "Order changed",
            TradeRequest.TOO_MANY_REQUESTS: "Too many requests",
            TradeRequest.NO_CHANGES: "No changes",
            TradeRequest.SERVER_DISABLES_AT: "Server disables AT",
            TradeRequest.CLIENT_DISABLES_AT: "Client disables AT",
            TradeRequest.LOCKED: "Locked",
            TradeRequest.FROZEN: "Frozen",
            TradeRequest.INVALID_FILL: "Invalid order filling type",
            TradeRequest.CONNECTION: "No connection with the trade server",
            TradeRequest.ONLY_REAL: "Operation is allowed only for live accounts",
            TradeRequest.LIMIT_ORDERS: "The number of pending orders has reached the limit",
            TradeRequest.LIMIT_VOLUME: "The volume of orders and positions for the symbol has reached the limit",
            TradeRequest.INVALID_ORDER: "Incorrect or prohibited order type",
            TradeRequest.POSITION_CLOSED: "Position with the specified POSITION_IDENTIFIER has already been closed",
            TradeRequest.INVALID_CLOSE_VOLUME: "A close volume exceeds the current position volume",
            TradeRequest.CLOSE_ORDER_EXIST: "A close order already exists for a specified position",
            TradeRequest.LIMIT_POSITIONS: "The number of open positions simultaneously present on an account can be limited",
            TradeRequest.REJECT_CANCEL: "The pending order activation request is rejected, the order is canceled",
            TradeRequest.LONG_ONLY: "The request is rejected, because the 'Only long positions are allowed' rule is set",
            TradeRequest.SHORT_ONLY: "The request is rejected, because the 'Only short positions are allowed' rule is set",
            TradeRequest.CLOSE_ONLY: "The request is rejected, because the 'Only position closing is allowed' rule is set",
            TradeRequest.FIFO_CLOSE: "The request is rejected, because 'Position closing is allowed only by FIFO rule' flag is set",
            TradeRequest.HEDGE_PROHIBITED: "The request is rejected, because the 'Opposite positions on a single symbol are disabled' rule is set",
        }
        return descriptions.get(self, f"Unknown retcode: {self.value}")
    
    @classmethod
    def from_code(cls, code: int):
        """
        Get TradeRequest enum from integer code
        :param code: Integer retcode
        :return: TradeRequest enum or None if not found
        """
        try:
            return cls(code)
        except ValueError:
            return None



