"""
Integration tests for clock synchronization monitoring
"""

import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock

from tests.shared.helpers.path_utils import setup_trading_server_path
setup_trading_server_path()

from monitoring.clock_sync_monitor import ClockSyncMonitor, get_global_monitor, set_global_monitor
from monitoring.mt5_clock_monitor import MT5ClockMonitor, get_global_mt5_monitor, set_global_mt5_monitor


class TestClockSyncIntegration(unittest.TestCase):
    """Integration tests for clock synchronization"""

    def setUp(self):
        """Set up test fixtures"""
        # Clear global monitors
        set_global_monitor(None)
        set_global_mt5_monitor(None)

    def tearDown(self):
        """Clean up after tests"""
        # Stop and clear monitors
        server_monitor = get_global_monitor()
        if server_monitor:
            server_monitor.stop()
            set_global_monitor(None)

        mt5_monitor = get_global_mt5_monitor()
        if mt5_monitor:
            mt5_monitor.reset_stats()
            set_global_mt5_monitor(None)

    def test_monitor_initialization(self):
        """Test that monitors can be initialized"""
        server_monitor = ClockSyncMonitor(
            check_interval_seconds=60,
            drift_threshold_seconds=1.0,
            enabled=False,  # Disable to avoid background thread
        )
        set_global_monitor(server_monitor)

        mt5_monitor = MT5ClockMonitor(
            window_size=100,
            drift_threshold_seconds=1.0,
            enabled=True,
        )
        set_global_mt5_monitor(mt5_monitor)

        # Verify monitors are accessible
        self.assertIsNotNone(get_global_monitor())
        self.assertIsNotNone(get_global_mt5_monitor())

    def test_health_check_integration(self):
        """Test health check endpoint integration"""
        # Initialize monitors
        server_monitor = ClockSyncMonitor(
            check_interval_seconds=60,
            drift_threshold_seconds=1.0,
            enabled=False,  # Disable to avoid background thread
        )
        set_global_monitor(server_monitor)

        mt5_monitor = MT5ClockMonitor(
            window_size=100,
            drift_threshold_seconds=1.0,
            enabled=True,
        )
        set_global_mt5_monitor(mt5_monitor)

        # Simulate some ticks
        base_time = datetime.now(timezone.utc)
        for i in range(10):
            tick_time = base_time + timedelta(seconds=0.1)
            receive_time = base_time
            mt5_monitor.track_tick(tick_time, receive_time, "USDJPY")

        # Get status from both monitors
        server_status = server_monitor.get_status()
        mt5_status = mt5_monitor.get_status()

        # Verify status structure
        self.assertIn("enabled", server_status)
        self.assertIn("enabled", mt5_status)
        self.assertIn("drift_stats", mt5_status)
        self.assertIn("negative_latency_stats", mt5_status)

    def test_prometheus_metrics_integration(self):
        """Test Prometheus metrics integration"""
        mt5_monitor = MT5ClockMonitor(
            window_size=100,
            drift_threshold_seconds=1.0,
            enabled=True,
        )

        base_time = datetime.now(timezone.utc)

        # Add ticks to trigger metrics update
        for i in range(10):
            tick_time = base_time + timedelta(seconds=0.1)
            receive_time = base_time
            mt5_monitor.track_tick(tick_time, receive_time, "USDJPY")

        # Verify metrics update doesn't raise exception
        # (metrics are updated internally in track_tick)
        drift_stats = mt5_monitor.get_drift_stats()
        self.assertGreater(drift_stats["sample_count"], 0)

    @patch("monitoring.mt5_clock_monitor.get_logger")
    def test_tick_processor_integration(self, mock_get_logger):
        """Test integration with TickProcessor pattern"""
        mock_logger = Mock()
        mock_logger.log_event = Mock()
        mock_get_logger.return_value = mock_logger

        # Initialize monitor
        mt5_monitor = MT5ClockMonitor(
            window_size=100,
            drift_threshold_seconds=1.0,
            enabled=True,
        )
        set_global_mt5_monitor(mt5_monitor)

        # Simulate tick processing pattern
        base_time = datetime.now(timezone.utc)
        receive_time = base_time

        # Simulate tick from MT5 (with timezone offset)
        tick_datetime_str = "2024-01-01 12:00:00.000"
        tick_datetime = datetime.fromisoformat(tick_datetime_str.replace(" ", "T"))
        tick_datetime = tick_datetime.replace(tzinfo=timezone.utc)

        # Track tick (as TickProcessor would)
        mt5_monitor.track_tick(
            tick_datetime=tick_datetime,
            receive_time=receive_time,
            symbol="USDJPY",
        )

        # Verify tracking worked
        drift_stats = mt5_monitor.get_drift_stats()
        self.assertEqual(drift_stats["sample_count"], 1)

    def test_alert_cooldown_integration(self):
        """Test alert cooldown prevents spam"""
        mt5_monitor = MT5ClockMonitor(
            window_size=100,
            drift_threshold_seconds=1.0,
            alert_cooldown_minutes=5,
            enabled=True,
        )

        base_time = datetime.now(timezone.utc)

        # Add ticks with large drift
        for i in range(100):
            tick_time = base_time + timedelta(seconds=2.0)  # 2.0s drift
            receive_time = base_time
            mt5_monitor.track_tick(tick_time, receive_time, "USDJPY")

        # First batch should trigger alert
        alert_count_1 = mt5_monitor._alert_count

        # Add more ticks immediately (should not trigger alert due to cooldown)
        for i in range(100):
            tick_time = base_time + timedelta(seconds=2.0)
            receive_time = base_time
            mt5_monitor.track_tick(tick_time, receive_time, "USDJPY")

        # Alert count should not increase (cooldown active)
        alert_count_2 = mt5_monitor._alert_count
        self.assertEqual(alert_count_1, alert_count_2)

    def test_status_aggregation(self):
        """Test status aggregation for health check"""
        server_monitor = ClockSyncMonitor(
            check_interval_seconds=60,
            drift_threshold_seconds=1.0,
            enabled=False,
        )
        set_global_monitor(server_monitor)

        mt5_monitor = MT5ClockMonitor(
            window_size=100,
            drift_threshold_seconds=1.0,
            enabled=True,
        )
        set_global_mt5_monitor(mt5_monitor)

        # Simulate ticks
        base_time = datetime.now(timezone.utc)
        for i in range(10):
            tick_time = base_time + timedelta(seconds=0.1)
            receive_time = base_time
            mt5_monitor.track_tick(tick_time, receive_time, "USDJPY")

        # Build health check response (simulating http_controller)
        server_status = server_monitor.get_status()
        mt5_status = mt5_monitor.get_status()

        # Aggregate status
        server_healthy = server_monitor.is_healthy()
        mt5_healthy = mt5_monitor.is_healthy()
        overall_healthy = server_healthy and mt5_healthy

        # Verify aggregation
        self.assertIsInstance(overall_healthy, bool)
        self.assertIn("status", mt5_status)
        self.assertIn("drift_stats", mt5_status)
        self.assertIn("negative_latency_stats", mt5_status)


if __name__ == "__main__":
    unittest.main()
