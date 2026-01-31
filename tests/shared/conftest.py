"""
Shared pytest fixtures and configuration
"""
import pytest
from tests.shared.helpers.path_utils import setup_api_path, setup_trading_server_path


# Setup paths for both components
setup_api_path()
setup_trading_server_path()
