"""
Broker Factory
Creates broker adapters from configuration
"""

from typing import Dict, Any, Optional
from trading.brokers.base import IBrokerAdapter
from trading.brokers.mt5_adapter import MT5BrokerAdapter
from mt5_connection.zeromq_terminal import ZeroMQTerminal


class BrokerFactory:
    """
    Factory for creating broker adapters from configuration
    """

    @staticmethod
    def create_from_config(
        config: Dict[str, Any], terminal: Optional[ZeroMQTerminal] = None
    ) -> IBrokerAdapter:
        """
        Create broker adapter from configuration

        :param config: Configuration dictionary with 'broker_type' and broker-specific settings
        :param terminal: Optional ZeroMQTerminal instance (for MT5 broker)
        :return: IBrokerAdapter instance
        :raises ValueError: If broker type is unsupported or configuration is invalid
        """
        broker_type = config.get("broker_type", "mt5").lower()

        if broker_type == "mt5":
            if terminal is None:
                raise ValueError("ZeroMQTerminal instance required for MT5 broker")
            return MT5BrokerAdapter.from_terminal(terminal)

        elif broker_type == "ctrader":
            # Future implementation
            raise NotImplementedError("cTrader broker adapter not yet implemented")

        elif broker_type == "crypto":
            # Future implementation
            raise NotImplementedError(
                "Crypto exchange broker adapter not yet implemented"
            )

        else:
            raise ValueError(f"Unsupported broker type: {broker_type}")

    @staticmethod
    def create_mt5_adapter(terminal: ZeroMQTerminal, oms=None) -> MT5BrokerAdapter:
        """
        Convenience method to create MT5 adapter

        :param terminal: ZeroMQTerminal instance
        :param oms: Optional OrderManagementSystem
        :return: MT5BrokerAdapter instance
        """
        return MT5BrokerAdapter.from_terminal(terminal, oms=oms)
