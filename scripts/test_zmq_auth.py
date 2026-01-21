#!/usr/bin/env python3
"""
Simple ZeroMQ authentication test script.
Tests connection and authentication with MT5 trading EA.
"""
import os
import zmq
import json
from dotenv import load_dotenv

load_dotenv()


def test_auth():
    """Test ZeroMQ authentication with MT5 EA."""
    host = os.getenv("ZMQ_HOST", "127.0.0.1")
    port = int(os.getenv("ZMQ_ORDER_PORT", 5556))
    login = int(os.getenv("ZMQ_TEST_LOGIN", 0))
    auth_token = os.getenv("ZMQ_TEST_AUTH_TOKEN", "")

    if not login or not auth_token:
        print("❌ Missing ZMQ_TEST_LOGIN or ZMQ_TEST_AUTH_TOKEN in environment.")
        print("   Please set these in your .env file.")
        return False

    print(f"Connecting to {host}:{port}...")
    context = zmq.Context()
    req_socket = context.socket(zmq.REQ)
    req_socket.connect(f"tcp://{host}:{port}")
    req_socket.setsockopt(zmq.RCVTIMEO, 10000)  # 10 second timeout

    # Send auth request
    auth_request = {
        "auth_code": 2,
        "login": login,
        "auth_token": auth_token,
    }
    print(f"Sending auth request: login={login}, token={'*' * len(auth_token)}")
    req_socket.send_string(json.dumps(auth_request))

    # Receive response
    try:
        response_str = req_socket.recv_string()
        response = json.loads(response_str)
        print(f"✅ Authentication Response: {response}")

        if response.get("auth_status") == 0:
            print("✅ Authentication SUCCESS")
            print(f"   Terminal ID: {response.get('terminal_id')}")
            return True
        else:
            print(f"❌ Authentication FAILED: {response.get('comment', 'Unknown error')}")
            return False
    except zmq.Again:
        print("❌ Timeout: EA did not respond within 10 seconds")
        print("   Make sure:")
        print("   1. EA is running on a chart")
        print("   2. EA port matches ZMQ_ORDER_PORT")
        print("   3. EA has 'Allow DLL imports' enabled")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        req_socket.close()
        context.term()


if __name__ == "__main__":
    success = test_auth()
    exit(0 if success else 1)
