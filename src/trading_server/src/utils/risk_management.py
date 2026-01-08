"""
Risk Management Module for Trading AI
Implements position sizing, stop loss, take profit, and risk limits
"""

from typing import Optional
from models.account import Account
from models.currency_pair import CurrencyPair


class RiskManager:
    """Risk management for trading operations"""

    def __init__(
        self,
        max_position_size: float = 0.1,  # Max 10% of account per trade
        max_daily_loss: float = 0.05,  # Max 5% daily loss
        max_drawdown: float = 0.20,  # Max 20% drawdown
        stop_loss_pct: float = 0.02,  # 2% stop loss
        take_profit_pct: float = 0.04,  # 4% take profit (2:1 ratio)
        max_open_positions: int = 3,
    ):
        """
        Initialize risk manager
        :param max_position_size: Maximum position size as fraction of account
        :param max_daily_loss: Maximum daily loss as fraction of account
        :param max_drawdown: Maximum drawdown as fraction of account
        :param stop_loss_pct: Stop loss as percentage of entry price
        :param take_profit_pct: Take profit as percentage of entry price
        :param max_open_positions: Maximum number of open positions
        """
        self.max_position_size = max_position_size
        self.max_daily_loss = max_daily_loss
        self.max_drawdown = max_drawdown
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_open_positions = max_open_positions

        self.initial_balance = None
        self.daily_start_balance = None

    def initialize(self, account: Account):
        """Initialize with account balance"""
        if self.initial_balance is None:
            self.initial_balance = account.balance
        if self.daily_start_balance is None:
            self.daily_start_balance = account.balance

    def calculate_position_size(
        self,
        account: Account,
        pair: CurrencyPair,
        entry_price: float,
        risk_amount: Optional[float] = None,
    ) -> float:
        """
        Calculate position size based on risk management rules
        :param account: Account object
        :param pair: Currency pair
        :param entry_price: Entry price for the trade
        :param risk_amount: Optional specific risk amount (uses stop loss if None)
        :return: Position size in lots
        """
        if account.balance <= 0:
            return 0.0

        # Calculate risk amount
        if risk_amount is None:
            risk_amount = account.balance * self.max_position_size

        # Calculate stop loss distance
        stop_loss_distance = entry_price * self.stop_loss_pct

        # Determine pip value based on pair type
        # Most pairs: 1 pip = 0.0001 (4 decimal places)
        # JPY pairs: 1 pip = 0.01 (2 decimal places)
        # Gold (XAU) pairs: 1 pip = 0.01 (2-3 decimal places, similar to JPY)
        pip_value = 0.0001
        if "JPY" in pair.symbol or "XAU" in pair.symbol:
            pip_value = 0.01

        # Calculate lot size
        # Risk = (Stop Loss in pips) * (Pip Value) * (Lot Size) * (Contract Size)
        contract_size = 100000  # Standard lot
        stop_loss_pips = stop_loss_distance / pip_value

        if stop_loss_pips > 0:
            # Position size = Risk Amount / (Stop Loss in pips * Pip Value * Contract Size)
            lot_size = risk_amount / (stop_loss_pips * pip_value * contract_size)
        else:
            lot_size = 0.0

        # Ensure minimum lot size (0.01) and maximum based on account
        lot_size = max(
            0.01, min(lot_size, account.balance * self.max_position_size / entry_price)
        )

        # Validate against margin requirements
        leverage = getattr(account, "leverage", 100)  # Default to 100:1 if not set
        required_margin = (lot_size * entry_price * contract_size) / leverage

        # Get available margin (margin_free is already calculated by MT5)
        margin_free = getattr(account, "margin_free", account.balance)
        available_margin = margin_free

        if required_margin > available_margin:
            # Reduce lot size to fit available margin
            lot_size = (available_margin * leverage) / (entry_price * contract_size)
            lot_size = max(0.01, round(lot_size, 2))

            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                f"Position size reduced due to margin constraints: "
                f"required={required_margin:.2f}, available={available_margin:.2f}"
            )

        return round(lot_size, 2)

    def calculate_stop_loss(self, entry_price: float, is_long: bool) -> float:
        """
        Calculate stop loss price
        :param entry_price: Entry price
        :param is_long: True for long position, False for short
        :return: Stop loss price
        """
        if is_long:
            return entry_price * (1 - self.stop_loss_pct)
        else:
            return entry_price * (1 + self.stop_loss_pct)

    def calculate_take_profit(self, entry_price: float, is_long: bool) -> float:
        """
        Calculate take profit price
        :param entry_price: Entry price
        :param is_long: True for long position, False for short
        :return: Take profit price
        """
        if is_long:
            return entry_price * (1 + self.take_profit_pct)
        else:
            return entry_price * (1 - self.take_profit_pct)

    def can_trade(self, account: Account):
        """
        Check if trading is allowed based on risk limits
        :param account: Account object
        :return: (can_trade: bool, reason: str)
        """
        if account.balance <= 0:
            return False, "Insufficient balance"

        # Check maximum drawdown
        if self.initial_balance:
            current_drawdown = (
                self.initial_balance - account.balance
            ) / self.initial_balance
            if current_drawdown > self.max_drawdown:
                return False, f"Maximum drawdown exceeded: {current_drawdown:.2%}"

        # Check daily loss
        if self.daily_start_balance:
            daily_loss = (
                self.daily_start_balance - account.balance
            ) / self.daily_start_balance
            if daily_loss > self.max_daily_loss:
                return False, f"Maximum daily loss exceeded: {daily_loss:.2%}"

        # Check maximum open positions
        if len(account.current_trade) >= self.max_open_positions:
            return False, f"Maximum open positions reached: {self.max_open_positions}"

        return True, "OK"

    def reset_daily(self, account: Account):
        """Reset daily tracking"""
        self.daily_start_balance = account.balance

    def check_correlation_risk(self, account: Account, new_pair: CurrencyPair) -> tuple:
        """
        Check if new position would create excessive correlation

        :param account: Account object
        :param new_pair: Currency pair for new position
        :return: (can_trade: bool, reason: str)
        """
        if len(account.current_trade) == 0:
            return True, "OK"

        # Get symbols of open positions
        open_symbols = [trade.pair.symbol for trade in account.current_trade.values()]

        # Extract base and quote currencies
        new_base = new_pair.symbol[:3]
        new_quote = new_pair.symbol[3:]

        # Count correlated positions
        # High correlation if same base or quote currency
        correlation_count = 0
        correlated_symbols = []

        for symbol in open_symbols:
            base = symbol[:3]
            quote = symbol[3:]

            # Check for same base or quote currency
            if new_base == base or new_quote == quote:
                correlation_count += 1
                correlated_symbols.append(symbol)

        # Limit: max 2 correlated positions (including the new one)
        max_correlated = 2
        if correlation_count >= max_correlated:
            return False, (
                f"Too many correlated positions: {correlation_count} positions share "
                f"base/quote currency with {new_pair.symbol} "
                f"(correlated: {', '.join(correlated_symbols)})"
            )

        return True, "OK"
