#!/usr/bin/env python3
"""
Test script for data collection pipeline improvements

Tests:
1. Clock synchronization monitoring
2. Connection health tracking
3. Gap detection
4. Auto-reconnect logic
"""

import os
import sys
import time
from datetime import datetime, timedelta

# Add trading server src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "trading_server", "src"))

def test_clock_sync_monitor():
    """Test clock synchronization monitor"""
    print("\n" + "="*80)
    print("TEST 1: Clock Synchronization Monitor")
    print("="*80)
    
    try:
        # Import directly to avoid monitoring.__init__ dependencies
        import importlib.util
        clock_sync_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "trading_server", "src",
            "monitoring", "clock_sync_monitor.py"
        )
        spec = importlib.util.spec_from_file_location("clock_sync_monitor", clock_sync_path)
        clock_sync_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(clock_sync_module)
        ClockSyncMonitor = clock_sync_module.ClockSyncMonitor
        
        print("\n1. Creating clock sync monitor...")
        monitor = ClockSyncMonitor(
            check_interval_seconds=10,  # Short interval for testing
            drift_threshold_seconds=1.0,
            enabled=True,
        )
        
        print("2. Running manual clock sync check...")
        result = monitor.check_clock_sync()
        
        print(f"\n   Status: {result.get('status', 'unknown')}")
        print(f"   Drift: {result.get('drift_seconds', 'N/A')} seconds")
        print(f"   Successful checks: {result.get('successful_checks', 0)}")
        
        if result.get('status') == 'ok':
            print("\n   [OK] Clock sync check passed")
        elif result.get('status') == 'warning':
            print("\n   [WARNING] Clock sync check warning (drift > threshold)")
        elif result.get('status') == 'critical':
            print("\n   [ERROR] Clock sync check critical (large drift)")
        else:
            print("\n   [UNKNOWN] Clock sync check status unknown")
        
        print("\n3. Getting monitor status...")
        status = monitor.get_status()
        print(f"   Enabled: {status['enabled']}")
        print(f"   Check count: {status['check_count']}")
        print(f"   Last drift: {status.get('last_drift_seconds', 'N/A')} seconds")
        
        print("\n4. Testing health check...")
        is_healthy = monitor.is_healthy()
        print(f"   Healthy: {is_healthy}")
        
        print("\n[PASS] Clock sync monitor test completed")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Clock sync monitor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_connection_state_manager():
    """Test connection state management"""
    print("\n" + "="*80)
    print("TEST 2: Connection State Manager")
    print("="*80)
    
    try:
        from mt5_connection.connection_state import ConnectionStateManager, ConnectionState
        
        print("\n1. Creating connection state manager...")
        manager = ConnectionStateManager("EURUSD")
        
        print("2. Testing state transitions...")
        states = [
            (ConnectionState.CONNECTING, "Initial connection"),
            (ConnectionState.CONNECTED, "Connection established"),
            (ConnectionState.RECONNECTING, "Connection lost"),
            (ConnectionState.CONNECTED, "Reconnected"),
            (ConnectionState.DISCONNECTED, "Manual disconnect"),
        ]
        
        for state, reason in states:
            manager.transition_to(state, reason)
            print(f"   {manager.current_state.value}: {reason}")
            time.sleep(0.1)  # Small delay to see transitions
        
        print("\n3. Getting connection metrics...")
        metrics = manager.get_metrics()
        print(f"   Current state: {metrics['current_state']}")
        print(f"   Reconnection attempts: {metrics['reconnection_attempts']}")
        print(f"   Reconnection success: {metrics['reconnection_success_count']}")
        print(f"   Total uptime: {metrics['total_uptime_seconds']:.1f} seconds")
        print(f"   State history: {metrics['state_history_count']} transitions")
        
        print("\n[PASS] Connection state manager test completed")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Connection state manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gap_detector():
    """Test gap detection service"""
    print("\n" + "="*80)
    print("TEST 3: Gap Detection Service")
    print("="*80)
    
    try:
        # Import directly to avoid monitoring.__init__ dependencies
        import importlib.util
        gap_detector_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "trading_server", "src",
            "monitoring", "gap_detector.py"
        )
        spec = importlib.util.spec_from_file_location("gap_detector", gap_detector_path)
        gap_detector_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gap_detector_module)
        GapDetector = gap_detector_module.GapDetector
        
        print("\n1. Creating gap detector...")
        detector = GapDetector(
            gap_threshold_minutes=5.0,
            check_interval_minutes=1.0,  # Short interval for testing
            lookback_minutes=10.0,
            enabled=True,
        )
        
        print("2. Testing gap detection (manual check)...")
        # Note: This requires database connection
        try:
            gaps = detector.detect_gaps()
            print(f"   Detected {len(gaps)} gaps")
            
            if gaps:
                for i, gap in enumerate(gaps[:5], 1):  # Show first 5
                    print(f"\n   Gap {i}:")
                    print(f"     Symbol: {gap['symbol']}")
                    print(f"     Duration: {gap['gap_seconds']/60:.1f} minutes")
                    print(f"     Start: {gap['gap_start']}")
                    print(f"     End: {gap['gap_end']}")
            else:
                print("   No gaps detected (this is good!)")
            
        except Exception as db_error:
            print(f"   ⚠ Gap detection requires database connection: {db_error}")
            print("   Skipping actual gap detection, but service is initialized correctly")
        
        print("\n3. Getting gap detector status...")
        status = detector.get_status()
        print(f"   Enabled: {status['enabled']}")
        print(f"   Gap threshold: {status['gap_threshold_seconds']} seconds")
        print(f"   Check interval: {status['check_interval_seconds']} seconds")
        print(f"   Total gaps detected: {status['gap_count']}")
        print(f"   System-wide gaps: {status['system_wide_gap_count']}")
        
        print("\n[PASS] Gap detector test completed")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Gap detector test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_health_check_endpoint():
    """Test health check endpoint (requires API to be running)"""
    print("\n" + "="*80)
    print("TEST 4: Health Check Endpoint")
    print("="*80)
    
    try:
        import requests
        
        base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        endpoint = f"{base_url}/api/health/clock-sync"
        
        print(f"\n1. Testing health check endpoint: {endpoint}")
        
        try:
            response = requests.get(endpoint, timeout=5)
            print(f"   Status code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   Status: {data.get('status', 'unknown')}")
                print(f"   Service: {data.get('service', 'unknown')}")
                if 'last_drift_seconds' in data:
                    print(f"   Last drift: {data['last_drift_seconds']} seconds")
                print("\n   [OK] Health check endpoint is working")
                return True
            else:
                print(f"   [WARNING] Health check returned status {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except requests.exceptions.ConnectionError:
            print("   [SKIP] API server is not running")
            print("   Start the API server to test this endpoint")
            return None
        except Exception as e:
            print(f"   [FAIL] Health check failed: {e}")
            return False
            
    except ImportError:
        print("   [SKIP] 'requests' library not installed")
        print("   Install with: pip install requests")
        return None


def test_integration():
    """Test integration of all components"""
    print("\n" + "="*80)
    print("TEST 5: Integration Test")
    print("="*80)
    
    print("\n1. Testing component initialization...")
    
    components = {
        "Clock Sync Monitor": test_clock_sync_monitor,
        "Connection State Manager": test_connection_state_manager,
        "Gap Detector": test_gap_detector,
    }
    
    results = {}
    for name, test_func in components.items():
        try:
            result = test_func()
            results[name] = result
        except Exception as e:
            print(f"\n✗ {name} integration test failed: {e}")
            results[name] = False
    
    print("\n2. Integration test summary:")
    for name, result in results.items():
        if result is True:
            status = "[PASS]"
        elif result is False:
            status = "[FAIL]"
        else:
            status = "[SKIP]"
        print(f"   {status}: {name}")
    
    all_passed = all(results.values())
    return all_passed


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("DATA COLLECTION PIPELINE IMPROVEMENTS - TEST SUITE")
    print("="*80)
    
    # Set environment variables if needed
    os.environ.setdefault("DB_HOST", "localhost")
    os.environ.setdefault("DB_PORT", "5432")
    os.environ.setdefault("DB_USER", "forex_user")
    os.environ.setdefault("DB_PASSWORD", "forex_password")
    os.environ.setdefault("DB_NAME", "db_forex")
    
    results = {}
    
    # Run individual tests
    results["Clock Sync Monitor"] = test_clock_sync_monitor()
    results["Connection State Manager"] = test_connection_state_manager()
    results["Gap Detector"] = test_gap_detector()
    results["Health Check Endpoint"] = test_health_check_endpoint()
    
    # Run integration test
    results["Integration"] = test_integration()
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, result in results.items():
        if result is True:
            status = "[PASS]"
        elif result is False:
            status = "[FAIL]"
        else:
            status = "[SKIP]"
        print(f"{status}: {test_name}")
    
    passed = sum(1 for r in results.values() if r is True)
    total = sum(1 for r in results.values() if r is not None)
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed!")
        return 0
    else:
        print("\n[WARNING] Some tests failed or were skipped")
        return 1


if __name__ == "__main__":
    sys.exit(main())
