"""
Analyze file size growth pattern from logs and parquet file
"""
import pandas as pd
import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

def parse_log_file(log_path: str) -> List[Dict]:
    """Parse log file to extract file size growth timestamps"""
    growth_points = []
    
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            # Match lines like: "2026-01-18 18:09:09,635 - dukascopy_backfill - DEBUG - [EURUSD] File growing: 4.37 MB (silent progress)"
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*File growing: ([\d.]+) MB', line)
            if match:
                timestamp_str = match.group(1)
                size_mb = float(match.group(2))
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                growth_points.append({
                    'timestamp': timestamp,
                    'size_mb': size_mb
                })
    
    return growth_points

def analyze_parquet_file(parquet_path: str) -> Dict:
    """Analyze the parquet file to get current stats"""
    df = pd.read_parquet(parquet_path)
    file_size_mb = os.path.getsize(parquet_path) / (1024 * 1024)
    
    # Get date range
    if 'timestamp' in df.columns:
        min_date = df['timestamp'].min()
        max_date = df['timestamp'].max()
        date_range = max_date - min_date
        days = date_range.total_seconds() / 86400
    else:
        min_date = df.index.min() if hasattr(df.index, 'min') else None
        max_date = df.index.max() if hasattr(df.index, 'max') else None
        if min_date and max_date:
            date_range = max_date - min_date
            days = date_range.total_seconds() / 86400
        else:
            days = None
    
    return {
        'rows': len(df),
        'file_size_mb': file_size_mb,
        'min_date': min_date,
        'max_date': max_date,
        'days': days,
        'columns': list(df.columns),
        'memory_size_mb': df.memory_usage(deep=True).sum() / (1024 * 1024)
    }

def calculate_growth_rate(growth_points: List[Dict], parquet_stats: Dict) -> Dict:
    """Calculate growth rate and create formula"""
    # Use parquet file stats for calculation (most accurate)
    if parquet_stats['days'] and parquet_stats['days'] > 0:
        # Calculate MB per day
        mb_per_day = parquet_stats['file_size_mb'] / parquet_stats['days']
        
        # Calculate ticks per day
        ticks_per_day = parquet_stats['rows'] / parquet_stats['days']
        
        # Calculate bytes per tick
        bytes_per_tick = (parquet_stats['file_size_mb'] * 1024 * 1024) / parquet_stats['rows']
        
        # If we have growth points, also calculate from logs
        mb_per_hour_from_logs = None
        if len(growth_points) >= 2:
            growth_points_sorted = sorted(growth_points, key=lambda x: x['timestamp'])
            first_point = growth_points_sorted[0]
            last_point = growth_points_sorted[-1]
            time_diff = (last_point['timestamp'] - first_point['timestamp']).total_seconds() / 3600
            size_diff = last_point['size_mb'] - first_point['size_mb']
            mb_per_hour_from_logs = size_diff / time_diff if time_diff > 0 else None
        
        return {
            'growth_rate_mb_per_hour': mb_per_hour_from_logs,
            'growth_rate_mb_per_day': mb_per_day,
            'ticks_per_day': ticks_per_day,
            'bytes_per_tick': bytes_per_tick,
            'compression_ratio': parquet_stats['memory_size_mb'] / parquet_stats['file_size_mb'] if parquet_stats['file_size_mb'] > 0 else 0,
            'formula': {
                'size_mb': f"{mb_per_day:.4f} * days",
                'size_gb': f"{mb_per_day / 1024:.6f} * days",
                'estimated_ticks': f"{ticks_per_day:.0f} * days"
            }
        }
    
    return {'error': 'Could not calculate growth rate - no date range in parquet file'}

def main():
    # Paths
    log_path = Path('logs/run-dukascopy.log')
    parquet_path = Path('data/dukascopy/EURUSD/2024.parquet')
    
    print("=" * 80)
    print("DUKASCOPY FILE SIZE GROWTH ANALYSIS")
    print("=" * 80)
    print()
    
    # Analyze parquet file
    print("1. Analyzing Parquet File...")
    print("-" * 80)
    if not parquet_path.exists():
        print(f"ERROR: Parquet file not found at {parquet_path}")
        return
    
    parquet_stats = analyze_parquet_file(str(parquet_path))
    print(f"File: {parquet_path}")
    print(f"  Rows (ticks): {parquet_stats['rows']:,}")
    print(f"  File size: {parquet_stats['file_size_mb']:.2f} MB")
    print(f"  Memory size (uncompressed): {parquet_stats['memory_size_mb']:.2f} MB")
    print(f"  Compression ratio: {parquet_stats['memory_size_mb'] / parquet_stats['file_size_mb']:.2f}x")
    print(f"  Date range: {parquet_stats['min_date']} to {parquet_stats['max_date']}")
    print(f"  Days covered: {parquet_stats['days']:.2f}")
    print(f"  Columns: {', '.join(parquet_stats['columns'])}")
    print()
    
    # Parse log file
    print("2. Parsing Log File for Growth Points...")
    print("-" * 80)
    if not log_path.exists():
        print(f"WARNING: Log file not found at {log_path}")
        growth_points = []
    else:
        growth_points = parse_log_file(str(log_path))
        print(f"Found {len(growth_points)} growth points in log")
        if growth_points:
            print(f"  First: {growth_points[0]['timestamp']} - {growth_points[0]['size_mb']:.2f} MB")
            print(f"  Last: {growth_points[-1]['timestamp']} - {growth_points[-1]['size_mb']:.2f} MB")
    print()
    
    # Calculate growth rate
    print("3. Calculating Growth Rate and Formula...")
    print("-" * 80)
    growth_rate = calculate_growth_rate(growth_points, parquet_stats)
    
    if 'error' not in growth_rate:
        print(f"Growth Rate: {growth_rate['growth_rate_mb_per_day']:.4f} MB/day")
        if growth_rate['growth_rate_mb_per_hour']:
            print(f"Growth Rate (from logs): {growth_rate['growth_rate_mb_per_hour']:.4f} MB/hour")
        print(f"Ticks per day: {growth_rate['ticks_per_day']:,.0f}")
        print(f"Bytes per tick: {growth_rate['bytes_per_tick']:.2f} bytes")
        print(f"Compression ratio: {growth_rate['compression_ratio']:.2f}x")
        print()
        print("ESTIMATION FORMULAS:")
        print("-" * 80)
        print(f"File Size (MB) = {growth_rate['formula']['size_mb']}")
        print(f"File Size (GB) = {growth_rate['formula']['size_gb']}")
        print(f"Estimated Ticks = {growth_rate['formula']['estimated_ticks']}")
        print()
        
        # Example calculations
        print("EXAMPLE ESTIMATIONS:")
        print("-" * 80)
        for days in [1, 7, 30, 90, 365]:
            size_mb = growth_rate['growth_rate_mb_per_day'] * days
            size_gb = size_mb / 1024
            ticks = growth_rate['ticks_per_day'] * days
            print(f"  {days:3d} days: {size_mb:8.2f} MB ({size_gb:6.2f} GB) - ~{ticks:,.0f} ticks")
        
        # Calculate for full year
        print()
        print("FULL YEAR ESTIMATION (2024):")
        print("-" * 80)
        year_days = 366  # 2024 is a leap year
        year_size_mb = growth_rate['growth_rate_mb_per_day'] * year_days
        year_size_gb = year_size_mb / 1024
        year_ticks = growth_rate['ticks_per_day'] * year_days
        print(f"  Full year ({year_days} days): {year_size_mb:8.2f} MB ({year_size_gb:6.2f} GB) - ~{year_ticks:,.0f} ticks")
    else:
        print(f"ERROR: {growth_rate['error']}")
    
    print()
    print("=" * 80)

if __name__ == '__main__':
    main()
