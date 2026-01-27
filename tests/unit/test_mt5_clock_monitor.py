"""
Unit tests for MT5ClockMonitor
"""

import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "backend" / "trading_server" / "src"))

from monitoring.mt5_clock_monitor import MT5ClockMonitor, get_global_mt5_monitor, set_global_mt5_monitor


class TestMT5ClockMonitor(unittest.TestCase):
    """Test MT5ClockMonitor functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.monitor = MT5ClockMonitor(
            window_size=100,
            drift_threshold_seconds=1.0,
            alert_cooldown_minutes=1,
            negative_latency_warning_threshold=0.1,
            negative_latency_critical_threshold=0.2,
            enabled=True,
        )

    def tearDown(self):
        """Clean up after tests"""
        self.monitor.reset_stats()

    def test_initialization(self):
        """Test monitor initialization"""
        self.assertTrue(self.monitor.enabled)
        self.assertEqual(self.monitor.window_size, 100)
        self.assertEqual(self.monitor.drift_threshold, 1.0)
        self.assertEqual(self.monitor.negative_latency_warning_threshold, 0.1)
        self.assertEqual(self.monitor.negative_latency_critical_threshold, 0.2)

    def test_track_tick_no_drift(self):
        """Test tracking tick with no drift"""
        tick_time = datetime.now(timezone.utc)
        receive_time = tick_time  # No drift

        self.monitor.track_tick(tick_time, receive_time, "USDJPY")

        drift_stats = self.monitor.get_drift_stats()
        self.assertEqual(drift_stats["sample_count"], 1)
        self.assertAlmostEqual(drift_stats["avg_drift_seconds"], 0.0, places=3)

    def test_track_tick_positive_drift(self):
        """Test tracking tick with positive drift (broker ahead)"""
        receive_time = datetime.now(timezone.utc)
        tick_time = receive_time + timedelta(seconds=0.5)  # Broker 0.5s ahead

        self.monitor.track_tick(tick_time, receive_time, "USDJPY")

        drift_stats = self.monitor.get_drift_stats()
        self.assertEqual(drift_stats["sample_count"], 1)
        self.assertAlmostEqual(drift_stats["avg_drift_seconds"], 0.5, places=3)

    def test_track_tick_negative_drift(self):
        """Test tracking tick with negative drift (broker behind)"""
        receive_time = datetime.now(timezone.utc)
        tick_time = receive_time - timedelta(seconds=0.3)  # Broker 0.3s behind

        self.monitor.track_tick(tick_time, receive_time, "USDJPY")

        drift_stats = self.monitor.get_drift_stats()
        self.assertEqual(drift_stats["sample_count"], 1)
        self.assertAlmostEqual(drift_stats["avg_drift_seconds"], -0.3, places=3)

        # Should count as negative latency
        negative_latency_stats = self.monitor.get_negative_latency_stats()
        self.assertEqual(negative_latency_stats["negative_latency_count"], 1)
        self.assertEqual(negative_latency_stats["total_tick_count"], 1)
        self.assertEqual(negative_latency_stats["negative_latency_rate"], 1.0)

    def test_rolling_window(self):
        """Test rolling window behavior"""
        base_time = datetime.now(timezone.utc)

        # Add 150 ticks (window_size is 100)
        for i in range(150):
            tick_time = base_time + timedelta(seconds=i * 0.01)
            receive_time = tick_time
            self.monitor.track_tick(tick_time, receive_time, "USDJPY")

        drift_stats = self.monitor.get_drift_stats()
        # Should only have last 100 ticks
        self.assertEqual(drift_stats["sample_count"], 100)

    def test_drift_statistics(self):
        """Test drift statistics calculation"""
        base_time = datetime.now(timezone.utc)

        # Add ticks with varying drift
        drifts = [-0.1, -0.05, 0.0, 0.05, 0.1]
        for drift in drifts:
            tick_time = base_time + timedelta(seconds=drift)
            receive_time = base_time
            self.monitor.track_tick(tick_time, receive_time, "USDJPY")

        drift_stats = self.monitor.get_drift_stats()
        self.assertEqual(drift_stats["sample_count"], 5)
        self.assertAlmostEqual(drift_stats["avg_drift_seconds"], 0.0, places=3)
        self.assertAlmostEqual(drift_stats["min_drift_seconds"], -0.1, places=3)
        self.assertAlmostEqual(drift_stats["max_drift_seconds"], 0.1, places=3)
        self.assertAlmostEqual(drift_stats["median_drift_seconds"], 0.0, places=3)

    def test_negative_latency_rate(self):
        """Test negative latency rate calculation"""
        base_time = datetime.now(timezone.utc)

        # Add 10 ticks: 3 with negative latency, 7 without
        for i in range(10):
            if i < 3:
                # Negative latency (broker behind)
                tick_time = base_time - timedelta(seconds=0.1)
            else:
                # No negative latency
                tick_time = base_time + timedelta(seconds=0.1)
            receive_time = base_time
            self.monitor.track_tick(tick_time, receive_time, "USDJPY")

        negative_latency_stats = self.monitor.get_negative_latency_stats()
        self.assertEqual(negative_latency_stats["negative_latency_count"], 3)
        self.assertEqual(negative_latency_stats["total_tick_count"], 10)
        self.assertAlmostEqual(negative_latency_stats["negative_latency_rate"], 0.3, places=1)

    def test_is_healthy(self):
        """Test health check"""
        base_time = datetime.now(timezone.utc)

        # Add ticks with small drift (< threshold)
        for i in range(10):
            tick_time = base_time + timedelta(seconds=0.5)  # 0.5s drift
            receive_time = base_time
            self.monitor.track_tick(tick_time, receive_time, "USDJPY")

        # Should be healthy (drift < 1.0s threshold)
        self.assertTrue(self.monitor.is_healthy())

        # Add ticks with large drift (> threshold)
        for i in range(100):
            tick_time = base_time + timedelta(seconds=2.0)  # 2.0s drift
            receive_time = base_time
            self.monitor.track_tick(tick_time, receive_time, "USDJPY")

        # Should be unhealthy (drift > 1.0s threshold)
        self.assertFalse(self.monitor.is_healthy())

    def test_is_healthy_negative_latency(self):
        """Test health check with high negative latency rate"""
        base_time = datetime.now(timezone.utc)

        # Add ticks with high negative latency rate (> 20%)
        for i in range(100):
            if i < 25:  # 25% negative latency
                tick_time = base_time - timedelta(seconds=0.1)
            else:
                tick_time = base_time + timedelta(seconds=0.1)
            receive_time = base_time
            self.monitor.track_tick(tick_time, receive_time, "USDJPY")

        # Should be unhealthy (negative latency rate > 20%)
        self.assertFalse(self.monitor.is_healthy())

    def test_get_status(self):
        """Test status reporting"""
        base_time = datetime.now(timezone.utc)

        # Add some ticks
        for i in range(10):
            tick_time = base_time + timedelta(seconds=0.1)
            receive_time = base_time
            self.monitor.track_tick(tick_time, receive_time, "USDJPY")

        status = self.monitor.get_status()
        self.assertTrue(status["enabled"])
        self.assertEqual(status["status"], "ok")
        self.assertIn("drift_stats", status)
        self.assertIn("negative_latency_stats", status)
        self.assertEqual(status["drift_stats"]["sample_count"], 10)

    def test_reset_stats(self):
        """Test statistics reset"""
        base_time = datetime.now(timezone.utc)

        # Add some ticks
        for i in range(10):
            tick_time = base_time + timedelta(seconds=0.1)
            receive_time = base_time
            self.monitor.track_tick(tick_time, receive_time, "USDJPY")

        # Reset stats
        self.monitor.reset_stats()

        drift_stats = self.monitor.get_drift_stats()
        self.assertEqual(drift_stats["sample_count"], 0)

        negative_latency_stats = self.monitor.get_negative_latency_stats()
        self.assertEqual(negative_latency_stats["negative_latency_count"], 0)
        self.assertEqual(negative_latency_stats["total_tick_count"], 0)

    def test_timezone_handling(self):
        """Test timezone-aware datetime handling"""
        # Test with timezone-naive datetime (should be converted to UTC)
        tick_time_naive = datetime.now()
        receive_time_naive = datetime.now()

        self.monitor.track_tick(tick_time_naive, receive_time_naive, "USDJPY")

        # Should not raise exception
        drift_stats = self.monitor.get_drift_stats()
        self.assertIsNotNone(drift_stats)

    def test_disabled_monitor(self):
        """Test disabled monitor doesn't track"""
        monitor = MT5ClockMonitor(enabled=False)
        base_time = datetime.now(timezone.utc)

        monitor.track_tick(base_time, base_time, "USDJPY")

        drift_stats = monitor.get_drift_stats()
        self.assertEqual(drift_stats["sample_count"], 0)

    @patch("monitoring.mt5_clock_monitor.get_logger")
    def test_alert_drift(self, mock_get_logger):
        """Test drift alerting"""
        mock_logger = Mock()
        mock_logger.log_event = Mock()
        mock_get_logger.return_value = mock_logger

        monitor = MT5ClockMonitor(
            window_size=100,
            drift_threshold_seconds=1.0,
            alert_cooldown_minutes=0,  # No cooldown for testing
            enabled=True,
        )

        base_time = datetime.now(timezone.utc)

        # Add ticks with large drift (> threshold)
        for i in range(100):
            tick_time = base_time + timedelta(seconds=2.0)  # 2.0s drift
            receive_time = base_time
            monitor.track_tick(tick_time, receive_time, "USDJPY")

        # Should have triggered alert
        # Note: Alert is triggered internally, we just verify no exception

    @patch("monitoring.mt5_clock_monitor.get_logger")
    def test_alert_negative_latency(self, mock_get_logger):
        """Test negative latency alerting"""
        mock_logger = Mock()
        mock_logger.log_event = Mock()
        mock_get_logger.return_value = mock_logger

        monitor = MT5ClockMonitor(
            window_size=100,
            negative_latency_warning_threshold=0.1,
            negative_latency_critical_threshold=0.2,
            alert_cooldown_minutes=0,  # No cooldown for testing
            enabled=True,
        )

        base_time = datetime.now(timezone.utc)

        # Add ticks with high negative latency rate (> 20%)
        for i in range(100):
            if i < 25:  # 25% negative latency
                tick_time = base_time - timedelta(seconds=0.1)
            else:
                tick_time = base_time + timedelta(seconds=0.1)
            receive_time = base_time
            monitor.track_tick(tick_time, receive_time, "USDJPY")

        # Should have triggered alert
        # Note: Alert is triggered internally, we just verify no exception


class TestGlobalMT5Monitor(unittest.TestCase):
    """Test global MT5 monitor access"""

    def setUp(self):
        """Set up test fixtures"""
        # Clear global monitor
        set_global_mt5_monitor(None)

    def tearDown(self):
        """Clean up after tests"""
        # Clear global monitor
        set_global_mt5_monitor(None)

    def test_get_global_monitor_none(self):
        """Test getting global monitor when not set"""
        monitor = get_global_mt5_monitor()
        self.assertIsNone(monitor)

    def test_set_get_global_monitor(self):
        """Test setting and getting global monitor"""
        monitor = MT5ClockMonitor()
        set_global_mt5_monitor(monitor)

        retrieved = get_global_mt5_monitor()
        self.assertIs(retrieved, monitor)

    def test_replace_global_monitor(self):
        """Test replacing global monitor"""
        monitor1 = MT5ClockMonitor()
        monitor2 = MT5ClockMonitor()

        set_global_mt5_monitor(monitor1)
        self.assertIs(get_global_mt5_monitor(), monitor1)

        set_global_mt5_monitor(monitor2)
        self.assertIs(get_global_mt5_monitor(), monitor2)


if __name__ == "__main__":
    unittest.main()
