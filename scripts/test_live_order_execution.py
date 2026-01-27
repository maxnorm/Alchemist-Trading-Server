#!/usr/bin/env python3
"""
Live Order Execution Test for ZeroMQ Integration
WARNING: This executes REAL trades on your account!

Usage:
    python scripts/test_live_order_execution.py
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
ZMQ_HOST = os.getenv("ZMQ_HOST", "127.0.0.1")
ZMQ_ORDER_PORT = int(os.getenv("ZMQ_ORDER_PORT", "5556"))
MT5_ACCOUNT_ID = int(os.getenv("MT5_ACCOUNT_ID", "452449"))
MT5_AUTH_TOKEN = os.getenv("MT5_AUTH_TOKEN", "q5vtY4Oyb2yaei_svLvMk-gDXsTcNFIQyxjI83oTeY4")

# Order parameters (can be overridden by command line)
TEST_SYMBOL = os.getenv("TEST_SYMBOL", "EURUSD")
TEST_LOT_SIZE = 0.01  # Micro lot - minimal risk
HOLD_DURATION_SECONDS = 30  # How long to keep the position open


def send_request(socket, message):
    """Send request and get response"""
    socket.send_string(json.dumps(message))
    response = socket.recv_string()
    return json.loads(response)


def print_section(text):
    """Print section header"""
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70 + "\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Live Order Execution Test")
    parser.add_argument("--auto-execute", action="store_true", 
                       help="Skip confirmation and execute order automatically")
    parser.add_argument("--symbol", type=str, default=TEST_SYMBOL,
                       help="Symbol to trade (default: EURUSD)")
    parser.add_argument("--lot-size", type=float, default=TEST_LOT_SIZE,
                       help="Lot size (default: 0.01)")
    parser.add_argument("--hold-seconds", type=int, default=HOLD_DURATION_SECONDS,
                       help="Hold duration in seconds (default: 30)")
    args = parser.parse_args()
    
    test_symbol = args.symbol
    test_lot_size = args.lot_size
    hold_duration = args.hold_seconds
    
    print_section("LIVE ORDER EXECUTION TEST")
    print(f"WARNING: This will place a REAL order on account {MT5_ACCOUNT_ID}")
    print(f"Symbol: {test_symbol}")
    print(f"Size: {test_lot_size} lots")
    print(f"Hold duration: {hold_duration} seconds")
    print("\n" + "=" * 70)
    
    # User confirmation (unless auto-execute)
    if not args.auto_execute:
        response = input("\nType 'EXECUTE' to proceed: ")
        if response != "EXECUTE":
            print("Test cancelled.")
            return
    else:
        print("\n[AUTO-EXECUTE] Proceeding automatically (--auto-execute flag set)")
        time.sleep(2)  # Brief pause to show the warning
    
    # Setup ZeroMQ
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.RCVTIMEO, 10000)
    socket.setsockopt(zmq.SNDTIMEO, 10000)
    socket.connect(f"tcp://{ZMQ_HOST}:{ZMQ_ORDER_PORT}")
    print(f"\n[INFO] Connected to {ZMQ_HOST}:{ZMQ_ORDER_PORT}")
    
    try:
        # Step 1: Authenticate (optional - may not be required)
        print("\n[STEP 1] Authenticating...")
        auth_request = {
            "auth_code": 2,
            "login": MT5_ACCOUNT_ID,
            "auth_token": MT5_AUTH_TOKEN
        }
        auth_response = send_request(socket, auth_request)
        
        if auth_response.get("auth_status") != 0:
            print(f"[WARN] Authentication failed: {auth_response.get('comment')}")
            print("[INFO] Continuing anyway - EA may not require auth for orders")
        else:
            print(f"[PASS] Authenticated as terminal {auth_response['terminal_id']}")
        
        # Step 2: Get initial account balance
        print("\n[STEP 2] Getting initial account balance...")
        account_request = {"request": 100}  # ACCOUNT_INFOS
        account_info = send_request(socket, account_request)
        initial_balance = account_info['balance']
        initial_equity = account_info['equity']
        print(f"[INFO] Initial Balance: ${initial_balance:.2f}")
        print(f"[INFO] Initial Equity: ${initial_equity:.2f}")
        
        # Step 3: Place BUY order
        print(f"\n[STEP 3] Placing BUY order ({test_lot_size} lots {test_symbol})...")
        order_request = {
            "request": 101,  # OPEN_ORDER
            "symbol": test_symbol,
            "order_type": 0,  # ORDER_TYPE_BUY
            "lotsize": test_lot_size,
            "sl": 0.0,  # No stop loss for test
            "tp": 0.0   # No take profit for test
        }
        
        start_time = time.time()
        order_response = send_request(socket, order_request)
        order_latency = (time.time() - start_time) * 1000
        
        print(f"[INFO] Order Response: {json.dumps(order_response, indent=2)}")
        print(f"[INFO] Execution Latency: {order_latency:.2f}ms")
        
        if order_response['return_code'] != 10009:  # TRADE_RETCODE_DONE
            print(f"[ERROR] Order failed: {order_response['comment']}")
            print(f"[INFO] Return code: {order_response['return_code']}")
            return
        
        ticket = order_response['ticket']
        open_price = order_response['price']
        print(f"\n[PASS] Order placed successfully!")
        print(f"       Ticket: {ticket}")
        print(f"       Price: {open_price}")
        print(f"       Lot Size: {order_response['lotsize']}")
        
        # Step 4: Wait before closing
        print(f"\n[STEP 4] Holding position for {hold_duration} seconds...")
        print("         Check MT5 'Trade' tab to see the position...")
        for i in range(hold_duration):
            remaining = hold_duration - i
            print(f"         Closing in {remaining} seconds...", end='\r')
            time.sleep(1)
        print("\n")
        
        # Step 5: Close position
        print(f"[STEP 5] Closing position (ticket {ticket})...")
        close_request = {
            "request": 102,  # CLOSE_ORDER
            "ticket": ticket,
            "lotsize": test_lot_size
        }
        
        start_time = time.time()
        close_response = send_request(socket, close_request)
        close_latency = (time.time() - start_time) * 1000
        
        print(f"[INFO] Close Response: {json.dumps(close_response, indent=2)}")
        print(f"[INFO] Close Latency: {close_latency:.2f}ms")
        
        if close_response['return_code'] != 10009:
            print(f"[WARN] Close may have failed: {close_response['comment']}")
        else:
            print(f"[PASS] Position closed successfully!")
            close_price = close_response.get('order', {}).get('close_price', 0)
            print(f"       Close Price: {close_price}")
        
        # Step 6: Final account status
        print("\n[STEP 6] Final account status...")
        final_account = close_response.get('account', send_request(socket, {"request": 100}))
        final_balance = final_account['balance']
        final_equity = final_account['equity']
        
        balance_change = final_balance - initial_balance
        equity_change = final_equity - initial_equity
        
        print(f"[INFO] Final Balance: ${final_balance:.2f} ({balance_change:+.2f})")
        print(f"[INFO] Final Equity: ${final_equity:.2f} ({equity_change:+.2f})")
        
        # Summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"Symbol: {test_symbol}")
        print(f"Lot Size: {test_lot_size}")
        print(f"Open Price: {open_price}")
        print(f"Close Price: {close_price if 'close_price' in locals() else 'N/A'}")
        print(f"Order Latency: {order_latency:.2f}ms")
        print(f"Close Latency: {close_latency:.2f}ms")
        print(f"Balance Change: ${balance_change:+.2f}")
        print(f"Status: {'PASS' if close_response['return_code'] == 10009 else 'PARTIAL'}")
        print("=" * 70)
        
    except zmq.Again:
        print("\n[ERROR] Timeout: EA did not respond within 10 seconds")
        print("[INFO] Check that Trading EA is running and AutoTrading is enabled")
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        socket.close()
        context.term()
        print("\n[INFO] Connection closed")


if __name__ == "__main__":
    main()
