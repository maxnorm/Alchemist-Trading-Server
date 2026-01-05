#!/usr/bin/env python3

import os
import sys
import warnings
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Suppress TensorFlow informational warnings about CUDA/GPU
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")  # 0=all, 1=info, 2=warnings, 3=errors

# Suppress NumPy FutureWarning about np.object deprecation
warnings.filterwarnings("ignore", category=FutureWarning, message=".*np.object.*")

# Suppress urllib3 connection retry warnings for MLflow (will be handled gracefully)
import logging
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)

from server import Server
from database import Database
from web_scraper.web_scraper_myfxbook import WebScraperMyfxbook


def parse_arguments():
    """
    Parse the arguments form terminal
    """
    parser = argparse.ArgumentParser(
        description="The Alchemist Trading Server - AI Trading Server for real-time data streaming, DRL model training, and automated trading operations",
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

    return server


def start():
    """Start the program"""
    args = parse_arguments()
    load_dotenv()
    create_composition_root(verbose=args.verbose)


if __name__ == "__main__":
    start()
