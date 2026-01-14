#!/usr/bin/env python3
"""
MT5 Historical Data Backfill Script
Backfills tick data from MT5 and generates OHLCV bars for all timeframes
"""

import argparse
import sys
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

# Add src/trading_server/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "trading_server", "src"))

from database import Database
from connectors.mt5_tick_connector import MT5TickConnector
from connectors.base import ConnectorConfig
from infrastructure.backfill.progress_tracker import BackfillProgressTracker
from utils.ohlcv_aggregator import TickToOHLCVAggregator
from data.quality_gates import QualityGate
from utils.logging_config import get_logger


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="Backfill MT5 historical data")
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
        "--resume",
        action="store_true",
        help="Resume from last successful checkpoint",
    )
    parser.add_argument(
        "--skip-ohlcv",
        action="store_true",
        help="Skip OHLCV aggregation (only backfill ticks)",
    )
    parser.add_argument(
        "--timeframes",
        type=str,
        nargs="+",
        default=["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
        help="Timeframes to generate (default: all)",
    )
    return parser.parse_args()


def parse_datetime(dt_str: str) -> datetime:
    """Parse datetime string to datetime object"""
    try:
        # Try ISO format first
        if "T" in dt_str:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        else:
            # Date only - assume start of day UTC
            return datetime.strptime(dt_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise ValueError(f"Invalid datetime format: {dt_str}. Use YYYY-MM-DD or ISO format.") from e


def backfill_ticks(
    connector: MT5TickConnector,
    start_time: datetime,
    end_time: datetime,
    progress_tracker: BackfillProgressTracker,
    progress_id: int,
    db: Database,
) -> int:
    """
    Backfill ticks from MT5 and store in database

    :param connector: MT5 tick connector
    :param start_time: Start time
    :param end_time: End time
    :param progress_tracker: Progress tracker
    :param progress_id: Progress record ID
    :param db: Database instance
    :return: Number of ticks collected
    """
    logger = get_logger("backfill_script", "backfill_mt5_data.log")
    logger.info(f"Starting tick backfill from {start_time} to {end_time}")

    ticks_collected = 0
    last_successful_time = start_time
    batch_size = 100  # Store ticks in batches

    tick_batch = []
    quality_gate = QualityGate()

    try:
        # Backfill ticks
        for normalized_tick in connector.backfill(start_time, end_time):
            # Store tick
            symbol = normalized_tick.get("symbol", connector.symbol)
            timestamp = normalized_tick.get("timestamp")
            bid = normalized_tick.get("bid")
            ask = normalized_tick.get("ask")

            if not all([symbol, timestamp, bid, ask]):
                continue

            # Convert timestamp to datetime if needed
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

            # Add to batch
            tick_batch.append((symbol, timestamp, ask, bid))

            # Store batch when it reaches size
            if len(tick_batch) >= batch_size:
                inserted = db.insert_forex_ticks_batch(tick_batch)
                ticks_collected += inserted
                tick_batch = []

                # Update progress
                last_successful_time = timestamp
                progress_tracker.update_progress(
                    progress_id, last_successful_time, ticks_collected
                )

                logger.debug(f"Collected {ticks_collected} ticks so far...")

        # Store remaining ticks
        if tick_batch:
            inserted = db.insert_forex_ticks_batch(tick_batch)
            ticks_collected += inserted
            last_successful_time = tick_batch[-1][1] if tick_batch else last_successful_time
            progress_tracker.update_progress(
                progress_id, last_successful_time, ticks_collected
            )

        logger.info(f"Tick backfill completed: {ticks_collected} ticks collected")
        return ticks_collected

    except Exception as e:
        logger.error(f"Error during tick backfill: {e}", exc_info=True)
        progress_tracker.mark_failed(progress_id, str(e))
        raise


def aggregate_ohlcv(
    symbol: str,
    start_time: datetime,
    end_time: datetime,
    timeframes: list,
    db: Database,
) -> dict:
    """
    Aggregate ticks to OHLCV bars for all timeframes

    :param symbol: Trading symbol
    :param start_time: Start time
    :param end_time: End time
    :param timeframes: List of timeframes
    :param db: Database instance
    :return: Dictionary mapping timeframe to number of bars created
    """
    logger = get_logger("backfill_script", "backfill_mt5_data.log")
    logger.info(f"Starting OHLCV aggregation for {symbol}")

    # Get ticks from database
    logger.info("Fetching ticks from database...")
    ticks = db.get_recent_ticks(
        symbol=symbol,
        limit=1000000,  # Large limit
        hours=int((end_time - start_time).total_seconds() / 3600) + 1,
    )

    if not ticks:
        logger.warning("No ticks found in database for aggregation")
        return {}

    # Convert to aggregator format
    tick_list = []
    for tick in ticks:
        tick_datetime = tick.get("event_time") or tick.get("datetime")
        if not tick_datetime:
            continue

        # Filter by time range
        if isinstance(tick_datetime, str):
            try:
                tick_datetime = datetime.fromisoformat(
                    tick_datetime.replace("Z", "+00:00")
                )
            except ValueError:
                continue

        if tick_datetime < start_time or tick_datetime > end_time:
            continue

        tick_list.append(
            {
                "timestamp": tick_datetime,
                "bid": tick.get("bid", 0.0),
                "ask": tick.get("ask", 0.0),
                "volume": tick.get("volume"),
            }
        )

    logger.info(f"Processing {len(tick_list)} ticks for aggregation")

    # Aggregate
    aggregator = TickToOHLCVAggregator()
    result = {}

    for timeframe in timeframes:
        logger.info(f"Aggregating {timeframe} bars...")
        bars = aggregator.aggregate_ticks(tick_list, timeframe)

        if not bars:
            logger.warning(f"No {timeframe} bars generated")
            continue

        # Prepare bars for database
        bar_list = []
        for bar in bars:
            bar_list.append(
                {
                    "symbol": symbol,
                    "datetime": bar["datetime"],
                    "open": bar["open"],
                    "high": bar["high"],
                    "low": bar["low"],
                    "close": bar["close"],
                    "volume": bar.get("volume"),
                    "timeframe": timeframe,
                }
            )

        # Store bars
        inserted = db.insert_forex_bars_batch(bar_list)
        result[timeframe] = inserted
        logger.info(f"Stored {inserted} {timeframe} bars")

    return result


def main():
    """Main backfill function"""
    args = parse_args()
    logger = get_logger("backfill_script", "backfill_mt5_data.log")

    # Parse times
    start_time = parse_datetime(args.start_time)
    end_time = parse_datetime(args.end_time)

    if start_time >= end_time:
        logger.error("start_time must be < end_time")
        sys.exit(1)

    symbol = args.symbol.upper()

    logger.info(
        f"Starting backfill for {symbol} from {start_time} to {end_time}"
    )

    # Initialize components
    db = Database()
    progress_tracker = BackfillProgressTracker(db)

    # Check for existing progress
    existing_progress = progress_tracker.get_progress(
        "mt5_tick", symbol, start_time, end_time
    )

    if args.resume and existing_progress:
        progress_id = existing_progress["id"]
        resume_point = progress_tracker.get_resume_point(progress_id)
        if resume_point:
            logger.info(f"Resuming from {resume_point}")
            start_time = resume_point
    else:
        # Create new progress record
        progress_id = progress_tracker.start_backfill(
            "mt5_tick", symbol, start_time, end_time
        )

    # Create connector (backfill doesn't need socket, but connector requires it)
    # Use a dummy socket object
    class DummySocket:
        pass

    config = ConnectorConfig(
        source="mt5",
        symbol=symbol,
        extra_config={"digits": 5},
    )
    connector = MT5TickConnector(
        socket=DummySocket(),  # Not used for backfill
        symbol=symbol,
        config=config,
    )

    try:
        # Backfill ticks
        ticks_collected = backfill_ticks(
            connector, start_time, end_time, progress_tracker, progress_id, db
        )

        # Mark tick backfill as completed
        progress_tracker.mark_completed(progress_id)

        # Aggregate OHLCV if not skipped
        if not args.skip_ohlcv:
            ohlcv_results = aggregate_ohlcv(
                symbol, start_time, end_time, args.timeframes, db
            )
            logger.info(f"OHLCV aggregation results: {ohlcv_results}")
        else:
            logger.info("Skipping OHLCV aggregation")

        logger.info(
            f"Backfill completed successfully: {ticks_collected} ticks collected"
        )

    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        progress_tracker.mark_failed(progress_id, str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
