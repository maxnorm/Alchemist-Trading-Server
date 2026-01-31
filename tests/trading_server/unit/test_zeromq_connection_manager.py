import sys

import pytest

zmq = pytest.importorskip("zmq")

from infrastructure.zeromq.zeromq_connection_manager import ZeroMQConnectionManager


class FakeSocket:
    def __init__(self):
        self.connected = None
        self.subscribed = None

    def connect(self, address):
        self.connected = address

    def setsockopt_string(self, option, value):
        self.subscribed = (option, value)


class FakeContext:
    def socket(self, socket_type):
        _ = socket_type
        return FakeSocket()


class FakeZMQConnection:
    def __init__(self, socket, socket_type, timeout=30.0):
        self.socket = socket
        self.socket_type = socket_type
        self.timeout = timeout
        self.sent = None

    def send_msg(self, msg):
        self.sent = msg

    async def get_response(self, timeout=None):
        _ = timeout
        return {"auth_status": 0}


class FakeTerminal:
    def __init__(self, zmq_conn):
        self.conn = zmq_conn


class FakeStreamer:
    def __init__(self, zmq_conn, pair, db=None):
        self.conn = zmq_conn
        self.pair = pair
        self.db = db
        self._tick_queue = []
    
    def put_tick(self, tick_data):
        """Queue-based tick forwarding method."""
        self._tick_queue.append(tick_data)


def _install_fake_module(module_name, symbol_name, symbol_value):
    module = type(sys)(module_name)
    setattr(module, symbol_name, symbol_value)
    sys.modules[module_name] = module


def test_connect_terminal_creates_lock(monkeypatch):
    monkeypatch.setattr(
        "infrastructure.zeromq.zeromq_connection_manager.zmq.Context",
        FakeContext,
    )
    monkeypatch.setattr(
        "infrastructure.zeromq.zeromq_connection_manager.ZeroMQConnection",
        FakeZMQConnection,
    )
    _install_fake_module("mt5_connection.zeromq_terminal", "ZeroMQTerminal", FakeTerminal)

    manager = ZeroMQConnectionManager(host="127.0.0.1", order_port=5556, tick_port=5555)
    terminal = manager.connect_terminal(account_login=123, auth_token="token", port_offset=1)

    assert isinstance(terminal, FakeTerminal)
    assert manager.get_terminal_lock(123) is not None


def test_connect_streamer_by_symbol_creates_queue_based_streamer(monkeypatch):
    """Test that connect_streamer_by_symbol creates a queue-based streamer without SUB socket."""
    monkeypatch.setattr(
        "infrastructure.zeromq.zeromq_connection_manager.zmq.Context",
        FakeContext,
    )
    _install_fake_module(
        "mt5_connection.zeromq_tick_streamer",
        "ZeroMQTickStreamer",
        FakeStreamer,
    )

    manager = ZeroMQConnectionManager(host="127.0.0.1", order_port=5556, tick_port=5555)
    streamer = manager.connect_streamer_by_symbol(symbol="EURUSD", digits=5, port_offset=2)

    assert isinstance(streamer, FakeStreamer)
    # Streamer should be created with None for zmq_conn (queue-based)
    assert streamer.conn is None
    # Test that put_tick() method works
    test_tick = {"symbol": "EURUSD", "bid": 1.1000, "ask": 1.1001}
    streamer.put_tick(test_tick)
    assert len(streamer._tick_queue) == 1
    assert streamer._tick_queue[0] == test_tick
