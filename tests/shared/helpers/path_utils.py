"""Centralized path utilities for tests"""
import sys
from pathlib import Path


def setup_api_path():
    """Add API source to Python path"""
    project_root = Path(__file__).parent.parent.parent.parent
    api_src = project_root / "src" / "backend" / "api" / "src"
    if str(api_src) not in sys.path:
        sys.path.insert(0, str(api_src))


def setup_trading_server_path():
    """Add Trading Server source to Python path"""
    project_root = Path(__file__).parent.parent.parent.parent
    server_src = project_root / "src" / "backend" / "trading_server" / "src"
    if str(server_src) not in sys.path:
        sys.path.insert(0, str(server_src))
