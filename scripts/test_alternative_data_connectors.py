"""
Test Alternative Data Connectors
Verifies that all alternative data connectors work correctly
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'trading_server', 'src'))

from datetime import datetime, timedelta
from connectors.fred_connector import FREDConnector
from connectors.ecb_connector import ECBConnector
from connectors.world_bank_connector import WorldBankConnector
from connectors.base import ConnectorConfig
from utils.logging_config import get_logger

logger = get_logger("test_connectors", "test_connectors.log")


def test_fred():
    """Test FRED connector"""
    
    logger.info("=" * 80)
    logger.info("TESTING FRED CONNECTOR")
    logger.info("=" * 80)
    
    config = ConnectorConfig(name="fred", enabled=True, extra_config={})
    connector = FREDConnector(config)
    
    # Test connection
    if not connector.connect():
        logger.error("✗ FRED connection failed")
        logger.error("  Check FRED_API_KEY environment variable")
        logger.error("  Get free API key from: https://fred.stlouisfed.org/")
        return False
    
    logger.info("✓ FRED connection successful")
    
    # Test available range
    try:
        earliest, latest = connector.get_available_range()
        logger.info(f"✓ Available range: {earliest.date()} to {latest.date()}")
    except Exception as e:
        logger.error(f"✗ Failed to get available range: {e}")
        return False
    
    # Test backfill (1 month)
    try:
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        
        logger.info(f"Testing backfill: {start.date()} to {end.date()}")
        
        count = 0
        for event in connector.backfill(start, end):
            count += 1
            if count == 1:
                logger.info(f"  Sample event: {event}")
        
        logger.info(f"✓ Backfill test successful: {count} events retrieved")
        
        if count == 0:
            logger.warning("  Warning: No events retrieved (may be normal for this date range)")
        
    except Exception as e:
        logger.error(f"✗ Backfill test failed: {e}")
        return False
    finally:
        connector.disconnect()
    
    logger.info("✓ FRED connector test PASSED\n")
    return True


def test_ecb():
    """Test ECB connector"""
    
    logger.info("=" * 80)
    logger.info("TESTING ECB CONNECTOR")
    logger.info("=" * 80)
    
    config = ConnectorConfig(name="ecb", enabled=True, extra_config={})
    connector = ECBConnector(config)
    
    # Test connection
    if not connector.connect():
        logger.error("✗ ECB connection failed")
        return False
    
    logger.info("✓ ECB connection successful")
    
    # Test available range
    try:
        earliest, latest = connector.get_available_range()
        logger.info(f"✓ Available range: {earliest.date()} to {latest.date()}")
    except Exception as e:
        logger.error(f"✗ Failed to get available range: {e}")
        return False
    
    # Test backfill (3 months)
    try:
        start = datetime(2024, 1, 1)
        end = datetime(2024, 3, 31)
        
        logger.info(f"Testing backfill: {start.date()} to {end.date()}")
        
        count = 0
        for event in connector.backfill(start, end):
            count += 1
            if count == 1:
                logger.info(f"  Sample event: {event}")
        
        logger.info(f"✓ Backfill test successful: {count} events retrieved")
        
        if count == 0:
            logger.warning("  Warning: No events retrieved (may be normal for this date range)")
        
    except Exception as e:
        logger.error(f"✗ Backfill test failed: {e}")
        return False
    finally:
        connector.disconnect()
    
    logger.info("✓ ECB connector test PASSED\n")
    return True


def test_world_bank():
    """Test World Bank connector"""
    
    logger.info("=" * 80)
    logger.info("TESTING WORLD BANK CONNECTOR")
    logger.info("=" * 80)
    
    config = ConnectorConfig(name="world_bank", enabled=True, extra_config={})
    connector = WorldBankConnector(config)
    
    # Test connection
    if not connector.connect():
        logger.error("✗ World Bank connection failed")
        logger.error("  Check wbdata library installation: pip install wbdata")
        return False
    
    logger.info("✓ World Bank connection successful")
    
    # Test available range
    try:
        earliest, latest = connector.get_available_range()
        logger.info(f"✓ Available range: {earliest.date()} to {latest.date()}")
    except Exception as e:
        logger.error(f"✗ Failed to get available range: {e}")
        return False
    
    # Test backfill (5 years)
    try:
        start = datetime(2019, 1, 1)
        end = datetime(2023, 12, 31)
        
        logger.info(f"Testing backfill: {start.date()} to {end.date()}")
        logger.info("  Note: World Bank data is annual, so this may take a moment...")
        
        count = 0
        for event in connector.backfill(start, end):
            count += 1
            if count == 1:
                logger.info(f"  Sample event: {event}")
            
            # Limit test to first 10 events to avoid long wait
            if count >= 10:
                logger.info("  (Stopping test after 10 events)")
                break
        
        logger.info(f"✓ Backfill test successful: {count}+ events retrieved")
        
    except Exception as e:
        logger.error(f"✗ Backfill test failed: {e}")
        return False
    finally:
        connector.disconnect()
    
    logger.info("✓ World Bank connector test PASSED\n")
    return True


def main():
    """Main entry point"""
    
    logger.info("\n" + "=" * 80)
    logger.info("ALTERNATIVE DATA CONNECTORS TEST SUITE")
    logger.info("=" * 80 + "\n")
    
    results = {}
    
    # Test each connector
    results['FRED'] = test_fred()
    results['ECB'] = test_ecb()
    results['World Bank'] = test_world_bank()
    
    # Print summary
    logger.info("=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    for connector, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        logger.info(f"{connector:<15} {status}")
    
    logger.info("=" * 80)
    
    # Return exit code
    all_passed = all(results.values())
    
    if all_passed:
        logger.info("\n✓ All tests PASSED")
        return 0
    else:
        logger.error("\n✗ Some tests FAILED")
        return 1


if __name__ == "__main__":
    exit(main())
