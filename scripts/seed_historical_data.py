#!/usr/bin/env python3
"""
Seed Historical Data Script
Loads Dukascopy Parquet files into TimescaleDB for production deployment
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional
import pandas as pd
import pyarrow.parquet as pq

# Store original directory
original_dir = os.getcwd()
script_dir = os.path.dirname(os.path.abspath(__file__))

# Add trading_server to path and change to that directory for imports
trading_server_src = os.path.abspath(os.path.join(script_dir, "..", "src", "trading_server", "src"))
sys.path.insert(0, trading_server_src)
os.chdir(trading_server_src)

# Now imports will work with relative paths
from database import Database
from data.quality_gates import QualityGate
from utils.logging_config import get_logger

# Change back to original directory after imports
os.chdir(original_dir)

logger = get_logger("seed_historical_data", "seed_historical_data.log")


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Seed historical data from Parquet files into TimescaleDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Seed all data
  python seed_historical_data.py --data-dir data/dukascopy

  # Seed specific pairs
  python seed_historical_data.py --data-dir data/dukascopy --pairs EURUSD,GBPUSD

  # Seed specific years only
  python seed_historical_data.py --data-dir data/dukascopy --years 2022-2024

  # Dry run (validation only)
  python seed_historical_data.py --data-dir data/dukascopy --dry-run
        """
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="Directory containing Parquet files (organized by symbol)",
    )
    parser.add_argument(
        "--pairs",
        type=str,
        help="Comma-separated list of pairs to seed (default: all found)",
    )
    parser.add_argument(
        "--years",
        type=str,
        help="Year range to seed (e.g., '2022-2024', default: all)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10000,
        help="Database insert batch size (default: 10000)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip pairs/years with existing data (check database first)",
    )
    parser.add_argument(
        "--validate-quality",
        action="store_true",
        help="Run quality gate validation (slower but safer)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run - validate files without inserting",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output",
    )

    return parser.parse_args()


def discover_parquet_files(data_dir: Path) -> Dict[str, List[Path]]:
    """
    Discover Parquet files organized by symbol

    :param data_dir: Data directory
    :return: Dictionary mapping symbol to list of Parquet files
    """
    logger.info(f"Discovering Parquet files in {data_dir}")

    discovered = {}

    # Look for symbol directories
    for symbol_dir in data_dir.iterdir():
        if not symbol_dir.is_dir():
            continue

        symbol = symbol_dir.name
        parquet_files = list(symbol_dir.glob("*.parquet"))

        if parquet_files:
            discovered[symbol] = sorted(parquet_files)
            logger.info(f"Found {len(parquet_files)} files for {symbol}")

    logger.info(f"Discovered {len(discovered)} symbols with {sum(len(f) for f in discovered.values())} files")
    return discovered


def filter_by_years(parquet_files: List[Path], year_range: str) -> List[Path]:
    """
    Filter Parquet files by year range

    :param parquet_files: List of Parquet files
    :param year_range: Year range string (e.g., '2022-2024')
    :return: Filtered list
    """
    try:
        start_year, end_year = map(int, year_range.split('-'))
    except ValueError:
        raise ValueError(f"Invalid year range format: {year_range}. Use 'YYYY-YYYY'")

    filtered = []
    for file in parquet_files:
        # Extract year from filename (e.g., 2022.parquet)
        try:
            year = int(file.stem)
            if start_year <= year <= end_year:
                filtered.append(file)
        except ValueError:
            # Not a year-based filename, include it
            filtered.append(file)

    logger.info(f"Filtered {len(filtered)}/{len(parquet_files)} files for year range {year_range}")
    return filtered


def check_existing_data(db: Database, symbol: str, year: int) -> bool:
    """
    Check if data already exists for symbol/year

    :param db: Database instance
    :param symbol: Trading symbol
    :param year: Year
    :return: True if data exists
    """
    query = """
        SELECT COUNT(*) as count
        FROM ticks_forex tf
        INNER JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
        WHERE fp.symbol = :symbol
          AND EXTRACT(YEAR FROM tf.datetime) = :year
        LIMIT 1
    """

    result = db.execute_one(query, {'symbol': symbol, 'year': year})
    if result and result[0] > 0:
        logger.info(f"[{symbol}] Year {year} has existing data ({result[0]} records)")
        return True

    return False


def load_parquet_file(parquet_file: Path) -> pd.DataFrame:
    """
    Load Parquet file into DataFrame

    :param parquet_file: Path to Parquet file
    :return: DataFrame
    """
    logger.info(f"Loading {parquet_file.name} ({parquet_file.stat().st_size / (1024*1024):.2f} MB)")

    df = pd.read_parquet(parquet_file)

    # Ensure required columns
    required_cols = ['timestamp', 'bid', 'ask', 'symbol']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # Ensure timestamp is datetime
    if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)

    # Sort by timestamp
    df = df.sort_values('timestamp').reset_index(drop=True)

    logger.info(f"Loaded {len(df)} ticks from {parquet_file.name}")
    return df


def seed_parquet_file(
    parquet_file: Path,
    db: Database,
    batch_size: int = 10000,
    validate_quality: bool = False,
    dry_run: bool = False
) -> Dict:
    """
    Seed ticks from Parquet file into database

    :param parquet_file: Path to Parquet file
    :param db: Database instance
    :param batch_size: Batch size for inserts
    :param validate_quality: Run quality gate validation
    :param dry_run: Dry run mode
    :return: Statistics dictionary
    """
    stats = {
        'file': parquet_file.name,
        'total_ticks': 0,
        'inserted': 0,
        'skipped': 0,
        'errors': 0,
        'start_time': datetime.now(timezone.utc),
        'end_time': None
    }

    try:
        # Load Parquet file
        df = load_parquet_file(parquet_file)
        stats['total_ticks'] = len(df)

        if dry_run:
            logger.info(f"[DRY RUN] Would insert {len(df)} ticks from {parquet_file.name}")
            stats['end_time'] = datetime.now(timezone.utc)
            return stats

        # Quality gate validation (optional)
        quality_gate = QualityGate() if validate_quality else None

        # Process in batches
        batch = []
        for idx, row in df.iterrows():
            try:
                symbol = row['symbol']
                timestamp = row['timestamp']
                bid = float(row['bid'])
                ask = float(row['ask'])

                # Quality gate validation
                if quality_gate:
                    is_valid, error_msg = quality_gate.validate_tick(
                        symbol=symbol,
                        tick_datetime=timestamp,
                        bid=bid,
                        ask=ask
                    )
                    if not is_valid:
                        stats['skipped'] += 1
                        continue

                batch.append((symbol, timestamp, ask, bid))

                # Insert batch when full
                if len(batch) >= batch_size:
                    inserted = db.insert_forex_ticks_batch(batch)
                    if inserted > 0:
                        stats['inserted'] += inserted
                    else:
                        stats['errors'] += len(batch)
                    batch = []

                    # Progress log
                    if stats['inserted'] % 100000 == 0:
                        logger.info(f"  Progress: {stats['inserted']:,} ticks inserted")

            except Exception as e:
                logger.warning(f"Error processing row {idx}: {e}")
                stats['errors'] += 1
                continue

        # Insert remaining batch
        if batch:
            inserted = db.insert_forex_ticks_batch(batch)
            if inserted > 0:
                stats['inserted'] += inserted
            else:
                stats['errors'] += len(batch)

        stats['end_time'] = datetime.now(timezone.utc)
        elapsed = (stats['end_time'] - stats['start_time']).total_seconds()

        logger.info(f"✓ {parquet_file.name}: Inserted {stats['inserted']:,}/{stats['total_ticks']:,} ticks in {elapsed:.1f}s")

    except Exception as e:
        stats['end_time'] = datetime.now(timezone.utc)
        logger.error(f"✗ Failed to seed {parquet_file.name}: {e}", exc_info=True)
        raise

    return stats


def seed_symbol(
    symbol: str,
    parquet_files: List[Path],
    db: Database,
    batch_size: int,
    skip_existing: bool,
    validate_quality: bool,
    dry_run: bool
) -> Dict:
    """
    Seed all Parquet files for a symbol

    :param symbol: Trading symbol
    :param parquet_files: List of Parquet files
    :param db: Database instance
    :param batch_size: Batch size
    :param skip_existing: Skip if data exists
    :param validate_quality: Validate with quality gates
    :param dry_run: Dry run mode
    :return: Summary statistics
    """
    logger.info("=" * 80)
    logger.info(f"SEEDING {symbol} ({len(parquet_files)} files)")
    logger.info("=" * 80)

    summary = {
        'symbol': symbol,
        'files_processed': 0,
        'files_skipped': 0,
        'files_failed': 0,
        'total_ticks': 0,
        'inserted': 0,
        'skipped': 0,
        'errors': 0,
        'start_time': datetime.now(timezone.utc),
        'end_time': None
    }

    for parquet_file in parquet_files:
        try:
            # Extract year from filename
            year = None
            try:
                year = int(parquet_file.stem)
            except ValueError:
                pass

            # Check for existing data
            if skip_existing and year:
                if check_existing_data(db, symbol, year):
                    logger.info(f"[{symbol}] Skipping {year} (data exists)")
                    summary['files_skipped'] += 1
                    continue

            # Seed file
            stats = seed_parquet_file(
                parquet_file,
                db,
                batch_size,
                validate_quality,
                dry_run
            )

            summary['files_processed'] += 1
            summary['total_ticks'] += stats['total_ticks']
            summary['inserted'] += stats['inserted']
            summary['skipped'] += stats['skipped']
            summary['errors'] += stats['errors']

        except Exception as e:
            logger.error(f"[{symbol}] Failed to seed {parquet_file.name}: {e}")
            summary['files_failed'] += 1
            continue

    summary['end_time'] = datetime.now(timezone.utc)
    elapsed = (summary['end_time'] - summary['start_time']).total_seconds()

    logger.info("=" * 80)
    logger.info(f"{symbol} SUMMARY")
    logger.info(f"Files: {summary['files_processed']} processed, {summary['files_skipped']} skipped, {summary['files_failed']} failed")
    logger.info(f"Ticks: {summary['inserted']:,}/{summary['total_ticks']:,} inserted ({summary['skipped']:,} skipped, {summary['errors']:,} errors)")
    logger.info(f"Time: {elapsed:.1f}s")
    logger.info("=" * 80)

    return summary


def main():
    """Main entry point"""
    args = parse_args()

    # Setup
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return 1

    # Discover Parquet files
    discovered = discover_parquet_files(data_dir)
    if not discovered:
        logger.error(f"No Parquet files found in {data_dir}")
        return 1

    # Filter by pairs if specified
    if args.pairs:
        requested_pairs = [p.strip().upper() for p in args.pairs.split(',')]
        discovered = {symbol: files for symbol, files in discovered.items()
                     if symbol in requested_pairs}
        if not discovered:
            logger.error(f"None of the requested pairs found: {args.pairs}")
            return 1

    # Filter by years if specified
    if args.years:
        for symbol in discovered:
            discovered[symbol] = filter_by_years(discovered[symbol], args.years)

    logger.info(f"Will seed {len(discovered)} symbols")

    if args.dry_run:
        logger.info("DRY RUN - No data will be inserted")
        total_files = sum(len(files) for files in discovered.values())
        logger.info(f"Would process {total_files} files")
        for symbol, files in discovered.items():
            logger.info(f"  {symbol}: {len(files)} files")
        return 0

    # Initialize database
    logger.info("Initializing database connection...")
    try:
        db = Database()
        if not db.check_connection_health():
            logger.error("Database connection health check failed")
            return 1
        logger.info("✓ Database connection healthy")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return 1

    # Seed all symbols
    overall_start = datetime.now(timezone.utc)
    results = {}

    for symbol, parquet_files in discovered.items():
        try:
            summary = seed_symbol(
                symbol,
                parquet_files,
                db,
                args.batch_size,
                args.skip_existing,
                args.validate_quality,
                args.dry_run
            )
            results[symbol] = summary
        except KeyboardInterrupt:
            logger.warning("Interrupted by user")
            return 130
        except Exception as e:
            logger.error(f"Failed to seed {symbol}: {e}", exc_info=True)
            results[symbol] = {'symbol': symbol, 'status': 'failed', 'error': str(e)}
            continue

    # Final summary
    overall_elapsed = (datetime.now(timezone.utc) - overall_start).total_seconds()

    logger.info("=" * 80)
    logger.info("FINAL SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total Time: {overall_elapsed:.1f}s ({overall_elapsed/60:.1f} minutes)")
    logger.info(f"Symbols: {len(results)}")

    total_inserted = sum(r.get('inserted', 0) for r in results.values())
    total_ticks = sum(r.get('total_ticks', 0) for r in results.values())
    total_errors = sum(r.get('errors', 0) for r in results.values())

    logger.info(f"Total Ticks: {total_inserted:,}/{total_ticks:,} inserted ({total_errors:,} errors)")

    if total_inserted > 0:
        rate = total_inserted / overall_elapsed
        logger.info(f"Insert Rate: {rate:,.0f} ticks/second")

    # Per-symbol summary
    logger.info("\nPer-Symbol Summary:")
    for symbol, result in sorted(results.items()):
        if 'inserted' in result:
            logger.info(f"  {symbol}: {result['inserted']:,}/{result['total_ticks']:,} ticks")
        else:
            logger.info(f"  {symbol}: {result.get('status', 'unknown')}")

    logger.info("=" * 80)

    # Return error code if any failures
    failed_count = sum(1 for r in results.values() if r.get('status') == 'failed')
    if failed_count > 0:
        logger.warning(f"{failed_count} symbols failed")
        return 1

    logger.info("✓ All symbols completed successfully")
    return 0


if __name__ == "__main__":
    exit(main())
