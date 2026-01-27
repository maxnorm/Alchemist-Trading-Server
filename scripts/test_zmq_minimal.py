#!/usr/bin/env python3
"""Minimal ZeroMQ test to debug EA communication"""
import zmq
import json
import time

# Test parameters
HOST = "127.0.0.1"
PORT = 5556
LOGIN = 452449
AUTH_TOKEN = "q5vtY4Oyb2yaei_svLvMk-gDXsTcNFIQyxjI83oTeY4"

print(f"Connecting to {HOST}:{PORT}...")
context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.setsockopt(zmq.RCVTIMEO, 10000)
socket.connect(f"tcp://{HOST}:{PORT}")

# Test 1: Send auth request
print("\n=== Test 1: Authentication Request ===")
auth_request = {
    "auth_code": 2,
    "login": LOGIN,
    "auth_token": AUTH_TOKEN,
}
print(f"Sending: {json.dumps(auth_request, indent=2)}")
socket.send_string(json.dumps(auth_request))

print("Waiting for response...")
response_str = socket.recv_string()
print(f"Received (raw): {response_str}")
response = json.loads(response_str)
print(f"Received (parsed): {json.dumps(response, indent=2)}")

# Test 2: Send account info request (requires new socket after REQ/REP)
print("\n=== Test 2: Account Info Request ===")
socket.close()
socket = context.socket(zmq.REQ)
socket.setsockopt(zmq.RCVTIMEO, 10000)
socket.connect(f"tcp://{HOST}:{PORT}")

account_request = {"request": 100}
print(f"Sending: {json.dumps(account_request, indent=2)}")
socket.send_string(json.dumps(account_request))

print("Waiting for response...")
response_str = socket.recv_string()
print(f"Received (raw): {response_str}")
response = json.loads(response_str)
print(f"Received (parsed): {json.dumps(response, indent=2)}")

socket.close()
context.term()
print("\nTest complete!")
