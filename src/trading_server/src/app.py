#!/usr/bin/env python3

import os
import warnings
import argparse
from datetime import datetime
from dotenv import load_dotenv
import logging
from server import Server
from database import Database
from web_scraper.web_scraper_myfxbook import WebScraperMyfxbook

# Suppress TensorFlow informational warnings about CUDA/GPU
os.environ.setdefault(
    "TF_CPP_MIN_LOG_LEVEL", "2"
)  # 0=all, 1=info, 2=warnings, 3=errors

# Suppress NumPy FutureWarning about np.object deprecation
warnings.filterwarnings("ignore", category=FutureWarning, message=".*np.object.*")

# Suppress urllib3 connection retry warnings for MLflow (will be handled gracefully)
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)


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
    :return: Configured Server instance
    """
    # Create shared dependencies
    database = Database()
    scraper = WebScraperMyfxbook(
        email=os.getenv("MYFXBOOK_EMAIL"),
        password=os.getenv("MYFXBOOK_PASSWORD"),
        url=os.getenv("URL_MYFXBOOK"),
    )

    server = Server(verbose=verbose, database=database, scraper=scraper)

    # Start clock sync monitor
    try:
        from monitoring.clock_sync_monitor import ClockSyncMonitor
        clock_monitor = ClockSyncMonitor(
            check_interval_seconds=int(os.getenv("CLOCK_SYNC_CHECK_INTERVAL", "300")),
            drift_threshold_seconds=float(os.getenv("CLOCK_SYNC_DRIFT_THRESHOLD", "1.0")),
            enabled=os.getenv("CLOCK_SYNC_MONITOR_ENABLED", "true").lower() == "true",
        )
        clock_monitor.start()
        if verbose:
            print("Clock sync monitor started")
    except Exception as e:
        if verbose:
            print(f"Warning: Could not start clock sync monitor: {e}")

    # Start gap detector
    try:
        from monitoring.gap_detector import GapDetector
        gap_detector = GapDetector(
            gap_threshold_minutes=float(os.getenv("GAP_THRESHOLD_MINUTES", "5.0")),
            check_interval_minutes=float(os.getenv("GAP_CHECK_INTERVAL_MINUTES", "5.0")),
            lookback_minutes=float(os.getenv("GAP_LOOKBACK_MINUTES", "10.0")),
            enabled=os.getenv("GAP_DETECTOR_ENABLED", "true").lower() == "true",
        )
        gap_detector.start()
        if verbose:
            print("Gap detector started")
    except Exception as e:
        if verbose:
            print(f"Warning: Could not start gap detector: {e}")

    return server


def start():
    """Start the program"""
    args = parse_arguments()
    load_dotenv()
    create_composition_root(verbose=args.verbose)


if __name__ == "__main__":
    start()
