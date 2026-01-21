"""
Alternative Data Backfill Orchestrator
Coordinates backfill from all alternative data sources (FRED, ECB, World Bank)
"""

import sys
import os

# Add trading_server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'trading_server', 'src'))

from datetime import datetime, timedelta
from typing import Dict, Optional
import psycopg2
from psycopg2.extras import execute_batch
import argparse

from connectors.fred_connector import FREDConnector
from connectors.ecb_connector import ECBConnector
from connectors.world_bank_connector import WorldBankConnector
from connectors.base import ConnectorConfig
from utils.logging_config import get_logger

logger = get_logger("alternative_data_backfill", "alternative_data_backfill.log")


class AlternativeDataBackfiller:
    """Orchestrates backfill from multiple alternative data sources"""
    
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
    
    def backfill_fred(self, start_date: datetime, end_date: datetime):
        """Backfill FRED economic indicators"""
        
        logger.info("=" * 80)
        logger.info("BACKFILLING FRED (US ECONOMIC INDICATORS)")
        logger.info(f"Period: {start_date.date()} to {end_date.date()}")
        logger.info("=" * 80)
        
        fred_config = ConnectorConfig(name="fred", enabled=True, extra_config={})
        fred = FREDConnector(fred_config)
        
        if not fred.connect():
            logger.error("Failed to connect to FRED API. Check FRED_API_KEY environment variable.")
            return
        
        self._log_backfill_status('economic_indicator', 'FRED', start_date, end_date, 'in_progress')
        
        try:
            rows_inserted = 0
            rows_rejected = 0
            
            for event in fred.backfill(start_date, end_date):
                try:
                    self._insert_economic_indicator(event)
                    rows_inserted += 1
                    
                    if rows_inserted % 100 == 0:
                        logger.info(f"  FRED: Inserted {rows_inserted} indicators...")
                        
                except Exception as e:
                    rows_rejected += 1
                    logger.warning(f"  Failed to insert indicator: {e}")
            
            self._log_backfill_status('economic_indicator', 'FRED', start_date, end_date, 
                                     'completed', rows_inserted=rows_inserted, rows_rejected=rows_rejected)
            logger.info(f"✓ FRED backfill completed: {rows_inserted} inserted, {rows_rejected} rejected")
            
        except Exception as e:
            self._log_backfill_status('economic_indicator', 'FRED', start_date, end_date, 
                                     'failed', error_message=str(e))
            logger.error(f"✗ FRED backfill failed: {e}", exc_info=True)
        finally:
            fred.disconnect()
    
    def backfill_ecb(self, start_date: datetime, end_date: datetime):
        """Backfill ECB economic indicators"""
        
        logger.info("=" * 80)
        logger.info("BACKFILLING ECB (EUROZONE ECONOMIC INDICATORS)")
        logger.info(f"Period: {start_date.date()} to {end_date.date()}")
        logger.info("=" * 80)
        
        ecb_config = ConnectorConfig(name="ecb", enabled=True, extra_config={})
        ecb = ECBConnector(ecb_config)
        
        if not ecb.connect():
            logger.error("Failed to connect to ECB API")
            return
        
        self._log_backfill_status('economic_indicator', 'ECB', start_date, end_date, 'in_progress')
        
        try:
            rows_inserted = 0
            rows_rejected = 0
            
            for event in ecb.backfill(start_date, end_date):
                try:
                    self._insert_economic_indicator(event)
                    rows_inserted += 1
                    
                    if rows_inserted % 50 == 0:
                        logger.info(f"  ECB: Inserted {rows_inserted} indicators...")
                        
                except Exception as e:
                    rows_rejected += 1
                    logger.warning(f"  Failed to insert indicator: {e}")
            
            self._log_backfill_status('economic_indicator', 'ECB', start_date, end_date, 
                                     'completed', rows_inserted=rows_inserted, rows_rejected=rows_rejected)
            logger.info(f"✓ ECB backfill completed: {rows_inserted} inserted, {rows_rejected} rejected")
            
        except Exception as e:
            self._log_backfill_status('economic_indicator', 'ECB', start_date, end_date, 
                                     'failed', error_message=str(e))
            logger.error(f"✗ ECB backfill failed: {e}", exc_info=True)
        finally:
            ecb.disconnect()
    
    def backfill_world_bank(self, start_date: datetime, end_date: datetime):
        """Backfill World Bank economic indicators"""
        
        logger.info("=" * 80)
        logger.info("BACKFILLING WORLD BANK (GLOBAL ECONOMIC INDICATORS)")
        logger.info(f"Period: {start_date.date()} to {end_date.date()}")
        logger.info("=" * 80)
        
        wb_config = ConnectorConfig(name="world_bank", enabled=True, extra_config={})
        wb = WorldBankConnector(wb_config)
        
        if not wb.connect():
            logger.error("Failed to connect to World Bank API. Check wbdata library installation.")
            return
        
        self._log_backfill_status('economic_indicator', 'WORLD_BANK', start_date, end_date, 'in_progress')
        
        try:
            rows_inserted = 0
            rows_rejected = 0
            
            for event in wb.backfill(start_date, end_date):
                try:
                    self._insert_economic_indicator(event)
                    rows_inserted += 1
                    
                    if rows_inserted % 50 == 0:
                        logger.info(f"  World Bank: Inserted {rows_inserted} indicators...")
                        
                except Exception as e:
                    rows_rejected += 1
                    logger.warning(f"  Failed to insert indicator: {e}")
            
            self._log_backfill_status('economic_indicator', 'WORLD_BANK', start_date, end_date, 
                                     'completed', rows_inserted=rows_inserted, rows_rejected=rows_rejected)
            logger.info(f"✓ World Bank backfill completed: {rows_inserted} inserted, {rows_rejected} rejected")
            
        except Exception as e:
            self._log_backfill_status('economic_indicator', 'WORLD_BANK', start_date, end_date, 
                                     'failed', error_message=str(e))
            logger.error(f"✗ World Bank backfill failed: {e}", exc_info=True)
        finally:
            wb.disconnect()
    
    def _insert_economic_indicator(self, event: Dict):
        """Insert economic indicator into database"""
        
        cursor = self.conn.cursor()
        
        query = """
            INSERT INTO economic_indicators 
                (timestamp, series_id, value, source, country, frequency, receive_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (timestamp, series_id, source) DO NOTHING
        """
        
        cursor.execute(query, (
            event['timestamp'],
            event['series_id'],
            event['value'],
            event['source'],
            event.get('country'),
            event.get('frequency'),
            event.get('receive_time', datetime.now())
        ))
        
        self.conn.commit()
        cursor.close()
    
    def _log_backfill_status(self, data_type, source, start_date, end_date, status, 
                            rows_inserted=None, rows_rejected=None, error_message=None):
        """Log backfill progress"""
        
        cursor = self.conn.cursor()
        
        query = """
            INSERT INTO alternative_data_backfill_status 
                (data_type, source, start_date, end_date, status, 
                 rows_inserted, rows_rejected, error_message, completed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (data_type, source, start_date, end_date) 
            DO UPDATE SET 
                status = EXCLUDED.status,
                rows_inserted = EXCLUDED.rows_inserted,
                rows_rejected = EXCLUDED.rows_rejected,
                error_message = EXCLUDED.error_message,
                completed_at = EXCLUDED.completed_at
        """
        
        completed_at = datetime.now() if status in ['completed', 'failed'] else None
        
        cursor.execute(query, (
            data_type, source, start_date, end_date, status,
            rows_inserted, rows_rejected, error_message, completed_at
        ))
        
        self.conn.commit()
        cursor.close()
    
    def backfill_all(self, start_date: datetime, end_date: datetime, sources: list = None):
        """Backfill all alternative data sources"""
        
        if sources is None:
            sources = ['fred', 'ecb', 'world_bank']
        
        logger.info("=" * 80)
        logger.info("ALTERNATIVE DATA BACKFILL - MASTER ORCHESTRATOR")
        logger.info(f"Period: {start_date.date()} to {end_date.date()}")
        logger.info(f"Sources: {', '.join(sources)}")
        logger.info("=" * 80)
        
        start_time = datetime.now()
        
        # Backfill each source
        if 'fred' in sources:
            self.backfill_fred(start_date, end_date)
        
        if 'ecb' in sources:
            self.backfill_ecb(start_date, end_date)
        
        if 'world_bank' in sources:
            self.backfill_world_bank(start_date, end_date)
        
        # Print summary
        elapsed = datetime.now() - start_time
        logger.info("=" * 80)
        logger.info("BACKFILL SUMMARY")
        logger.info(f"Total time: {elapsed}")
        logger.info("=" * 80)
        
        self._print_summary()
    
    def _print_summary(self):
        """Print backfill summary"""
        
        cursor = self.conn.cursor()
        
        query = """
            SELECT 
                data_type,
                source,
                status,
                rows_inserted,
                rows_rejected,
                ROUND(rows_rejected::NUMERIC / NULLIF(rows_inserted + rows_rejected, 0) * 100, 2) as rejection_rate_pct,
                completed_at - created_at as duration
            FROM alternative_data_backfill_status
            ORDER BY completed_at DESC
            LIMIT 10
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        if results:
            logger.info("\nRecent backfill jobs:")
            logger.info("-" * 120)
            logger.info(f"{'Data Type':<20} {'Source':<15} {'Status':<12} {'Inserted':<10} {'Rejected':<10} {'Rej %':<8} {'Duration':<15}")
            logger.info("-" * 120)
            
            for row in results:
                data_type, source, status, inserted, rejected, rej_pct, duration = row
                logger.info(f"{data_type:<20} {source:<15} {status:<12} {inserted or 0:<10} {rejected or 0:<10} {rej_pct or 0:<8} {str(duration) if duration else 'N/A':<15}")
            
            logger.info("-" * 120)
        
        # Print data statistics
        query = """
            SELECT 
                source,
                COUNT(*) as total_indicators,
                COUNT(DISTINCT series_id) as unique_series,
                MIN(timestamp) as earliest,
                MAX(timestamp) as latest
            FROM economic_indicators
            GROUP BY source
            ORDER BY source
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        if results:
            logger.info("\nEconomic Indicators in Database:")
            logger.info("-" * 100)
            logger.info(f"{'Source':<15} {'Total':<10} {'Series':<10} {'Earliest':<25} {'Latest':<25}")
            logger.info("-" * 100)
            
            for row in results:
                source, total, series, earliest, latest = row
                logger.info(f"{source:<15} {total:<10} {series:<10} {str(earliest):<25} {str(latest):<25}")
            
            logger.info("-" * 100)
        
        cursor.close()


def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(description='Backfill alternative data sources')
    parser.add_argument('--start', type=str, required=True, 
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, required=True, 
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--sources', type=str, default='fred,ecb,world_bank',
                       help='Comma-separated list of sources (fred,ecb,world_bank)')
    parser.add_argument('--db-host', type=str, default='localhost',
                       help='Database host')
    parser.add_argument('--db-port', type=int, default=5432,
                       help='Database port')
    parser.add_argument('--db-name', type=str, default='db_forex',
                       help='Database name')
    parser.add_argument('--db-user', type=str, default='forex_user',
                       help='Database user')
    
    args = parser.parse_args()
    
    # Parse dates
    try:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        logger.error("Use YYYY-MM-DD format (e.g., 2020-01-01)")
        return 1
    
    # Validate date range
    if start_date >= end_date:
        logger.error("Start date must be before end date")
        return 1
    
    if end_date > datetime.now():
        logger.warning("End date is in the future. Adjusting to current date.")
        end_date = datetime.now()
    
    # Parse sources
    sources = [s.strip().lower() for s in args.sources.split(',')]
    valid_sources = ['fred', 'ecb', 'world_bank']
    invalid_sources = [s for s in sources if s not in valid_sources]
    
    if invalid_sources:
        logger.error(f"Invalid sources: {invalid_sources}")
        logger.error(f"Valid sources: {valid_sources}")
        return 1
    
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
    
    # Check API keys
    if 'fred' in sources:
        if not os.getenv('FRED_API_KEY'):
            logger.warning("FRED_API_KEY not set. FRED backfill will be skipped.")
            sources.remove('fred')
    
    if not sources:
        logger.error("No valid sources to backfill")
        return 1
    
    # Run backfill
    try:
        backfiller = AlternativeDataBackfiller(db_config)
        backfiller.connect_db()
        
        backfiller.backfill_all(start_date, end_date, sources)
        
        backfiller.disconnect_db()
        
        logger.info("\n✓ All backfill operations completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
