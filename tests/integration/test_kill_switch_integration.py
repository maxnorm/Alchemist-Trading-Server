"""
Integration tests for Kill Switch with Trading Controller

Tests the kill switch integration with the trading system.
"""

import pytest
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/trading_server/src'))

from risk.kill_switch import KillSwitch, KillSwitchState, FileTrigger


class MockAgent:
    """Mock DQN Agent for testing"""
    action_size = 4
    
    def act(self, state, training=False, action_mask=None):
        return 0  # Always HOLD


class MockEnvironment:
    """Mock Trading Environment for testing"""
    data_providers = []
    
    def get_state(self):
        import numpy as np
        return np.zeros((50, 15))
    
    def decode_action(self, action):
        from domain.action_type import ActionType
        return None, ActionType.HOLD


class MockAccount:
    """Mock Account for testing"""
    login = "12345"
    balance = 10000.0
    current_trade = {}
    
    def close_order(self, trade_id):
        if trade_id in self.current_trade:
            del self.current_trade[trade_id]


class MockRiskManager:
    """Mock Risk Manager for testing"""
    def initialize(self, account):
        pass
    
    def can_trade(self, account):
        return True, "OK"


class TestKillSwitchTradingControllerIntegration:
    """Integration tests for KillSwitch with TradingController"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def mock_components(self):
        """Create mock components for trading controller"""
        return {
            'agent': MockAgent(),
            'environment': MockEnvironment(),
            'account': MockAccount(),
            'risk_manager': MockRiskManager()
        }
    
    def _ensure_controller_stopped(self, controller, thread, timeout=3):
        """Helper to ensure controller and thread are properly stopped"""
        try:
            # Explicitly stop controller if still running
            if controller.is_running:
                controller.stop()
            
            # Wait for thread to finish
            thread.join(timeout=timeout)
            
            # If thread is still alive after timeout, ensure controller is stopped
            # (stop() is now idempotent, so safe to call again)
            if thread.is_alive() and controller.is_running:
                controller.stop()
        except Exception as e:
            # Log but don't fail test on cleanup errors
            print(f"Warning: Error during controller cleanup: {e}")
    
    def test_trading_controller_stops_on_kill_switch(self, temp_dir, mock_components):
        """Test that trading controller stops when kill switch triggers"""
        from trading_controller import TradingController
        
        kill_switch = KillSwitch(audit_log_path=str(temp_dir / "audit.json"))
        
        controller = TradingController(
            agent=mock_components['agent'],
            environment=mock_components['environment'],
            account=mock_components['account'],
            risk_manager=mock_components['risk_manager'],
            kill_switch=kill_switch,
            trading_enabled=False
        )
        
        try:
            # Start controller in background as daemon thread
            controller_thread = threading.Thread(target=controller.start, daemon=True)
            controller_thread.start()
            
            # Wait for controller to start
            time.sleep(0.5)
            assert controller.is_running
            
            # Trigger kill switch
            kill_switch.trigger("Test stop")
            
            # Wait for controller to stop
            time.sleep(0.5)
            
            assert not controller.is_running
            assert kill_switch.is_active()
        finally:
            # Ensure cleanup
            self._ensure_controller_stopped(controller, controller_thread)
    
    def test_controller_cannot_start_with_active_kill_switch(self, temp_dir, mock_components):
        """Test that controller cannot start when kill switch is active"""
        from trading_controller import TradingController
        
        kill_switch = KillSwitch(audit_log_path=str(temp_dir / "audit.json"))
        kill_switch.arm()
        kill_switch.trigger("Pre-triggered")
        
        controller = TradingController(
            agent=mock_components['agent'],
            environment=mock_components['environment'],
            account=mock_components['account'],
            risk_manager=mock_components['risk_manager'],
            kill_switch=kill_switch,
            trading_enabled=False
        )
        
        # Try to start - should not actually start
        controller.start()
        
        # Controller should not be running
        assert not controller.is_running
    
    def test_positions_closed_via_broker(self, temp_dir, mock_components):
        """Test that positions are closed when kill switch triggers"""
        # Setup account with open positions
        mock_components['account'].current_trade = {
            'trade1': Mock(),
            'trade2': Mock()
        }
        
        kill_switch = KillSwitch(audit_log_path=str(temp_dir / "audit.json"))
        
        from trading_controller import TradingController
        controller = TradingController(
            agent=mock_components['agent'],
            environment=mock_components['environment'],
            account=mock_components['account'],
            risk_manager=mock_components['risk_manager'],
            kill_switch=kill_switch,
            trading_enabled=True
        )
        
        # Trigger kill switch through controller
        controller.trigger_kill_switch("Close all positions")
        
        # Positions should be closed
        assert len(mock_components['account'].current_trade) == 0
    
    def test_kill_switch_survives_controller_restart(self, temp_dir, mock_components):
        """Test that kill switch state persists across controller restarts"""
        audit_path = str(temp_dir / "audit.json")
        
        # First instance
        kill_switch1 = KillSwitch(audit_log_path=audit_path)
        kill_switch1.arm()
        kill_switch1.trigger("Persistent trigger")
        
        assert kill_switch1.is_active()
        
        # Create new kill switch instance (simulating restart)
        kill_switch2 = KillSwitch(audit_log_path=audit_path)
        
        # Load events from audit log
        events = kill_switch2.get_audit_log()
        
        # Should have the event from first instance
        assert len(events) >= 1
        assert events[-1]['reason'] == "Persistent trigger"
    
    def test_file_trigger_integration(self, temp_dir, mock_components):
        """Test file-based kill switch trigger with controller"""
        from trading_controller import TradingController
        
        kill_file = temp_dir / "kill.flag"
        
        kill_switch = KillSwitch(audit_log_path=str(temp_dir / "audit.json"))
        file_trigger = FileTrigger(kill_file_path=str(kill_file))
        kill_switch.register_trigger(file_trigger)
        
        controller = TradingController(
            agent=mock_components['agent'],
            environment=mock_components['environment'],
            account=mock_components['account'],
            risk_manager=mock_components['risk_manager'],
            kill_switch=kill_switch,
            trading_enabled=False
        )
        
        try:
            # Start controller as daemon thread
            controller_thread = threading.Thread(target=controller.start, daemon=True)
            controller_thread.start()
            
            time.sleep(0.5)
            assert controller.is_running
            
            # Create kill file to trigger
            kill_file.write_text("File trigger test")
            
            # Wait for trigger to be detected
            time.sleep(2)
            
            assert kill_switch.is_active()
            assert not controller.is_running
        finally:
            # Ensure cleanup
            self._ensure_controller_stopped(controller, controller_thread)
    
    def test_reset_allows_restart(self, temp_dir, mock_components):
        """Test that resetting kill switch allows controller restart"""
        from trading_controller import TradingController
        
        kill_switch = KillSwitch(audit_log_path=str(temp_dir / "audit.json"))
        
        controller = TradingController(
            agent=mock_components['agent'],
            environment=mock_components['environment'],
            account=mock_components['account'],
            risk_manager=mock_components['risk_manager'],
            kill_switch=kill_switch,
            trading_enabled=False
        )
        
        # Trigger kill switch
        kill_switch.arm()
        kill_switch.trigger("Initial trigger")
        assert kill_switch.is_active()
        
        # Try to start - should fail
        controller.start()
        assert not controller.is_running
        
        # Reset kill switch
        success = controller.reset_kill_switch("admin")
        assert success
        assert not kill_switch.is_active()
        
        # Now controller should be able to start
        controller_thread = threading.Thread(target=controller.start, daemon=True)
        controller_thread.start()
        
        try:
            time.sleep(0.5)
            assert controller.is_running
            
            controller.stop()
        finally:
            # Ensure cleanup
            self._ensure_controller_stopped(controller, controller_thread)
    
    def test_safety_status_reporting(self, temp_dir, mock_components):
        """Test that safety status is correctly reported"""
        from trading_controller import TradingController
        from risk.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
        from risk.oms import OrderManagementSystem
        
        kill_switch = KillSwitch(audit_log_path=str(temp_dir / "audit.json"))
        circuit_breaker = CircuitBreaker(CircuitBreakerConfig())
        oms = OrderManagementSystem(persistence_path=str(temp_dir / "oms.json"))
        
        controller = TradingController(
            agent=mock_components['agent'],
            environment=mock_components['environment'],
            account=mock_components['account'],
            risk_manager=mock_components['risk_manager'],
            kill_switch=kill_switch,
            circuit_breaker=circuit_breaker,
            oms=oms,
            trading_enabled=True
        )
        
        status = controller.get_safety_status()
        
        assert 'trading_enabled' in status
        assert status['trading_enabled'] is True
        assert 'kill_switch' in status
        assert 'circuit_breaker' in status
        assert 'oms' in status


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
