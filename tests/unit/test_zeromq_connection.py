import asyncio

import pytest

zmq = pytest.importorskip("zmq")

from mt5_connection.zeromq_conn import ZeroMQConnection


class FakeSocket:
    def __init__(self):
        self.sent_json = None
        self.sent_multipart = None
        self.closed = False
        self._recv_json_value = {"ok": True}
        self._recv_multipart_value = [b"EURUSD", b'{"symbol":"EURUSD","bid":1.1,"ask":1.2}']

    def setsockopt(self, *args, **kwargs):
        return None

    def send_json(self, msg, flags=None):
        self.sent_json = (msg, flags)

    def send_multipart(self, parts, flags=None):
        self.sent_multipart = (parts, flags)

    def recv_json(self, flags=None):
        return self._recv_json_value

    def recv_multipart(self, flags=None):
        return self._recv_multipart_value


class ErrorSocket(FakeSocket):
    def send_json(self, msg, flags=None):
        raise zmq.Again()

    def recv_json(self, flags=None):
        raise zmq.Again()


def test_send_msg_req_sets_payload():
    sock = FakeSocket()
    conn = ZeroMQConnection(sock, "REQ", timeout=1.0)
    payload = {"request": 100}

    conn.send_msg(payload)

    assert sock.sent_json[0] == payload
    assert sock.sent_json[1] == zmq.NOBLOCK


def test_send_msg_pub_sends_multipart():
    sock = FakeSocket()
    conn = ZeroMQConnection(sock, "PUB", timeout=1.0)
    payload = {"symbol": "EURUSD", "bid": 1.1, "ask": 1.2}

    conn.send_msg(payload)

    parts, flags = sock.sent_multipart
    assert parts[0] == b"EURUSD"
    assert b'"symbol": "EURUSD"' in parts[1]
    assert flags == zmq.NOBLOCK


@pytest.mark.asyncio
async def test_get_response_req_returns_json():
    sock = FakeSocket()
    conn = ZeroMQConnection(sock, "REQ", timeout=1.0)

    response = await conn.get_response()

    assert response == {"ok": True}
    assert conn.last_recv_ts() is not None


@pytest.mark.asyncio
async def test_get_response_sub_returns_json():
    sock = FakeSocket()
    conn = ZeroMQConnection(sock, "SUB", timeout=1.0)

    response = await conn.get_response()

    assert response["symbol"] == "EURUSD"


def test_send_msg_timeout_raises():
    sock = ErrorSocket()
    conn = ZeroMQConnection(sock, "REQ", timeout=1.0)

    with pytest.raises(TimeoutError):
        conn.send_msg({"request": 100})


@pytest.mark.asyncio
async def test_get_response_error_raises_connection_error():
    sock = ErrorSocket()
    conn = ZeroMQConnection(sock, "REQ", timeout=0.01)

    with pytest.raises(ConnectionError):
        await conn.get_response(timeout=0.01)
