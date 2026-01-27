"""
Stress tests for safety components

Tests safety components under high load and concurrent access.
"""

import pytest
import os
import sys
import tempfile
import threading
import time
import random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/backend/trading_server/src'))

from risk.kill_switch import KillSwitch, KillSwitchState
from risk.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from risk.oms import OrderManagementSystem, Order, OrderState


class TestSafetyUnderLoad:
    """Stress tests for safety components under high load"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_kill_switch_under_high_order_volume(self, temp_dir):
        """Test kill switch responsiveness under high order volume"""
        kill_switch = KillSwitch(audit_log_path=str(temp_dir / "audit.json"))
        kill_switch.arm()
        
        # Simulate high-frequency trading with concurrent checks
        check_count = [0]
        trigger_time = [None]
        detection_times = []
        
        def check_kill_switch():
            while not kill_switch.is_active():
                check_count[0] += 1
                time.sleep(0.001)  # 1ms between checks
                if check_count[0] > 10000:  # Safety limit
                    break
            if trigger_time[0]:
                detection_times.append(time.time() - trigger_time[0])
        
        # Start multiple check threads as daemon threads
        threads = []
        for _ in range(10):
            t = threading.Thread(target=check_kill_switch, daemon=True)
            threads.append(t)
            t.start()
        
        # Wait a bit then trigger
        time.sleep(0.1)
        trigger_time[0] = time.time()
        kill_switch.trigger("High volume test")
        
        # Wait for all threads to detect (with timeout)
        for t in threads:
            t.join(timeout=1)
        
        # Verify all threads detected the trigger
        assert kill_switch.is_active()
        assert len(detection_times) > 0
        
        # Detection should be fast (< 100ms)
        avg_detection_time = sum(detection_times) / len(detection_times)
        assert avg_detection_time < 0.1, f"Detection too slow: {avg_detection_time}s"
    
    def test_circuit_breaker_under_rapid_trades(self, temp_dir):
        """Test circuit breaker accuracy under rapid trade recording"""
        circuit_breaker = CircuitBreaker(CircuitBreakerConfig(
            max_loss_per_hour_pct=0.05,
            max_loss_per_day_pct=0.10
        ))
        circuit_breaker.initialize(100000.0)
        
        num_trades = 1000
        trades_recorded = [0]
        lock = threading.Lock()
        
        def record_trades(trade_values):
            for pnl in trade_values:
                circuit_breaker.record_trade(pnl)
                with lock:
                    trades_recorded[0] += 1
        
        # Generate random trades
        trade_batches = []
        for _ in range(10):
            batch = [random.uniform(-100, 100) for _ in range(100)]
            trade_batches.append(batch)
        
        # Record trades concurrently
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(record_trades, batch) for batch in trade_batches]
            for future in as_completed(futures):
                future.result()
        
        elapsed_time = time.time() - start_time
        
        # Verify all trades recorded
        assert trades_recorded[0] == num_trades
        
        # Verify metrics are consistent
        metrics = circuit_breaker.get_metrics()
        
        # Total P&L should match
        expected_pnl = sum(sum(batch) for batch in trade_batches)
        actual_pnl = metrics['daily_pnl']
        
        # Allow small floating point error
        assert abs(expected_pnl - actual_pnl) < 1.0
        
        print(f"Recorded {num_trades} trades in {elapsed_time:.3f}s")
        print(f"Rate: {num_trades/elapsed_time:.0f} trades/sec")
    
    def test_oms_concurrent_order_submission(self, temp_dir):
        """Test OMS handles concurrent order submissions correctly"""
        oms = OrderManagementSystem(persistence_path=str(temp_dir / "oms.json"))
        
        num_orders = 100
        submitted_ids = []
        lock = threading.Lock()
        errors = []
        
        def submit_order(i):
            try:
                order = Order(
                    client_order_id=f"concurrent-order-{i}",
                    symbol="EURUSD",
                    side="BUY" if i % 2 == 0 else "SELL",
                    quantity=0.1
                )
                order_id = oms.submit_order(order)
                with lock:
                    submitted_ids.append(order_id)
            except Exception as e:
                with lock:
                    errors.append(str(e))
        
        # Submit orders concurrently
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(submit_order, i) for i in range(num_orders)]
            for future in as_completed(futures):
                future.result()
        
        elapsed_time = time.time() - start_time
        
        # Verify no errors
        assert len(errors) == 0, f"Errors occurred: {errors}"
        
        # Verify all orders submitted
        assert len(submitted_ids) == num_orders
        
        # Verify all order IDs are unique
        assert len(set(submitted_ids)) == num_orders
        
        # Verify OMS state is consistent
        assert len(oms.orders) == num_orders
        
        print(f"Submitted {num_orders} orders in {elapsed_time:.3f}s")
        print(f"Rate: {num_orders/elapsed_time:.0f} orders/sec")
    
    def test_oms_idempotency_under_concurrent_duplicates(self, temp_dir):
        """Test OMS idempotency with concurrent duplicate submissions"""
        oms = OrderManagementSystem(persistence_path=str(temp_dir / "oms.json"))
        
        # All threads will try to submit the same order
        client_order_id = "unique-idempotent-order"
        submitted_ids = []
        lock = threading.Lock()
        
        def submit_duplicate():
            order = Order(
                client_order_id=client_order_id,
                symbol="EURUSD",
                side="BUY",
                quantity=0.1
            )
            order_id = oms.submit_order(order)
            with lock:
                submitted_ids.append(order_id)
        
        # Submit same order from many threads
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(submit_duplicate) for _ in range(100)]
            for future in as_completed(futures):
                future.result()
        
        # All submissions should return the same order ID
        assert len(set(submitted_ids)) == 1, "Idempotency failed - got different IDs"
        
        # Only one order should exist
        assert len(oms.orders) == 1
    
    def test_oms_concurrent_fills(self, temp_dir):
        """Test OMS handles concurrent fill processing correctly"""
        oms = OrderManagementSystem(persistence_path=str(temp_dir / "oms.json"))
        
        # Create an order to fill
        order = Order(
            client_order_id="fill-test",
            symbol="EURUSD",
            side="BUY",
            quantity=1.0  # Will be filled in parts
        )
        order_id = oms.submit_order(order)
        
        # Simulate concurrent partial fills
        fill_count = [0]
        lock = threading.Lock()
        
        def process_fill(fill_qty, fill_price):
            oms.handle_fill({
                'order_id': order_id,
                'quantity': fill_qty,
                'price': fill_price
            })
            with lock:
                fill_count[0] += 1
        
        # Submit 10 partial fills of 0.1 each
        fills = [(0.1, 1.0850 + i * 0.0001) for i in range(10)]
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_fill, qty, price) for qty, price in fills]
            for future in as_completed(futures):
                future.result()
        
        # Verify order is fully filled
        final_order = oms.get_order(order_id)
        assert abs(final_order.filled_quantity - 1.0) < 0.0001
        assert final_order.state == OrderState.FILLED
        assert len(final_order.fills) == 10
    
    def test_mixed_safety_operations_under_load(self, temp_dir):
        """Test all safety components working together under load"""
        kill_switch = KillSwitch(audit_log_path=str(temp_dir / "audit.json"))
        circuit_breaker = CircuitBreaker(CircuitBreakerConfig())
        oms = OrderManagementSystem(persistence_path=str(temp_dir / "oms.json"))
        
        circuit_breaker.initialize(100000.0)
        kill_switch.arm()
        
        operations_completed = [0]
        errors = []
        lock = threading.Lock()
        
        def trading_operations():
            """Simulate a trading thread"""
            for i in range(50):
                try:
                    # Check kill switch
                    if kill_switch.is_active():
                        break
                    
                    # Check circuit breaker
                    can_trade, _ = circuit_breaker.check()
                    if not can_trade:
                        break
                    
                    # Submit order
                    order = Order(
                        client_order_id=f"mixed-{threading.current_thread().name}-{i}",
                        symbol=random.choice(["EURUSD", "GBPUSD", "USDJPY"]),
                        side=random.choice(["BUY", "SELL"]),
                        quantity=random.uniform(0.01, 0.1)
                    )
                    order_id = oms.submit_order(order)
                    
                    # Simulate fill
                    oms.handle_fill({
                        'order_id': order_id,
                        'quantity': order.quantity,
                        'price': random.uniform(1.0, 150.0)
                    })
                    
                    # Record trade result
                    pnl = random.uniform(-50, 50)
                    circuit_breaker.record_trade(pnl)
                    
                    with lock:
                        operations_completed[0] += 1
                    
                    time.sleep(0.001)  # Small delay
                    
                except Exception as e:
                    with lock:
                        errors.append(str(e))
        
        # Run multiple trading threads as daemon threads
        threads = []
        for _ in range(10):
            t = threading.Thread(target=trading_operations, daemon=True)
            threads.append(t)
            t.start()
        
        # Let them run for a bit
        time.sleep(1)
        
        # Trigger kill switch
        kill_switch.trigger("Test complete")
        
        # Wait for all threads to finish (with timeout)
        for t in threads:
            t.join(timeout=2)
        
        # Verify no errors
        assert len(errors) == 0, f"Errors: {errors}"
        
        print(f"Completed {operations_completed[0]} operations")
        print(f"Orders in OMS: {len(oms.orders)}")
        print(f"Circuit breaker metrics: {circuit_breaker.get_metrics()}")
    
    def test_persistence_under_rapid_updates(self, temp_dir):
        """Test OMS persistence handles rapid updates without corruption"""
        oms = OrderManagementSystem(persistence_path=str(temp_dir / "oms.json"))
        
        # Rapidly create and update orders
        for i in range(100):
            order = Order(
                client_order_id=f"rapid-{i}",
                symbol="EURUSD",
                side="BUY",
                quantity=0.1
            )
            order_id = oms.submit_order(order)
            oms.handle_fill({
                'order_id': order_id,
                'quantity': 0.1,
                'price': 1.0850
            })
        
        # Create new OMS instance and verify data
        oms2 = OrderManagementSystem(persistence_path=str(temp_dir / "oms.json"))
        
        assert len(oms2.orders) == 100
        
        # Verify all orders are filled
        filled_count = sum(1 for o in oms2.orders.values() if o.state == OrderState.FILLED)
        assert filled_count == 100


class TestLoadMetrics:
    """Test performance metrics under load"""
    
    def test_circuit_breaker_check_performance(self):
        """Measure circuit breaker check performance"""
        circuit_breaker = CircuitBreaker(CircuitBreakerConfig())
        circuit_breaker.initialize(10000.0)
        
        # Pre-populate with data
        for _ in range(100):
            circuit_breaker.record_trade(random.uniform(-10, 10))
            circuit_breaker.record_latency(random.uniform(10, 100))
        
        # Measure check performance
        iterations = 10000
        start_time = time.time()
        
        for _ in range(iterations):
            circuit_breaker.check()
        
        elapsed_time = time.time() - start_time
        avg_time_ms = (elapsed_time / iterations) * 1000
        
        print(f"Circuit breaker check: {avg_time_ms:.4f}ms average")
        
        # Should be very fast (< 1ms)
        assert avg_time_ms < 1.0
    
    def test_oms_order_submission_performance(self, tmp_path):
        """Measure OMS order submission performance"""
        oms = OrderManagementSystem(persistence_path=str(tmp_path / "oms.json"))
        
        iterations = 1000
        start_time = time.time()
        
        for i in range(iterations):
            order = Order(
                client_order_id=f"perf-test-{i}",
                symbol="EURUSD",
                side="BUY",
                quantity=0.1
            )
            oms.submit_order(order)
        
        elapsed_time = time.time() - start_time
        avg_time_ms = (elapsed_time / iterations) * 1000
        
        print(f"OMS submit: {avg_time_ms:.4f}ms average")
        
        # Should be reasonably fast (< 5ms including persistence)
        assert avg_time_ms < 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
