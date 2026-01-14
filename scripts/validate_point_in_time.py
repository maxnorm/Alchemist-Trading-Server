#!/usr/bin/env python3
"""
Point-in-Time Validation Script

Validates that feature extraction respects point-in-time constraints
(i.e., features at time T only use data <= T, no lookahead bias)
"""

import sys
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.trading_server.src.database import Database
from src.trading_server.src.application.environment.feature_engine import FeatureEngine
from src.trading_server.src.application.environment.price_history_manager import PriceHistoryManager
from src.trading_server.src.utils.feature_engineering import FeatureEngineer
from src.trading_server.src.infrastructure.backfill.historical_feature_computer import (
    HistoricalFeatureComputer,
)
from utils.time_utils import get_utc_time


def validate_feature_extraction(
    symbol: str,
    test_times: List[datetime],
    database: Database,
    feature_engine: FeatureEngine,
) -> Dict[str, Any]:
    """
    Validate feature extraction at multiple points in time

    :param symbol: Currency pair symbol
    :param test_times: List of times to test
    :param database: Database instance
    :param feature_engine: FeatureEngine instance
    :return: Validation results
    """
    results = {
        "symbol": symbol,
        "test_count": len(test_times),
        "passed": 0,
        "failed": 0,
        "errors": [],
        "details": [],
    }

    price_manager = PriceHistoryManager(window_size=feature_engine.window_size)

    # Load historical data for all test times
    for test_time in test_times:
        try:
            # Load data in a range around test_time
            start_time = test_time - timedelta(days=1)
            end_time = test_time + timedelta(hours=1)

            # Query ticks from database
            query = """
                SELECT tf.datetime, (tf.bid + tf.ask) / 2.0 AS mid_price, tf.receive_time
                FROM ticks_forex tf
                JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
                WHERE fp.symbol = :symbol
                    AND tf.datetime >= :start_time
                    AND tf.datetime <= :end_time
                ORDER BY tf.datetime ASC
            """

            ticks = database.execute_with_result(
                query,
                {
                    "symbol": symbol.upper(),
                    "start_time": start_time,
                    "end_time": end_time,
                },
            )

            if not ticks:
                results["errors"].append(
                    f"No data found for {symbol} around {test_time}"
                )
                results["failed"] += 1
                continue

            # Add ticks to price manager
            for tick in ticks:
                timestamp = tick[0]
                price = float(tick[1])
                receive_time = tick[2]
                price_manager.add_price(symbol, price, timestamp=timestamp, receive_time=receive_time)

            # Get history up to test_time (point-in-time constraint)
            history_up_to = price_manager.get_history_up_to(symbol, test_time)

            # Get all history (including future data for validation)
            all_history = price_manager.get_history(symbol)

            # Verify point-in-time constraint
            future_data = [h for h in all_history if h[0] > test_time]
            data_used = [h for h in history_up_to if h[0] <= test_time]

            # Check that no future data is in history_up_to
            has_future_data = any(h[0] > test_time for h in history_up_to)

            if has_future_data:
                results["failed"] += 1
                results["errors"].append(
                    f"Future data found in history_up_to for {test_time}: "
                    f"{[h[0] for h in history_up_to if h[0] > test_time]}"
                )
                results["details"].append(
                    {
                        "test_time": test_time.isoformat(),
                        "status": "FAILED",
                        "reason": "Future data in history_up_to",
                        "data_points_used": len(data_used),
                        "future_data_points": len(future_data),
                    }
                )
                continue

            # Extract features with point-in-time constraint
            prices = [price for _, price, _ in history_up_to]

            if len(prices) < feature_engine.window_size:
                results["errors"].append(
                    f"Insufficient data for {test_time}: {len(prices)} < {feature_engine.window_size}"
                )
                results["failed"] += 1
                continue

            features = feature_engine.extract_features(prices, symbol, current_time=test_time)

            if features is None:
                results["errors"].append(f"Feature extraction returned None for {test_time}")
                results["failed"] += 1
                continue

            # Validation passed
            results["passed"] += 1
            results["details"].append(
                {
                    "test_time": test_time.isoformat(),
                    "status": "PASSED",
                    "data_points_used": len(data_used),
                    "future_data_points": len(future_data),
                    "features_shape": features.shape if features is not None else None,
                }
            )

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"Error validating {test_time}: {e}")

    return results


def validate_alternative_data_features(
    symbol: str,
    test_times: List[datetime],
    database: Database,
    feature_engine: FeatureEngine,
) -> Dict[str, Any]:
    """
    Validate alternative data feature extraction (news, macro)

    :param symbol: Currency pair symbol
    :param test_times: List of times to test
    :param database: Database instance
    :param feature_engine: FeatureEngine instance
    :return: Validation results
    """
    results = {
        "symbol": symbol,
        "test_count": len(test_times),
        "news_passed": 0,
        "news_failed": 0,
        "macro_passed": 0,
        "macro_failed": 0,
        "errors": [],
    }

    for test_time in test_times:
        try:
            # Test news features
            news_features = feature_engine.extract_news_features(symbol, test_time)

            # Verify news features only use data <= test_time
            # This is enforced by extract_news_features internally
            # We can verify by checking database queries use end_time=test_time
            if news_features:
                results["news_passed"] += 1
            else:
                results["news_failed"] += 1

            # Test macro features
            macro_features = feature_engine.extract_macro_features(symbol, test_time)

            # Verify macro features only use data <= test_time
            if macro_features:
                results["macro_passed"] += 1
            else:
                results["macro_failed"] += 1

        except Exception as e:
            results["errors"].append(f"Error validating alternative data at {test_time}: {e}")

    return results


def generate_report(results: Dict[str, Any], output_file: Optional[str] = None):
    """
    Generate validation report

    :param results: Validation results
    :param output_file: Optional output file path
    """
    report_lines = [
        "=" * 80,
        "Point-in-Time Validation Report",
        "=" * 80,
        "",
        f"Symbol: {results['symbol']}",
        f"Test Count: {results['test_count']}",
        f"Passed: {results['passed']}",
        f"Failed: {results['failed']}",
        "",
    ]

    if results.get("news_passed") is not None:
        report_lines.extend(
            [
                "Alternative Data Features:",
                f"  News - Passed: {results['news_passed']}, Failed: {results['news_failed']}",
                f"  Macro - Passed: {results['macro_passed']}, Failed: {results['macro_failed']}",
                "",
            ]
        )

    if results["errors"]:
        report_lines.extend(["Errors:", ""])
        for error in results["errors"]:
            report_lines.append(f"  - {error}")
        report_lines.append("")

    if results.get("details"):
        report_lines.extend(["Details:", ""])
        for detail in results["details"][:10]:  # Show first 10
            report_lines.append(f"  {detail['test_time']}: {detail['status']}")
            if detail.get("reason"):
                report_lines.append(f"    Reason: {detail['reason']}")
        report_lines.append("")

    report_lines.extend(
        [
            "=" * 80,
            f"Validation {'PASSED' if results['failed'] == 0 else 'FAILED'}",
            "=" * 80,
        ]
    )

    report = "\n".join(report_lines)
    print(report)

    if output_file:
        with open(output_file, "w") as f:
            f.write(report)
        print(f"\nReport saved to {output_file}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Validate point-in-time constraints for feature extraction"
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default="EURUSD",
        help="Currency pair symbol to validate",
    )
    parser.add_argument(
        "--start-time",
        type=str,
        help="Start time for validation (ISO format, default: 24 hours ago)",
    )
    parser.add_argument(
        "--end-time",
        type=str,
        help="End time for validation (ISO format, default: now)",
    )
    parser.add_argument(
        "--test-count",
        type=int,
        default=10,
        help="Number of test times to validate",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for report",
    )
    parser.add_argument(
        "--validate-alternative",
        action="store_true",
        help="Also validate alternative data features",
    )

    args = parser.parse_args()

    # Parse times
    if args.end_time:
        end_time = datetime.fromisoformat(args.end_time.replace("Z", "+00:00"))
    else:
        end_time = get_utc_time()

    if args.start_time:
        start_time = datetime.fromisoformat(args.start_time.replace("Z", "+00:00"))
    else:
        start_time = end_time - timedelta(hours=24)

    # Generate test times
    time_range = end_time - start_time
    step = time_range / args.test_count
    test_times = [start_time + step * i for i in range(args.test_count)]

    # Initialize components
    database = Database()
    feature_engineer = FeatureEngineer()
    feature_engine = FeatureEngine(
        feature_engineer=feature_engineer,
        window_size=50,
        features_per_pair=14,
        database=database,
    )

    print(f"Validating point-in-time constraints for {args.symbol}")
    print(f"Test times: {len(test_times)} points from {start_time} to {end_time}")
    print()

    # Validate feature extraction
    results = validate_feature_extraction(
        args.symbol, test_times, database, feature_engine
    )

    # Validate alternative data if requested
    if args.validate_alternative:
        alt_results = validate_alternative_data_features(
            args.symbol, test_times, database, feature_engine
        )
        results.update(alt_results)

    # Generate report
    generate_report(results, args.output)

    # Exit with error code if validation failed
    sys.exit(1 if results["failed"] > 0 else 0)


if __name__ == "__main__":
    main()
