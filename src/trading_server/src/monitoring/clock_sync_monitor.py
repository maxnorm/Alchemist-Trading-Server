"""
Clock Synchronization Monitor

Monitors server clock synchronization with NTP servers and logs warnings
if drift exceeds threshold.
"""

import socket
import struct
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, List
from utils.time_utils import get_utc_time
from utils.logging_config import get_logger


class ClockSyncMonitor:
    """
    Monitor clock synchronization with NTP servers
    """

    # NTP protocol constants
    REFERENCE_TIME = 2208988800  # 1970-01-01 00:00:00
    NTP_PACKET_FORMAT = "!12I"
    NTP_DELTA = 2208988800

    def __init__(
        self,
        ntp_servers: Optional[List[str]] = None,
        check_interval_seconds: int = 300,  # 5 minutes
        drift_threshold_seconds: float = 1.0,
        enabled: bool = True,
    ):
        """
        Initialize clock sync monitor

        :param ntp_servers: List of NTP server hostnames (default: common NTP servers)
        :param check_interval_seconds: Interval between checks in seconds
        :param drift_threshold_seconds: Maximum acceptable drift in seconds
        :param enabled: Whether monitoring is enabled
        """
        self.ntp_servers = ntp_servers or [
            "pool.ntp.org",
            "time.google.com",
            "time.cloudflare.com",
            "time.windows.com",
        ]
        self.check_interval = check_interval_seconds
        self.drift_threshold = drift_threshold_seconds
        self.enabled = enabled

        # Initialize logger
        try:
            self.logger = get_logger("clock_sync_monitor", "clock_sync_monitor.log")
            self._use_structured = hasattr(self.logger, "log_event")
        except Exception:
            import logging

            self.logger = logging.getLogger("clock_sync_monitor")
            self._use_structured = False

        # Monitoring state
        self._monitoring_thread: Optional[threading.Thread] = None
        self._shutdown_flag = threading.Event()
        self._last_check_time: Optional[datetime] = None
        self._last_drift: Optional[float] = None
        self._last_status: str = "unknown"
        self._check_count = 0
        self._warning_count = 0

    def start(self):
        """Start monitoring in background thread"""
        if not self.enabled:
            return

        if self._monitoring_thread and self._monitoring_thread.is_alive():
            return  # Already running

        self._shutdown_flag.clear()
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True
        )
        self._monitoring_thread.start()

        if self._use_structured:
            self.logger.log_event(
                event_type="clock_sync_monitor_started",
                message="Clock sync monitor started",
                metrics={
                    "check_interval": self.check_interval,
                    "drift_threshold": self.drift_threshold,
                },
            )
        else:
            self.logger.info(
                f"Clock sync monitor started (interval: {self.check_interval}s, threshold: {self.drift_threshold}s)"
            )

    def stop(self):
        """Stop monitoring"""
        self._shutdown_flag.set()
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=5.0)

        if self._use_structured:
            self.logger.log_event(
                event_type="clock_sync_monitor_stopped",
                message="Clock sync monitor stopped",
            )
        else:
            self.logger.info("Clock sync monitor stopped")

    def _monitoring_loop(self):
        """Background monitoring loop"""
        while not self._shutdown_flag.is_set():
            try:
                self.check_clock_sync()
            except Exception as e:
                if self._use_structured:
                    self.logger.log_event(
                        event_type="clock_sync_check_error",
                        message=f"Error during clock sync check: {e}",
                        level="ERROR",
                    )
                else:
                    self.logger.error(
                        f"Error during clock sync check: {e}", exc_info=True
                    )

            # Wait for next check or shutdown
            self._shutdown_flag.wait(self.check_interval)

    def get_ntp_time(
        self, host: str, port: int = 123, timeout: int = 5
    ) -> Optional[datetime]:
        """
        Get time from NTP server

        :param host: NTP server hostname
        :param port: NTP server port
        :param timeout: Connection timeout in seconds
        :return: NTP time as datetime or None if failed
        """
        try:
            # Create NTP request packet
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.settimeout(timeout)

            # Send NTP request
            data = b"\x1b" + 47 * b"\0"
            client.sendto(data, (host, port))

            # Receive response
            data, address = client.recvfrom(1024)
            client.close()

            # Parse NTP response
            if data:
                unpacked = struct.unpack(
                    self.NTP_PACKET_FORMAT,
                    data[0 : struct.calcsize(self.NTP_PACKET_FORMAT)],
                )
                seconds = unpacked[10] - self.NTP_DELTA
                fraction = unpacked[11] / 2**32
                ntp_time = seconds + fraction
                return datetime.fromtimestamp(ntp_time, tz=timezone.utc)
        except Exception:
            return None
        return None  # Explicit return for MyPy

    def check_clock_sync(self) -> Dict:
        """
        Check clock synchronization with NTP servers

        :return: Dictionary with check results
        """
        server_time = get_utc_time()
        successful_checks = 0
        total_drift = 0.0
        drifts = []

        # Try each NTP server
        for server in self.ntp_servers:
            ntp_time = self.get_ntp_time(server)
            if ntp_time:
                # Calculate drift
                drift_seconds = (server_time - ntp_time).total_seconds()
                total_drift += drift_seconds
                drifts.append(drift_seconds)
                successful_checks += 1

        self._check_count += 1
        self._last_check_time = server_time

        if successful_checks > 0:
            avg_drift = total_drift / successful_checks
            self._last_drift = avg_drift

            # Determine status
            if abs(avg_drift) <= self.drift_threshold:
                status = "ok"
                level = "INFO"
            elif abs(avg_drift) <= 5.0:
                status = "warning"
                level = "WARNING"
                self._warning_count += 1
            else:
                status = "critical"
                level = "ERROR"
                self._warning_count += 1

            self._last_status = status

            # Log result
            if self._use_structured:
                self.logger.log_event(
                    event_type="clock_sync_check",
                    message=f"Clock sync check: {status}, drift: {avg_drift:.3f}s",
                    metrics={
                        "drift_seconds": avg_drift,
                        "status": status,
                        "successful_checks": successful_checks,
                        "total_servers": len(self.ntp_servers),
                        "drifts": drifts,
                    },
                    level=level,
                )
            else:
                if status == "ok":
                    self.logger.debug(
                        f"Clock sync OK: drift {avg_drift:.3f}s (threshold: {self.drift_threshold}s)"
                    )
                else:
                    getattr(self.logger, level.lower())(
                        f"Clock sync {status.upper()}: drift {avg_drift:.3f}s "
                        f"(threshold: {self.drift_threshold}s)"
                    )

            return {
                "status": status,
                "drift_seconds": avg_drift,
                "successful_checks": successful_checks,
                "server_time": server_time.isoformat(),
                "drifts": drifts,
            }
        else:
            # No successful checks
            self._last_status = "error"
            if self._use_structured:
                self.logger.log_event(
                    event_type="clock_sync_check_failed",
                    message="Clock sync check failed: could not connect to any NTP servers",
                    level="ERROR",
                )
            else:
                self.logger.error(
                    "Clock sync check failed: could not connect to any NTP servers"
                )

            return {
                "status": "error",
                "drift_seconds": None,
                "successful_checks": 0,
                "server_time": server_time.isoformat(),
            }

    def get_status(self) -> Dict:
        """
        Get current monitoring status

        :return: Dictionary with current status
        """
        return {
            "enabled": self.enabled,
            "last_check_time": (
                self._last_check_time.isoformat() if self._last_check_time else None
            ),
            "last_drift_seconds": self._last_drift,
            "last_status": self._last_status,
            "check_count": self._check_count,
            "warning_count": self._warning_count,
            "check_interval_seconds": self.check_interval,
            "drift_threshold_seconds": self.drift_threshold,
        }

    def is_healthy(self) -> bool:
        """
        Check if clock sync is healthy

        :return: True if clock is synchronized within threshold
        """
        if self._last_status in ["ok", "warning"]:
            return True
        return False


# Module-level singleton for global monitor access
_global_monitor: Optional["ClockSyncMonitor"] = None


def get_global_monitor() -> Optional["ClockSyncMonitor"]:
    """
    Get the global ClockSyncMonitor instance.

    :return: ClockSyncMonitor instance or None if not set
    """
    return _global_monitor


def set_global_monitor(monitor: "ClockSyncMonitor") -> None:
    """
    Set the global ClockSyncMonitor instance.

    :param monitor: ClockSyncMonitor instance to register globally
    """
    global _global_monitor
    _global_monitor = monitor