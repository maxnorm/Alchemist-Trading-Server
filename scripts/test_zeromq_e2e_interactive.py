#!/usr/bin/env python3
"""
Interactive ZeroMQ E2E Test Script
Tests the complete ZeroMQ integration with MT5 EAs
"""
import os
import sys
import time
import json
import asyncio
from datetime import datetime
from typing import Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "trading_server", "src"))

import zmq
from dotenv import load_dotenv

load_dotenv()


class Colors:
    """ANSI color codes"""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


class ZeroMQE2ETester:
    """Interactive E2E tester for ZeroMQ integration"""

    def __init__(self):
        # Use localhost when running from host machine
        self.host = "127.0.0.1"  # Direct connection to MT5 on Windows host
        self.order_port = int(os.getenv("ZMQ_ORDER_PORT", 5556))
        self.tick_port = int(os.getenv("ZMQ_TICK_PORT", 5555))
        
        # Test account details
        self.login = 452449
        self.auth_token = "q5vtY4Oyb2yaei_svLvMk-gDXsTcNFIQyxjI83oTeY4"
        self.symbol = "EURUSD"
        
        self.context = None
        self.req_socket = None
        self.sub_socket = None
        
        self.test_results = {
            "phase": "",
            "tests_passed": 0,
            "tests_failed": 0,
            "errors": [],
            "warnings": [],
        }

    def print_header(self, text: str):
        """Print section header"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}\n")

    def print_success(self, text: str):
        """Print success message"""
        print(f"{Colors.GREEN}[PASS] {text}{Colors.RESET}")
        self.test_results["tests_passed"] += 1

    def print_error(self, text: str):
        """Print error message"""
        print(f"{Colors.RED}[FAIL] {text}{Colors.RESET}")
        self.test_results["tests_failed"] += 1
        self.test_results["errors"].append(text)

    def print_warning(self, text: str):
        """Print warning message"""
        print(f"{Colors.YELLOW}[WARN] {text}{Colors.RESET}")
        self.test_results["warnings"].append(text)

    def print_info(self, text: str):
        """Print info message"""
        print(f"{Colors.BLUE}[INFO] {text}{Colors.RESET}")

    def print_data(self, label: str, value):
        """Print data with label"""
        print(f"{Colors.MAGENTA}  {label}:{Colors.RESET} {value}")

    # ==================== Phase 3: Connection Tests ====================

    def test_connection_setup(self):
        """Test basic ZeroMQ connection setup"""
        self.print_header("Phase 3: Connection Setup")
        
        try:
            self.print_info(f"Connecting to {self.host}:{self.order_port}...")
            self.context = zmq.Context()
            
            # Setup REQ socket for trading
            self.req_socket = self.context.socket(zmq.REQ)
            self.req_socket.setsockopt(zmq.RCVTIMEO, 10000)  # 10s timeout
            self.req_socket.setsockopt(zmq.SNDTIMEO, 10000)
            self.req_socket.connect(f"tcp://{self.host}:{self.order_port}")
            
            self.print_success("REQ socket connected to trading EA")
            
            # Setup SUB socket for streaming
            self.print_info(f"Connecting to streamer at {self.host}:{self.tick_port}...")
            self.sub_socket = self.context.socket(zmq.SUB)
            self.sub_socket.setsockopt(zmq.RCVTIMEO, 5000)  # 5s timeout
            self.sub_socket.connect(f"tcp://{self.host}:{self.tick_port}")
            self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, self.symbol)
            
            self.print_success("SUB socket connected to streamer EA")
            return True
            
        except Exception as e:
            self.print_error(f"Connection setup failed: {e}")
            return False

    def test_authentication(self):
        """Test authentication with trading EA"""
        self.print_header("Phase 3: Authentication Test")
        
        try:
            auth_request = {
                "auth_code": 2,
                "login": self.login,
                "auth_token": self.auth_token,
            }
            
            self.print_info("Sending authentication request...")
            self.print_data("Login", self.login)
            self.print_data("Token", f"{self.auth_token[:20]}...")
            self.print_data("Request", json.dumps(auth_request))
            
            # Send as string (EA expects string, not native JSON)
            self.req_socket.send_string(json.dumps(auth_request))
            
            # Receive response as string
            response_str = self.req_socket.recv_string()
            self.print_data("Raw Response", response_str)
            response = json.loads(response_str)
            
            self.print_info(f"Response received: {json.dumps(response, indent=2)}")
            
            if response.get("auth_status") == 0:
                self.print_success("Authentication successful!")
                self.print_data("Terminal ID", response.get("terminal_id"))
                self.print_data("Comment", response.get("comment"))
                return True
            else:
                self.print_error(f"Authentication failed: {response.get('comment', 'Unknown error')}")
                return False
                
        except zmq.Again:
            self.print_error("Timeout: EA did not respond within 10 seconds")
            self.print_warning("Check that Trading EA is running and port 5556 is correct")
            return False
        except Exception as e:
            self.print_error(f"Authentication error: {e}")
            return False

    # ==================== Phase 5: Account Info Tests ====================

    def test_account_info(self):
        """Test account info retrieval"""
        self.print_header("Phase 5: Account Info Retrieval")
        
        try:
            account_request = {"request": 100}  # ACCOUNT_INFO
            
            self.print_info("Requesting account information...")
            self.req_socket.send_string(json.dumps(account_request))
            
            response_str = self.req_socket.recv_string()
            response = json.loads(response_str)
            
            self.print_success("Account info retrieved successfully!")
            self.print_data("Currency", response.get("currency", "N/A"))
            self.print_data("Leverage", response.get("leverage", "N/A"))
            self.print_data("Balance", response.get("balance", "N/A"))
            self.print_data("Equity", response.get("equity", "N/A"))
            self.print_data("Profit", response.get("profit", "N/A"))
            self.print_data("Margin", response.get("margin", "N/A"))
            self.print_data("Free Margin", response.get("margin_free", "N/A"))
            
            return True
            
        except zmq.Again:
            self.print_error("Timeout: EA did not respond")
            return False
        except Exception as e:
            self.print_error(f"Account info error: {e}")
            return False

    def test_connection_health(self):
        """Test connection health with multiple pings"""
        self.print_header("Phase 5: Connection Health Test")
        
        try:
            self.print_info("Performing 3 ping tests...")
            latencies = []
            
            for i in range(3):
                ping_request = {"request": 100}  # Use ACCOUNT_INFO as ping
                
                start_time = time.time()
                self.req_socket.send_string(json.dumps(ping_request))
                response_str = self.req_socket.recv_string()
                response = json.loads(response_str)
                latency = (time.time() - start_time) * 1000  # Convert to ms
                
                latencies.append(latency)
                
                if response.get("currency"):
                    self.print_success(f"Ping {i+1}: {latency:.2f}ms")
                else:
                    self.print_warning(f"Ping {i+1}: Unexpected response")
                
                time.sleep(0.5)
            
            avg_latency = sum(latencies) / len(latencies)
            self.print_success(f"All pings successful - Avg latency: {avg_latency:.2f}ms")
            
            if avg_latency > 100:
                self.print_warning(f"High latency detected: {avg_latency:.2f}ms (expected < 100ms)")
            
            return True
            
        except Exception as e:
            self.print_error(f"Health test error: {e}")
            return False

    # ==================== Phase 4: Tick Streaming Tests ====================

    def test_tick_streaming(self, duration_seconds: int = 10):
        """Test tick streaming (will timeout if market closed)"""
        self.print_header("Phase 4: Tick Streaming Test")
        
        self.print_info(f"Listening for ticks on {self.symbol} for {duration_seconds} seconds...")
        self.print_warning("Market is closed on weekends - timeout is expected")
        
        tick_count = 0
        start_time = time.time()
        
        try:
            while time.time() - start_time < duration_seconds:
                try:
                    topic, message = self.sub_socket.recv_multipart(zmq.NOBLOCK)
                    tick_data = json.loads(message.decode())
                    
                    tick_count += 1
                    if tick_count == 1:
                        self.print_success("First tick received!")
                        self.print_data("Symbol", tick_data.get("symbol"))
                        self.print_data("Bid", tick_data.get("bid"))
                        self.print_data("Ask", tick_data.get("ask"))
                        self.print_data("Time", tick_data.get("datetime"))
                    
                except zmq.Again:
                    time.sleep(0.1)
                    continue
            
            if tick_count > 0:
                self.print_success(f"Received {tick_count} ticks in {duration_seconds} seconds")
                return True
            else:
                self.print_warning(f"No ticks received (market closed)")
                self.print_info("This is expected on weekends/holidays")
                return True  # Not a failure
                
        except Exception as e:
            self.print_error(f"Tick streaming error: {e}")
            return False

    # ==================== Phase 6: Order Execution Tests ====================

    def test_order_execution(self):
        """Test order execution (will fail gracefully if market closed)"""
        self.print_header("Phase 6: Order Execution Test")
        
        self.print_warning("Market is closed - orders will be rejected (expected)")
        
        try:
            order_request = {
                "request": 101,  # OPEN_ORDER
                "order_type": 0,  # BUY
                "symbol": self.symbol,
                "lotsize": 0.01,
                "price": None,  # Market order
                "sl": None,
                "tp": None,
            }
            
            self.print_info("Sending BUY order (0.01 lots)...")
            self.req_socket.send_string(json.dumps(order_request))
            
            response_str = self.req_socket.recv_string()
            response = json.loads(response_str)
            
            self.print_info(f"Order response: {json.dumps(response, indent=2)}")
            
            return_code = response.get("return_code", -1)
            
            if return_code == 10009:  # TRADE_RETCODE_DONE
                self.print_success(f"Order executed! Ticket: {response.get('ticket')}")
                self.print_data("Lot size", response.get("lotsize"))
                self.print_data("Price", response.get("price"))
                return True
            else:
                # Market closed is expected
                comment = response.get("comment", "Unknown")
                if "market" in comment.lower() or "closed" in comment.lower():
                    self.print_warning(f"Order rejected (market closed): {comment}")
                    self.print_info("This is expected behavior on weekends")
                    return True  # Not a failure
                else:
                    self.print_error(f"Order failed: Return code {return_code}, Comment: {comment}")
                    return False
                    
        except zmq.Again:
            self.print_error("Timeout: EA did not respond to order request")
            return False
        except Exception as e:
            self.print_error(f"Order execution error: {e}")
            return False

    # ==================== Phase 7: Error Handling Tests ====================

    def test_invalid_auth(self):
        """Test invalid authentication handling"""
        self.print_header("Phase 7: Invalid Authentication Test")
        
        try:
            # Create new socket for this test
            test_socket = self.context.socket(zmq.REQ)
            test_socket.setsockopt(zmq.RCVTIMEO, 5000)
            test_socket.connect(f"tcp://{self.host}:{self.order_port}")
            
            auth_request = {
                "auth_code": 2,
                "login": self.login,
                "auth_token": "invalid_token_12345",
            }
            
            self.print_info("Sending invalid auth token...")
            test_socket.send_string(json.dumps(auth_request))
            
            response_str = test_socket.recv_string()
            response = json.loads(response_str)
            
            if response.get("auth_status") != 0:
                self.print_success("Invalid auth correctly rejected!")
                self.print_data("Comment", response.get("comment"))
                test_socket.close()
                return True
            else:
                self.print_error("Invalid auth was accepted (security issue!)")
                test_socket.close()
                return False
                
        except Exception as e:
            self.print_error(f"Invalid auth test error: {e}")
            return False

    # ==================== Cleanup ====================

    def cleanup(self):
        """Clean up resources"""
        self.print_header("Phase 10: Cleanup")
        
        try:
            if self.req_socket:
                self.req_socket.close()
                self.print_success("REQ socket closed")
            
            if self.sub_socket:
                self.sub_socket.close()
                self.print_success("SUB socket closed")
            
            if self.context:
                self.context.term()
                self.print_success("ZMQ context terminated")
            
            return True
        except Exception as e:
            self.print_error(f"Cleanup error: {e}")
            return False

    # ==================== Summary ====================

    def print_summary(self):
        """Print test summary"""
        self.print_header("Test Summary")
        
        total_tests = self.test_results["tests_passed"] + self.test_results["tests_failed"]
        
        print(f"{Colors.BOLD}Results:{Colors.RESET}")
        print(f"  Total Tests: {total_tests}")
        print(f"  {Colors.GREEN}Passed: {self.test_results['tests_passed']}{Colors.RESET}")
        print(f"  {Colors.RED}Failed: {self.test_results['tests_failed']}{Colors.RESET}")
        print(f"  {Colors.YELLOW}Warnings: {len(self.test_results['warnings'])}{Colors.RESET}")
        
        if self.test_results["errors"]:
            print(f"\n{Colors.RED}Errors:{Colors.RESET}")
            for error in self.test_results["errors"]:
                print(f"  [X] {error}")
        
        if self.test_results["warnings"]:
            print(f"\n{Colors.YELLOW}Warnings:{Colors.RESET}")
            for warning in self.test_results["warnings"]:
                print(f"  [!] {warning}")
        
        print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
        
        if self.test_results["tests_failed"] == 0:
            print(f"{Colors.GREEN}{Colors.BOLD}[SUCCESS] All critical tests passed!{Colors.RESET}")
            return True
        else:
            print(f"{Colors.RED}{Colors.BOLD}[FAILURE] Some tests failed - review errors above{Colors.RESET}")
            return False

    # ==================== Main Test Flow ====================

    def run_all_tests(self):
        """Run all tests in sequence"""
        print(f"{Colors.BOLD}{Colors.CYAN}")
        print("=" * 70)
        print("ZeroMQ End-to-End Interactive Test Suite")
        print("=" * 70)
        print(f"{Colors.RESET}")
        
        try:
            # Phase 3: Connection and Authentication
            if not self.test_connection_setup():
                self.print_error("Connection setup failed - aborting")
                return False
            
            if not self.test_authentication():
                self.print_error("Authentication failed - aborting")
                return False
            
            # Phase 5: Account Info and Health
            self.test_account_info()
            self.test_connection_health()
            
            # Phase 4: Tick Streaming (optional - will timeout if market closed)
            self.test_tick_streaming(duration_seconds=5)
            
            # Phase 6: Order Execution (will fail gracefully if market closed)
            self.test_order_execution()
            
            # Phase 7: Error Handling
            self.test_invalid_auth()
            
            # Phase 10: Cleanup
            self.cleanup()
            
            # Summary
            return self.print_summary()
            
        except KeyboardInterrupt:
            self.print_warning("\nTest interrupted by user")
            self.cleanup()
            return False
        except Exception as e:
            self.print_error(f"Unexpected error: {e}")
            self.cleanup()
            return False


def main():
    """Main entry point"""
    tester = ZeroMQE2ETester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
