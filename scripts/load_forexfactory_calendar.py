"""
Load ForexFactory Economic Calendar from Hugging Face Dataset
Downloads and loads historical economic calendar data (2007-2025) into database
"""

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from datetime import datetime
import os
import sys
import argparse
from typing import Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'trading_server', 'src'))
from utils.logging_config import get_logger

logger = get_logger("forexfactory_loader", "forexfactory_loader.log")

# Hugging Face dataset URL
DATASET_URL = "https://huggingface.co/datasets/Ehsanrs2/Forex_Factory_Calendar/resolve/main/data.csv"


class ForexFactoryLoader:
    """Loads ForexFactory economic calendar data into database"""
    
    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.conn = None
    
    def connect_db(self):
        """Connect to PostgreSQL/TimescaleDB"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            logger.info("Connected to database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def disconnect_db(self):
        """Disconnect from database"""
        if self.conn:
            self.conn.close()
            logger.info("Disconnected from database")
    
    def download_dataset(self, cache_file: str = None) -> pd.DataFrame:
        """Download ForexFactory dataset from Hugging Face"""
        
        # Check if cached file exists
        if cache_file and os.path.exists(cache_file):
            logger.info(f"Loading cached dataset from {cache_file}")
            df = pd.read_csv(cache_file)
            logger.info(f"Loaded {len(df)} events from cache")
            return df
        
        logger.info("Downloading ForexFactory calendar dataset from Hugging Face...")
        logger.info(f"URL: {DATASET_URL}")
        
        try:
            df = pd.read_csv(DATASET_URL)
            logger.info(f"Downloaded {len(df)} calendar events")
            
            # Cache for future use
            if cache_file:
                df.to_csv(cache_file, index=False)
                logger.info(f"Cached dataset to {cache_file}")
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to download dataset: {e}")
            raise
    
    def transform_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform and clean the dataset"""
        
        logger.info("Transforming data...")
        
        # Parse DateTime column
        df['DateTime'] = pd.to_datetime(df['DateTime'], errors='coerce')
        
        # Remove rows with invalid timestamps
        before_count = len(df)
        df = df.dropna(subset=['DateTime'])
        after_count = len(df)
        
        if before_count > after_count:
            logger.warning(f"Removed {before_count - after_count} rows with invalid timestamps")
        
        # Standardize impact values
        impact_map = {
            'Low': 'LOW',
            'Medium': 'MEDIUM',
            'High': 'HIGH',
            'low': 'LOW',
            'medium': 'MEDIUM',
            'high': 'HIGH',
        }
        df['Impact'] = df['Impact'].map(impact_map).fillna('MEDIUM')
        
        # Convert numeric columns
        for col in ['Actual', 'Forecast', 'Previous']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Ensure Currency column exists
        if 'Currency' not in df.columns:
            logger.warning("Currency column not found. Using empty values.")
            df['Currency'] = None
        
        # Ensure Event column exists
        if 'Event' not in df.columns:
            logger.error("Event column not found. Cannot proceed.")
            raise ValueError("Event column is required")
        
        logger.info(f"Transformed {len(df)} events")
        return df
    
    def load_to_database(self, df: pd.DataFrame, batch_size: int = 1000):
        """Load calendar events into database"""
        
        logger.info(f"Loading {len(df)} events into database...")
        
        cursor = self.conn.cursor()
        
        # Prepare data in batches
        total_inserted = 0
        total_skipped = 0
        
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size]
            
            data = []
            for _, row in batch.iterrows():
                try:
                    data.append((
                        row['DateTime'],
                        row.get('Currency'),  # country
                        row.get('Currency'),  # currency
                        row.get('Event'),
                        row.get('Impact'),
                        row.get('Actual'),
                        row.get('Forecast'),
                        row.get('Previous'),
                        'forexfactory',
                        datetime.now()
                    ))
                except Exception as e:
                    logger.warning(f"Error preparing row: {e}")
                    continue
            
            if not data:
                continue
            
            # Bulk insert
            query = """
                INSERT INTO economic_calendar 
                    (timestamp, country, currency, event, impact, actual, forecast, previous, source, receive_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (timestamp, event, country, source) DO NOTHING
            """
            
            try:
                execute_batch(cursor, query, data, page_size=1000)
                self.conn.commit()
                
                # Get number of inserted rows (approximate)
                inserted = len(data)
                total_inserted += inserted
                
                logger.info(f"  Batch {i//batch_size + 1}: Inserted ~{inserted} events (total: {total_inserted})")
                
            except Exception as e:
                logger.error(f"Error inserting batch: {e}")
                self.conn.rollback()
                total_skipped += len(data)
        
        cursor.close()
        
        logger.info(f"✓ Load completed: {total_inserted} events inserted, {total_skipped} skipped")
        
        return total_inserted, total_skipped
    
    def verify_data(self):
        """Verify loaded data"""
        
        logger.info("Verifying loaded data...")
        
        cursor = self.conn.cursor()
        
        # Check total count
        cursor.execute("SELECT COUNT(*) FROM economic_calendar WHERE source = 'forexfactory'")
        total = cursor.fetchone()[0]
        logger.info(f"  Total events: {total}")
        
        # Check date range
        cursor.execute("""
            SELECT MIN(timestamp), MAX(timestamp) 
            FROM economic_calendar 
            WHERE source = 'forexfactory'
        """)
        earliest, latest = cursor.fetchone()
        logger.info(f"  Date range: {earliest} to {latest}")
        
        # Check currency distribution
        cursor.execute("""
            SELECT currency, COUNT(*) as count
            FROM economic_calendar
            WHERE source = 'forexfactory'
            GROUP BY currency
            ORDER BY count DESC
            LIMIT 10
        """)
        logger.info("  Top currencies:")
        for currency, count in cursor.fetchall():
            logger.info(f"    {currency}: {count} events")
        
        # Check impact distribution
        cursor.execute("""
            SELECT impact, COUNT(*) as count
            FROM economic_calendar
            WHERE source = 'forexfactory'
            GROUP BY impact
            ORDER BY count DESC
        """)
        logger.info("  Impact distribution:")
        for impact, count in cursor.fetchall():
            logger.info(f"    {impact}: {count} events")
        
        cursor.close()


def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(description='Load ForexFactory economic calendar')
    parser.add_argument('--cache-file', type=str, default='forexfactory_calendar.csv',
                       help='Cache file path for downloaded dataset')
    parser.add_argument('--batch-size', type=int, default=1000,
                       help='Batch size for database inserts')
    parser.add_argument('--db-host', type=str, default='localhost',
                       help='Database host')
    parser.add_argument('--db-port', type=int, default=5432,
                       help='Database port')
    parser.add_argument('--db-name', type=str, default='db_forex',
                       help='Database name')
    parser.add_argument('--db-user', type=str, default='forex_user',
                       help='Database user')
    parser.add_argument('--skip-download', action='store_true',
                       help='Skip download and use cached file only')
    
    args = parser.parse_args()
    
    # Database config
    db_password = os.getenv('POSTGRES_PASSWORD')
    if not db_password:
        logger.error("POSTGRES_PASSWORD environment variable not set")
        return 1
    
    db_config = {
        'host': args.db_host,
        'port': args.db_port,
        'database': args.db_name,
        'user': args.db_user,
        'password': db_password
    }
    
    try:
        loader = ForexFactoryLoader(db_config)
        loader.connect_db()
        
        # Download dataset
        if args.skip_download:
            if not os.path.exists(args.cache_file):
                logger.error(f"Cache file {args.cache_file} not found and --skip-download specified")
                return 1
            logger.info(f"Using cached file: {args.cache_file}")
            df = pd.read_csv(args.cache_file)
        else:
            df = loader.download_dataset(cache_file=args.cache_file)
        
        # Transform data
        df = loader.transform_data(df)
        
        # Load to database
        inserted, skipped = loader.load_to_database(df, batch_size=args.batch_size)
        
        # Verify
        loader.verify_data()
        
        loader.disconnect_db()
        
        logger.info("\n" + "=" * 80)
        logger.info("FOREXFACTORY CALENDAR LOAD COMPLETED SUCCESSFULLY")
        logger.info(f"Total events: {len(df)}")
        logger.info(f"Inserted: {inserted}")
        logger.info(f"Skipped: {skipped}")
        logger.info("=" * 80)
        
        return 0
        
    except Exception as e:
        logger.error(f"Load failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
