"""
Unit tests for Kill Switch module

Tests all trigger mechanisms and core functionality.
"""

import pytest
import os
import sys
import tempfile
import socket
import threading
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/backend/trading_server/src'))

from risk.kill_switch import (
    KillSwitch,
    KillSwitchState,
    FileTrigger,
    EnvironmentTrigger,
    NetworkTrigger,
    SignalTrigger,
    KillSwitchEvent
)


class TestFileTrigger:
    """Tests for FileTrigger"""
    
    def test_file_trigger_not_triggered_when_file_missing(self, tmp_path):
        """Test that trigger returns False when file doesn't exist"""
        kill_file = tmp_path / "kill.flag"
        trigger = FileTrigger(kill_file_path=str(kill_file))
        
        triggered, reason = trigger.check()
        
        assert triggered is False
        assert reason == ""
    
    def test_file_trigger_activates_on_file_creation(self, tmp_path):
        """Test that trigger activates when file is created"""
        kill_file = tmp_path / "kill.flag"
        trigger = FileTrigger(kill_file_path=str(kill_file))
        
        # Create the kill file
        kill_file.write_text("Emergency stop requested")
        
        triggered, reason = trigger.check()
        
        assert triggered is True
        assert "Emergency stop requested" in reason
    
    def test_file_trigger_reads_reason_from_file(self, tmp_path):
        """Test that trigger reads reason from file content"""
        kill_file = tmp_path / "kill.flag"
        trigger = FileTrigger(kill_file_path=str(kill_file))
        
        expected_reason = "Critical error detected"
        kill_file.write_text(expected_reason)
        
        triggered, reason = trigger.check()
        
        assert triggered is True
        assert reason == expected_reason
    
    def test_file_trigger_reset_removes_file(self, tmp_path):
        """Test that reset removes the kill file"""
        kill_file = tmp_path / "kill.flag"
        trigger = FileTrigger(kill_file_path=str(kill_file))
        
        # Create file
        kill_file.write_text("test")
        assert kill_file.exists()
        
        # Reset should remove it
        trigger.reset()
        
        assert not kill_file.exists()
    
    def test_file_trigger_handles_empty_file(self, tmp_path):
        """Test that trigger handles empty kill file"""
        kill_file = tmp_path / "kill.flag"
        trigger = FileTrigger(kill_file_path=str(kill_file))
        
        # Create empty file
        kill_file.touch()
        
        triggered, reason = trigger.check()
        
        assert triggered is True
        assert "Kill file detected" in reason


class TestEnvironmentTrigger:
    """Tests for EnvironmentTrigger"""
    
    def test_environment_trigger_not_triggered_by_default(self):
        """Test that trigger returns False when env var not set"""
        # Ensure env var is not set
        if "TRADING_KILL" in os.environ:
            del os.environ["TRADING_KILL"]
        
        trigger = EnvironmentTrigger()
        
        triggered, reason = trigger.check()
        
        assert triggered is False
    
    def test_environment_trigger_activates_on_env_var_1(self):
        """Test that trigger activates when env var is '1'"""
        os.environ["TRADING_KILL"] = "1"
        
        try:
            trigger = EnvironmentTrigger()
            triggered, reason = trigger.check()
            
            assert triggered is True
            assert "TRADING_KILL=1" in reason
        finally:
            del os.environ["TRADING_KILL"]
    
    def test_environment_trigger_activates_on_env_var_true(self):
        """Test that trigger activates when env var is 'true'"""
        os.environ["TRADING_KILL"] = "true"
        
        try:
            trigger = EnvironmentTrigger()
            triggered, reason = trigger.check()
            
            assert triggered is True
        finally:
            del os.environ["TRADING_KILL"]
    
    def test_environment_trigger_ignores_other_values(self):
        """Test that trigger ignores non-truthy values"""
        os.environ["TRADING_KILL"] = "false"
        
        try:
            trigger = EnvironmentTrigger()
            triggered, reason = trigger.check()
            
            assert triggered is False
        finally:
            del os.environ["TRADING_KILL"]
    
    def test_environment_trigger_reset_clears_env_var(self):
        """Test that reset clears the environment variable"""
        os.environ["TRADING_KILL"] = "1"
        
        trigger = EnvironmentTrigger()
        trigger.reset()
        
        assert "TRADING_KILL" not in os.environ
    
    def test_custom_env_var_name(self):
        """Test using custom environment variable name"""
        os.environ["MY_CUSTOM_KILL"] = "1"
        
        try:
            trigger = EnvironmentTrigger(env_var="MY_CUSTOM_KILL")
            triggered, reason = trigger.check()
            
            assert triggered is True
            assert "MY_CUSTOM_KILL" in reason
        finally:
            del os.environ["MY_CUSTOM_KILL"]


class TestNetworkTrigger:
    """Tests for NetworkTrigger"""
    
    def test_network_trigger_starts_listening(self):
        """Test that network trigger starts UDP listener"""
        trigger = NetworkTrigger(port=19999)  # Use non-standard port
        
        trigger.start_monitoring()
        time.sleep(0.1)  # Let thread start
        
        assert trigger._monitoring is True
        assert trigger._socket is not None
        
        trigger.stop_monitoring()
    
    def test_network_trigger_activates_on_udp_message(self):
        """Test that trigger activates on UDP KILL message"""
        trigger = NetworkTrigger(port=19998)
        callback_called = threading.Event()
        
        def callback(reason, trigger_type):
            callback_called.set()
        
        trigger.on_trigger = callback
        trigger.start_monitoring()
        time.sleep(0.1)
        
        # Send UDP kill command
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(b"KILL", ("127.0.0.1", 19998))
        sock.close()
        
        # Wait for callback
        callback_called.wait(timeout=2)
        
        trigger.stop_monitoring()
        
        assert callback_called.is_set()
        assert trigger._triggered is True
    
    def test_network_trigger_with_reason(self):
        """Test that trigger captures reason from message"""
        trigger = NetworkTrigger(port=19997)
        trigger.start_monitoring()
        time.sleep(0.1)
        
        # Send UDP kill command with reason
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(b"KILL:Emergency shutdown", ("127.0.0.1", 19997))
        sock.close()
        
        time.sleep(0.2)  # Wait for processing
        
        triggered, reason = trigger.check()
        
        trigger.stop_monitoring()
        
        assert triggered is True
        assert "Emergency shutdown" in reason
    
    def test_network_trigger_reset(self):
        """Test that reset clears triggered state"""
        trigger = NetworkTrigger(port=19996)
        trigger._triggered = True
        trigger._trigger_reason = "test"
        
        trigger.reset()
        
        assert trigger._triggered is False
        assert trigger._trigger_reason == ""


class TestKillSwitch:
    """Tests for KillSwitch main class"""
    
    def test_kill_switch_initial_state_disabled(self, tmp_path):
        """Test that kill switch starts disabled"""
        ks = KillSwitch(audit_log_path=str(tmp_path / "audit.json"))
        
        assert ks.state == KillSwitchState.DISABLED
        assert not ks.is_active()
    
    def test_kill_switch_arm_changes_state(self, tmp_path):
        """Test that arming changes state to ARMED"""
        ks = KillSwitch(audit_log_path=str(tmp_path / "audit.json"))
        
        ks.arm()
        
        assert ks.state == KillSwitchState.ARMED
    
    def test_kill_switch_trigger_changes_state(self, tmp_path):
        """Test that triggering changes state to TRIGGERED"""
        ks = KillSwitch(audit_log_path=str(tmp_path / "audit.json"))
        ks.arm()
        
        ks.trigger("Test trigger")
        
        assert ks.state == KillSwitchState.TRIGGERED
        assert ks.is_active()
    
    def test_all_positions_closed_on_trigger(self, tmp_path):
        """Test that all positions are closed when triggered"""
        mock_broker = Mock()
        mock_broker.close_all_positions.return_value = 3
        
        ks = KillSwitch(
            broker_adapter=mock_broker,
            audit_log_path=str(tmp_path / "audit.json")
        )
        ks.arm()
        
        ks.trigger("Test")
        
        mock_broker.close_all_positions.assert_called_once()
    
    def test_audit_log_created_on_trigger(self, tmp_path):
        """Test that audit log is created when triggered"""
        audit_path = tmp_path / "audit.json"
        ks = KillSwitch(audit_log_path=str(audit_path))
        ks.arm()
        
        ks.trigger("Audit test", "TestTrigger")
        
        assert audit_path.exists()
        
        import json
        with open(audit_path) as f:
            events = json.load(f)
        
        assert len(events) == 1
        assert events[0]['reason'] == "Audit test"
        assert events[0]['trigger_type'] == "TestTrigger"
    
    def test_reset_requires_approver_name(self, tmp_path):
        """Test that reset fails without approver name"""
        ks = KillSwitch(audit_log_path=str(tmp_path / "audit.json"))
        ks.arm()
        ks.trigger("Test")
        
        # Empty approver should fail
        result = ks.reset("")
        assert result is False
        assert ks.is_active()
        
        # None approver should fail
        result = ks.reset(None)
        assert result is False
        assert ks.is_active()
    
    def test_reset_with_approver_succeeds(self, tmp_path):
        """Test that reset succeeds with valid approver"""
        ks = KillSwitch(audit_log_path=str(tmp_path / "audit.json"))
        ks.arm()
        ks.trigger("Test")
        
        result = ks.reset("admin_user")
        
        assert result is True
        assert not ks.is_active()
        assert ks.state == KillSwitchState.ARMED
    
    def test_reset_clears_trigger_file(self, tmp_path):
        """Test that reset clears all trigger states including file"""
        kill_file = tmp_path / "kill.flag"
        kill_file.write_text("test")
        
        ks = KillSwitch(audit_log_path=str(tmp_path / "audit.json"))
        file_trigger = FileTrigger(kill_file_path=str(kill_file))
        ks.register_trigger(file_trigger)
        ks.arm()
        ks.trigger("Test")
        
        ks.reset("admin")
        
        assert not kill_file.exists()
    
    def test_callback_called_on_trigger(self, tmp_path):
        """Test that callback is called when triggered"""
        callback_called = False
        callback_reason = None
        
        def callback(reason):
            nonlocal callback_called, callback_reason
            callback_called = True
            callback_reason = reason
        
        ks = KillSwitch(
            on_kill_callback=callback,
            audit_log_path=str(tmp_path / "audit.json")
        )
        ks.arm()
        
        ks.trigger("Callback test")
        
        assert callback_called
        assert callback_reason == "Callback test"
    
    def test_concurrent_triggers_handled_safely(self, tmp_path):
        """Test that concurrent triggers don't cause issues"""
        ks = KillSwitch(audit_log_path=str(tmp_path / "audit.json"))
        ks.arm()
        
        trigger_count = [0]
        
        def callback(reason):
            trigger_count[0] += 1
        
        ks.on_kill_callback = callback
        
        # Trigger from multiple threads as daemon threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=ks.trigger, args=(f"Test {i}",), daemon=True)
            threads.append(t)
            t.start()
        
        # Wait for all threads with timeout
        for t in threads:
            t.join(timeout=2)
        
        # Only one trigger should have been processed
        assert trigger_count[0] == 1
        assert ks.is_active()
    
    def test_register_default_triggers(self, tmp_path):
        """Test registering default triggers"""
        ks = KillSwitch(audit_log_path=str(tmp_path / "audit.json"))
        
        ks.register_default_triggers()
        
        # Should have at least FileTrigger, EnvironmentTrigger, NetworkTrigger
        assert len(ks._triggers) >= 3
    
    def test_context_manager(self, tmp_path):
        """Test using kill switch as context manager"""
        ks = KillSwitch(audit_log_path=str(tmp_path / "audit.json"))
        
        with ks:
            assert ks.state == KillSwitchState.ARMED
        
        assert ks.state == KillSwitchState.DISABLED
    
    def test_get_status(self, tmp_path):
        """Test getting kill switch status"""
        ks = KillSwitch(audit_log_path=str(tmp_path / "audit.json"))
        ks.register_trigger(FileTrigger(kill_file_path=str(tmp_path / "kill.flag")))
        ks.arm()
        
        status = ks.get_status()
        
        assert status['state'] == 'armed'
        assert 'FileTrigger' in status['triggers']
        assert status['event_count'] == 0


class TestKillSwitchEvent:
    """Tests for KillSwitchEvent dataclass"""
    
    def test_event_to_dict(self):
        """Test converting event to dictionary"""
        event = KillSwitchEvent(
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            reason="Test reason",
            trigger_type="TestTrigger",
            positions_closed=5
        )
        
        data = event.to_dict()
        
        assert data['timestamp'] == "2025-01-01T12:00:00"
        assert data['reason'] == "Test reason"
        assert data['trigger_type'] == "TestTrigger"
        assert data['positions_closed'] == 5
        assert data['approver'] is None
        assert data['reset_timestamp'] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
