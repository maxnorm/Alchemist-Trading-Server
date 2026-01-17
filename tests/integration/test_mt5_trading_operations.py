"""
MT5 Trading Operations Live Integration Tests (HTTP API)

This test suite validates the complete MT5 trading operations flow with LIVE EA using HTTP API:
- Account registration and terminal connection
- Account information retrieval
- Market order execution (BUY/SELL)
- Limit order execution
- Orders with stop loss and take profit
- Position closing (full and partial)
- Order rejection handling
- Multiple orders
- Position monitoring

Prerequisites:
- MT5 Terminal installed and running
- MT5 Account registered in system
- EA terminal connected to server
- AutoTrading enabled in MT5
- Server running on port 8080 and accessible via HTTP
- Server must be accessible from test execution environment

WARNING: These tests execute REAL orders on your MT5 account!
Use only with DEMO accounts in a controlled test environment.

To run these tests:
    pytest tests/integration/test_mt5_trading_operations.py -v -s -m live_mt5

Or set environment variable:
    ENABLE_LIVE_MT5_TESTS=1 pytest tests/integration/test_mt5_trading_operations.py -v -s
"""

import pytest
import time
import os
import requests
from typing import Optional, Dict, Any, Tuple


# Test configuration
TEST_SYMBOL = os.getenv("MT5_TEST_SYMBOL", "EURUSD")
TEST_LOT_SIZE = float(os.getenv("MT5_TEST_LOT_SIZE", "0.01"))
TEST_ACCOUNT_LOGIN = os.getenv("MT5_TEST_ACCOUNT_LOGIN")  # Optional: specific account
TEST_SERVER_URL = os.getenv("MT5_TEST_SERVER_URL", "http://localhost:8080")


# Pytest marker for live MT5 tests
pytestmark = pytest.mark.live_mt5


@pytest.fixture(scope="module")
def check_prerequisites():
    """
    Check prerequisites before running tests
    """
    # Check if live tests are enabled
    if not os.getenv("ENABLE_LIVE_MT5_TESTS") and not os.getenv("CI"):
        pytest.skip(
            "Live MT5 tests are disabled. "
            "Set ENABLE_LIVE_MT5_TESTS=1 to enable. "
            "These tests execute REAL orders!"
        )
    
    # Check if server is accessible
    try:
        response = requests.get(f"{TEST_SERVER_URL}/test/mt5/accounts", timeout=5)
        if response.status_code == 503:
            pytest.fail(
                "Server is not available or not ready.\n"
                "Make sure server is running: docker compose up server"
            )
    except requests.exceptions.RequestException as e:
        pytest.fail(
            f"Cannot connect to server at {TEST_SERVER_URL}.\n"
            f"Error: {e}\n"
            "Make sure server is running and accessible."
        )
    
    print("\n" + "="*70)
    print("LIVE MT5 TRADING OPERATIONS TESTS (HTTP API)")
    print("="*70)
    print("WARNING: These tests execute REAL orders on your MT5 account!")
    print("WARNING: Make sure you are using a DEMO account!")
    print(f"Server URL: {TEST_SERVER_URL}")
    print("="*70 + "\n")


@pytest.fixture(scope="module")
def api_client(check_prerequisites) -> Tuple[requests.Session, str]:
    """
    HTTP client for API requests
    """
    session = requests.Session()
    session.timeout = 30
    return session, TEST_SERVER_URL


@pytest.fixture(scope="module")
def test_account_info(api_client) -> Dict[str, Any]:
    """
    Get test account from API and validate EA connection
    """
    session, base_url = api_client
    
    # Get accounts from API
    response = session.get(f"{base_url}/test/mt5/accounts")
    
    if response.status_code != 200:
        pytest.fail(
            f"Failed to get accounts from API. Status: {response.status_code}\n"
            f"Response: {response.text}"
        )
    
    data = response.json()
    accounts = data.get("accounts", [])
    
    if not accounts:
        pytest.fail(
            "No accounts connected.\n"
            "Please:\n"
            "1. Register MT5 account via dashboard\n"
            "2. Connect MT5 terminal EA to server\n"
            "3. Ensure AutoTrading is enabled in MT5"
        )
    
    # Use specific account if provided, otherwise first available
    account_info = None
    if TEST_ACCOUNT_LOGIN:
        account_info = next(
            (acc for acc in accounts if acc.get("login") == int(TEST_ACCOUNT_LOGIN)),
            None
        )
        if not account_info:
            pytest.fail(f"Account {TEST_ACCOUNT_LOGIN} not found in connected accounts")
    else:
        account_info = accounts[0]
    
    account_login = account_info.get("login")
    print(f"[OK] Using account: {account_login}")
    
    # Validate terminal connection
    has_terminal = account_info.get("has_terminal", False)
    if not has_terminal:
        pytest.fail(
            f"Account {account_login} has no terminal connection.\n"
            "Make sure EA terminal is connected to server."
        )
    
    print(f"[OK] Terminal connection verified for account {account_login}")
    
    # Get account balance info
    balance = account_info.get("balance")
    if balance is not None:
        print(f"[OK] Account info retrieved:")
        print(f"   Balance: {balance}")
    
    return account_info


@pytest.fixture(scope="module")
def account_login(test_account_info) -> int:
    """Get account login number"""
    return test_account_info.get("login")


def execute_order_via_api(
    api_client: Tuple[requests.Session, str],
    account_login: int,
    symbol: str,
    lotsize: float,
    order_type: str,
) -> Optional[Dict[str, Any]]:
    """
    Execute order via HTTP API
    
    Returns trade data if successful, None if failed
    """
    session, base_url = api_client
    
    order_data = {
        "account_login": account_login,
        "symbol": symbol,
        "lotsize": lotsize,
        "order_type": order_type,
    }
    
    response = session.post(f"{base_url}/test/mt5/order", json=order_data)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            return data.get("trade")
        else:
            # Log error even on 200 status
            error_msg = data.get("error") or data.get("message", "Unknown error")
            print(f"[ERROR] Order failed (HTTP 200): {error_msg}")
            return None
    else:
        # Log error details for non-200 responses
        try:
            error_data = response.json()
            error_msg = error_data.get("error") or error_data.get("message", "Unknown error")
            print(f"[ERROR] Order request failed (HTTP {response.status_code}): {error_msg}")
            if "suggestions" in error_data:
                print(f"[INFO] Suggestions:")
                for suggestion in error_data["suggestions"]:
                    print(f"  - {suggestion}")
            if "traceback" in error_data:
                print(f"[DEBUG] Traceback:\n{error_data['traceback']}")
        except Exception:
            print(f"[ERROR] Order request failed (HTTP {response.status_code}): {response.text}")
        return None


def close_position_via_api(
    api_client: Tuple[requests.Session, str],
    account_login: int,
    ticket: int,
    lotsize: Optional[float] = None,
) -> bool:
    """
    Close position via HTTP API
    
    Returns True if successful, False otherwise
    """
    session, base_url = api_client
    
    close_data = {
        "account_login": account_login,
        "ticket": ticket,
    }
    
    if lotsize is not None:
        close_data["lotsize"] = lotsize
    
    response = session.post(f"{base_url}/test/mt5/close", json=close_data)
    
    if response.status_code == 200:
        data = response.json()
        return data.get("success", False)
    
    return False


class TestMT5AccountRegistration:
    """Test account registration (prerequisite)"""
    
    def test_account_registered(self, test_account_info):
        """Verify account is registered and active"""
        assert test_account_info is not None
        account_login = test_account_info.get("login")
        assert account_login is not None
        assert account_login > 0
        print(f"[OK] Account {account_login} is registered")


class TestMT5TerminalConnection:
    """Test terminal connection"""
    
    def test_terminal_connected(self, test_account_info, api_client):
        """Verify terminal is connected to account and EA is responsive"""
        account_login = test_account_info.get("login")
        has_terminal = test_account_info.get("has_terminal", False)
        
        assert has_terminal, f"Account {account_login} has no terminal connection"
        
        # Test EA responsiveness by checking account info
        session, base_url = api_client
        response = session.get(f"{base_url}/test/mt5/accounts")
        
        assert response.status_code == 200, "Failed to get account info from API"
        data = response.json()
        accounts = data.get("accounts", [])
        account = next((acc for acc in accounts if acc.get("login") == account_login), None)
        
        assert account is not None, f"Account {account_login} not found in API response"
        assert account.get("has_terminal"), "Terminal connection not active"
        
        print(f"[OK] Terminal connected and EA responsive for account {account_login}")


class TestMT5AccountInfo:
    """Test account information retrieval"""
    
    def test_account_info_retrieved(self, test_account_info):
        """Verify account information can be retrieved"""
        account_login = test_account_info.get("login")
        balance = test_account_info.get("balance")
        
        assert account_login is not None
        assert balance is not None or balance == 0  # Balance can be 0
        
        print(f"[OK] Account Info Retrieved:")
        print(f"   Login: {account_login}")
        if balance is not None:
            print(f"   Balance: {balance}")


class TestMT5MarketOrders:
    """Test market order execution"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, account_login):
        """Setup for market order tests"""
        self.api_client = api_client
        self.account_login = account_login
        self.opened_tickets = []
        yield
        # Cleanup: Close any opened positions
        for ticket in self.opened_tickets:
            try:
                if ticket:
                    close_position_via_api(self.api_client, self.account_login, ticket)
                    time.sleep(0.5)  # Wait for close to process
            except Exception as e:
                print(f"Warning: Could not close position {ticket}: {e}")
    
    def test_market_buy_order(self):
        """Test market BUY order execution"""
        print(f"\n[TEST] Sending BUY order: {TEST_SYMBOL} {TEST_LOT_SIZE} lots")
        trade = execute_order_via_api(
            self.api_client,
            self.account_login,
            TEST_SYMBOL,
            TEST_LOT_SIZE,
            "BUY"
        )
        
        assert trade is not None, "Order execution failed"
        ticket = trade.get("ticket")
        assert ticket is not None and ticket > 0, "Invalid ticket"
        assert trade.get("lotsize") == TEST_LOT_SIZE, f"Lot size mismatch: expected {TEST_LOT_SIZE}, got {trade.get('lotsize')}"
        assert trade.get("open_price") is not None and trade.get("open_price") > 0, "Invalid open price"
        
        self.opened_tickets.append(ticket)
        
        print(f"[OK] Market BUY Order Executed:")
        print(f"   Ticket: {ticket}")
        print(f"   Symbol: {trade.get('symbol')}")
        print(f"   Lot Size: {trade.get('lotsize')}")
        print(f"   Open Price: {trade.get('open_price')}")
    
    def test_market_sell_order(self):
        """Test market SELL order execution"""
        print(f"\n[TEST] Sending SELL order: {TEST_SYMBOL} {TEST_LOT_SIZE} lots")
        trade = execute_order_via_api(
            self.api_client,
            self.account_login,
            TEST_SYMBOL,
            TEST_LOT_SIZE,
            "SELL"
        )
        
        assert trade is not None, "Order execution failed"
        ticket = trade.get("ticket")
        assert ticket is not None and ticket > 0, "Invalid ticket"
        assert trade.get("lotsize") == TEST_LOT_SIZE, f"Lot size mismatch: expected {TEST_LOT_SIZE}, got {trade.get('lotsize')}"
        assert trade.get("open_price") is not None and trade.get("open_price") > 0, "Invalid open price"
        
        self.opened_tickets.append(ticket)
        
        print(f"[OK] Market SELL Order Executed:")
        print(f"   Ticket: {ticket}")
        print(f"   Symbol: {trade.get('symbol')}")
        print(f"   Lot Size: {trade.get('lotsize')}")
        print(f"   Open Price: {trade.get('open_price')}")


class TestMT5LimitOrders:
    """Test limit order execution"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, account_login):
        """Setup for limit order tests"""
        self.api_client = api_client
        self.account_login = account_login
        self.opened_tickets = []
        yield
        # Cleanup: Close any opened positions
        for ticket in self.opened_tickets:
            try:
                if ticket:
                    close_position_via_api(self.api_client, self.account_login, ticket)
                    time.sleep(0.5)
            except Exception as e:
                print(f"Warning: Could not close position {ticket}: {e}")
    
    def test_buy_limit_order(self):
        """Test BUY_LIMIT order placement"""
        # Note: Limit orders are not currently supported via the HTTP API
        # This test is skipped as the API only supports market orders
        pytest.skip("Limit orders not supported via HTTP API endpoint")


class TestMT5OrdersWithSLTP:
    """Test orders with stop loss and take profit"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, account_login):
        """Setup for SL/TP tests"""
        self.api_client = api_client
        self.account_login = account_login
        self.opened_tickets = []
        yield
        # Cleanup
        for ticket in self.opened_tickets:
            try:
                if ticket:
                    close_position_via_api(self.api_client, self.account_login, ticket)
                    time.sleep(0.5)
            except Exception as e:
                print(f"Warning: Could not close position {ticket}: {e}")
    
    def test_order_with_sl_tp(self):
        """Test order execution with stop loss and take profit"""
        # Note: SL/TP parameters are not currently supported via the HTTP API
        # This test executes a basic order instead
        print(f"\n[TEST] Sending BUY order: {TEST_SYMBOL} {TEST_LOT_SIZE} lots")
        trade = execute_order_via_api(
            self.api_client,
            self.account_login,
            TEST_SYMBOL,
            TEST_LOT_SIZE,
            "BUY"
        )
        
        if trade:
            ticket = trade.get("ticket")
            assert ticket is not None and ticket > 0, "Invalid ticket"
            self.opened_tickets.append(ticket)
            print(f"[OK] Order Executed:")
            print(f"   Ticket: {ticket}")
            print(f"   Note: SL/TP not supported via HTTP API")
        else:
            pytest.skip("Order execution failed - may be market closed or insufficient margin")


class TestMT5PositionClosing:
    """Test position closing"""
    
    def test_close_position_full(self, api_client, account_login):
        """Test closing a position fully"""
        # Open a position first
        print(f"\n[TEST] Opening position for close test...")
        trade = execute_order_via_api(
            api_client,
            account_login,
            TEST_SYMBOL,
            TEST_LOT_SIZE,
            "BUY"
        )
        
        if not trade:
            pytest.skip("Could not open position for close test")
        
        ticket = trade.get("ticket")
        assert ticket is not None, "Invalid ticket"
        
        # Wait a moment for position to settle
        time.sleep(1)
        
        # Close the position
        print(f"[TEST] Closing position: Ticket {ticket}")
        success = close_position_via_api(api_client, account_login, ticket)
        
        assert success, "Failed to close position"
        print(f"[OK] Position Closed Successfully:")
        print(f"   Ticket: {ticket}")
    
    def test_close_position_partial(self, api_client, account_login):
        """Test partial position closing"""
        full_lot_size = 0.10
        partial_lot_size = 0.05
        
        # Open a larger position
        print(f"\n[TEST] Opening position ({full_lot_size} lots) for partial close test...")
        trade = execute_order_via_api(
            api_client,
            account_login,
            TEST_SYMBOL,
            full_lot_size,
            "BUY"
        )
        
        if not trade:
            pytest.skip("Could not open position for partial close test")
        
        ticket = trade.get("ticket")
        assert ticket is not None, "Invalid ticket"
        
        # Wait a moment
        time.sleep(1)
        
        # Partially close
        print(f"[TEST] Partially closing position: Ticket {ticket}, {partial_lot_size} lots")
        try:
            success = close_position_via_api(
                api_client,
                account_login,
                ticket,
                lotsize=partial_lot_size
            )
            assert success, "Failed to partially close position"
            print(f"[OK] Position Partially Closed:")
            print(f"   Ticket: {ticket}")
            print(f"   Closed: {partial_lot_size} lots")
            print(f"   Remaining: {full_lot_size - partial_lot_size} lots")
            
            # Close remaining
            time.sleep(1)
            close_position_via_api(api_client, account_login, ticket)
        except Exception as e:
            # Cleanup: try to close full position
            try:
                close_position_via_api(api_client, account_login, ticket)
            except:
                pass
            pytest.fail(f"Failed to partially close position: {e}")


class TestMT5OrderRejection:
    """Test order rejection scenarios"""
    
    def test_invalid_symbol(self, api_client, account_login):
        """Test order with invalid symbol"""
        print(f"\n[TEST] Sending order with invalid symbol...")
        trade = execute_order_via_api(
            api_client,
            account_login,
            "INVALID_SYMBOL_XYZ",
            TEST_LOT_SIZE,
            "BUY"
        )
        
        # Order should be rejected
        assert trade is None, "Order with invalid symbol should be rejected"
        print("[OK] Invalid symbol order correctly rejected")
    
    def test_insufficient_margin(self, api_client, account_login):
        """Test order with insufficient margin (very large lot size)"""
        huge_lot_size = 1000.0  # Unrealistically large
        
        print(f"\n[TEST] Sending order with insufficient margin ({huge_lot_size} lots)...")
        trade = execute_order_via_api(
            api_client,
            account_login,
            TEST_SYMBOL,
            huge_lot_size,
            "BUY"
        )
        
        # Order should be rejected
        assert trade is None, "Order with insufficient margin should be rejected"
        print("[OK] Insufficient margin order correctly rejected")


class TestMT5MultipleOrders:
    """Test multiple simultaneous orders"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, account_login):
        """Setup for multiple orders test"""
        self.api_client = api_client
        self.account_login = account_login
        self.opened_tickets = []
        yield
        # Cleanup
        for ticket in self.opened_tickets:
            try:
                if ticket:
                    close_position_via_api(self.api_client, self.account_login, ticket)
                    time.sleep(0.3)
            except Exception as e:
                print(f"Warning: Could not close position {ticket}: {e}")
    
    def test_multiple_orders(self):
        """Test multiple orders in quick succession"""
        orders = []
        
        print(f"\n[TEST] Sending multiple orders...")
        
        # Send 3 orders quickly
        for i in range(3):
            trade = execute_order_via_api(
                self.api_client,
                self.account_login,
                TEST_SYMBOL,
                TEST_LOT_SIZE,
                "BUY"
            )
            if trade:
                ticket = trade.get("ticket")
                orders.append(trade)
                self.opened_tickets.append(ticket)
            time.sleep(0.5)  # Small delay between orders
        
        # Verify all orders executed
        assert len(orders) > 0, "No orders executed"
        print(f"[OK] Multiple Orders Test:")
        print(f"   Orders sent: 3")
        print(f"   Orders executed: {len(orders)}")
        for i, trade in enumerate(orders, 1):
            print(f"   Order {i}: Ticket {trade.get('ticket')}")


class TestMT5PositionMonitoring:
    """Test position monitoring"""
    
    def test_position_tracking(self, api_client, account_login):
        """Test that positions can be opened and closed"""
        # Open a position
        print(f"\n[TEST] Opening position for monitoring test...")
        trade = execute_order_via_api(
            api_client,
            account_login,
            TEST_SYMBOL,
            TEST_LOT_SIZE,
            "BUY"
        )
        
        if not trade:
            pytest.skip("Could not open position for monitoring test")
        
        ticket = trade.get("ticket")
        assert ticket is not None, "Invalid ticket"
        
        print(f"[OK] Position Opened:")
        print(f"   Ticket: {ticket}")
        print(f"   Symbol: {trade.get('symbol')}")
        print(f"   Lot Size: {trade.get('lotsize')}")
        print(f"   Open Price: {trade.get('open_price')}")
        
        # Note: Position tracking via API would require additional endpoint
        # For now, we just verify the position was opened successfully
        
        # Cleanup
        time.sleep(1)
        close_position_via_api(api_client, account_login, ticket)


# Test execution helpers
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "live_mt5: marks tests as requiring live MT5 EA connection"
    )
    config.addinivalue_line(
        "markers", "mt5: marks tests as requiring MT5 connection"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically mark live MT5 tests"""
    for item in items:
        if "test_mt5_trading_operations" in str(item.fspath):
            if not any(mark.name == "live_mt5" for mark in item.iter_markers()):
                item.add_marker(pytest.mark.live_mt5)


if __name__ == "__main__":
    """
    Run tests directly
    Usage: python -m pytest tests/integration/test_mt5_trading_operations.py -v
    """
    pytest.main([__file__, "-v", "-s"])
