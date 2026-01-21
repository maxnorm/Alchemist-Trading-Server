#!/usr/bin/env python3
"""
Test Tick Streaming for USDJPY via ZeroMQ
Tests the Streamer EA connection and tick reception
"""
import os
import sys
import time
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "trading_server", "src"))

import zmq
from dotenv import load_dotenv

load_dotenv()

# Configuration
# Default to 127.0.0.1 for direct host testing (not Docker)
default_host = "127.0.0.1"
zmq_host = os.getenv("ZMQ_HOST", default_host)
if zmq_host == "host.docker.internal":
    zmq_host = default_host
ZMQ_HOST = zmq_host
ZMQ_TICK_PORT = int(os.getenv("ZMQ_TICK_PORT", "5555"))
TEST_SYMBOL = "USDJPY"  # Streamer EA is on USDJPY chart
DURATION_SECONDS = 30


def print_section(text):
    """Print section header"""
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70 + "\n")


def main():
    print_section("USDJPY Tick Streaming Test")
    print(f"Connecting to Streamer EA at {ZMQ_HOST}:{ZMQ_TICK_PORT}")
    print(f"Symbol: {TEST_SYMBOL}")
    print(f"Duration: {DURATION_SECONDS} seconds")
    print("\n" + "=" * 70)
    
    # Setup ZeroMQ SUB socket
    context = zmq.Context()
    sub_socket = context.socket(zmq.SUB)
    sub_socket.setsockopt(zmq.RCVTIMEO, 5000)
    sub_socket.connect(f"tcp://{ZMQ_HOST}:{ZMQ_TICK_PORT}")
    
    # Subscribe to symbol (and also try empty string to get all messages)
    sub_socket.setsockopt_string(zmq.SUBSCRIBE, TEST_SYMBOL)
    sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")  # Also subscribe to all
    
    print(f"[INFO] Connected to streamer")
    print(f"[INFO] Subscribed to: {TEST_SYMBOL} and all topics")
    print(f"[INFO] Listening for ticks...")
    print(f"[INFO] Note: If no ticks, market may be closed or EA not receiving OnTick() events\n")
    
    tick_count = 0
    tick_times = []
    start_time = time.time()
    first_tick_time = None
    last_tick = None
    
    try:
        while time.time() - start_time < DURATION_SECONDS:
            try:
                # Receive multipart message: [topic, data]
                # EA sends: pubSocket.send(symbol, ZMQ_SNDMORE); pubSocket.send(msg);
                parts = sub_socket.recv_multipart(zmq.NOBLOCK)
                
                if len(parts) == 2:
                    topic_bytes, message_bytes = parts
                    topic = topic_bytes.decode('utf-8', errors='ignore')
                    message_str = message_bytes.decode('utf-8', errors='ignore')
                    
                    # Debug first message
                    if tick_count == 0:
                        print(f"[DEBUG] Topic: {topic} (bytes: {topic_bytes})")
                        print(f"[DEBUG] Message: {message_str[:100]}...")
                    
                    if not message_str or message_str.strip() == '':
                        print(f"[WARN] Empty message received, topic: {topic}")
                        continue
                    
                    tick_data = json.loads(message_str)
                elif len(parts) == 1:
                    # Single part message (fallback)
                    message_str = parts[0].decode('utf-8', errors='ignore')
                    if not message_str or message_str.strip() == '':
                        continue
                    tick_data = json.loads(message_str)
                else:
                    print(f"[WARN] Unexpected message format: {len(parts)} parts")
                    continue
                
                tick_count += 1
                tick_time = time.time()
                tick_times.append(tick_time)
                last_tick = tick_data
                
                if tick_count == 1:
                    first_tick_time = tick_time
                    print(f"[SUCCESS] First tick received!")
                    print(f"  Symbol: {tick_data.get('symbol')}")
                    print(f"  Bid: {tick_data.get('bid')}")
                    print(f"  Ask: {tick_data.get('ask')}")
                    print(f"  Time: {tick_data.get('datetime', 'N/A')}")
                    print()
                
                # Print every 10th tick
                if tick_count % 10 == 0:
                    elapsed = tick_time - start_time
                    rate = tick_count / elapsed
                    print(f"[INFO] Received {tick_count} ticks ({rate:.2f} ticks/sec)")
                
            except zmq.Again:
                time.sleep(0.1)
                continue
            except Exception as e:
                print(f"[ERROR] Error receiving tick: {e}")
                break
        
        elapsed = time.time() - start_time
        
        # Summary
        print("\n" + "=" * 70)
        print("TICK STREAMING TEST SUMMARY")
        print("=" * 70)
        
        if tick_count > 0:
            tick_rate = tick_count / elapsed
            first_tick_latency = (first_tick_time - start_time) * 1000 if first_tick_time else 0
            
            print(f"Total Ticks Received: {tick_count}")
            print(f"Duration: {elapsed:.2f} seconds")
            print(f"Tick Rate: {tick_rate:.2f} ticks/sec")
            print(f"First Tick Latency: {first_tick_latency:.2f}ms")
            
            if last_tick:
                print(f"\nLast Tick:")
                print(f"  Symbol: {last_tick.get('symbol')}")
                print(f"  Bid: {last_tick.get('bid')}")
                print(f"  Ask: {last_tick.get('ask')}")
                print(f"  Spread: {last_tick.get('ask', 0) - last_tick.get('bid', 0):.5f}")
                print(f"  Time: {last_tick.get('datetime', 'N/A')}")
            
            print(f"\n[SUCCESS] Tick streaming is working!")
            
            if tick_rate < 1.0:
                print(f"[WARN] Low tick rate: {tick_rate:.2f} ticks/sec")
            else:
                print(f"[PASS] Tick rate acceptable: {tick_rate:.2f} ticks/sec")
        else:
            print("[FAIL] No ticks received!")
            print("\nPossible issues:")
            print("  - Streamer EA not on USDJPY chart")
            print("  - Market closed for USDJPY")
            print("  - Symbol not actively trading")
            print("  - Check MT5 Journal for errors")
        
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n[INFO] Test interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        sub_socket.close()
        context.term()
        print("\n[INFO] Connection closed")


if __name__ == "__main__":
    main()
