#!/usr/bin/env python3
"""
Standalone Parquet Data Validation Script
Statistical validation of Dukascopy Parquet files before database seeding

NO dependencies on trading server - completely standalone
"""

import argparse
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('validate_parquet')


class ParquetValidator:
    """Statistical validator for Parquet tick data"""
    
    def __init__(self):
        self.validation_results = {}
    
    def load_parquet_file(self, file_path: Path) -> pd.DataFrame:
        """Load and prepare Parquet file"""
        logger.info(f"Loading {file_path.name}")
        df = pd.read_parquet(file_path)
        
        # Ensure timestamp is datetime
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        
        return df
    
    def validate_basic(self, df: pd.DataFrame, symbol: str, year: int) -> Dict:
        """Basic data validation checks"""
        issues = []
        
        # Check for nulls
        nulls = df.isnull().sum()
        if nulls.any():
            issues.append(f"Null values found: {nulls.to_dict()}")
        
        # Check required columns
        required_cols = ['timestamp', 'bid', 'ask', 'symbol']
        for col in required_cols:
            if col not in df.columns:
                issues.append(f"Missing required column: {col}")
        
        # Check symbol consistency
        if 'symbol' in df.columns:
            unique_symbols = df['symbol'].unique()
            if len(unique_symbols) != 1 or unique_symbols[0] != symbol:
                issues.append(f"Symbol mismatch: expected {symbol}, found {unique_symbols}")
        
        # Check timestamp order
        if not df['timestamp'].is_monotonic_increasing:
            issues.append("Timestamps not in chronological order")
        
        # Check year consistency
        years_in_data = df['timestamp'].dt.year.unique()
        if len(years_in_data) > 1:
            issues.append(f"Multiple years in file: {sorted(years_in_data)}")
        elif len(years_in_data) == 1 and years_in_data[0] != year:
            issues.append(f"Year mismatch: file={year}, data={years_in_data[0]}")
        
        return {
            'passed': len(issues) == 0,
            'issues': issues
        }
    
    def validate_prices(self, df: pd.DataFrame, symbol: str) -> Dict:
        """Validate price data"""
        issues = []
        warnings = []
        
        # Check for negative spreads
        negative_spreads = (df['ask'] < df['bid']).sum()
        if negative_spreads > 0:
            issues.append(f"{negative_spreads} negative spreads detected")
        
        # Check for zero spreads (suspicious)
        zero_spreads = (df['ask'] == df['bid']).sum()
        if zero_spreads > len(df) * 0.01:  # > 1% zero spreads
            warnings.append(f"{zero_spreads} zero spreads detected ({zero_spreads/len(df)*100:.2f}%)")
        
        # Check price ranges
        if df['bid'].min() < 0.0001:
            warnings.append(f"Very low bid price: {df['bid'].min()}")
        if df['ask'].min() < 0.0001:
            warnings.append(f"Very low ask price: {df['ask'].min()}")
        
        if df['bid'].max() > 1000000:
            warnings.append(f"Very high bid price: {df['bid'].max()}")
        if df['ask'].max() > 1000000:
            warnings.append(f"Very high ask price: {df['ask'].max()}")
        
        # Check for outliers (> 3 sigma)
        bid_mean = df['bid'].mean()
        bid_std = df['bid'].std()
        bid_outliers = ((df['bid'] - bid_mean).abs() > 3 * bid_std).sum()
        
        if bid_outliers > len(df) * 0.001:  # > 0.1% outliers
            warnings.append(f"{bid_outliers} bid price outliers (> 3 sigma)")
        
        return {
            'passed': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }
    
    def validate_spreads(self, df: pd.DataFrame, symbol: str) -> Dict:
        """Validate spread statistics"""
        warnings = []
        
        df['spread'] = df['ask'] - df['bid']
        
        mean_spread = df['spread'].mean()
        std_spread = df['spread'].std()
        
        # Check spread outliers (> 5 sigma)
        spread_outliers = ((df['spread'] - mean_spread).abs() > 5 * std_spread).sum()
        
        if spread_outliers > len(df) * 0.001:  # > 0.1%
            warnings.append(f"{spread_outliers} spread outliers detected (> 5 sigma)")
        
        # Calculate spread in pips (assuming 5 decimal places for most pairs)
        # This is approximate - different pairs have different pip values
        mean_spread_pips = mean_spread * 10000 if 'JPY' not in symbol else mean_spread * 100
        
        return {
            'passed': True,
            'warnings': warnings,
            'stats': {
                'mean_spread': float(mean_spread),
                'std_spread': float(std_spread),
                'mean_spread_pips': float(mean_spread_pips),
                'min_spread': float(df['spread'].min()),
                'max_spread': float(df['spread'].max()),
                'spread_outliers': int(spread_outliers)
            }
        }
    
    def validate_gaps(self, df: pd.DataFrame, symbol: str) -> Dict:
        """Detect time gaps in data"""
        warnings = []
        
        # Calculate time differences
        df['time_diff'] = df['timestamp'].diff()
        
        # Gaps > 5 minutes during trading hours
        large_gaps = df[df['time_diff'] > timedelta(minutes=5)]
        
        if len(large_gaps) > 0:
            # Filter out weekend gaps (acceptable)
            weekday_gaps = large_gaps[large_gaps['timestamp'].dt.dayofweek < 5]
            
            if len(weekday_gaps) > 10:  # More than 10 gaps
                warnings.append(f"{len(weekday_gaps)} gaps > 5 minutes detected during weekdays")
        
        # Check for missing days
        date_range = pd.date_range(
            start=df['timestamp'].min().date(),
            end=df['timestamp'].max().date(),
            freq='D'
        )
        
        actual_days = df['timestamp'].dt.date.unique()
        missing_days = len(date_range) - len(actual_days)
        
        if missing_days > len(date_range) * 0.05:  # > 5% missing
            warnings.append(f"{missing_days} missing days ({missing_days/len(date_range)*100:.1f}%)")
        
        return {
            'passed': True,
            'warnings': warnings,
            'stats': {
                'large_gaps': int(len(large_gaps)),
                'weekday_gaps': int(len(large_gaps[large_gaps['timestamp'].dt.dayofweek < 5])),
                'missing_days': int(missing_days),
                'total_days': int(len(date_range))
            }
        }
    
    def validate_volume(self, df: pd.DataFrame, symbol: str) -> Dict:
        """Validate tick volume and distribution"""
        warnings = []
        
        # Group by hour and count ticks
        df['hour'] = df['timestamp'].dt.floor('H')
        ticks_per_hour = df.groupby('hour').size()
        
        mean_ticks = ticks_per_hour.mean()
        std_ticks = ticks_per_hour.std()
        
        # Hours with very low activity
        low_activity_hours = (ticks_per_hour < mean_ticks * 0.1).sum()
        
        if low_activity_hours > len(ticks_per_hour) * 0.1:  # > 10%
            warnings.append(f"{low_activity_hours} hours with very low activity")
        
        return {
            'passed': True,
            'warnings': warnings,
            'stats': {
                'mean_ticks_per_hour': float(mean_ticks),
                'std_ticks_per_hour': float(std_ticks),
                'min_ticks_per_hour': int(ticks_per_hour.min()),
                'max_ticks_per_hour': int(ticks_per_hour.max()),
                'low_activity_hours': int(low_activity_hours)
            }
        }
    
    def validate_file(self, file_path: Path, symbol: str, year: int) -> Dict:
        """Run all validation checks on a Parquet file"""
        logger.info(f"Validating {symbol}/{year}")
        
        try:
            df = self.load_parquet_file(file_path)
            
            # Run all validation checks
            basic_result = self.validate_basic(df, symbol, year)
            price_result = self.validate_prices(df, symbol)
            spread_result = self.validate_spreads(df, symbol)
            gap_result = self.validate_gaps(df, symbol)
            volume_result = self.validate_volume(df, symbol)
            
            # Aggregate results
            all_issues = (
                basic_result.get('issues', []) +
                price_result.get('issues', []) +
                spread_result.get('issues', []) +
                gap_result.get('issues', [])
            )
            
            all_warnings = (
                basic_result.get('warnings', []) +
                price_result.get('warnings', []) +
                spread_result.get('warnings', []) +
                gap_result.get('warnings', []) +
                volume_result.get('warnings', [])
            )
            
            passed = (
                basic_result['passed'] and
                price_result['passed'] and
                spread_result['passed']
            )
            
            result = {
                'file': file_path.name,
                'status': 'PASS' if passed and len(all_warnings) == 0 else 'WARN' if passed else 'FAIL',
                'total_ticks': len(df),
                'date_range': [
                    df['timestamp'].min().isoformat(),
                    df['timestamp'].max().isoformat()
                ],
                'issues': all_issues,
                'warnings': all_warnings,
                'statistics': {
                    **spread_result.get('stats', {}),
                    **gap_result.get('stats', {}),
                    **volume_result.get('stats', {})
                }
            }
            
            if passed:
                if all_warnings:
                    logger.warning(f"[PASS] {symbol}/{year}: PASS with {len(all_warnings)} warnings")
                else:
                    logger.info(f"[PASS] {symbol}/{year}: PASS")
            else:
                logger.error(f"[FAIL] {symbol}/{year}: FAIL - {len(all_issues)} issues")
            
            return result
        
        except Exception as e:
            logger.error(f"[ERROR] {symbol}/{year}: ERROR - {e}")
            return {
                'file': file_path.name,
                'status': 'ERROR',
                'error': str(e)
            }
    
    def validate_symbol(self, symbol_dir: Path, symbol: str) -> Dict:
        """Validate all Parquet files for a symbol"""
        logger.info(f"Validating symbol: {symbol}")
        
        parquet_files = sorted(symbol_dir.glob("*.parquet"))
        if not parquet_files:
            logger.warning(f"No Parquet files found for {symbol}")
            return {
                'symbol': symbol,
                'status': 'NO_DATA',
                'files': []
            }
        
        file_results = []
        total_ticks = 0
        all_issues = []
        all_warnings = []
        
        for parquet_file in parquet_files:
            try:
                year = int(parquet_file.stem)
            except ValueError:
                logger.warning(f"Skipping non-year file: {parquet_file.name}")
                continue
            
            result = self.validate_file(parquet_file, symbol, year)
            file_results.append(result)
            
            total_ticks += result.get('total_ticks', 0)
            all_issues.extend(result.get('issues', []))
            all_warnings.extend(result.get('warnings', []))
        
        # Overall status
        statuses = [r['status'] for r in file_results]
        if 'FAIL' in statuses or 'ERROR' in statuses:
            overall_status = 'FAIL'
        elif 'WARN' in statuses:
            overall_status = 'WARN'
        else:
            overall_status = 'PASS'
        
        return {
            'symbol': symbol,
            'status': overall_status,
            'total_files': len(file_results),
            'total_ticks': total_ticks,
            'issues_count': len(all_issues),
            'warnings_count': len(all_warnings),
            'files': file_results
        }


def discover_symbols(data_dir: Path) -> List[str]:
    """Discover available symbols in data directory"""
    symbols = []
    for symbol_dir in data_dir.iterdir():
        if symbol_dir.is_dir():
            # Check if it has Parquet files
            if list(symbol_dir.glob("*.parquet")):
                symbols.append(symbol_dir.name)
    
    return sorted(symbols)


def print_summary(results: Dict[str, Dict]):
    """Print validation summary"""
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    total_symbols = len(results)
    passed = sum(1 for r in results.values() if r['status'] == 'PASS')
    warned = sum(1 for r in results.values() if r['status'] == 'WARN')
    failed = sum(1 for r in results.values() if r['status'] in ['FAIL', 'ERROR'])
    
    print(f"Total Symbols: {total_symbols}")
    print(f"  PASS: {passed}")
    print(f"  WARN: {warned}")
    print(f"  FAIL: {failed}")
    print()
    
    # Per-symbol summary
    for symbol, result in sorted(results.items()):
        status_prefix = {
            'PASS': '[PASS]',
            'WARN': '[WARN]',
            'FAIL': '[FAIL]',
            'ERROR': '[ERR ]',
            'NO_DATA': '[NONE]'
        }
        
        prefix = status_prefix.get(result['status'], '[????]')
        ticks = result.get('total_ticks', 0)
        issues = result.get('issues_count', 0)
        warnings = result.get('warnings_count', 0)
        
        print(f"{prefix} {symbol}: {result['status']:8} | {ticks:>12,} ticks | {issues} issues, {warnings} warnings")
    
    print("=" * 80)


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Validate Dukascopy Parquet data files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate all data
  python validate_parquet_data.py --data-dir data/dukascopy

  # Specific pair
  python validate_parquet_data.py --data-dir data/dukascopy --pair EURUSD

  # Generate JSON report
  python validate_parquet_data.py --data-dir data/dukascopy --report validation_report.json

  # Summary only
  python validate_parquet_data.py --data-dir data/dukascopy --summary
        """
    )
    
    parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="Directory containing Parquet files (organized by symbol)",
    )
    parser.add_argument(
        "--pair",
        type=str,
        help="Validate specific pair only",
    )
    parser.add_argument(
        "--report",
        type=str,
        help="Output JSON report file path",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show summary only (no detailed output)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output",
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.summary:
        logging.getLogger().setLevel(logging.WARNING)
    
    # Check data directory
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return 1
    
    # Discover symbols
    if args.pair:
        symbols = [args.pair.upper()]
    else:
        symbols = discover_symbols(data_dir)
    
    if not symbols:
        logger.error(f"No symbols found in {data_dir}")
        return 1
    
    logger.info(f"Validating {len(symbols)} symbols: {', '.join(symbols)}")
    
    # Validate each symbol
    validator = ParquetValidator()
    results = {}
    
    for symbol in symbols:
        symbol_dir = data_dir / symbol
        if not symbol_dir.exists():
            logger.warning(f"Directory not found: {symbol}")
            results[symbol] = {
                'symbol': symbol,
                'status': 'NO_DATA'
            }
            continue
        
        results[symbol] = validator.validate_symbol(symbol_dir, symbol)
    
    # Print summary
    print_summary(results)
    
    # Save report if requested
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        report_data = {
            'validated_at': datetime.now().isoformat(),
            'data_dir': str(data_dir),
            'symbols': results
        }
        
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        logger.info(f"Report saved to: {report_path}")
    
    # Return error code if any failures
    failed_count = sum(1 for r in results.values() if r['status'] in ['FAIL', 'ERROR'])
    if failed_count > 0:
        logger.error(f"{failed_count} symbols failed validation")
        return 1
    
    warned_count = sum(1 for r in results.values() if r['status'] == 'WARN')
    if warned_count > 0:
        logger.warning(f"{warned_count} symbols have warnings")
    
    logger.info("[SUCCESS] Validation complete")
    return 0


if __name__ == "__main__":
    exit(main())
