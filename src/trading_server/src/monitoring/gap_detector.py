"""
Gap Detection Service

Detects data gaps in tick data collection and sends alerts.
"""

import os
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from utils.time_utils import get_utc_time
from utils.market_utils import check_if_market_open
from utils.logging_config import get_logger
from database import Database


class GapDetector:
    """
    Detects gaps in tick data collection
    """

    def __init__(
        self,
        gap_threshold_minutes: float = 5.0,
        check_interval_minutes: float = 5.0,
        lookback_minutes: float = 10.0,
        enabled: bool = True,
    ):
        """
        Initialize gap detector

        :param gap_threshold_minutes: Minimum gap duration to alert (minutes)
        :param check_interval_minutes: Interval between gap checks (minutes)
        :param lookback_minutes: How far back to check for gaps (minutes)
        :param enabled: Whether gap detection is enabled
        """
        self.gap_threshold_seconds = gap_threshold_minutes * 60
        self.check_interval_seconds = check_interval_minutes * 60
        self.lookback_seconds = lookback_minutes * 60
        self.enabled = enabled

        # Initialize logger
        try:
            self.logger = get_logger("gap_detector", "gap_detector.log")
            self._use_structured = hasattr(self.logger, "log_event")
        except Exception:
            import logging
            self.logger = logging.getLogger("gap_detector")
            self._use_structured = False

        # Database connection
        self.db = Database()

        # Monitoring state
        self._monitoring_thread: Optional[threading.Thread] = None
        self._shutdown_flag = threading.Event()
        self._last_check_time: Optional[datetime] = None
        self._gap_count = 0
        self._system_wide_gap_count = 0

    def start(self):
        """Start gap detection in background thread"""
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
                event_type="gap_detector_started",
                message="Gap detector started",
                metrics={
                    "gap_threshold_seconds": self.gap_threshold_seconds,
                    "check_interval_seconds": self.check_interval_seconds,
                },
            )
        else:
            self.logger.info(
                f"Gap detector started (threshold: {self.gap_threshold_seconds}s, "
                f"interval: {self.check_interval_seconds}s)"
            )

    def stop(self):
        """Stop gap detection"""
        self._shutdown_flag.set()
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=5.0)

        if self._use_structured:
            self.logger.log_event(
                event_type="gap_detector_stopped",
                message="Gap detector stopped",
            )
        else:
            self.logger.info("Gap detector stopped")

    def _monitoring_loop(self):
        """Background monitoring loop"""
        while not self._shutdown_flag.is_set():
            try:
                # Only check during market hours
                if check_if_market_open():
                    self.detect_gaps()
            except Exception as e:
                if self._use_structured:
                    self.logger.log_event(
                        event_type="gap_detection_error",
                        message=f"Error during gap detection: {e}",
                        level="ERROR",
                    )
                else:
                    self.logger.error(f"Error during gap detection: {e}", exc_info=True)

            # Wait for next check or shutdown
            self._shutdown_flag.wait(self.check_interval_seconds)

    def detect_gaps(self) -> List[Dict]:
        """
        Detect gaps in tick data

        :return: List of detected gaps
        """
        current_time = get_utc_time()
        lookback_time = current_time - timedelta(seconds=self.lookback_seconds)

        # Query for gaps using SQL
        query = """
        WITH tick_times AS (
            SELECT 
                symbol,
                datetime,
                LAG(datetime) OVER (PARTITION BY symbol ORDER BY datetime) AS prev_datetime
            FROM ticks_forex
            WHERE datetime >= %s
        ),
        gaps AS (
            SELECT 
                symbol,
                prev_datetime AS gap_start,
                datetime AS gap_end,
                EXTRACT(EPOCH FROM (datetime - prev_datetime)) AS gap_seconds
            FROM tick_times
            WHERE prev_datetime IS NOT NULL
                AND EXTRACT(EPOCH FROM (datetime - prev_datetime)) > %s
        )
        SELECT 
            symbol,
            gap_start,
            gap_end,
            gap_seconds
        FROM gaps
        ORDER BY gap_seconds DESC
        LIMIT 100
        """

        try:
            # Use execute_many with parameterized query
            gaps = self.db.execute_many(
                query,
                {
                    'lookback_time': lookback_time,
                    'gap_threshold': self.gap_threshold_seconds
                }
            )

            detected_gaps = []
            for gap in gaps:
                gap_info = {
                    "symbol": gap[0],
                    "gap_start": gap[1],
                    "gap_end": gap[2],
                    "gap_seconds": float(gap[3]),
                }
                detected_gaps.append(gap_info)

            # Check for system-wide gaps (multiple symbols gap simultaneously)
            system_wide_gaps = self._detect_system_wide_gaps(detected_gaps)

            # Log and alert on gaps
            if detected_gaps:
                self._log_gaps(detected_gaps, system_wide_gaps)

            self._last_check_time = current_time
            return detected_gaps

        except Exception as e:
            if self._use_structured:
                self.logger.log_event(
                    event_type="gap_detection_query_error",
                    message=f"Error querying for gaps: {e}",
                    level="ERROR",
                )
            else:
                self.logger.error(f"Error querying for gaps: {e}", exc_info=True)
            return []

    def _detect_system_wide_gaps(self, gaps: List[Dict]) -> List[Dict]:
        """
        Detect system-wide gaps (multiple symbols gap simultaneously)

        :param gaps: List of detected gaps
        :return: List of system-wide gaps
        """
        # Group gaps by time window (within 1 minute)
        time_windows: Dict[str, List[Dict]] = {}
        for gap in gaps:
            gap_start = gap["gap_start"]
            if isinstance(gap_start, str):
                from datetime import datetime
                gap_start = datetime.fromisoformat(gap_start.replace("Z", "+00:00"))

            # Round to nearest minute for grouping
            window_key = gap_start.strftime("%Y-%m-%d %H:%M")
            if window_key not in time_windows:
                time_windows[window_key] = []
            time_windows[window_key].append(gap)

        # Find windows with 3+ symbols (system-wide)
        system_wide = []
        for window_key, window_gaps in time_windows.items():
            if len(window_gaps) >= 3:
                symbols = [g["symbol"] for g in window_gaps]
                avg_gap = sum(g["gap_seconds"] for g in window_gaps) / len(window_gaps)
                system_wide.append(
                    {
                        "window": window_key,
                        "symbols": symbols,
                        "symbol_count": len(symbols),
                        "avg_gap_seconds": avg_gap,
                        "gaps": window_gaps,
                    }
                )

        return system_wide

    def _send_alert(self, alert_type: str, message: str, severity: str, metrics: Dict):
        """
        Send alert via WebSocket (if API is available)

        :param alert_type: Type of alert
        :param message: Alert message
        :param severity: Alert severity (info, warning, error)
        :param metrics: Additional metrics
        """
        try:
            # Try to import and use WebSocket alert system
            import sys
            import os

            # Add API src to path
            api_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
                "api", "src"
            )
            if api_path not in sys.path:
                sys.path.insert(0, api_path)

            try:
                from websocket.channels import broadcast_alert
                import asyncio

                # Create event loop if needed
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                # Broadcast alert
                if loop.is_running():
                    # If loop is running, schedule coroutine
                    asyncio.create_task(
                        broadcast_alert(alert_type, message, severity)
                    )
                else:
                    # If loop is not running, run coroutine
                    loop.run_until_complete(
                        broadcast_alert(alert_type, message, severity)
                    )
            except ImportError:
                # WebSocket system not available - log only
                pass
        except Exception as e:
            # Alert system not available - log warning
            if self._use_structured:
                self.logger.log_event(
                    event_type="alert_send_failed",
                    message=f"Failed to send alert: {e}",
                    level="WARNING",
                )
            else:
                self.logger.warning(f"Failed to send alert: {e}")

    def _log_gaps(self, gaps: List[Dict], system_wide: List[Dict]):
        """
        Log detected gaps and send alerts

        :param gaps: List of detected gaps
        :param system_wide: List of system-wide gaps
        """
        # Log individual gaps
        for gap in gaps:
            self._gap_count += 1
            if self._use_structured:
                self.logger.log_event(
                    event_type="data_gap_detected",
                    message=(
                        f"Data gap detected for {gap['symbol']}: "
                        f"{gap['gap_seconds']/60:.1f} minutes"
                    ),
                    symbol=gap["symbol"],
                    metrics={
                        "gap_seconds": gap["gap_seconds"],
                        "gap_start": gap["gap_start"].isoformat()
                        if isinstance(gap["gap_start"], datetime)
                        else str(gap["gap_start"]),
                        "gap_end": gap["gap_end"].isoformat()
                        if isinstance(gap["gap_end"], datetime)
                        else str(gap["gap_end"]),
                    },
                    level="WARNING",
                )
            else:
                self.logger.warning(
                    f"Data gap detected for {gap['symbol']}: "
                    f"{gap['gap_seconds']/60:.1f} minutes "
                    f"({gap['gap_start']} to {gap['gap_end']})"
                )

            # Send alert for individual gap
            self._send_alert(
                alert_type="data_gap_detected",
                message=f"Data gap detected for {gap['symbol']}: {gap['gap_seconds']/60:.1f} minutes",
                severity="warning",
                metrics={
                    "symbol": gap["symbol"],
                    "gap_seconds": gap["gap_seconds"],
                },
            )

        # Log system-wide gaps
        for sw_gap in system_wide:
            self._system_wide_gap_count += 1
            if self._use_structured:
                self.logger.log_event(
                    event_type="system_wide_gap",
                    message=(
                        f"System-wide gap detected: {sw_gap['symbol_count']} symbols "
                        f"affected, avg gap: {sw_gap['avg_gap_seconds']/60:.1f} minutes"
                    ),
                    metrics={
                        "symbol_count": sw_gap["symbol_count"],
                        "symbols": sw_gap["symbols"],
                        "avg_gap_seconds": sw_gap["avg_gap_seconds"],
                        "window": sw_gap["window"],
                    },
                    level="ERROR",
                )
            else:
                self.logger.error(
                    f"System-wide gap detected: {sw_gap['symbol_count']} symbols "
                    f"affected at {sw_gap['window']}, "
                    f"avg gap: {sw_gap['avg_gap_seconds']/60:.1f} minutes"
                )

            # Send alert for system-wide gap
            self._send_alert(
                alert_type="system_wide_gap",
                message=(
                    f"System-wide gap: {sw_gap['symbol_count']} symbols affected, "
                    f"avg gap: {sw_gap['avg_gap_seconds']/60:.1f} minutes"
                ),
                severity="error",
                metrics={
                    "symbol_count": sw_gap["symbol_count"],
                    "avg_gap_seconds": sw_gap["avg_gap_seconds"],
                },
            )

        # Check for prolonged gaps (>30 minutes)
        prolonged_gaps = [
            g for g in gaps if g["gap_seconds"] > 30 * 60
        ]
        for gap in prolonged_gaps:
            self._send_alert(
                alert_type="prolonged_gap",
                message=(
                    f"Prolonged gap for {gap['symbol']}: "
                    f"{gap['gap_seconds']/60:.1f} minutes"
                ),
                severity="error",
                metrics={
                    "symbol": gap["symbol"],
                    "gap_seconds": gap["gap_seconds"],
                },
            )

    def get_status(self) -> Dict:
        """
        Get current gap detection status

        :return: Dictionary with current status
        """
        return {
            "enabled": self.enabled,
            "last_check_time": (
                self._last_check_time.isoformat() if self._last_check_time else None
            ),
            "gap_count": self._gap_count,
            "system_wide_gap_count": self._system_wide_gap_count,
            "gap_threshold_seconds": self.gap_threshold_seconds,
            "check_interval_seconds": self.check_interval_seconds,
        }
