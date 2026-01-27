#!/usr/bin/env python3
"""
Test script for data collection from each datasource connector

Tests:
1. Connection to each datasource
2. Schema retrieval
3. Available data range
4. Small backfill sample
5. Latest timestamp
6. Health check

Usage:
    python scripts/test_datasource_collection.py [--connector CONNECTOR_NAME] [--verbose]
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import traceback

# Add trading server src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "trading_server", "src"))

from connectors.base import ConnectorConfig
from connectors.registry import ConnectorRegistry


class DataSourceTester:
    """Test data collection for each datasource connector"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: Dict[str, Dict[str, Any]] = {}
        self.registry = ConnectorRegistry()

    def print_header(self, text: str) -> None:
        """Print a formatted header"""
        print("\n" + "=" * 80)
        print(f"  {text}")
        print("=" * 80)

    def print_test(self, test_name: str, status: str, details: str = "") -> None:
        """Print test result"""
        status_symbol = {
            "PASS": "✓",
            "FAIL": "✗",
            "SKIP": "⊘",
            "WARN": "⚠",
        }.get(status, "?")
        print(f"\n{status_symbol} {test_name}")
        if details:
            print(f"   {details}")

    def test_connector_connection(self, name: str, connector) -> bool:
        """Test connector connection"""
        try:
            if not hasattr(connector, "connect"):
                self.print_test(f"{name} - Connection", "SKIP", "No connect method")
                return False

            connected = connector.connect()
            if connected:
                self.print_test(f"{name} - Connection", "PASS", "Successfully connected")
                return True
            else:
                self.print_test(f"{name} - Connection", "FAIL", "Connection failed")
                return False
        except Exception as e:
            self.print_test(f"{name} - Connection", "FAIL", f"Error: {str(e)}")
            if self.verbose:
                traceback.print_exc()
            return False

    def test_connector_schema(self, name: str, connector) -> bool:
        """Test connector schema retrieval"""
        try:
            schema = connector.get_schema()
            if isinstance(schema, dict) and "source" in schema:
                source = schema.get("source", "unknown")
                data_type = schema.get("data_type", "unknown")
                fields = schema.get("fields", {})
                self.print_test(
                    f"{name} - Schema",
                    "PASS",
                    f"Source: {source}, Type: {data_type}, Fields: {len(fields)}",
                )
                if self.verbose:
                    print(f"   Schema details: {schema}")
                return True
            else:
                self.print_test(f"{name} - Schema", "FAIL", "Invalid schema format")
                return False
        except Exception as e:
            self.print_test(f"{name} - Schema", "FAIL", f"Error: {str(e)}")
            if self.verbose:
                traceback.print_exc()
            return False

    def test_connector_available_range(self, name: str, connector) -> bool:
        """Test connector available range"""
        try:
            if not connector.is_connected():
                self.print_test(f"{name} - Available Range", "SKIP", "Not connected")
                return False

            earliest, latest = connector.get_available_range()
            if isinstance(earliest, datetime) and isinstance(latest, datetime):
                duration = latest - earliest
                self.print_test(
                    f"{name} - Available Range",
                    "PASS",
                    f"Earliest: {earliest.strftime('%Y-%m-%d')}, "
                    f"Latest: {latest.strftime('%Y-%m-%d')}, "
                    f"Duration: {duration.days} days",
                )
                return True
            else:
                self.print_test(f"{name} - Available Range", "FAIL", "Invalid range format")
                return False
        except Exception as e:
            self.print_test(f"{name} - Available Range", "FAIL", f"Error: {str(e)}")
            if self.verbose:
                traceback.print_exc()
            return False

    def test_connector_backfill(self, name: str, connector) -> bool:
        """Test connector backfill with small sample"""
        try:
            if not connector.is_connected():
                self.print_test(f"{name} - Backfill", "SKIP", "Not connected")
                return False

            # Get available range
            try:
                earliest, latest = connector.get_available_range()
                # Use last 7 days or available range, whichever is smaller
                end_time = latest
                start_time = max(earliest, end_time - timedelta(days=7))
            except Exception:
                # If range not available, use last 7 days
                end_time = datetime.now()
                start_time = end_time - timedelta(days=7)

            if start_time >= end_time:
                self.print_test(f"{name} - Backfill", "SKIP", "Invalid time range")
                return False

            # Fetch small sample (limit to 10 records)
            events = []
            count = 0
            max_samples = 10

            for event in connector.backfill(start_time, end_time, batch_size=100):
                events.append(event)
                count += 1
                if count >= max_samples:
                    break

            if count > 0:
                # Validate event structure
                sample_event = events[0]
                required_fields = ["timestamp", "source"]
                missing_fields = [f for f in required_fields if f not in sample_event]

                if missing_fields:
                    self.print_test(
                        f"{name} - Backfill",
                        "WARN",
                        f"Fetched {count} events, but missing fields: {missing_fields}",
                    )
                else:
                    self.print_test(
                        f"{name} - Backfill",
                        "PASS",
                        f"Fetched {count} sample events successfully",
                    )
                    if self.verbose and events:
                        print(f"   Sample event: {sample_event}")
                return True
            else:
                self.print_test(f"{name} - Backfill", "WARN", "No events fetched")
                return False
        except Exception as e:
            self.print_test(f"{name} - Backfill", "FAIL", f"Error: {str(e)}")
            if self.verbose:
                traceback.print_exc()
            return False

    def test_connector_latest_timestamp(self, name: str, connector) -> bool:
        """Test connector latest timestamp"""
        try:
            if not connector.is_connected():
                self.print_test(f"{name} - Latest Timestamp", "SKIP", "Not connected")
                return False

            latest = connector.get_latest_timestamp()
            if latest is None:
                self.print_test(f"{name} - Latest Timestamp", "WARN", "No data available")
                return False
            elif isinstance(latest, datetime):
                age = datetime.now() - latest
                self.print_test(
                    f"{name} - Latest Timestamp",
                    "PASS",
                    f"Latest: {latest.strftime('%Y-%m-%d %H:%M:%S')}, "
                    f"Age: {age.days} days {age.seconds // 3600} hours",
                )
                return True
            else:
                self.print_test(f"{name} - Latest Timestamp", "FAIL", "Invalid timestamp format")
                return False
        except Exception as e:
            self.print_test(f"{name} - Latest Timestamp", "FAIL", f"Error: {str(e)}")
            if self.verbose:
                traceback.print_exc()
            return False

    def test_connector(self, name: str, connector) -> Dict[str, bool]:
        """Run all tests for a connector"""
        self.print_header(f"Testing Connector: {name}")

        results = {}

        # Test connection
        results["connection"] = self.test_connector_connection(name, connector)

        # Test schema
        results["schema"] = self.test_connector_schema(name, connector)

        # Test available range (requires connection)
        if results["connection"]:
            results["available_range"] = self.test_connector_available_range(name, connector)
        else:
            results["available_range"] = False
            self.print_test(f"{name} - Available Range", "SKIP", "Not connected")

        # Test backfill (requires connection)
        if results["connection"]:
            results["backfill"] = self.test_connector_backfill(name, connector)
        else:
            results["backfill"] = False
            self.print_test(f"{name} - Backfill", "SKIP", "Not connected")

        # Test latest timestamp (requires connection)
        if results["connection"]:
            results["latest_timestamp"] = self.test_connector_latest_timestamp(name, connector)
        else:
            results["latest_timestamp"] = False
            self.print_test(f"{name} - Latest Timestamp", "SKIP", "Not connected")

        # Cleanup
        try:
            if hasattr(connector, "disconnect"):
                connector.disconnect()
        except Exception:
            pass

        return results

    def get_available_connectors(self) -> Dict[str, Any]:
        """Get all available connector classes"""
        connectors = {}

        # Import connector classes
        try:
            from connectors import (
                MT5TickConnector,
                MT5PriceConnector,
                FREDConnector,
                WorldBankConnector,
                ECBConnector,
                RSSFeedConnector,
                WebScrapingConnector,
                NewsAPIConnector,
            )

            # MT5 connectors require special setup
            connectors["MT5Tick"] = {
                "class": MT5TickConnector,
                "config": ConnectorConfig(
                    source="mt5",
                    symbol="EURUSD",
                    extra_config={"digits": 5},
                ),
                "requires_socket": True,
            }

            connectors["MT5Price"] = {
                "class": MT5PriceConnector,
                "config": ConnectorConfig(
                    source="mt5",
                    symbol="EURUSD",
                    extra_config={"digits": 5},
                ),
                "requires_socket": True,
            }

            # FRED connector
            if FREDConnector is not None:
                connectors["FRED"] = {
                    "class": FREDConnector,
                    "config": ConnectorConfig(source="fred", symbol="US"),
                    "requires_socket": False,
                }

            # World Bank connector
            if WorldBankConnector is not None:
                connectors["WorldBank"] = {
                    "class": WorldBankConnector,
                    "config": ConnectorConfig(source="world_bank", symbol="US"),
                    "requires_socket": False,
                }

            # ECB connector
            if ECBConnector is not None:
                connectors["ECB"] = {
                    "class": ECBConnector,
                    "config": ConnectorConfig(source="ecb", symbol="EUR"),
                    "requires_socket": False,
                }

            # RSS Feed connector
            if RSSFeedConnector is not None:
                connectors["RSSFeed"] = {
                    "class": RSSFeedConnector,
                    "config": ConnectorConfig(source="rss", symbol="news"),
                    "requires_socket": False,
                }

            # Web Scraping connector
            if WebScrapingConnector is not None:
                connectors["WebScraping"] = {
                    "class": WebScrapingConnector,
                    "config": ConnectorConfig(source="web_scraping", symbol="news"),
                    "requires_socket": False,
                }

            # News API connector
            if NewsAPIConnector is not None:
                connectors["NewsAPI"] = {
                    "class": NewsAPIConnector,
                    "config": ConnectorConfig(source="newsapi", symbol="forex"),
                    "requires_socket": False,
                }

        except ImportError as e:
            print(f"Warning: Could not import some connectors: {e}")

        return connectors

    def create_connector_instance(self, name: str, connector_info: Dict[str, Any]) -> Optional[Any]:
        """Create a connector instance"""
        connector_class = connector_info["class"]
        config = connector_info["config"]
        requires_socket = connector_info.get("requires_socket", False)

        try:
            if requires_socket:
                # MT5 connectors require a socket connection
                # Check if we can create a mock socket or skip
                try:
                    # Try to import socket module to check if MT5 infrastructure exists
                    from unittest.mock import Mock
                    mock_socket = Mock()
                    
                    # For MT5TickConnector, try to create with mock socket
                    if name == "MT5Tick":
                        return connector_class(
                            socket=mock_socket,
                            symbol=config.symbol,
                            config=config
                        )
                    elif name == "MT5Price":
                        return connector_class(
                            socket=mock_socket,
                            symbol=config.symbol,
                            config=config
                        )
                    else:
                        self.print_test(
                            f"{name} - Connector Creation",
                            "SKIP",
                            f"{connector_class.__name__} requires MT5 socket connection",
                        )
                        return None
                except Exception as e:
                    self.print_test(
                        f"{name} - Connector Creation",
                        "SKIP",
                        f"{connector_class.__name__} requires MT5 socket connection: {str(e)}",
                    )
                    return None
            else:
                # Create connector with config
                return connector_class(config=config)
        except Exception as e:
            self.print_test(f"{name} - Connector Creation", "FAIL", f"Error: {str(e)}")
            if self.verbose:
                traceback.print_exc()
            return None

    def run_tests(self, connector_name: Optional[str] = None) -> None:
        """Run tests for all connectors or a specific one"""
        self.print_header("Data Source Collection Test Suite")

        # Get available connectors
        available_connectors = self.get_available_connectors()

        if not available_connectors:
            print("\n✗ No connectors available. Check dependencies and imports.")
            return

        # Filter to specific connector if requested
        if connector_name:
            if connector_name not in available_connectors:
                print(f"\n✗ Connector '{connector_name}' not found.")
                print(f"Available connectors: {', '.join(available_connectors.keys())}")
                return
            available_connectors = {connector_name: available_connectors[connector_name]}

        print(f"\nFound {len(available_connectors)} connector(s) to test:")
        for name in available_connectors.keys():
            print(f"  - {name}")

        # Test each connector
        for name, connector_info in available_connectors.items():
            try:
                # Create connector instance
                connector = self.create_connector_instance(name, connector_info)
                if connector is None:
                    self.results[name] = {"skipped": True, "reason": "Could not create instance"}
                    continue

                # Run tests
                results = self.test_connector(name, connector)
                self.results[name] = results

            except Exception as e:
                print(f"\n✗ Error testing {name}: {e}")
                if self.verbose:
                    traceback.print_exc()
                self.results[name] = {"error": str(e)}

    def print_summary(self) -> None:
        """Print test summary"""
        self.print_header("Test Summary")

        if not self.results:
            print("\nNo tests were run.")
            return

        total_connectors = len(self.results)
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0
        skipped_connectors = []

        for connector_name, results in self.results.items():
            if isinstance(results, dict):
                if "skipped" in results:
                    skipped_connectors.append((connector_name, results.get("reason", "Unknown")))
                    continue
                if "error" in results:
                    print(f"\n{connector_name}:")
                    print(f"  ✗ Error: {results['error']}")
                    failed_tests += 1
                    continue

            print(f"\n{connector_name}:")
            for test_name, result in results.items():
                if result is True:
                    status = "PASS"
                    passed_tests += 1
                elif result is False:
                    status = "FAIL"
                    failed_tests += 1
                else:
                    status = "SKIP"
                    skipped_tests += 1

                status_symbol = {"PASS": "✓", "FAIL": "✗", "SKIP": "⊘"}.get(status, "?")
                print(f"  {status_symbol} {test_name}")

        if skipped_connectors:
            print("\nSkipped Connectors:")
            for name, reason in skipped_connectors:
                print(f"  ⊘ {name}: {reason}")

        print("\n" + "-" * 80)
        print(f"Total Connectors: {total_connectors}")
        print(f"Passed Tests: {passed_tests}")
        print(f"Failed Tests: {failed_tests}")
        print(f"Skipped Tests: {skipped_tests}")
        if skipped_connectors:
            print(f"Skipped Connectors: {len(skipped_connectors)}")
        print("-" * 80)

        if failed_tests == 0 and skipped_tests == 0 and not skipped_connectors:
            print("\n✓ All tests passed!")
        elif failed_tests == 0:
            print("\n⚠ Some tests were skipped (check requirements above)")
        else:
            print("\n✗ Some tests failed (check errors above)")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Test data collection for each datasource")
    parser.add_argument(
        "--connector",
        type=str,
        help="Test specific connector only (e.g., FRED, WorldBank, RSSFeed)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Database credentials must be provided via environment variables (.env file)
    # Required: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

    tester = DataSourceTester(verbose=args.verbose)
    tester.run_tests(connector_name=args.connector)
    tester.print_summary()

    # Return exit code based on results
    failed = sum(
        1
        for r in tester.results.values()
        if isinstance(r, dict) and any(v is False for v in r.values() if isinstance(v, bool))
    )
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
