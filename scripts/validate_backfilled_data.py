#!/usr/bin/env python3
"""
Validate Backfilled Data Script
Checks for gaps, verifies data quality, and generates validation report
"""

import argparse
import sys
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from pathlib import Path

# Add src/backend/trading_server/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "backend", "trading_server", "src"))

from database import Database
from utils.logging_config import get_logger


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="Validate backfilled data")
    parser.add_argument(
        "--symbol",
        type=str,
        required=True,
        help="Trading symbol (e.g., EURUSD)",
    )
    parser.add_argument(
        "--start-time",
        type=str,
        required=True,
        help="Start time (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
    )
    parser.add_argument(
        "--end-time",
        type=str,
        required=True,
        help="End time (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path for report (default: docs/generated/validation_report_{symbol}_{timestamp}.md)",
    )
    return parser.parse_args()


def parse_datetime(dt_str: str) -> datetime:
    """Parse datetime string to datetime object"""
    try:
        if "T" in dt_str:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        else:
            return datetime.strptime(dt_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise ValueError(f"Invalid datetime format: {dt_str}") from e


def detect_gaps(ticks: List[Dict], expected_interval: timedelta = timedelta(seconds=1)) -> List[Dict]:
    """
    Detect gaps in tick data

    :param ticks: List of tick dictionaries
    :param expected_interval: Expected interval between ticks
    :return: List of gap dictionaries
    """
    gaps = []
    if len(ticks) < 2:
        return gaps

    for i in range(len(ticks) - 1):
        current_time = ticks[i].get("event_time") or ticks[i].get("datetime")
        next_time = ticks[i + 1].get("event_time") or ticks[i + 1].get("datetime")

        if not current_time or not next_time:
            continue

        if isinstance(current_time, str):
            current_time = datetime.fromisoformat(current_time.replace("Z", "+00:00"))
        if isinstance(next_time, str):
            next_time = datetime.fromisoformat(next_time.replace("Z", "+00:00"))

        gap_duration = next_time - current_time
        if gap_duration > expected_interval * 10:  # Gap is 10x expected interval
            gaps.append(
                {
                    "start": current_time,
                    "end": next_time,
                    "duration": gap_duration,
                }
            )

    return gaps


def validate_price_sanity(ticks: List[Dict]) -> List[str]:
    """
    Validate price sanity (reasonable ranges, no negative spreads)

    :param ticks: List of tick dictionaries
    :return: List of issues found
    """
    issues = []

    for tick in ticks:
        bid = tick.get("bid", 0.0)
        ask = tick.get("ask", 0.0)

        # Check for negative or zero prices
        if bid <= 0 or ask <= 0:
            issues.append(f"Invalid price: bid={bid}, ask={ask}")

        # Check for negative spread
        if ask < bid:
            issues.append(f"Negative spread: bid={bid}, ask={ask}")

        # Check for unreasonable spread (more than 1% of price)
        if bid > 0:
            spread_pct = (ask - bid) / bid * 100
            if spread_pct > 1.0:
                issues.append(f"Unreasonable spread: {spread_pct:.2f}%")

    return issues


def validate_timestamps(ticks: List[Dict], start_time: datetime, end_time: datetime) -> List[str]:
    """
    Validate timestamps (all in UTC, no future timestamps)

    :param ticks: List of tick dictionaries
    :param start_time: Expected start time
    :param end_time: Expected end time
    :return: List of issues found
    """
    issues = []
    now = datetime.now(timezone.utc)

    for tick in ticks:
        timestamp = tick.get("event_time") or tick.get("datetime")
        if not timestamp:
            issues.append("Missing timestamp")
            continue

        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                issues.append(f"Invalid timestamp format: {timestamp}")
                continue

        # Check if future timestamp
        if timestamp > now:
            issues.append(f"Future timestamp: {timestamp}")

        # Check if outside expected range
        if timestamp < start_time or timestamp > end_time:
            issues.append(f"Timestamp outside range: {timestamp}")

    return issues


def validate_ohlcv_consistency(bars: List[Dict]) -> List[str]:
    """
    Validate OHLCV consistency (High >= Low, Open/Close within High/Low range)

    :param bars: List of bar dictionaries
    :return: List of issues found
    """
    issues = []

    for bar in bars:
        high = bar.get("high", 0.0)
        low = bar.get("low", 0.0)
        open_price = bar.get("open", 0.0)
        close = bar.get("close", 0.0)

        # Check High >= Low
        if high < low:
            issues.append(f"High < Low: high={high}, low={low}")

        # Check Open/Close within High/Low range
        if open_price < low or open_price > high:
            issues.append(f"Open outside High/Low range: open={open_price}, high={high}, low={low}")

        if close < low or close > high:
            issues.append(f"Close outside High/Low range: close={close}, high={high}, low={low}")

    return issues


def generate_report(
    symbol: str,
    start_time: datetime,
    end_time: datetime,
    ticks: List[Dict],
    bars: List[Dict],
    gaps: List[Dict],
    price_issues: List[str],
    timestamp_issues: List[str],
    ohlcv_issues: List[str],
    output_path: str,
) -> None:
    """
    Generate validation report in markdown format

    :param symbol: Trading symbol
    :param start_time: Start time
    :param end_time: End time
    :param ticks: List of ticks
    :param bars: List of bars
    :param gaps: List of gaps
    :param price_issues: List of price issues
    :param timestamp_issues: List of timestamp issues
    :param ohlcv_issues: List of OHLCV issues
    :param output_path: Output file path
    """
    report = f"""# Data Validation Report

**Symbol:** {symbol}  
**Date Range:** {start_time} to {end_time}  
**Generated:** {datetime.now(timezone.utc).isoformat()}

## Summary Statistics

- **Ticks Collected:** {len(ticks)}
- **Bars Generated:** {len(bars)}
- **Gaps Detected:** {len(gaps)}
- **Price Issues:** {len(price_issues)}
- **Timestamp Issues:** {len(timestamp_issues)}
- **OHLCV Issues:** {len(ohlcv_issues)}

## Data Quality Metrics

- **Pass Rate:** {((len(ticks) - len(price_issues) - len(timestamp_issues)) / len(ticks) * 100) if ticks else 0:.2f}%
- **Gap Rate:** {(len(gaps) / max(1, len(ticks) - 1) * 100) if ticks else 0:.2f}%

## Gaps Detected

"""
    if gaps:
        report += "| Start Time | End Time | Duration |\n"
        report += "|------------|----------|----------|\n"
        for gap in gaps[:20]:  # Limit to first 20 gaps
            report += f"| {gap['start']} | {gap['end']} | {gap['duration']} |\n"
        if len(gaps) > 20:
            report += f"\n*... and {len(gaps) - 20} more gaps*\n"
    else:
        report += "No gaps detected.\n"

    report += "\n## Issues Found\n\n"

    if price_issues:
        report += "### Price Issues\n\n"
        for issue in price_issues[:50]:  # Limit to first 50
            report += f"- {issue}\n"
        if len(price_issues) > 50:
            report += f"\n*... and {len(price_issues) - 50} more price issues*\n"
        report += "\n"

    if timestamp_issues:
        report += "### Timestamp Issues\n\n"
        for issue in timestamp_issues[:50]:
            report += f"- {issue}\n"
        if len(timestamp_issues) > 50:
            report += f"\n*... and {len(timestamp_issues) - 50} more timestamp issues*\n"
        report += "\n"

    if ohlcv_issues:
        report += "### OHLCV Issues\n\n"
        for issue in ohlcv_issues[:50]:
            report += f"- {issue}\n"
        if len(ohlcv_issues) > 50:
            report += f"\n*... and {len(ohlcv_issues) - 50} more OHLCV issues*\n"
        report += "\n"

    report += "\n## Recommendations\n\n"

    if gaps:
        report += "- **Gaps Found:** Consider backfilling missing time periods\n"
    if price_issues:
        report += "- **Price Issues:** Review data source and validation rules\n"
    if timestamp_issues:
        report += "- **Timestamp Issues:** Verify timezone handling and clock synchronization\n"
    if ohlcv_issues:
        report += "- **OHLCV Issues:** Review aggregation logic\n"

    if not gaps and not price_issues and not timestamp_issues and not ohlcv_issues:
        report += "✅ **No issues detected. Data quality is good.**\n"

    # Write report
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report)

    print(f"Validation report saved to: {output_path}")


def main():
    """Main validation function"""
    args = parse_args()
    logger = get_logger("validate_backfilled_data", "validate_backfilled_data.log")

    # Parse times
    start_time = parse_datetime(args.start_time)
    end_time = parse_datetime(args.end_time)

    symbol = args.symbol.upper()

    logger.info(f"Validating backfilled data for {symbol} from {start_time} to {end_time}")

    # Initialize database
    db = Database()

    # Get ticks
    logger.info("Fetching ticks from database...")
    hours = int((end_time - start_time).total_seconds() / 3600) + 1
    ticks = db.get_recent_ticks(symbol=symbol, limit=1000000, hours=hours)

    # Filter by time range
    filtered_ticks = []
    for tick in ticks:
        tick_time = tick.get("event_time") or tick.get("datetime")
        if not tick_time:
            continue

        if isinstance(tick_time, str):
            try:
                tick_time = datetime.fromisoformat(tick_time.replace("Z", "+00:00"))
            except ValueError:
                continue

        if start_time <= tick_time <= end_time:
            filtered_ticks.append(tick)

    logger.info(f"Found {len(filtered_ticks)} ticks in range")

    # Get bars
    logger.info("Fetching bars from database...")
    bars = []
    for timeframe in ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]:
        timeframe_bars = db.get_bars_by_timeframe(
            symbol=symbol, timeframe=timeframe, start_time=start_time, end_time=end_time
        )
        bars.extend(timeframe_bars)

    logger.info(f"Found {len(bars)} bars in range")

    # Run validations
    logger.info("Running validations...")
    gaps = detect_gaps(filtered_ticks)
    price_issues = validate_price_sanity(filtered_ticks)
    timestamp_issues = validate_timestamps(filtered_ticks, start_time, end_time)
    ohlcv_issues = validate_ohlcv_consistency(bars)

    # Generate report
    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = f"docs/generated/validation_report_{symbol}_{timestamp}.md"

    generate_report(
        symbol=symbol,
        start_time=start_time,
        end_time=end_time,
        ticks=filtered_ticks,
        bars=bars,
        gaps=gaps,
        price_issues=price_issues,
        timestamp_issues=timestamp_issues,
        ohlcv_issues=ohlcv_issues,
        output_path=output_path,
    )

    # Print summary
    print(f"\nValidation Summary:")
    print(f"  Ticks: {len(filtered_ticks)}")
    print(f"  Bars: {len(bars)}")
    print(f"  Gaps: {len(gaps)}")
    print(f"  Issues: {len(price_issues) + len(timestamp_issues) + len(ohlcv_issues)}")

    if gaps or price_issues or timestamp_issues or ohlcv_issues:
        sys.exit(1)
    else:
        print("✅ All validations passed!")


if __name__ == "__main__":
    main()
