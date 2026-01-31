"""
Unit tests for Kill Switch database persistence
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from tests.shared.helpers.path_utils import setup_trading_server_path
setup_trading_server_path()

from risk.kill_switch import KillSwitch, KillSwitchState, KillSwitchEvent


class TestKillSwitchDatabase:
    """Tests for Kill Switch database persistence"""
    
    @pytest.fixture
    def mock_database(self):
        """Create mock database connection"""
        db = Mock()
        conn = Mock()
        cursor = Mock()
        
        conn.cursor.return_value = cursor
        cursor.lastrowid = 1
        cursor.execute.return_value = None
        
        db._Database__get_connection.return_value = conn
        
        return db
    
    @pytest.fixture
    def kill_switch(self, mock_database, tmp_path):
        """Create kill switch with database"""
        return KillSwitch(
            database=mock_database,
            audit_log_path=str(tmp_path / "audit.json")
        )
    
    def test_logs_event_to_database_on_trigger(self, kill_switch, mock_database):
        """Test that kill switch logs events to database"""
        kill_switch.arm()
        
        # Trigger kill switch
        kill_switch.trigger("Test trigger", "Manual")
        
        # Verify database was called
        assert mock_database._Database__get_connection.called
        
        # Get the connection and cursor
        conn = mock_database._Database__get_connection.return_value
        cursor = conn.cursor.return_value
        
        # Verify INSERT was called
        assert cursor.execute.called
        
        # Check the query contains expected fields
        call_args = cursor.execute.call_args
        query = call_args[0][0]
        assert "INSERT INTO kill_switch_events" in query
        assert "trigger_source" in query
        assert "reason" in query
        assert "positions_closed" in query
    
    def test_updates_resolution_on_reset(self, kill_switch, mock_database):
        """Test that kill switch updates database on reset"""
        kill_switch.arm()
        kill_switch.trigger("Test trigger", "Manual")
        
        # Reset
        kill_switch.reset("admin")
        
        # Verify UPDATE was called
        conn = mock_database._Database__get_connection.return_value
        cursor = conn.cursor.return_value
        
        # Should have INSERT (trigger) and UPDATE (reset) calls
        assert cursor.execute.call_count >= 2
        
        # Check for UPDATE query
        calls = [call[0][0] for call in cursor.execute.call_args_list]
        update_calls = [c for c in calls if "UPDATE" in c.upper()]
        assert len(update_calls) > 0
    
    def test_handles_database_failure_gracefully(self, kill_switch, tmp_path):
        """Test that kill switch handles database failures gracefully"""
        # Create database that raises exception
        failing_db = Mock()
        failing_db._Database__get_connection.side_effect = Exception("DB connection failed")
        
        kill_switch.database = failing_db
        kill_switch.arm()
        
        # Should not raise exception
        kill_switch.trigger("Test trigger", "Manual")
        
        # Should still have event in memory
        assert len(kill_switch._events) > 0
    
    def test_persists_multiple_events(self, kill_switch, mock_database):
        """Test that multiple events are persisted"""
        kill_switch.arm()
        
        # Trigger multiple times
        kill_switch.trigger("Event 1", "Manual")
        kill_switch.reset("admin1")
        kill_switch.trigger("Event 2", "FileTrigger")
        kill_switch.reset("admin2")
        
        # Verify multiple database calls
        conn = mock_database._Database__get_connection.return_value
        cursor = conn.cursor.return_value
        
        # Should have at least 2 INSERT calls (one per trigger)
        insert_calls = [call for call in cursor.execute.call_args_list 
                        if "INSERT" in call[0][0].upper()]
        assert len(insert_calls) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
