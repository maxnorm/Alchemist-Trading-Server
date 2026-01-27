#!/usr/bin/env python3
import os
import time

from dotenv import load_dotenv

from server import Server
from codes.order_type import OrderType
from models.currency_pair import CurrencyPair


def main():
    load_dotenv()

    login = os.getenv("ZMQ_TEST_LOGIN")
    auth_token = os.getenv("ZMQ_TEST_AUTH_TOKEN")
    symbol = os.getenv("ZMQ_TEST_SYMBOL", "EURUSD")
    digits = int(os.getenv("ZMQ_TEST_DIGITS", "5"))
    lotsize = float(os.getenv("ZMQ_TEST_LOTSIZE", "0.01"))

    if not login or not auth_token:
        raise SystemExit(
            "Missing ZMQ_TEST_LOGIN or ZMQ_TEST_AUTH_TOKEN in environment."
        )

    server = Server(verbose=True)
    account = server.connect_account(
        account_login=int(login),
        auth_token=auth_token,
        symbol=symbol,
        digits=digits,
    )

    pair = CurrencyPair(symbol, digits)
    print("Submitting test order...")
    trade = account.send_order(OrderType.BUY, pair, lotsize)
    print(f"Trade executed: ticket={trade.ticket}, price={trade.open_price}")

    time.sleep(2)


if __name__ == "__main__":
    main()
