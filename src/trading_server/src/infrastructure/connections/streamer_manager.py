"""
Streamer connection manager
Manages tick streamer connections
"""

import json
import socket
import threading
from typing import Dict, List, Optional

from codes.socket_code import Socket
from models.currency_pair import CurrencyPair
from mt5_connection.tick_streamer import MT5TickStreamer
from connectors.mt5_tick_connector import MT5TickConnector
from connectors.base import ConnectorConfig, IDataSourceConnector


class StreamerManager:
    """Manages tick streamer connections"""

    def __init__(
        self, database, stop_char: str = "\n", verbose: bool = False, console_lock=None
    ):
        """
        Initialize streamer manager
        :param database: Database instance
        :param stop_char: Character that marks end of message
        :param verbose: Enable verbose logging
        :param console_lock: Thread lock for console output
        """
        self.database = database
        self.stop_char = stop_char
        self.verbose = verbose
        self.console_lock = console_lock
        self.streamers: List[MT5TickStreamer] = []
        self.currency_pairs: Dict[str, CurrencyPair] = {}
        self.connectors: Dict[str, IDataSourceConnector] = {}  # symbol -> connector

    def authenticate_streamer(self, client: socket.socket, infos: Dict) -> bool:
        """
        Authenticate and set up a streamer connection
        :param client: Client socket
        :param infos: Authentication info dictionary
        :return: True if successful
        """
        if len(infos) != 3:
            return False

        # Send successful auth response
        data = {"auth_status": Socket.SUCCESSFUL_AUTH.value}
        client.send(bytes(json.dumps(data) + "\n", "utf-8"))

        # Create currency pair
        pair = CurrencyPair(infos["symbol"], infos["digits"])
        self.currency_pairs[infos["symbol"]] = pair

        # Create and start streamer
        streamer = MT5TickStreamer(
            client, pair, self.stop_char, self.verbose, self.console_lock, self.database
        )

        threading.Thread(target=streamer.receive_tick).start()
        self.streamers.append(streamer)

        # Create connector wrapping the streamer
        connector_config = ConnectorConfig(
            source="mt5",
            symbol=infos["symbol"],
            extra_config={"digits": infos["digits"]},
        )
        connector = MT5TickConnector(
            socket=client,
            symbol=infos["symbol"],
            config=connector_config,
            streamer=streamer,  # Use existing streamer
        )
        self.connectors[infos["symbol"]] = connector

        return True

    def get_currency_pairs(self) -> Dict[str, CurrencyPair]:
        """Get all currency pairs"""
        return self.currency_pairs.copy()

    def get_connectors(self) -> List[IDataSourceConnector]:
        """
        Get all data source connectors

        :return: List of connector instances
        """
        return list(self.connectors.values())

    def get_connector(self, symbol: str) -> Optional[IDataSourceConnector]:
        """
        Get connector for a specific symbol

        :param symbol: Trading symbol
        :return: Connector instance or None if not found
        """
        return self.connectors.get(symbol)
