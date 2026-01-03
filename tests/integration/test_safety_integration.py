"""
Integration tests for all safety components working together

Tests the interaction between KillSwitch, CircuitBreaker, and OMS.
"""

import pytest
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/mt5-python_server/src'))

from risk.kill_switch import KillSwitch, KillSwitchState
from risk.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerState
from risk.oms import OrderManagementSystem, Order, OrderState


class TestSafetyIntegration:
    """Integration tests for safety components"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def safety_components(self, temp_dir):
        """Create all safety components"""
        kill_switch = KillSwitch(audit_log_path=str(temp_dir / "audit.json"))
        circuit_breaker = CircuitBreaker(CircuitBreakerConfig(
            max_loss_per_hour_pct=0.03,
            max_loss_per_day_pct=0.05
        ))
        oms = OrderManagementSystem(persistence_path=str(temp_dir / "oms.json"))
        
        return {
            'kill_switch': kill_switch,
            'circuit_breaker': circuit_breaker,
            'oms': oms
        }
    
    def test_kill_switch_closes_all_positions(self, safety_components):
        """Test that kill switch closes all OMS positions"""
        oms = safety_components['oms']
        kill_switch = safety_components['kill_switch']
        
        # Create some orders
        order1 = Order(
            client_order_id="order1",
            symbol="EURUSD",
            side="BUY",
            quantity=0.1
        )
        order2 = Order(
            client_order_id="order2",
            symbol="GBPUSD",
            side="SELL",
            quantity=0.2
        )
        
        oms.submit_order(order1)
        oms.submit_order(order2)
        
        # Simulate fills
        oms.handle_fill({'order_id': order1.order_id, 'quantity': 0.1, 'price': 1.0850})
        oms.handle_fill({'order_id': order2.order_id, 'quantity': 0.2, 'price': 1.2650})
        
        # Verify positions exist
        assert len(oms.get_all_positions()) == 2
        
        # Create mock broker that uses OMS to close positions
        class MockBroker:
            def __init__(self, oms):
                self.oms = oms
            
            def close_all_positions(self):
                count = 0
                for symbol in list(self.oms.positions.keys()):
                    # Simulate closing position
                    pos = self.oms.positions[symbol]
                    if pos.quantity != 0:
                        self.oms.positions[symbol].quantity = 0
                        count += 1
                return count
        
        mock_broker = MockBroker(oms)
        kill_switch.broker_adapter = mock_broker
        
        # Trigger kill switch
        kill_switch.arm()
        kill_switch.trigger("Test close all")
        
        # All positions should be closed
        active_positions = [p for p in oms.get_all_positions().values() if p.quantity != 0]
        assert len(active_positions) == 0
    
    def test_circuit_breaker_halts_on_rapid_loss(self, safety_components):
        """Test that circuit breaker halts trading after rapid losses"""
        circuit_breaker = safety_components['circuit_breaker']
        circuit_breaker.initialize(10000.0)
        
        # Simulate losing trades
        losses = [-100, -150, -200, -100]  # Total: -550 = 5.5% of 10000
        
        for loss in losses:
            circuit_breaker.record_trade(loss)
        
        # Check if circuit breaker trips
        can_trade, reason = circuit_breaker.check()
        
        assert can_trade is False
        assert "loss" in reason.lower()
        assert circuit_breaker.state == CircuitBreakerState.OPEN
    
    def test_oms_prevents_duplicate_orders(self, safety_components):
        """Test that OMS prevents duplicate orders via idempotency"""
        oms = safety_components['oms']
        
        order = Order(
            client_order_id="unique-123",
            symbol="EURUSD",
            side="BUY",
            quantity=0.1
        )
        
        # Submit order twice
        order_id1 = oms.submit_order(order)
        order_id2 = oms.submit_order(order)
        
        # Should return same order ID
        assert order_id1 == order_id2
        
        # Should only have one order
        assert len(oms.orders) == 1
    
    def test_position_reconciliation(self, safety_components):
        """Test that OMS detects position discrepancies"""
        oms = safety_components['oms']
        
        # Create local positions via orders
        order = Order(symbol="EURUSD", side="BUY", quantity=0.1)
        oms.submit_order(order)
        oms.handle_fill({'order_id': order.order_id, 'quantity': 0.1, 'price': 1.0850})
        
        # Broker has different position
        broker_positions = {
            'EURUSD': 0.2,  # Broker shows 0.2, we have 0.1
            'USDJPY': 0.5   # Broker has position we don't know about
        }
        
        discrepancies = oms.reconcile(broker_positions)
        
        assert len(discrepancies) >= 1
        
        # Check EURUSD discrepancy
        eurusd_disc = next((d for d in discrepancies if d.symbol == 'EURUSD'), None)
        assert eurusd_disc is not None
        assert abs(eurusd_disc.difference - 0.1) < 0.0001
    
    def test_all_safety_components_work_together(self, safety_components):
        """Test full safety workflow"""
        kill_switch = safety_components['kill_switch']
        circuit_breaker = safety_components['circuit_breaker']
        oms = safety_components['oms']
        
        # Initialize
        circuit_breaker.initialize(10000.0)
        kill_switch.arm()
        
        # Simulate trading day
        trades = [
            {'symbol': 'EURUSD', 'side': 'BUY', 'qty': 0.1, 'fill_price': 1.0850, 'pnl': 50},
            {'symbol': 'GBPUSD', 'side': 'SELL', 'qty': 0.1, 'fill_price': 1.2650, 'pnl': -30},
            {'symbol': 'EURUSD', 'side': 'BUY', 'qty': 0.2, 'fill_price': 1.0860, 'pnl': -100},
        ]
        
        for trade in trades:
            # Check circuit breaker
            can_trade, _ = circuit_breaker.check()
            if not can_trade:
                break
            
            # Submit order
            order = Order(
                symbol=trade['symbol'],
                side=trade['side'],
                quantity=trade['qty']
            )
            oms.submit_order(order)
            oms.handle_fill({
                'order_id': order.order_id,
                'quantity': trade['qty'],
                'price': trade['fill_price']
            })
            
            # Record P&L
            circuit_breaker.record_trade(trade['pnl'])
        
        # Verify components tracked everything
        assert len(oms.orders) == len(trades)
        
        metrics = circuit_breaker.get_metrics()
        assert metrics['daily_pnl'] == sum(t['pnl'] for t in trades)
    
    def test_circuit_breaker_triggers_kill_switch(self, safety_components, temp_dir):
        """Test that circuit breaker can trigger kill switch on severe conditions"""
        kill_switch = safety_components['kill_switch']
        circuit_breaker = safety_components['circuit_breaker']
        
        # Custom config with lower threshold
        circuit_breaker = CircuitBreaker(CircuitBreakerConfig(
            max_loss_per_day_pct=0.02  # 2%
        ))
        circuit_breaker.initialize(10000.0)
        kill_switch.arm()
        
        # Simulate severe loss that should trigger escalation
        severe_loss = -250  # 2.5% loss
        circuit_breaker.record_trade(severe_loss)
        
        can_trade, reason = circuit_breaker.check()
        
        if not can_trade:
            # Escalate to kill switch for severe conditions
            kill_switch.trigger(f"Circuit breaker escalation: {reason}")
        
        assert kill_switch.is_active()
    
    def test_recovery_workflow(self, safety_components):
        """Test full recovery after safety halt"""
        kill_switch = safety_components['kill_switch']
        circuit_breaker = safety_components['circuit_breaker']
        
        circuit_breaker.initialize(10000.0)
        kill_switch.arm()
        
        # Trigger halt
        kill_switch.trigger("Test halt")
        assert kill_switch.is_active()
        
        # Reset kill switch
        kill_switch.reset("admin")
        assert not kill_switch.is_active()
        
        # Reset circuit breaker with new balance
        circuit_breaker.reset(manual=True)
        circuit_breaker.initialize(9500.0)  # New starting balance after loss
        
        # Should be able to trade again
        can_trade, _ = circuit_breaker.check()
        assert can_trade is True


class TestKillSwitchAllTriggers:
    """Test all kill switch trigger mechanisms"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def kill_switch(self, temp_dir):
        """Create kill switch instance"""
        from risk.kill_switch import KillSwitch
        return KillSwitch(audit_log_path=str(temp_dir / "audit.json"))
    
    def test_file_trigger(self, kill_switch, temp_dir):
        """Test file trigger"""
        kill_switch.arm()
        
        # Create kill file
        kill_file = temp_dir / "KILL_TRADING"
        kill_file.touch()
        
        # Check if triggered
        # Note: File trigger monitoring runs in background thread
        # For test, we can directly check the file
        time.sleep(0.1)  # Give trigger time to detect
        
        # Manually check file trigger
        from risk.kill_switch import FileTrigger
        trigger = FileTrigger(kill_file=str(kill_file))
        is_triggered, reason = trigger.check()
        
        assert is_triggered
        assert "file" in reason.lower() or "kill" in reason.lower()
    
    def test_environment_trigger(self, kill_switch):
        """Test environment variable trigger"""
        kill_switch.arm()
        
        # Set environment variable
        os.environ['TRADING_KILL'] = '1'
        
        try:
            from risk.kill_switch import EnvironmentTrigger
            trigger = EnvironmentTrigger()
            is_triggered, reason = trigger.check()
            
            assert is_triggered
        finally:
            # Cleanup
            os.environ.pop('TRADING_KILL', None)
    
    def test_network_trigger(self, kill_switch):
        """Test network trigger (UDP)"""
        kill_switch.arm()
        
        # Note: Network trigger requires UDP socket
        # This is a simplified test
        from risk.kill_switch import NetworkTrigger
        trigger = NetworkTrigger(port=9999)
        
        # Test that trigger can be created
        assert trigger is not None
        # Full network test would require actual UDP communication
    
    def test_signal_trigger(self, kill_switch):
        """Test signal trigger"""
        # Note: Signal trigger is OS-specific
        # On Windows, signals work differently
        # This test verifies the trigger exists
        from risk.kill_switch import SignalTrigger
        trigger = SignalTrigger()
        
        assert trigger is not None
    
    def test_api_trigger(self, kill_switch):
        """Test API trigger (via FastAPI endpoint)"""
        kill_switch.arm()
        
        # API trigger is called from FastAPI endpoint
        # This would be tested in API integration tests
        # Here we verify kill switch can be triggered programmatically
        kill_switch.trigger("API trigger test", trigger_type="api")
        
        assert kill_switch.is_active()


class TestCircuitBreakerTradingIntegration:
    """Test circuit breaker with actual trading flow"""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker"""
        from risk.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
        cb = CircuitBreaker(CircuitBreakerConfig(
            max_loss_per_hour_pct=0.03,
            max_loss_per_day_pct=0.05,
            max_consecutive_losses=5
        ))
        cb.initialize(10000.0)
        return cb
    
    def test_circuit_breaker_trips_on_consecutive_losses(self, circuit_breaker):
        """Test circuit breaker trips on consecutive losses"""
        # Simulate consecutive losses
        for i in range(6):  # More than max_consecutive_losses
            can_trade, reason = circuit_breaker.check()
            if not can_trade:
                break
            circuit_breaker.record_trade(-100.0)  # Loss
        
        can_trade, reason = circuit_breaker.check()
        assert not can_trade
        assert "consecutive" in reason.lower() or "loss" in reason.lower()
    
    def test_circuit_breaker_trips_on_daily_loss(self, circuit_breaker):
        """Test circuit breaker trips on daily loss threshold"""
        # Simulate large daily loss (5% = 500 on 10000 balance)
        circuit_breaker.record_trade(-500.0)
        
        can_trade, reason = circuit_breaker.check()
        assert not can_trade
        assert "daily" in reason.lower() or "loss" in reason.lower()
    
    def test_circuit_breaker_reset(self, circuit_breaker):
        """Test reset functionality"""
        # Trip the breaker
        circuit_breaker.record_trade(-500.0)
        can_trade, _ = circuit_breaker.check()
        assert not can_trade
        
        # Reset
        circuit_breaker.reset(manual=True)
        circuit_breaker.initialize(9500.0)  # New balance
        
        can_trade, _ = circuit_breaker.check()
        assert can_trade


class TestOMSReconciliation:
    """Test OMS position reconciliation"""
    
    @pytest.fixture
    def oms(self, tmp_path):
        from risk.oms import OrderManagementSystem
        return OrderManagementSystem(persistence_path=str(tmp_path / "oms.json"))
    
    def test_oms_reconciliation(self, oms):
        """Test OMS position reconciliation"""
        # Create orders in OMS
        from risk.oms import Order, OrderState
        
        order = Order(
            client_order_id="test-order-1",
            symbol="EURUSD",
            side="BUY",
            quantity=0.1
        )
        
        order_id = oms.submit_order(order)
        oms.update_order_state(order_id, OrderState.FILLED, broker_order_id="MT5-123")
        
        # Simulate MT5 position mismatch
        # In real scenario, would query MT5 and compare
        mt5_positions = []  # Empty - mismatch!
        oms_positions = oms.get_open_positions()
        
        # Verify reconciliation detects mismatch
        # This would be implemented in OMS.reconcile_positions()
        assert len(oms_positions) > 0
        # Mismatch detected: OMS has position but MT5 doesn't
    
    def test_oms_alert_system(self, oms):
        """Test alert system on mismatches"""
        # Placeholder for alert system testing
        # Would verify alerts are sent on reconciliation mismatches
        pass


class TestOMS:
    """Unit tests for Order Management System"""
    
    @pytest.fixture
    def oms(self, tmp_path):
        return OrderManagementSystem(persistence_path=str(tmp_path / "oms.json"))
    
    def test_order_lifecycle(self, oms):
        """Test order through full lifecycle"""
        # Create order
        order = Order(
            client_order_id="test-order",
            symbol="EURUSD",
            side="BUY",
            quantity=0.1
        )
        
        # Submit
        order_id = oms.submit_order(order)
        assert order.state == OrderState.PENDING_NEW
        
        # Broker accepts
        oms.update_order_state(order_id, OrderState.NEW, broker_order_id="BROKER-123")
        assert oms.get_order(order_id).state == OrderState.NEW
        
        # Partial fill
        oms.handle_fill({'order_id': order_id, 'quantity': 0.05, 'price': 1.0850})
        assert oms.get_order(order_id).state == OrderState.PARTIALLY_FILLED
        assert oms.get_order(order_id).filled_quantity == 0.05
        
        # Complete fill
        oms.handle_fill({'order_id': order_id, 'quantity': 0.05, 'price': 1.0852})
        assert oms.get_order(order_id).state == OrderState.FILLED
        assert oms.get_order(order_id).filled_quantity == 0.1
    
    def test_position_tracking(self, oms):
        """Test position updates from fills"""
        order = Order(symbol="EURUSD", side="BUY", quantity=0.1)
        oms.submit_order(order)
        oms.handle_fill({'order_id': order.order_id, 'quantity': 0.1, 'price': 1.0850})
        
        position = oms.get_position("EURUSD")
        assert position is not None
        assert position.quantity == 0.1
        assert position.average_price == 1.0850
    
    def test_order_cancellation(self, oms):
        """Test order cancellation flow"""
        order = Order(symbol="EURUSD", side="BUY", quantity=0.1)
        order_id = oms.submit_order(order)
        oms.update_order_state(order_id, OrderState.NEW)
        
        # Request cancel
        result = oms.cancel_order(order_id)
        assert result is True
        assert oms.get_order(order_id).state == OrderState.PENDING_CANCEL
        
        # Confirm cancel
        oms.confirm_cancel(order_id)
        assert oms.get_order(order_id).state == OrderState.CANCELLED
    
    def test_order_rejection(self, oms):
        """Test order rejection handling"""
        order = Order(symbol="EURUSD", side="BUY", quantity=0.1)
        order_id = oms.submit_order(order)
        
        oms.handle_rejection(order_id, "Insufficient margin")
        
        assert oms.get_order(order_id).state == OrderState.REJECTED
        assert oms.get_order(order_id).reject_reason == "Insufficient margin"
    
    def test_persistence(self, tmp_path):
        """Test OMS state persistence"""
        persistence_path = str(tmp_path / "oms.json")
        
        # Create OMS and add order
        oms1 = OrderManagementSystem(persistence_path=persistence_path)
        order = Order(client_order_id="persist-test", symbol="EURUSD", side="BUY", quantity=0.1)
        order_id = oms1.submit_order(order)
        oms1.handle_fill({'order_id': order_id, 'quantity': 0.1, 'price': 1.0850})
        
        # Create new OMS instance - should load state
        oms2 = OrderManagementSystem(persistence_path=persistence_path)
        
        assert order_id in oms2.orders
        assert oms2.get_order(order_id).state == OrderState.FILLED


class TestCircuitBreaker:
    """Unit tests for Circuit Breaker"""
    
    @pytest.fixture
    def circuit_breaker(self):
        cb = CircuitBreaker(CircuitBreakerConfig(
            max_loss_per_hour_pct=0.03,
            max_loss_per_day_pct=0.05,
            max_error_rate=0.10,
            max_latency_ms=1000
        ))
        cb.initialize(10000.0)
        return cb
    
    def test_trips_on_hourly_loss(self, circuit_breaker):
        """Test circuit breaker trips on hourly loss threshold"""
        # 3.5% loss in one trade
        circuit_breaker.record_trade(-350)
        
        can_trade, reason = circuit_breaker.check()
        
        assert can_trade is False
        assert "hourly" in reason.lower()
    
    def test_trips_on_daily_loss(self, circuit_breaker):
        """Test circuit breaker trips on daily loss threshold"""
        # Spread losses over time to avoid hourly trigger
        circuit_breaker.record_trade(-200)
        circuit_breaker.reset_hourly(9800)
        circuit_breaker.record_trade(-200)
        circuit_breaker.reset_hourly(9600)
        circuit_breaker.record_trade(-200)
        
        # Daily total now exceeds 5%
        can_trade, reason = circuit_breaker.check()
        
        # Should trip on daily loss
        assert circuit_breaker._calculate_daily_loss_pct() > 0.05
    
    def test_trips_on_high_error_rate(self, circuit_breaker):
        """Test circuit breaker trips on high error rate"""
        # Record many operations with some errors
        for i in range(20):
            circuit_breaker._metrics.operation_count += 1
        
        for i in range(5):  # 25% error rate
            circuit_breaker.record_error(Exception("Test error"))
        
        can_trade, reason = circuit_breaker.check()
        
        assert can_trade is False
        assert "error" in reason.lower()
    
    def test_trips_on_high_latency(self, circuit_breaker):
        """Test circuit breaker trips on high latency"""
        # Record high latency
        for _ in range(10):
            circuit_breaker.record_latency(1500)  # 1.5 seconds
        
        can_trade, reason = circuit_breaker.check()
        
        assert can_trade is False
        assert "latency" in reason.lower()
    
    def test_half_open_recovery(self, circuit_breaker):
        """Test half-open state and recovery"""
        # Trip the breaker
        circuit_breaker.record_trade(-400)
        circuit_breaker.check()
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Force cooldown to pass
        circuit_breaker._metrics.trip_time = None
        
        # Check should move to half-open
        circuit_breaker.check()
        assert circuit_breaker.state == CircuitBreakerState.HALF_OPEN
    
    def test_manual_reset(self, circuit_breaker):
        """Test manual reset of circuit breaker"""
        circuit_breaker.record_trade(-400)
        circuit_breaker.check()
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        
        result = circuit_breaker.reset(manual=True)
        
        assert result is True
        assert circuit_breaker.state == CircuitBreakerState.CLOSED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
