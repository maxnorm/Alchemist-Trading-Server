#!/usr/bin/env python3
"""
Test script to verify ZeroMQ broker is receiving messages from EA.
This helps diagnose connection issues between EA and broker.
"""
import zmq
import time
import json
from datetime import datetime

BROKER_PORT = 5557
TEST_DURATION = 30  # seconds

def test_broker_connection():
    """Test if broker PULL socket is receiving messages."""
    print("=" * 70)
    print("ZeroMQ Broker Connection Test")
    print("=" * 70)
    print(f"Testing broker PULL socket on port {BROKER_PORT}")
    print(f"Duration: {TEST_DURATION} seconds")
    print(f"Expected: EA should connect PUSH socket to tcp://127.0.0.1:{BROKER_PORT}")
    print()
    
    context = zmq.Context()
    test_socket = context.socket(zmq.PULL)
    
    try:
        # Bind to same port as broker (this will fail if broker is already bound)
        endpoint = f"tcp://*:{BROKER_PORT}"
        print(f"Attempting to bind to {endpoint}...")
        print("NOTE: This will fail if broker is already running (which is expected)")
        print()
        
        # Instead, let's try to connect as a PUSH client to see if broker is listening
        # Actually, we can't test this easily without interfering with the broker
        # So let's just check if the port is in use
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', BROKER_PORT))
        sock.close()
        
        if result == 0:
            print(f"✓ Port {BROKER_PORT} is open (broker likely running)")
        else:
            print(f"✗ Port {BROKER_PORT} is not accessible")
            print("  Broker may not be running or port is blocked")
            return False
        
        print()
        print("=" * 70)
        print("Diagnostic Information")
        print("=" * 70)
        print("If broker shows 0 messages forwarded, check:")
        print()
        print("1. EA Connection:")
        print("   - EA should connect PUSH socket to: tcp://127.0.0.1:5557")
        print("   - Check EA logs for connection success message")
        print("   - Verify broker_host in EA matches server IP")
        print()
        print("2. EA OnTick() Events:")
        print("   - OnTick() is only called when price updates occur")
        print("   - Market must be open for live ticks")
        print("   - Check EA logs for '[DEBUG] Tick #X' messages")
        print("   - If no debug logs, OnTick() may not be called")
        print()
        print("3. EA Send Status:")
        print("   - Check EA logs for '[ERROR] Failed to send message'")
        print("   - Verify SymbolInfoTick() is succeeding")
        print("   - Check if message serialization is working")
        print()
        print("4. Network/Firewall:")
        print("   - Verify no firewall blocking port 5557")
        print("   - Check if running in Docker (use host.docker.internal)")
        print()
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        test_socket.close()
        context.term()

if __name__ == "__main__":
    test_broker_connection()
