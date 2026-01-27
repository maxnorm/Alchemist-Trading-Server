#!/usr/bin/env python3
"""
Test ZeroMQ account info request.
Tests authentication and account info retrieval.
"""
import os
import zmq
import json
from dotenv import load_dotenv

load_dotenv()


def test_account_info():
    """Test account info request via ZeroMQ."""
    host = os.getenv("ZMQ_HOST", "127.0.0.1")
    port = int(os.getenv("ZMQ_ORDER_PORT", 5556))
    login = int(os.getenv("ZMQ_TEST_LOGIN", 0))
    auth_token = os.getenv("ZMQ_TEST_AUTH_TOKEN", "")

    if not login or not auth_token:
        print("❌ Missing ZMQ_TEST_LOGIN or ZMQ_TEST_AUTH_TOKEN in environment.")
        return False

    context = zmq.Context()
    req_socket = context.socket(zmq.REQ)
    req_socket.connect(f"tcp://{host}:{port}")
    req_socket.setsockopt(zmq.RCVTIMEO, 10000)

    try:
        # Step 1: Authenticate
        print("Step 1: Authenticating...")
        auth_request = {"auth_code": 2, "login": login, "auth_token": auth_token}
        req_socket.send_string(json.dumps(auth_request))
        auth_response = json.loads(req_socket.recv_string())
        print(f"   Auth response: {auth_response}")

        if auth_response.get("auth_status") != 0:
            print(f"❌ Authentication failed: {auth_response.get('comment')}")
            return False

        print("✅ Authentication successful")

        # Step 2: Request account info
        print("\nStep 2: Requesting account info...")
        account_request = {"request": 100}
        req_socket.send_string(json.dumps(account_request))
        account_response = json.loads(req_socket.recv_string())
        print(f"✅ Account Info:")
        print(f"   Currency: {account_response.get('currency')}")
        print(f"   Leverage: {account_response.get('leverage')}")
        print(f"   Balance: {account_response.get('balance')}")
        print(f"   Equity: {account_response.get('equity')}")
        print(f"   Profit: {account_response.get('profit')}")
        print(f"   Margin: {account_response.get('margin')}")
        print(f"   Free Margin: {account_response.get('margin_free')}")

        return True

    except zmq.Again:
        print("❌ Timeout: EA did not respond")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        req_socket.close()
        context.term()


if __name__ == "__main__":
    success = test_account_info()
    exit(0 if success else 1)
