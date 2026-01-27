#!/usr/bin/env python3
"""
End-to-End Tick Streaming Test
Tests the complete integration: Streamer EA -> ZeroMQ -> Trading Server -> Database
"""
import os
import sys
import time
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "trading_server", "src"))

from dotenv import load_dotenv
from infrastructure.zeromq.zeromq_connection_manager import ZeroMQConnectionManager
from models.currency_pair import CurrencyPair
from database import Database

load_dotenv()

# Configuration
ZMQ_HOST = os.getenv("ZMQ_HOST", "127.0.0.1")
ZMQ_TICK_PORT = int(os.getenv("ZMQ_TICK_PORT", "5555"))
TEST_SYMBOL = "USDJPY"
TEST_DIGITS = 3  # USDJPY typically has 3 digits
TEST_DURATION = 60  # Test for 60 seconds
ACCOUNT_LOGIN = int(os.getenv("MT5_ACCOUNT_ID", "452449"))


def print_section(text):
    """Print section header"""
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70 + "\n")


def main():
    print_section("End-to-End Tick Streaming Integration Test")
    print(f"Symbol: {TEST_SYMBOL}")
    print(f"Duration: {TEST_DURATION} seconds")
    print(f"Host: {ZMQ_HOST}:{ZMQ_TICK_PORT}")
    print("\nThis test will:")
    print("  1. Connect to Streamer EA via ZeroMQ")
    print("  2. Receive ticks using Trading Server code")
    print("  3. Process ticks through quality gates")
    print("  4. Store ticks in database")
    print("  5. Verify database storage")
    print("\n" + "=" * 70)
    
    # Initialize components
    print("\n[STEP 1] Initializing components...")
    zmq_manager = ZeroMQConnectionManager(
        host=ZMQ_HOST,
        tick_port=ZMQ_TICK_PORT,
        order_port=5556,  # Not used for streaming
        timeout=30.0
    )
    
    currency_pair = CurrencyPair(TEST_SYMBOL, TEST_DIGITS)
    database = Database()
    
    print(f"[INFO] ZeroMQ Manager initialized")
    print(f"[INFO] Currency Pair: {TEST_SYMBOL} ({TEST_DIGITS} digits)")
    print(f"[INFO] Database connection ready")
    
    # Connect streamer
    print(f"\n[STEP 2] Connecting to Streamer EA...")
    try:
        streamer = zmq_manager.connect_streamer(
            account_login=ACCOUNT_LOGIN,
            symbol=TEST_SYMBOL,
            port_offset=0,
            digits=TEST_DIGITS
        )
        print(f"[SUCCESS] Streamer connected")
    except Exception as e:
        print(f"[ERROR] Failed to connect streamer: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Start receiving ticks in a thread
    print(f"\n[STEP 3] Starting tick reception...")
    import threading
    
    tick_count = [0]  # Use list for mutable counter
    errors = []
    start_time = time.time()
    
    def receive_ticks():
        """Receive ticks in a separate thread"""
        try:
            while time.time() - start_time < TEST_DURATION:
                try:
                    # Use the streamer's receive_tick method
                    result = streamer.receive_tick()
                    if result:
                        tick_count[0] += 1
                        if tick_count[0] % 10 == 0:
                            elapsed = time.time() - start_time
                            rate = tick_count[0] / elapsed if elapsed > 0 else 0
                            print(f"[INFO] Received {tick_count[0]} ticks ({rate:.2f} ticks/sec)")
                except Exception as e:
                    errors.append(str(e))
                    if len(errors) <= 3:  # Only print first few errors
                        print(f"[WARN] Error receiving tick: {e}")
                    time.sleep(0.1)
        except Exception as e:
            errors.append(f"Thread error: {e}")
            print(f"[ERROR] Thread error: {e}")
    
    thread = threading.Thread(target=receive_ticks, daemon=True)
    thread.start()
    
    print(f"[INFO] Tick reception started (running for {TEST_DURATION} seconds)...")
    print(f"[INFO] Monitor database for incoming ticks...\n")
    
    # Wait for test duration
    try:
        thread.join(timeout=TEST_DURATION + 5)
    except KeyboardInterrupt:
        print("\n[INFO] Test interrupted by user")
    
    elapsed = time.time() - start_time
    
    # Check database
    print(f"\n[STEP 4] Checking database for stored ticks...")
    try:
        # Query recent ticks from database
        query = """
            SELECT COUNT(*) as count, 
                   MAX(timestamp) as latest_tick,
                   MIN(timestamp) as earliest_tick
            FROM forex_ticks 
            WHERE symbol = %s 
            AND timestamp > NOW() - INTERVAL '2 minutes'
        """
        
        result = database.execute_query(query, (TEST_SYMBOL,))
        if result:
            db_count = result[0][0] if result[0] else 0
            latest = result[0][1] if result[0] and result[0][1] else None
            earliest = result[0][2] if result[0] and result[0][2] else None
            
            print(f"[INFO] Ticks in database (last 2 minutes): {db_count}")
            if latest:
                print(f"[INFO] Latest tick: {latest}")
            if earliest:
                print(f"[INFO] Earliest tick: {earliest}")
        else:
            print(f"[WARN] No database results")
    except Exception as e:
        print(f"[WARN] Could not query database: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("END-TO-END TEST SUMMARY")
    print("=" * 70)
    
    print(f"Test Duration: {elapsed:.2f} seconds")
    print(f"Ticks Received: {tick_count[0]}")
    
    if tick_count[0] > 0:
        tick_rate = tick_count[0] / elapsed if elapsed > 0 else 0
        print(f"Tick Rate: {tick_rate:.2f} ticks/sec")
        print(f"\n[SUCCESS] Tick streaming is working!")
        
        if tick_rate < 0.5:
            print(f"[WARN] Low tick rate: {tick_rate:.2f} ticks/sec")
        else:
            print(f"[PASS] Tick rate acceptable: {tick_rate:.2f} ticks/sec")
    else:
        print(f"\n[FAIL] No ticks received!")
        print("\nPossible issues:")
        print("  - Market closed for USDJPY")
        print("  - Streamer EA not receiving OnTick() events")
        print("  - Check MT5 Journal for errors")
        print("  - Verify EA is on USDJPY chart with AutoTrading enabled")
    
    if errors:
        print(f"\n[WARN] Errors encountered: {len(errors)}")
        for error in errors[:5]:  # Show first 5 errors
            print(f"  - {error}")
    
    print("=" * 70)
    
    # Cleanup
    try:
        zmq_manager.disconnect_streamer(ACCOUNT_LOGIN)
        print("\n[INFO] Streamer disconnected")
    except:
        pass


if __name__ == "__main__":
    main()
