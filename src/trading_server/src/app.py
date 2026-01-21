#!/usr/bin/env python3

import os
import warnings
import argparse
import signal
import sys
import threading
import time
from datetime import datetime
from dotenv import load_dotenv
import logging
from server import Server
from database import Database
from web_scraper.web_scraper_myfxbook import WebScraperMyfxbook
from monitoring.mt5_clock_monitor import MT5ClockMonitor, set_global_mt5_monitor
from monitoring.clock_sync_monitor import ClockSyncMonitor, set_global_monitor
from monitoring.gap_detector import GapDetector


# Suppress TensorFlow informational warnings about CUDA/GPU
os.environ.setdefault(
    "TF_CPP_MIN_LOG_LEVEL", "2"
)  # 0=all, 1=info, 2=warnings, 3=errors

# Suppress NumPy FutureWarning about np.object deprecation
warnings.filterwarnings("ignore", category=FutureWarning, message=".*np.object.*")

# Suppress urllib3 connection retry warnings for MLflow (will be handled gracefully)
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)

# Global shutdown event for coordination
_shutdown_event = None


def parse_arguments():
    """
    Parse the arguments form terminal
    """
    parser = argparse.ArgumentParser(
        description=(
            "The Alchemist Trading Server - AI Trading Server for real-time "
            "data streaming, DRL model training, and automated trading operations"
        ),
        epilog=f"{datetime.now().year}, Alchemist Capital",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Activate the verbose mode on the server",
    )
    args = parser.parse_args()
    return args


def create_composition_root(verbose: bool = False):
    """
    Create composition root - wire all dependencies
    :param verbose: Enable verbose logging
    :return: Tuple of (Server instance, ClockSyncMonitor, GapDetector)
    """
    # Create shared dependencies
    database = Database()
    scraper = WebScraperMyfxbook(
        email=os.getenv("MYFXBOOK_EMAIL"),
        password=os.getenv("MYFXBOOK_PASSWORD"),
        url=os.getenv("URL_MYFXBOOK"),
    )

    server = Server(verbose=verbose, database=database, scraper=scraper)

    clock_monitor = None
    gap_detector = None
    mt5_monitor = None

    # Start clock sync monitor
    try:
        clock_monitor = ClockSyncMonitor(
            check_interval_seconds=int(os.getenv("CLOCK_SYNC_CHECK_INTERVAL", "300")),
            drift_threshold_seconds=float(
                os.getenv("CLOCK_SYNC_DRIFT_THRESHOLD", "1.0")
            ),
            enabled=os.getenv("CLOCK_SYNC_MONITOR_ENABLED", "true").lower() == "true",
        )
        clock_monitor.start()
        # Register as global monitor for HTTP endpoint access
        set_global_monitor(clock_monitor)
        if verbose:
            print("Clock sync monitor started")
    except Exception as e:
        if verbose:
            print(f"Warning: Could not start clock sync monitor: {e}")

    # Start gap detector
    try:
        gap_detector = GapDetector(
            gap_threshold_minutes=float(os.getenv("GAP_THRESHOLD_MINUTES", "5.0")),
            check_interval_minutes=float(
                os.getenv("GAP_CHECK_INTERVAL_MINUTES", "5.0")
            ),
            lookback_minutes=float(os.getenv("GAP_LOOKBACK_MINUTES", "10.0")),
            enabled=os.getenv("GAP_DETECTOR_ENABLED", "true").lower() == "true",
        )
        gap_detector.start()
        if verbose:
            print("Gap detector started")
    except Exception as e:
        if verbose:
            print(f"Warning: Could not start gap detector: {e}")

    # Start MT5 clock monitor
    try:
        mt5_monitor = MT5ClockMonitor(
            window_size=int(os.getenv("MT5_CLOCK_WINDOW_SIZE", "1000")),
            drift_threshold_seconds=float(
                os.getenv("MT5_CLOCK_DRIFT_THRESHOLD", "1.0")
            ),
            alert_cooldown_minutes=int(
                os.getenv("MT5_CLOCK_ALERT_COOLDOWN_MINUTES", "5")
            ),
            negative_latency_warning_threshold=float(
                os.getenv("NEGATIVE_LATENCY_WARNING_THRESHOLD", "0.1")
            ),
            negative_latency_critical_threshold=float(
                os.getenv("NEGATIVE_LATENCY_CRITICAL_THRESHOLD", "0.2")
            ),
            enabled=os.getenv("MT5_CLOCK_MONITOR_ENABLED", "true").lower() == "true",
        )
        # Register as global monitor for HTTP endpoint access
        set_global_mt5_monitor(mt5_monitor)
        if verbose:
            print("MT5 clock monitor initialized")
    except Exception as e:
        if verbose:
            print(f"Warning: Could not initialize MT5 clock monitor: {e}")

    return server, clock_monitor, gap_detector, mt5_monitor


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global _shutdown_event
    if _shutdown_event:
        _shutdown_event.set()
    print(f"\nReceived signal {signum}, shutting down gracefully...")
    sys.exit(0)


def start():
    """Start the program"""
    global _shutdown_event

    args = parse_arguments()
    load_dotenv()

    # Create shutdown event for coordination
    _shutdown_event = threading.Event()

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize server and monitoring components
    server, clock_monitor, gap_detector, mt5_monitor = create_composition_root(verbose=args.verbose)

    if args.verbose:
        print("Trading server initialized and running. Press Ctrl+C to stop.")

    # Keep the main thread alive
    try:
        while not _shutdown_event.is_set():
            _shutdown_event.wait(timeout=1.0)
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)
    finally:
        # Cleanup on shutdown
        if clock_monitor:
            try:
                clock_monitor.stop()
            except Exception:
                pass
        if gap_detector:
            try:
                gap_detector.stop()
            except Exception:
                pass
        if args.verbose:
            print("Trading server stopped.")


if __name__ == "__main__":
    start()
