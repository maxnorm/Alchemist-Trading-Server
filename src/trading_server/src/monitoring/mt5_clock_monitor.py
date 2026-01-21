"""
MT5 Broker Clock Monitor

Monitors MT5 broker clock drift relative to server clock by analyzing
tick.time_msc (converted to datetime) vs server receive_time.

Since MT5 broker clock cannot be controlled by the client, this monitor
tracks drift and alerts when it exceeds thresholds, enabling proactive
identification of clock synchronization issues.
"""

import os
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import statistics

from utils.time_utils import get_utc_time
from utils.logging_config import get_logger


class MT5ClockMonitor:
    """
    Monitor MT5 broker clock drift relative to server clock
    """

    def __init__(
        self,
        window_size: int = 1000,
        drift_threshold_seconds: float = 1.0,
        alert_cooldown_minutes: int = 5,
        negative_latency_warning_threshold: float = 0.1,  # 10%
        negative_latency_critical_threshold: float = 0.2,  # 20%
        enabled: bool = True,
    ):
        """
        Initialize MT5 clock monitor

        :param window_size: Rolling window size for drift statistics
        :param drift_threshold_seconds: Maximum acceptable drift in seconds
        :param alert_cooldown_minutes: Minutes between alerts for same issue
        :param negative_latency_warning_threshold: Warning threshold for negative latency rate (0.0-1.0)
        :param negative_latency_critical_threshold: Critical threshold for negative latency rate (0.0-1.0)
        :param enabled: Whether monitoring is enabled
        """
        self.window_size = window_size
        self.drift_threshold = drift_threshold_seconds
        self.alert_cooldown = timedelta(minutes=alert_cooldown_minutes)
        self.negative_latency_warning_threshold = negative_latency_warning_threshold
        self.negative_latency_critical_threshold = negative_latency_critical_threshold
        self.enabled = enabled

        # Initialize logger
        try:
            self.logger = get_logger("mt5_clock_monitor", "mt5_clock_monitor.log")
            self._use_structured = hasattr(self.logger, "log_event")
        except Exception:
            import logging

            self.logger = logging.getLogger("mt5_clock_monitor")
            self._use_structured = False

        # Drift tracking: deque of (timestamp, drift_seconds) tuples
        self._drift_history: deque = deque(maxlen=window_size)
        self._lock = threading.RLock()  # Use reentrant lock to allow nested lock acquisition

        # Negative latency tracking
        self._negative_latency_count = 0
        self._total_tick_count = 0

        # Alert state
        self._last_alert_time: Optional[datetime] = None
        self._last_alert_type: Optional[str] = None
        self._alert_count = 0

        # Statistics
        self._last_status: str = "unknown"
        self._last_check_time: Optional[datetime] = None

    def track_tick(
        self,
        tick_datetime: datetime,
        receive_time: datetime,
        symbol: Optional[str] = None,
    ) -> None:
        """
        Track a tick to monitor MT5 broker clock drift

        :param tick_datetime: Tick datetime from MT5 broker (event_time)
        :param receive_time: Server receive time
        :param symbol: Symbol (optional, for logging)
        """
        if not self.enabled:
            return

        try:
            # Ensure both times are timezone-aware UTC
            if tick_datetime.tzinfo is None:
                tick_datetime = tick_datetime.replace(tzinfo=timezone.utc)
            else:
                tick_datetime = tick_datetime.astimezone(timezone.utc)

            if receive_time.tzinfo is None:
                receive_time = receive_time.replace(tzinfo=timezone.utc)
            else:
                receive_time = receive_time.astimezone(timezone.utc)

            # Calculate drift: positive = broker ahead, negative = broker behind
            drift_seconds = (tick_datetime - receive_time).total_seconds()

            with self._lock:
                # Store drift in rolling window
                self._drift_history.append((receive_time, drift_seconds))

                # Track negative latency
                self._total_tick_count += 1
                if drift_seconds < 0:
                    self._negative_latency_count += 1

                # Update last check time
                self._last_check_time = receive_time

                # Update Prometheus metrics
                self._update_metrics()

                # Check for alerts (with cooldown)
                self._check_alerts(drift_seconds, symbol)

        except Exception as e:
            if self._use_structured:
                self.logger.log_event(
                    event_type="mt5_clock_track_error",
                    message=f"Error tracking tick for clock monitoring: {e}",
                    symbol=symbol or "unknown",
                    level="ERROR",
                )
            else:
                self.logger.error(
                    f"Error tracking tick for clock monitoring: {e}", exc_info=True
                )

    def _check_alerts(self, drift_seconds: float, symbol: Optional[str] = None) -> None:
        """Check if alerts should be triggered"""
        current_time = get_utc_time()

        # Check cooldown
        if (
            self._last_alert_time
            and (current_time - self._last_alert_time) < self.alert_cooldown
        ):
            return

        # Calculate negative latency rate
        negative_latency_rate = (
            self._negative_latency_count / self._total_tick_count
            if self._total_tick_count > 0
            else 0.0
        )

        # Check for persistent drift
        if len(self._drift_history) >= 100:  # Need enough samples
            recent_drifts = [d[1] for d in list(self._drift_history)[-100:]]
            avg_drift = statistics.mean(recent_drifts)
            abs_avg_drift = abs(avg_drift)

            if abs_avg_drift > self.drift_threshold:
                # Persistent drift detected
                if (
                    self._last_alert_type != "drift"
                    or not self._last_alert_time
                    or (current_time - self._last_alert_time) >= self.alert_cooldown
                ):
                    self._alert_drift(avg_drift, symbol)
                    self._last_alert_time = current_time
                    self._last_alert_type = "drift"
                    self._alert_count += 1

        # Check for high negative latency rate
        if negative_latency_rate >= self.negative_latency_critical_threshold:
            if (
                self._last_alert_type != "negative_latency_critical"
                or not self._last_alert_time
                or (current_time - self._last_alert_time) >= self.alert_cooldown
            ):
                self._alert_negative_latency(negative_latency_rate, "critical", symbol)
                self._last_alert_time = current_time
                self._last_alert_type = "negative_latency_critical"
                self._alert_count += 1
        elif negative_latency_rate >= self.negative_latency_warning_threshold:
            if (
                self._last_alert_type != "negative_latency_warning"
                or not self._last_alert_time
                or (current_time - self._last_alert_time) >= self.alert_cooldown
            ):
                self._alert_negative_latency(negative_latency_rate, "warning", symbol)
                self._last_alert_time = current_time
                self._last_alert_type = "negative_latency_warning"
                self._alert_count += 1

    def _alert_drift(self, avg_drift: float, symbol: Optional[str] = None) -> None:
        """Alert on persistent clock drift"""
        abs_drift = abs(avg_drift)
        direction = "ahead" if avg_drift > 0 else "behind"

        if self._use_structured:
            self.logger.log_event(
                event_type="mt5_clock_drift_alert",
                message=f"MT5 broker clock drift detected: {abs_drift:.3f}s {direction} server",
                symbol=symbol or "all",
                metrics={
                    "avg_drift_seconds": avg_drift,
                    "abs_drift_seconds": abs_drift,
                    "direction": direction,
                    "threshold_seconds": self.drift_threshold,
                    "sample_count": len(self._drift_history),
                },
                level="WARNING",
            )
        else:
            self.logger.warning(
                f"MT5 broker clock drift alert: {abs_drift:.3f}s {direction} server "
                f"(threshold: {self.drift_threshold}s, samples: {len(self._drift_history)})"
            )

    def _alert_negative_latency(
        self,
        rate: float,
        severity: str,
        symbol: Optional[str] = None,
    ) -> None:
        """Alert on high negative latency rate"""
        level = "ERROR" if severity == "critical" else "WARNING"
        threshold = (
            self.negative_latency_critical_threshold
            if severity == "critical"
            else self.negative_latency_warning_threshold
        )

        if self._use_structured:
            self.logger.log_event(
                event_type="mt5_negative_latency_alert",
                message=f"High negative latency rate detected: {rate*100:.1f}% ({severity})",
                symbol=symbol or "all",
                metrics={
                    "negative_latency_rate": rate,
                    "negative_latency_count": self._negative_latency_count,
                    "total_tick_count": self._total_tick_count,
                    "threshold": threshold,
                    "severity": severity,
                },
                level=level,
            )
        else:
            self.logger.warning(
                f"MT5 negative latency alert ({severity}): {rate*100:.1f}% "
                f"(threshold: {threshold*100:.1f}%, "
                f"negative: {self._negative_latency_count}/{self._total_tick_count})"
            )

    def get_drift_stats(self) -> Dict[str, any]:
        """
        Get drift statistics from rolling window

        :return: Dictionary with drift statistics
        """
        with self._lock:
            if not self._drift_history:
                return {
                    "sample_count": 0,
                    "avg_drift_seconds": None,
                    "min_drift_seconds": None,
                    "max_drift_seconds": None,
                    "median_drift_seconds": None,
                    "stddev_drift_seconds": None,
                }

            drifts = [d[1] for d in self._drift_history]

            return {
                "sample_count": len(drifts),
                "avg_drift_seconds": float(statistics.mean(drifts)),
                "min_drift_seconds": float(min(drifts)),
                "max_drift_seconds": float(max(drifts)),
                "median_drift_seconds": float(statistics.median(drifts)),
                "stddev_drift_seconds": (
                    float(statistics.stdev(drifts)) if len(drifts) > 1 else 0.0
                ),
            }

    def get_negative_latency_stats(self) -> Dict[str, any]:
        """
        Get negative latency statistics

        :return: Dictionary with negative latency statistics
        """
        with self._lock:
            rate = (
                self._negative_latency_count / self._total_tick_count
                if self._total_tick_count > 0
                else 0.0
            )

            return {
                "negative_latency_count": self._negative_latency_count,
                "total_tick_count": self._total_tick_count,
                "negative_latency_rate": rate,
                "status": self._get_negative_latency_status(rate),
            }

    def _get_negative_latency_status(self, rate: float) -> str:
        """Get status string for negative latency rate"""
        if rate >= self.negative_latency_critical_threshold:
            return "critical"
        elif rate >= self.negative_latency_warning_threshold:
            return "warning"
        else:
            return "ok"

    def get_status(self) -> Dict[str, any]:
        """
        Get current monitoring status

        :return: Dictionary with current status
        """
        drift_stats = self.get_drift_stats()
        negative_latency_stats = self.get_negative_latency_stats()

        # Determine overall status
        status = "ok"
        if drift_stats["sample_count"] > 0:
            abs_avg_drift = abs(drift_stats["avg_drift_seconds"] or 0.0)
            if abs_avg_drift > self.drift_threshold:
                status = "warning"
            elif abs_avg_drift > self.drift_threshold * 2:
                status = "critical"

        if negative_latency_stats["status"] == "critical":
            status = "critical"
        elif negative_latency_stats["status"] == "warning" and status == "ok":
            status = "warning"

        self._last_status = status

        return {
            "enabled": self.enabled,
            "status": status,
            "last_check_time": (
                self._last_check_time.isoformat() if self._last_check_time else None
            ),
            "drift_stats": drift_stats,
            "negative_latency_stats": negative_latency_stats,
            "alert_count": self._alert_count,
            "window_size": self.window_size,
            "drift_threshold_seconds": self.drift_threshold,
        }

    def is_healthy(self) -> bool:
        """
        Check if MT5 clock sync is healthy

        :return: True if clock drift is within threshold and negative latency rate is acceptable
        """
        drift_stats = self.get_drift_stats()
        negative_latency_stats = self.get_negative_latency_stats()

        # Check drift
        if drift_stats["sample_count"] > 0:
            abs_avg_drift = abs(drift_stats["avg_drift_seconds"] or 0.0)
            if abs_avg_drift > self.drift_threshold:
                return False

        # Check negative latency rate
        if negative_latency_stats["status"] == "critical":
            return False

        return True

    def _update_metrics(self) -> None:
        """Update Prometheus metrics"""
        try:
            from monitoring.metrics import (
                clock_drift_seconds,
                negative_latency_rate,
                clock_sync_status,
            )

            # Update drift metric
            drift_stats = self.get_drift_stats()
            if drift_stats["sample_count"] > 0 and drift_stats["avg_drift_seconds"] is not None:
                clock_drift_seconds.labels(source="mt5_broker").set(
                    drift_stats["avg_drift_seconds"]
                )

            # Update negative latency rate
            negative_latency_stats = self.get_negative_latency_stats()
            negative_latency_rate.set(negative_latency_stats["negative_latency_rate"])

            # Update health status (1=healthy, 0=unhealthy)
            is_healthy = self.is_healthy()
            clock_sync_status.labels(source="mt5_broker").set(1.0 if is_healthy else 0.0)

        except Exception as e:
            # Don't fail if metrics update fails
            if self._use_structured:
                self.logger.log_event(
                    event_type="mt5_clock_metrics_error",
                    message=f"Error updating Prometheus metrics: {e}",
                    level="WARNING",
                )
            else:
                self.logger.warning(f"Error updating Prometheus metrics: {e}")

    def reset_stats(self) -> None:
        """Reset statistics (useful for testing)"""
        with self._lock:
            self._drift_history.clear()
            self._negative_latency_count = 0
            self._total_tick_count = 0
            self._alert_count = 0
            self._last_alert_time = None
            self._last_alert_type = None
            self._last_status = "unknown"


# Module-level singleton for global monitor access
_global_mt5_monitor: Optional["MT5ClockMonitor"] = None


def get_global_mt5_monitor() -> Optional["MT5ClockMonitor"]:
    """
    Get the global MT5ClockMonitor instance.

    :return: MT5ClockMonitor instance or None if not set
    """
    return _global_mt5_monitor


def set_global_mt5_monitor(monitor: "MT5ClockMonitor") -> None:
    """
    Set the global MT5ClockMonitor instance.

    :param monitor: MT5ClockMonitor instance to register globally
    """
    global _global_mt5_monitor
    _global_mt5_monitor = monitor
