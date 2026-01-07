#!/usr/bin/env python
"""
Export data from database for DVC versioning.

Usage:
    python scripts/export-data.py --type ticks --output data/raw/ticks.parquet
    python scripts/export-data.py --type calendar --output data/raw/calendar.parquet
    python scripts/export-data.py --type ticks --output data/raw/ticks.parquet --days 90
"""

import argparse
import os
import sys
import json
import hashlib
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src/trading_server/src'))

try:
    import pandas as pd
except ImportError:
    print("pandas required. Install with: pip install pandas")
    sys.exit(1)


def get_database_connection():
    """Get database connection"""
    try:
        from database import Database
        return Database()
    except ImportError:
        print("Database module not found. Using mock data for testing.")
        return None


def auto_version_export(output_path: str, metadata: dict) -> None:
    """
    Automatically version exported data with DVC.
    
    Args:
        output_path: Path to the exported file
        metadata: Metadata dictionary from export
    """
    try:
        from mlops.data_versioner import DataVersioner
        versioner = DataVersioner()
        
        if versioner._dvc_available:
            # Add to DVC tracking
            dvc_file = versioner.add(output_path)
            print(f"Added to DVC tracking: {dvc_file}")
            
            # Optionally push to remote (commented out for now)
            # versioner.push()
        else:
            print("DVC not available - skipping versioning")
    except Exception as e:
        print(f"Warning: Failed to version with DVC: {e}")


def export_ticks(db, output_path: str, days: int = 30) -> dict:
    """
    Export tick data to parquet format.
    
    Args:
        db: Database connection
        output_path: Output file path
        days: Number of days of data to export
        
    Returns:
        Metadata dictionary
    """
    print(f"Exporting {days} days of tick data...")
    
    if db is None:
        # Create mock data for testing
        print("Using mock data (no database connection)")
        df = pd.DataFrame({
            'symbol': ['EURUSD'] * 1000,
            'datetime': pd.date_range(end=datetime.now(), periods=1000, freq='1min'),
            'bid': [1.0850 + 0.0001 * i for i in range(1000)],
            'ask': [1.0851 + 0.0001 * i for i in range(1000)],
            'volume': [100] * 1000
        })
    else:
        # Query ticks from database
        query = """
            SELECT symbol, datetime, bid, ask, volume
            FROM ticks_forex
            WHERE datetime >= DATE_SUB(NOW(), INTERVAL %s DAY)
            ORDER BY datetime
        """
        
        try:
            df = db.query_to_dataframe(query, (days,))
        except Exception as e:
            print(f"Error querying database: {e}")
            print("Using empty DataFrame")
            df = pd.DataFrame(columns=['symbol', 'datetime', 'bid', 'ask', 'volume'])
    
    # Ensure output directory exists
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save to parquet
    df.to_parquet(output_path, index=False, compression='snappy')
    
    # Generate hash for versioning
    file_hash = hashlib.md5(open(output_path, 'rb').read()).hexdigest()[:8]
    
    # Create metadata
    metadata = {
        'export_date': datetime.now().isoformat(),
        'export_type': 'ticks',
        'row_count': len(df),
        'date_range': {
            'start': df['datetime'].min().isoformat() if len(df) > 0 else None,
            'end': df['datetime'].max().isoformat() if len(df) > 0 else None,
        },
        'symbols': df['symbol'].unique().tolist() if len(df) > 0 else [],
        'file_size_bytes': output_path.stat().st_size,
        'hash': file_hash,
        'days_requested': days
    }
    
    # Save metadata
    metadata_path = output_path.with_suffix('.metadata.json')
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Exported {len(df)} rows to {output_path}")
    print(f"Metadata saved to {metadata_path}")
    
    # Auto-version with DVC
    auto_version_export(str(output_path), metadata)
    
    return metadata


def export_calendar(db, output_path: str, days: int = 90) -> dict:
    """
    Export economic calendar data to parquet format.
    
    Args:
        db: Database connection
        output_path: Output file path
        days: Number of days of data to export
        
    Returns:
        Metadata dictionary
    """
    print(f"Exporting {days} days of economic calendar data...")
    
    if db is None:
        # Create mock data for testing
        print("Using mock data (no database connection)")
        df = pd.DataFrame({
            'datetime': pd.date_range(end=datetime.now(), periods=100, freq='1D'),
            'event': ['Test Event'] * 100,
            'currency': ['USD'] * 50 + ['EUR'] * 50,
            'impact': ['High'] * 30 + ['Medium'] * 40 + ['Low'] * 30,
            'actual': [0.5] * 100,
            'forecast': [0.4] * 100,
            'previous': [0.3] * 100
        })
    else:
        # Query calendar from database
        query = """
            SELECT *
            FROM economic_calendar
            WHERE datetime >= DATE_SUB(NOW(), INTERVAL %s DAY)
            ORDER BY datetime
        """
        
        try:
            df = db.query_to_dataframe(query, (days,))
        except Exception as e:
            print(f"Error querying database: {e}")
            print("Using empty DataFrame")
            df = pd.DataFrame()
    
    # Ensure output directory exists
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save to parquet
    df.to_parquet(output_path, index=False, compression='snappy')
    
    # Generate hash
    file_hash = hashlib.md5(open(output_path, 'rb').read()).hexdigest()[:8]
    
    # Create metadata
    metadata = {
        'export_date': datetime.now().isoformat(),
        'export_type': 'calendar',
        'row_count': len(df),
        'date_range': {
            'start': df['datetime'].min().isoformat() if len(df) > 0 and 'datetime' in df else None,
            'end': df['datetime'].max().isoformat() if len(df) > 0 and 'datetime' in df else None,
        },
        'file_size_bytes': output_path.stat().st_size,
        'hash': file_hash,
        'days_requested': days
    }
    
    # Save metadata
    metadata_path = output_path.with_suffix('.metadata.json')
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Exported {len(df)} rows to {output_path}")
    
    # Auto-version with DVC
    auto_version_export(str(output_path), metadata)
    
    return metadata


def main():
    parser = argparse.ArgumentParser(
        description="Export data from database for DVC versioning"
    )
    parser.add_argument(
        "--type",
        choices=["ticks", "calendar"],
        required=True,
        help="Type of data to export"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output file path (parquet format)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days of data to export (default: 30)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually exporting"
    )
    
    args = parser.parse_args()
    
    if args.dry_run:
        print(f"Would export {args.days} days of {args.type} data to {args.output}")
        return
    
    db = get_database_connection()
    
    if args.type == "ticks":
        metadata = export_ticks(db, args.output, args.days)
    else:
        metadata = export_calendar(db, args.output, args.days)
    
    print(f"\nExport complete: {json.dumps(metadata, indent=2)}")


if __name__ == "__main__":
    main()
