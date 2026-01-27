#!/usr/bin/env python3
import os
import time

from dotenv import load_dotenv

from server import Server


def main():
    load_dotenv()

    login = os.getenv("ZMQ_TEST_LOGIN")
    auth_token = os.getenv("ZMQ_TEST_AUTH_TOKEN")
    symbol = os.getenv("ZMQ_TEST_SYMBOL", "EURUSD")
    digits = int(os.getenv("ZMQ_TEST_DIGITS", "5"))

    if not login or not auth_token:
        raise SystemExit(
            "Missing ZMQ_TEST_LOGIN or ZMQ_TEST_AUTH_TOKEN in environment."
        )

    server = Server(verbose=True)
    server.connect_account(
        account_login=int(login),
        auth_token=auth_token,
        symbol=symbol,
        digits=digits,
    )

    print("Waiting for ticks...")
    time.sleep(10)
    print("Check database for recent ticks.")


if __name__ == "__main__":
    main()
