#!/usr/bin/env python3
"""Debug ZeroMQ JSON communication with EA"""
import zmq
import json

HOST = "127.0.0.1"
PORT = 5556

context = zmq.Context()

# Test different JSON formats
test_cases = [
    {
        "name": "Standard format with spaces",
        "data": {"auth_code": 2, "login": 452449, "auth_token": "q5vtY4Oyb2yaei_svLvMk-gDXsTcNFIQyxjI83oTeY4"},
        "format": lambda d: json.dumps(d)
    },
    {
        "name": "Compact format (no spaces)",
        "data": {"auth_code": 2, "login": 452449, "auth_token": "q5vtY4Oyb2yaei_svLvMk-gDXsTcNFIQyxjI83oTeY4"},
        "format": lambda d: json.dumps(d, separators=(',', ':'))
    },
    {
        "name": "Account info request",
        "data": {"request": 100},
        "format": lambda d: json.dumps(d)
    },
]

for i, test in enumerate(test_cases):
    print(f"\n{'='*70}")
    print(f"Test {i+1}: {test['name']}")
    print(f"{'='*70}")
    
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.RCVTIMEO, 5000)
    socket.connect(f"tcp://{HOST}:{PORT}")
    
    message = test['format'](test['data'])
    print(f"Sending: {message}")
    print(f"Length: {len(message)} bytes")
    print(f"Bytes: {message.encode('utf-8').hex()}")
    
    socket.send_string(message)
    
    try:
        response_str = socket.recv_string()
        print(f"Response: {response_str}")
        response = json.loads(response_str)
        
        if response.get("auth_status") == 0:
            print("[SUCCESS] Authentication successful!")
        elif "currency" in response:
            print("[SUCCESS] Account info received!")
        else:
            print(f"[FAIL] {response.get('comment', 'Unknown error')}")
    except zmq.Again:
        print("[TIMEOUT] No response from EA")
    except Exception as e:
        print(f"[ERROR] {e}")
    
    socket.close()

context.term()
print("\n" + "="*70)
print("Debug complete!")
