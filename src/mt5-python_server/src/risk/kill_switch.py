"""
Kill Switch Module

Independent kill switch with multiple trigger mechanisms for emergency trading halt.
Designed to work independently of the main trading loop to ensure safety even if
the trading loop hangs or crashes.

Trigger mechanisms:
1. FileTrigger - Watches for a kill file on disk
2. EnvironmentTrigger - Checks TRADING_KILL environment variable
3. NetworkTrigger - UDP listener for remote kill commands
4. SignalTrigger - Handles OS signals (SIGUSR1 on Unix)
5. APITrigger - Called from FastAPI endpoint (Phase 2)
"""

import os
import sys
import socket
import threading
import time
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional, Protocol, Any
from dataclasses import dataclass, field


class KillSwitchState(Enum):
    """Kill switch states"""
    ARMED = "armed"          # Ready to trigger
    TRIGGERED = "triggered"  # Kill switch has been activated
    DISABLED = "disabled"    # Kill switch is disabled


@dataclass
class KillSwitchEvent:
    """Represents a kill switch trigger event"""
    timestamp: datetime
    reason: str
    trigger_type: str
    positions_closed: int = 0
    approver: Optional[str] = None
    reset_timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'reason': self.reason,
            'trigger_type': self.trigger_type,
            'positions_closed': self.positions_closed,
            'approver': self.approver,
            'reset_timestamp': self.reset_timestamp.isoformat() if self.reset_timestamp else None
        }


class KillSwitchTrigger(Protocol):
    """Protocol for kill switch trigger mechanisms"""
    
    @property
    def name(self) -> str:
        """Trigger name for logging"""
        ...
    
    def check(self) -> tuple[bool, str]:
        """
        Check if trigger condition is met.
        Returns: (is_triggered, reason)
        """
        ...
    
    def start_monitoring(self) -> None:
        """Start monitoring for trigger condition"""
        ...
    
    def stop_monitoring(self) -> None:
        """Stop monitoring"""
        ...
    
    def reset(self) -> None:
        """Reset trigger state"""
        ...


class BaseTrigger(ABC):
    """Base class for trigger implementations"""
    
    def __init__(self, on_trigger: Callable[[str, str], None] = None):
        """
        Args:
            on_trigger: Callback when trigger fires (reason, trigger_type)
        """
        self.on_trigger = on_trigger
        self._monitoring = False
        self._thread: Optional[threading.Thread] = None
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Trigger name"""
        pass
    
    @abstractmethod
    def check(self) -> tuple[bool, str]:
        """Check trigger condition"""
        pass
    
    def start_monitoring(self) -> None:
        """Start background monitoring"""
        if self._monitoring:
            return
        self._monitoring = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        self.logger.info(f"{self.name} trigger monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop background monitoring"""
        self._monitoring = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        self.logger.info(f"{self.name} trigger monitoring stopped")
    
    def _monitor_loop(self) -> None:
        """Background monitoring loop"""
        while self._monitoring:
            try:
                triggered, reason = self.check()
                if triggered and self.on_trigger:
                    self.on_trigger(reason, self.name)
            except Exception as e:
                self.logger.error(f"Error in {self.name} trigger: {e}")
            time.sleep(1)  # Check every second
    
    def reset(self) -> None:
        """Reset trigger state - override in subclasses if needed"""
        pass


class FileTrigger(BaseTrigger):
    """
    File-based trigger that watches for a kill file.
    
    On Windows: C:\\trading\\kill.flag
    On Unix: /var/run/trading.kill
    
    Creating this file will trigger the kill switch.
    """
    
    def __init__(
        self,
        on_trigger: Callable[[str, str], None] = None,
        kill_file_path: str = None
    ):
        super().__init__(on_trigger)
        
        if kill_file_path:
            self.kill_file = Path(kill_file_path)
        elif sys.platform == 'win32':
            self.kill_file = Path("C:/trading/kill.flag")
        else:
            self.kill_file = Path("/var/run/trading.kill")
    
    @property
    def name(self) -> str:
        return "FileTrigger"
    
    def check(self) -> tuple[bool, str]:
        """Check if kill file exists"""
        if self.kill_file.exists():
            try:
                content = self.kill_file.read_text().strip()
                reason = content if content else "Kill file detected"
            except Exception:
                reason = "Kill file detected"
            return True, reason
        return False, ""
    
    def reset(self) -> None:
        """Remove kill file on reset"""
        try:
            if self.kill_file.exists():
                self.kill_file.unlink()
                self.logger.info(f"Kill file removed: {self.kill_file}")
        except Exception as e:
            self.logger.error(f"Failed to remove kill file: {e}")


class EnvironmentTrigger(BaseTrigger):
    """
    Environment variable trigger.
    
    Set TRADING_KILL=1 to trigger the kill switch.
    """
    
    def __init__(
        self,
        on_trigger: Callable[[str, str], None] = None,
        env_var: str = "TRADING_KILL"
    ):
        super().__init__(on_trigger)
        self.env_var = env_var
    
    @property
    def name(self) -> str:
        return "EnvironmentTrigger"
    
    def check(self) -> tuple[bool, str]:
        """Check if environment variable is set"""
        value = os.getenv(self.env_var, "").strip()
        if value in ("1", "true", "TRUE", "yes", "YES"):
            return True, f"Environment variable {self.env_var}={value}"
        return False, ""
    
    def reset(self) -> None:
        """Clear environment variable on reset"""
        if self.env_var in os.environ:
            del os.environ[self.env_var]
            self.logger.info(f"Environment variable {self.env_var} cleared")


class NetworkTrigger(BaseTrigger):
    """
    UDP network trigger.
    
    Send 'KILL' or 'KILL:<reason>' to UDP port 9999 to trigger.
    """
    
    def __init__(
        self,
        on_trigger: Callable[[str, str], None] = None,
        port: int = 9999,
        host: str = "0.0.0.0"
    ):
        super().__init__(on_trigger)
        self.port = port
        self.host = host
        self._socket: Optional[socket.socket] = None
        self._triggered = False
        self._trigger_reason = ""
    
    @property
    def name(self) -> str:
        return "NetworkTrigger"
    
    def check(self) -> tuple[bool, str]:
        """Check if network trigger was received"""
        if self._triggered:
            return True, self._trigger_reason
        return False, ""
    
    def start_monitoring(self) -> None:
        """Start UDP listener"""
        if self._monitoring:
            return
        
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind((self.host, self.port))
            self._socket.settimeout(1)
            self.logger.info(f"NetworkTrigger listening on UDP {self.host}:{self.port}")
        except Exception as e:
            self.logger.error(f"Failed to start NetworkTrigger: {e}")
            return
        
        self._monitoring = True
        self._thread = threading.Thread(target=self._udp_listen_loop, daemon=True)
        self._thread.start()
    
    def stop_monitoring(self) -> None:
        """Stop UDP listener"""
        self._monitoring = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        self.logger.info("NetworkTrigger stopped")
    
    def _udp_listen_loop(self) -> None:
        """Listen for UDP kill commands"""
        while self._monitoring and self._socket:
            try:
                data, addr = self._socket.recvfrom(1024)
                message = data.decode().strip()
                
                if message.startswith("KILL"):
                    if ":" in message:
                        reason = message.split(":", 1)[1]
                    else:
                        reason = f"Network kill command from {addr}"
                    
                    self._triggered = True
                    self._trigger_reason = reason
                    self.logger.warning(f"Kill command received from {addr}: {reason}")
                    
                    if self.on_trigger:
                        self.on_trigger(reason, self.name)
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self._monitoring:
                    self.logger.error(f"Error in UDP listener: {e}")
    
    def reset(self) -> None:
        """Reset trigger state"""
        self._triggered = False
        self._trigger_reason = ""


class SignalTrigger(BaseTrigger):
    """
    OS signal trigger.
    
    On Unix: SIGUSR1 triggers the kill switch
    On Windows: Uses a named event (not implemented in this version)
    """
    
    def __init__(self, on_trigger: Callable[[str, str], None] = None):
        super().__init__(on_trigger)
        self._triggered = False
        self._trigger_reason = ""
    
    @property
    def name(self) -> str:
        return "SignalTrigger"
    
    def check(self) -> tuple[bool, str]:
        """Check if signal was received"""
        if self._triggered:
            return True, self._trigger_reason
        return False, ""
    
    def start_monitoring(self) -> None:
        """Register signal handler"""
        if sys.platform != 'win32':
            import signal
            signal.signal(signal.SIGUSR1, self._handle_signal)
            self.logger.info("SignalTrigger registered for SIGUSR1")
        else:
            self.logger.info("SignalTrigger not available on Windows")
        self._monitoring = True
    
    def stop_monitoring(self) -> None:
        """Unregister signal handler"""
        if sys.platform != 'win32':
            import signal
            signal.signal(signal.SIGUSR1, signal.SIG_DFL)
        self._monitoring = False
    
    def _handle_signal(self, signum, frame):
        """Handle SIGUSR1 signal"""
        self._triggered = True
        self._trigger_reason = "SIGUSR1 signal received"
        self.logger.warning("SIGUSR1 signal received - triggering kill switch")
        if self.on_trigger:
            self.on_trigger(self._trigger_reason, self.name)
    
    def reset(self) -> None:
        """Reset trigger state"""
        self._triggered = False
        self._trigger_reason = ""


class KillSwitch:
    """
    Main kill switch controller.
    
    Manages multiple trigger mechanisms and ensures all positions are closed
    when triggered. The kill switch is designed to work independently of the
    main trading loop.
    
    Usage:
        kill_switch = KillSwitch(
            broker_adapter=terminal,
            on_kill_callback=handle_emergency_shutdown
        )
        kill_switch.arm()
        
        # In trading loop:
        if kill_switch.is_active():
            break
        
        # To manually trigger:
        kill_switch.trigger("Manual emergency stop")
        
        # To reset (requires approver):
        kill_switch.reset("operator_name")
    """
    
    def __init__(
        self,
        broker_adapter: Any = None,
        on_kill_callback: Callable[[str], None] = None,
        audit_log_path: str = None,
        database: Any = None
    ):
        """
        Args:
            broker_adapter: Broker/terminal adapter for closing positions
            on_kill_callback: Callback when kill switch triggers
            audit_log_path: Path to audit log file
            database: Database connection for persistence (optional)
        """
        self.broker_adapter = broker_adapter
        self.on_kill_callback = on_kill_callback
        self.audit_log_path = Path(audit_log_path) if audit_log_path else Path("logs/kill_switch_audit.json")
        self.database = database
        
        self._state = KillSwitchState.DISABLED
        self._triggers: List[BaseTrigger] = []
        self._lock = threading.RLock()
        self._events: List[KillSwitchEvent] = []
        self._current_event: Optional[KillSwitchEvent] = None
        
        self.logger = logging.getLogger(__name__)
        
        # Ensure audit log directory exists
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing events
        self._load_audit_log()
    
    @property
    def state(self) -> KillSwitchState:
        """Current kill switch state"""
        return self._state
    
    def register_trigger(self, trigger: BaseTrigger) -> None:
        """Register a trigger mechanism"""
        trigger.on_trigger = self._handle_trigger
        self._triggers.append(trigger)
        self.logger.info(f"Registered trigger: {trigger.name}")
    
    def register_default_triggers(self) -> None:
        """Register all default trigger mechanisms"""
        self.register_trigger(FileTrigger())
        self.register_trigger(EnvironmentTrigger())
        self.register_trigger(NetworkTrigger())
        if sys.platform != 'win32':
            self.register_trigger(SignalTrigger())
    
    def arm(self) -> None:
        """Arm the kill switch and start monitoring"""
        with self._lock:
            if self._state == KillSwitchState.TRIGGERED:
                self.logger.warning("Cannot arm - kill switch is triggered. Reset first.")
                return
            
            self._state = KillSwitchState.ARMED
            
            for trigger in self._triggers:
                trigger.start_monitoring()
            
            self.logger.info("Kill switch ARMED")
    
    def disarm(self) -> None:
        """Disarm the kill switch and stop monitoring"""
        with self._lock:
            for trigger in self._triggers:
                trigger.stop_monitoring()
            
            self._state = KillSwitchState.DISABLED
            self.logger.info("Kill switch DISARMED")
    
    def is_active(self) -> bool:
        """Check if kill switch has been triggered"""
        return self._state == KillSwitchState.TRIGGERED
    
    def trigger(self, reason: str, trigger_type: str = "Manual") -> None:
        """
        Trigger the kill switch.
        
        Args:
            reason: Reason for triggering
            trigger_type: Type of trigger (e.g., "FileTrigger", "Manual")
        """
        with self._lock:
            if self._state == KillSwitchState.TRIGGERED:
                self.logger.warning("Kill switch already triggered")
                return
            
            self._state = KillSwitchState.TRIGGERED
            
            self.logger.critical(f"🚨 KILL SWITCH TRIGGERED: {reason} (via {trigger_type})")
            
            # Close all positions
            positions_closed = self._close_all_positions()
            
            # Create event
            self._current_event = KillSwitchEvent(
                timestamp=datetime.now(),
                reason=reason,
                trigger_type=trigger_type,
                positions_closed=positions_closed
            )
            self._events.append(self._current_event)
            
            # Save to audit log
            self._save_audit_log()
            
            # Log to database
            self._log_to_database(self._current_event)
            
            # Call callback
            if self.on_kill_callback:
                try:
                    self.on_kill_callback(reason)
                except Exception as e:
                    self.logger.error(f"Error in kill callback: {e}")
    
    def _handle_trigger(self, reason: str, trigger_type: str) -> None:
        """Handle trigger from a trigger mechanism"""
        self.trigger(reason, trigger_type)
    
    def _close_all_positions(self) -> int:
        """
        Close all open positions via broker adapter.
        
        Returns: Number of positions closed
        """
        if not self.broker_adapter:
            self.logger.warning("No broker adapter - cannot close positions")
            return 0
        
        positions_closed = 0
        
        try:
            # Try different methods depending on broker adapter interface
            if hasattr(self.broker_adapter, 'close_all_positions'):
                positions_closed = self.broker_adapter.close_all_positions()
            elif hasattr(self.broker_adapter, 'get_positions'):
                positions = self.broker_adapter.get_positions()
                for pos in positions:
                    try:
                        if hasattr(self.broker_adapter, 'close_position'):
                            self.broker_adapter.close_position(pos)
                            positions_closed += 1
                    except Exception as e:
                        self.logger.error(f"Failed to close position {pos}: {e}")
            else:
                self.logger.warning("Broker adapter doesn't support position closing")
        except Exception as e:
            self.logger.error(f"Error closing positions: {e}")
        
        self.logger.info(f"Closed {positions_closed} positions")
        return positions_closed
    
    def reset(self, approver: str) -> bool:
        """
        Reset the kill switch.
        
        Requires an approver name for audit trail.
        
        Args:
            approver: Name of person approving the reset
            
        Returns: True if reset successful
        """
        if not approver or not approver.strip():
            self.logger.error("Reset requires approver name")
            return False
        
        with self._lock:
            if self._state != KillSwitchState.TRIGGERED:
                self.logger.warning("Kill switch is not triggered - nothing to reset")
                return False
            
            # Update event with reset info
            if self._current_event:
                self._current_event.approver = approver
                self._current_event.reset_timestamp = datetime.now()
                self._save_audit_log()
                
                # Update database with reset info
                self._update_database_resolution(self._current_event)
            
            # Reset all triggers
            for trigger in self._triggers:
                trigger.reset()
            
            self._state = KillSwitchState.ARMED
            self._current_event = None
            
            self.logger.info(f"Kill switch RESET by {approver}")
            return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get current kill switch status"""
        return {
            'state': self._state.value,
            'triggers': [t.name for t in self._triggers],
            'current_event': self._current_event.to_dict() if self._current_event else None,
            'event_count': len(self._events)
        }
    
    def get_audit_log(self) -> List[Dict]:
        """Get audit log entries"""
        return [e.to_dict() for e in self._events]
    
    def _save_audit_log(self) -> None:
        """Save events to audit log file"""
        try:
            with open(self.audit_log_path, 'w') as f:
                json.dump([e.to_dict() for e in self._events], f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save audit log: {e}")
    
    def _load_audit_log(self) -> None:
        """Load events from audit log file"""
        try:
            if self.audit_log_path.exists():
                with open(self.audit_log_path, 'r') as f:
                    data = json.load(f)
                    for entry in data:
                        event = KillSwitchEvent(
                            timestamp=datetime.fromisoformat(entry['timestamp']),
                            reason=entry['reason'],
                            trigger_type=entry['trigger_type'],
                            positions_closed=entry.get('positions_closed', 0),
                            approver=entry.get('approver'),
                            reset_timestamp=datetime.fromisoformat(entry['reset_timestamp']) if entry.get('reset_timestamp') else None
                        )
                        self._events.append(event)
        except Exception as e:
            self.logger.error(f"Failed to load audit log: {e}")
    
    def __enter__(self):
        """Context manager entry"""
        self.arm()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disarm()
        return False
    
    def _log_to_database(self, event: KillSwitchEvent) -> None:
        """Log kill switch event to database"""
        if not self.database:
            return
        
        try:
            conn = self.database._Database__get_connection()
            cursor = conn.cursor()
            
            query = """
                INSERT INTO kill_switch_events (
                    trigger_source, reason, positions_closed, approver, created_at, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """
            
            cursor.execute(query, (
                event.trigger_type,
                event.reason,
                event.positions_closed,
                event.approver,
                event.timestamp,
                event.reset_timestamp
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.logger.debug(f"Logged kill switch event to database: {event.trigger_type}")
            
        except Exception as e:
            self.logger.error(f"Failed to log kill switch event to database: {e}", exc_info=True)
            # Don't raise - allow operation to continue
    
    def _update_database_resolution(self, event: KillSwitchEvent) -> None:
        """Update database with kill switch resolution"""
        if not self.database or not event.reset_timestamp:
            return
        
        try:
            conn = self.database._Database__get_connection()
            cursor = conn.cursor()
            
            # Find the most recent event with matching trigger_source and reason
            # and update its resolved_at timestamp
            query = """
                UPDATE kill_switch_events
                SET resolved_at = ?, approver = ?
                WHERE trigger_source = ? AND reason = ? AND resolved_at IS NULL
                ORDER BY created_at DESC
                LIMIT 1
            """
            
            cursor.execute(query, (
                event.reset_timestamp,
                event.approver,
                event.trigger_type,
                event.reason
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.logger.debug(f"Updated kill switch resolution in database")
            
        except Exception as e:
            self.logger.error(f"Failed to update kill switch resolution in database: {e}", exc_info=True)
            # Don't raise - allow operation to continue
