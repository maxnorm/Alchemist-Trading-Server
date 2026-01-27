#!/usr/bin/env python3
"""
Execute MT5 Order Test - TC-MT5-TRADE-002
This script executes a market BUY order test through the server.

Usage:
    docker compose exec server python /app/scripts/run_mt5_order_test.py
    OR
    python scripts/run_mt5_order_test.py (if run from server container)
"""

import sys
import os
import time
from pathlib import Path

# Add paths
sys.path.insert(0, '/app')
sys.path.insert(0, '/app/src/backend/trading_server/src')

print("="*70)
print("MT5 Order Execution Test - TC-MT5-TRADE-002")
print("="*70)
print("\n[INFO] Testing Market BUY Order Execution")
print("[INFO] Account: 452449")
print("[INFO] Symbol: EURUSD")
print("[INFO] Lot Size: 0.01")
print("[INFO] Order Type: BUY (Market)")
print()

try:
    # Try to import server module
    try:
        from src.backend.trading_server.src import server
    except ImportError:
        try:
            import server
        except ImportError:
            # Try absolute import
            sys.path.insert(0, '/app/src/backend/trading_server/src')
            import server
    
    # Get server instance
    s = getattr(server, '_global_server_instance', None)
    
    if not s:
        print("[ERROR] Server instance not found")
        print("[INFO] The server may not have stored the global instance")
        print("[INFO] Trying alternative approach...")
        
        # Alternative: Check if server module has accounts
        if hasattr(server, 'Server'):
            print("[INFO] Server class found, but instance not accessible")
            print("[INFO] You may need to modify app.py to store the instance")
            print("\n[INFO] Alternative: Use test_mt5_orders_simple.py script")
            sys.exit(1)
        else:
            print("[ERROR] Cannot access server instance")
            sys.exit(1)
    
    print("[OK] Server instance found")
    
    # Check connected accounts
    if not hasattr(s, '_Server__accounts'):
        print("[ERROR] Cannot access server accounts")
        sys.exit(1)
    
    accounts = s._Server__accounts
    print(f"[OK] Connected accounts: {len(accounts)}")
    
    if accounts:
        for acc in accounts:
            print(f"   - Account: {acc.login}")
    else:
        print("[ERROR] No accounts connected")
        print("[INFO] Make sure the EA terminal is connected")
        sys.exit(1)
    
    # Find account 452449
    account = None
    for acc in accounts:
        if acc.login == 452449:
            account = acc
            break
    
    if not account:
        print(f"\n[ERROR] Account 452449 not found in connected accounts")
        print(f"[INFO] Available accounts: {[acc.login for acc in accounts]}")
        print(f"[INFO] Make sure the EA terminal is connected for account 452449")
        sys.exit(1)
    
    print(f"\n[OK] Account 452449 found")
    
    # Check if account has terminal
    if not hasattr(account, 'terminal') or account.terminal is None:
        print("[ERROR] Account does not have a terminal connection")
        print("[INFO] Make sure the EA terminal is connected")
        sys.exit(1)
    
    print(f"[OK] Terminal connection verified")
    
    # Send test order
    print("\n" + "="*70)
    print("Sending Test BUY Order")
    print("="*70)
    print("\n[INFO] Order details:")
    print("   Symbol: EURUSD")
    print("   Type: BUY (Market)")
    print("   Lot size: 0.01")
    print()
    
    try:
        # Use server's send_test_order method
        trade = s.send_test_order(452449, 'EURUSD', 0.01, 'BUY')
        
        if trade:
            print("\n" + "="*70)
            print("[✅ SUCCESS] Order EXECUTED!")
            print("="*70)
            print(f"\n[OK] Order Details:")
            print(f"   Ticket: {trade.ticket}")
            print(f"   Symbol: {trade.pair.symbol if hasattr(trade, 'pair') else 'N/A'}")
            print(f"   Open Price: {trade.open_price}")
            print(f"   Lot Size: {trade.lotsize}")
            print(f"   Type: BUY")
            
            if hasattr(trade, 'open_time'):
                print(f"   Open Time: {trade.open_time}")
            
            print("\n[INFO] Next Steps:")
            print("   1. Check MT5 terminal for open position")
            print("   2. Verify position in dashboard")
            print("   3. Check database for trade record")
            print("   4. Proceed with TC-MT5-TRADE-006 (Close Position)")
            
            print("\n" + "="*70)
            print("Test Result: ✅ PASS")
            print("="*70)
            
        else:
            print("\n" + "="*70)
            print("[❌ FAILED] Order was not executed")
            print("="*70)
            print("\n[INFO] Possible reasons:")
            print("   1. Order was rejected by MT5")
            print("   2. Insufficient margin")
            print("   3. Market is closed")
            print("   4. Invalid symbol or lot size")
            print("   5. AutoTrading not enabled in MT5")
            print("\n[INFO] Check server logs for details:")
            print("   docker compose logs server | Select-String -Pattern 'order|BUY|ERROR'")
            print("\n[INFO] Check MT5 terminal EA logs for error codes")
            
            print("\n" + "="*70)
            print("Test Result: ❌ FAIL")
            print("="*70)
            sys.exit(1)
            
    except Exception as e:
        print(f"\n[ERROR] Exception during order execution: {e}")
        import traceback
        traceback.print_exc()
        print("\n" + "="*70)
        print("Test Result: ❌ FAIL (Exception)")
        print("="*70)
        sys.exit(1)
        
except Exception as e:
    print(f"\n[ERROR] Failed to access server: {e}")
    import traceback
    traceback.print_exc()
    print("\n[INFO] Troubleshooting:")
    print("   1. Make sure server is running: docker compose ps server")
    print("   2. Check server logs: docker compose logs server")
    print("   3. Try alternative test script: python scripts/test_mt5_orders_simple.py")
    sys.exit(1)
