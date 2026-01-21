#!/usr/bin/env python3
"""
Comprehensive ZeroMQ connection test script.
Tests all aspects of the ZeroMQ connection between server and MT5.

Usage:
    python scripts/test_zeromq_connection_comprehensive.py
    docker compose exec server python scripts/test_zeromq_connection_comprehensive.py
"""
import os
import sys
import time
import json
from typing import Dict, Optional
from datetime import datetime

import zmq
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "trading_server", "src"))

load_dotenv()


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


class ZeroMQConnectionTester:
    """Comprehensive ZeroMQ connection tester"""

    def __init__(self):
        self.host = os.getenv("ZMQ_HOST", "127.0.0.1")
        self.order_port = int(os.getenv("ZMQ_ORDER_PORT", 5556))
        self.tick_port = int(os.getenv("ZMQ_TICK_PORT", 5555))
        self.login = int(os.getenv("ZMQ_TEST_LOGIN", 0))
        self.auth_token = os.getenv("ZMQ_TEST_AUTH_TOKEN", "")
        self.symbol = os.getenv("ZMQ_TEST_SYMBOL", "EURUSD")
        self.digits = int(os.getenv("ZMQ_TEST_DIGITS", "5"))

        self.context = None
        self.req_socket = None
        self.sub_socket = None

        self.results = {
            "network_connectivity": False,
            "authentication": False,
            "account_info": False,
            "tick_streaming": False,
            "connection_health": False,
            "error_count": 0,
            "warnings": [],
            "errors": [],
        }

    def print_header(self, text: str):
        """Print formatted header"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}\n")

    def print_success(self, text: str):
        """Print success message"""
        print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")

    def print_error(self, text: str):
        """Print error message"""
        print(f"{Colors.RED}❌ {text}{Colors.RESET}")
        self.results["error_count"] += 1
        self.results["errors"].append(text)

    def print_warning(self, text: str):
        """Print warning message"""
        print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")
        self.results["warnings"].append(text)

    def print_info(self, text: str):
        """Print info message"""
        print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")

    def check_prerequisites(self) -> bool:
        """Check prerequisites before testing"""
        self.print_header("Prerequisites Check")

        if not self.login or not self.auth_token:
            self.print_error(
                "Missing ZMQ_TEST_LOGIN or ZMQ_TEST_AUTH_TOKEN in environment."
            )
            self.print_info("Please set these in your .env file:")
            self.print_info("  ZMQ_TEST_LOGIN=123456")
            self.print_info("  ZMQ_TEST_AUTH_TOKEN=your_token")
            return False

        self.print_success(f"Login: {self.login}")
        self.print_success(f"Host: {self.host}")
        self.print_success(f"Order Port: {self.order_port}")
        self.print_success(f"Tick Port: {self.tick_port}")
        self.print_success(f"Symbol: {self.symbol}")

        return True

    def test_network_connectivity(self) -> bool:
        """Test basic network connectivity"""
        self.print_header("Network Connectivity Test")

        try:
            self.print_info(f"Connecting to {self.host}:{self.order_port}...")
            self.context = zmq.Context()
            self.req_socket = self.context.socket(zmq.REQ)
            self.req_socket.setsockopt(zmq.RCVTIMEO, 5000)  # 5 second timeout
            self.req_socket.connect(f"tcp://{self.host}:{self.order_port}")

            self.print_success("Socket connected successfully")
            self.results["network_connectivity"] = True
            return True

        except Exception as e:
            self.print_error(f"Failed to connect: {e}")
            self.print_info("Troubleshooting:")
            self.print_info("  1. Verify MT5 EA is running and bound to port")
            self.print_info("  2. Check ZMQ_HOST is correct")
            self.print_info("  3. Verify Windows Firewall allows connections")
            self.print_info("  4. Check port is not in use by another process")
            return False

    def test_authentication(self) -> bool:
        """Test authentication"""
        self.print_header("Authentication Test")

        if not self.results["network_connectivity"]:
            self.print_error("Skipping authentication test (network connectivity failed)")
            return False

        try:
            auth_request = {
                "auth_code": 2,
                "login": self.login,
                "auth_token": self.auth_token,
            }

            self.print_info("Sending authentication request...")
            self.req_socket.send_string(json.dumps(auth_request))

            response_str = self.req_socket.recv_string()
            response = json.loads(response_str)

            self.print_info(f"Response: {json.dumps(response, indent=2)}")

            if response.get("auth_status") == 0:
                self.print_success("Authentication successful")
                terminal_id = response.get("terminal_id", "N/A")
                self.print_info(f"Terminal ID: {terminal_id}")
                self.results["authentication"] = True
                return True
            else:
                error_msg = response.get("comment", "Unknown error")
                self.print_error(f"Authentication failed: {error_msg}")
                self.print_info("Troubleshooting:")
                self.print_info("  1. Verify auth_token matches EA configuration")
                self.print_info("  2. Check account_login matches MT5 account")
                self.print_info("  3. Verify EA has correct auth_token input parameter")
                return False

        except zmq.Again:
            self.print_error("Timeout: EA did not respond within 5 seconds")
            self.print_info("Make sure EA is running and processing requests")
            return False
        except Exception as e:
            self.print_error(f"Authentication error: {e}")
            return False

    def test_account_info(self) -> bool:
        """Test account info request"""
        self.print_header("Account Info Test")

        if not self.results["authentication"]:
            self.print_error("Skipping account info test (authentication failed)")
            return False

        try:
            account_request = {"request": 100}  # ACCOUNT_INFO
            self.print_info("Requesting account information...")
            self.req_socket.send_string(json.dumps(account_request))

            response_str = self.req_socket.recv_string()
            response = json.loads(response_str)

            self.print_success("Account Info Retrieved:")
            print(f"  Currency: {response.get('currency', 'N/A')}")
            print(f"  Leverage: {response.get('leverage', 'N/A')}")
            print(f"  Balance: {response.get('balance', 'N/A')}")
            print(f"  Equity: {response.get('equity', 'N/A')}")
            print(f"  Profit: {response.get('profit', 'N/A')}")
            print(f"  Margin: {response.get('margin', 'N/A')}")
            print(f"  Free Margin: {response.get('margin_free', 'N/A')}")

            self.results["account_info"] = True
            return True

        except zmq.Again:
            self.print_error("Timeout: EA did not respond")
            return False
        except Exception as e:
            self.print_error(f"Account info error: {e}")
            return False

    def test_tick_streaming(self) -> bool:
        """Test tick streaming connection"""
        self.print_header("Tick Streaming Test")

        try:
            self.print_info(f"Connecting to streamer at {self.host}:{self.tick_port}...")
            self.sub_socket = self.context.socket(zmq.SUB)
            self.sub_socket.setsockopt(zmq.RCVTIMEO, 10000)  # 10 second timeout
            self.sub_socket.connect(f"tcp://{self.host}:{self.tick_port}")
            self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, self.symbol)

            self.print_info(f"Subscribed to {self.symbol}, waiting for ticks...")
            self.print_info("(This may take a few seconds if market is closed)")

            # Try to receive a tick
            start_time = time.time()
            timeout = 15  # 15 seconds

            while time.time() - start_time < timeout:
                try:
                    topic, message = self.sub_socket.recv_multipart(zmq.NOBLOCK)
                    tick_data = json.loads(message.decode())

                    self.print_success("Tick received!")
                    print(f"  Symbol: {tick_data.get('symbol', 'N/A')}")
                    print(f"  Bid: {tick_data.get('bid', 'N/A')}")
                    print(f"  Ask: {tick_data.get('ask', 'N/A')}")
                    print(f"  Time: {tick_data.get('datetime', 'N/A')}")

                    self.results["tick_streaming"] = True
                    return True

                except zmq.Again:
                    # No message yet, continue waiting
                    time.sleep(0.5)
                    continue

            self.print_warning("No ticks received within timeout period")
            self.print_info("This may be normal if:")
            self.print_info("  1. Market is closed")
            self.print_info("  2. Streamer EA is not running")
            self.print_info("  3. Symbol is not available")
            return False

        except Exception as e:
            self.print_error(f"Tick streaming error: {e}")
            self.print_info("Troubleshooting:")
            self.print_info("  1. Verify streamer EA is running")
            self.print_info("  2. Check symbol matches subscription")
            self.print_info("  3. Verify PUB socket is bound correctly")
            return False

    def test_connection_health(self) -> bool:
        """Test connection health with multiple pings"""
        self.print_header("Connection Health Test")

        if not self.results["authentication"]:
            self.print_error("Skipping health test (authentication failed)")
            return False

        try:
            self.print_info("Performing 3 ping tests...")
            success_count = 0
            total_latency = 0

            for i in range(3):
                ping_request = {"request": 100}  # ACCOUNT_INFO as ping
                start_time = time.time()

                self.req_socket.send_string(json.dumps(ping_request))
                response_str = self.req_socket.recv_string()
                response = json.loads(response_str)

                latency = (time.time() - start_time) * 1000  # Convert to ms
                total_latency += latency

                if response.get("currency"):
                    success_count += 1
                    self.print_success(f"Ping {i+1}: {latency:.2f}ms")
                else:
                    self.print_warning(f"Ping {i+1}: Unexpected response")

                time.sleep(0.5)  # Small delay between pings

            if success_count == 3:
                avg_latency = total_latency / 3
                self.print_success(f"All pings successful (avg latency: {avg_latency:.2f}ms)")
                self.results["connection_health"] = True
                return True
            else:
                self.print_warning(f"Only {success_count}/3 pings successful")
                return False

        except Exception as e:
            self.print_error(f"Health test error: {e}")
            return False

    def cleanup(self):
        """Clean up resources"""
        if self.req_socket:
            self.req_socket.close()
        if self.sub_socket:
            self.sub_socket.close()
        if self.context:
            self.context.term()

    def print_summary(self):
        """Print test summary"""
        self.print_header("Test Summary")

        total_tests = 5
        passed_tests = sum(
            [
                self.results["network_connectivity"],
                self.results["authentication"],
                self.results["account_info"],
                self.results["tick_streaming"],
                self.results["connection_health"],
            ]
        )

        print(f"Tests Passed: {passed_tests}/{total_tests}")
        print(f"Errors: {self.results['error_count']}")
        print(f"Warnings: {len(self.results['warnings'])}")

        print("\nDetailed Results:")
        print(f"  Network Connectivity: {'✅' if self.results['network_connectivity'] else '❌'}")
        print(f"  Authentication: {'✅' if self.results['authentication'] else '❌'}")
        print(f"  Account Info: {'✅' if self.results['account_info'] else '❌'}")
        print(f"  Tick Streaming: {'✅' if self.results['tick_streaming'] else '❌'}")
        print(f"  Connection Health: {'✅' if self.results['connection_health'] else '❌'}")

        if self.results["warnings"]:
            print("\nWarnings:")
            for warning in self.results["warnings"]:
                print(f"  ⚠️  {warning}")

        if self.results["errors"]:
            print("\nErrors:")
            for error in self.results["errors"]:
                print(f"  ❌ {error}")

        print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")

        if passed_tests == total_tests:
            print(f"{Colors.GREEN}{Colors.BOLD}✅ All tests passed!{Colors.RESET}")
            return True
        elif passed_tests >= 3:
            print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  Some tests passed, but issues detected{Colors.RESET}")
            return False
        else:
            print(f"{Colors.RED}{Colors.BOLD}❌ Most tests failed - connection not working{Colors.RESET}")
            return False

    def run_all_tests(self) -> bool:
        """Run all tests"""
        print(f"{Colors.BOLD}{Colors.CYAN}")
        print("=" * 60)
        print("ZeroMQ Connection Comprehensive Test Suite")
        print("=" * 60)
        print(f"{Colors.RESET}")

        try:
            # Check prerequisites
            if not self.check_prerequisites():
                return False

            # Run tests in sequence
            self.test_network_connectivity()
            self.test_authentication()
            self.test_account_info()
            self.test_tick_streaming()
            self.test_connection_health()

            # Print summary
            return self.print_summary()

        finally:
            self.cleanup()


def main():
    """Main entry point"""
    tester = ZeroMQConnectionTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
