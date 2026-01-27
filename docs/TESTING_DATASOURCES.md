# Testing Data Collection for Each Datasource

This guide explains how to test data collection for each datasource connector in the system.

## Overview

The platform supports multiple datasource connectors:
- **MT5Tick** - MT5 tick data (requires MT5 connection)
- **MT5Price** - MT5 price data (requires MT5 connection)
- **FRED** - US economic indicators from Federal Reserve
- **WorldBank** - Global economic indicators
- **ECB** - European Central Bank indicators
- **RSSFeed** - RSS news feeds
- **WebScraping** - Web scraping for news
- **NewsAPI** - News API connector

## Quick Start

### Test All Datasources

Run the comprehensive test script:

```bash
python scripts/test_datasource_collection.py
```

This will:
1. Test connection to each available datasource
2. Retrieve and validate schema
3. Check available data range
4. Fetch a small sample of data (backfill test)
5. Get latest timestamp
6. Provide a summary report

### Test Specific Datasource

Test a single datasource:

```bash
python scripts/test_datasource_collection.py --connector FRED
python scripts/test_datasource_collection.py --connector WorldBank
python scripts/test_datasource_collection.py --connector RSSFeed
```

### Verbose Output

Get detailed output including error traces:

```bash
python scripts/test_datasource_collection.py --verbose
```

## Prerequisites

### Environment Variables

Some connectors require API keys:

```bash
# FRED API (free key from https://fred.stlouisfed.org/)
export FRED_API_KEY="your_fred_api_key"

# NewsAPI (free key from https://newsapi.org/)
export NEWSAPI_API_KEY="your_newsapi_key"
```

### Database Connection

For connectors that read from database (like MT5 connectors), ensure database is running:

```bash
# Default database settings
export DB_HOST="localhost"
export DB_PORT="5432"
export DB_USER="forex_user"
export DB_PASSWORD="forex_password"
export DB_NAME="db_forex"
```

### Python Dependencies

Install required packages:

```bash
# For FRED connector
pip install fredapi

# For World Bank connector
pip install wbdata

# For RSS Feed connector
pip install feedparser

# For Web Scraping connector
pip install beautifulsoup4 requests selenium

# For News API connector
pip install newsapi-python
```

## Test Output

### Example Output

```
================================================================================
  Data Source Collection Test Suite
================================================================================

Found 6 connector(s) to test:
  - FRED
  - WorldBank
  - ECB
  - RSSFeed
  - WebScraping
  - NewsAPI

================================================================================
  Testing Connector: FRED
================================================================================

✓ FRED - Connection
   Successfully connected

✓ FRED - Schema
   Source: fred, Type: economic_indicator, Fields: 5

✓ FRED - Available Range
   Earliest: 1950-01-01, Latest: 2024-01-15, Duration: 27029 days

✓ FRED - Backfill
   Fetched 10 sample events successfully

✓ FRED - Latest Timestamp
   Latest: 2024-01-15 00:00:00, Age: 0 days 5 hours

================================================================================
  Test Summary
================================================================================

FRED:
  ✓ connection
  ✓ schema
  ✓ available_range
  ✓ backfill
  ✓ latest_timestamp

--------------------------------------------------------------------------------
Total Connectors: 6
Passed Tests: 30
Failed Tests: 0
Skipped Tests: 0
--------------------------------------------------------------------------------

✓ All tests passed!
```

## What Each Test Checks

### 1. Connection Test
- Verifies the connector can establish a connection to the datasource
- Tests authentication (if required)
- Validates basic connectivity

### 2. Schema Test
- Retrieves the connector's schema definition
- Validates schema structure (source, data_type, fields)
- Checks that schema follows expected format

### 3. Available Range Test
- Gets the earliest and latest available data timestamps
- Calculates the data range duration
- Useful for understanding historical data availability

### 4. Backfill Test
- Fetches a small sample (10 events) from the datasource
- Validates event structure (timestamp, source fields)
- Tests data normalization
- Uses last 7 days or available range (whichever is smaller)

### 5. Latest Timestamp Test
- Gets the timestamp of the most recent data
- Calculates data age (how fresh the data is)
- Useful for monitoring data staleness

## Troubleshooting

### Connection Failures

**FRED Connector:**
```
✗ FRED - Connection
   Error: FRED_API_KEY not found in environment
```
**Solution:** Set `FRED_API_KEY` environment variable

**World Bank Connector:**
```
✗ WorldBank - Connection
   Error: wbdata library not installed
```
**Solution:** Install with `pip install wbdata`

**RSS Feed Connector:**
```
✗ RSSFeed - Connection
   Error: feedparser library not installed
```
**Solution:** Install with `pip install feedparser`

### Schema Issues

If schema test fails:
- Check connector implementation
- Verify `get_schema()` returns proper dictionary
- Ensure schema includes `source`, `data_type`, and `fields`

### Backfill Issues

If backfill test fails:
- Check network connectivity
- Verify API rate limits not exceeded
- Check date range is valid
- Ensure data source has data for the requested period

### MT5 Connectors

MT5 connectors require:
- MT5 terminal running
- Socket connection established
- Database with MT5 data

These connectors are skipped in automated tests unless MT5 infrastructure is available.

## Manual Testing

### Test Individual Connector Methods

You can also test connectors programmatically:

```python
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, 'src/trading_server/src')

from connectors.base import ConnectorConfig
from connectors import FREDConnector

# Create connector
config = ConnectorConfig(source="fred", symbol="US")
connector = FREDConnector(config=config)

# Test connection
if connector.connect():
    print("Connected successfully")
    
    # Get schema
    schema = connector.get_schema()
    print(f"Schema: {schema}")
    
    # Get available range
    earliest, latest = connector.get_available_range()
    print(f"Range: {earliest} to {latest}")
    
    # Fetch sample data
    end_time = datetime.now()
    start_time = end_time - timedelta(days=7)
    
    count = 0
    for event in connector.backfill(start_time, end_time):
        print(f"Event: {event}")
        count += 1
        if count >= 5:
            break
    
    # Get latest timestamp
    latest_ts = connector.get_latest_timestamp()
    print(f"Latest timestamp: {latest_ts}")
    
    # Disconnect
    connector.disconnect()
else:
    print("Connection failed")
```

## Integration with CI/CD

The test script can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Test Datasources
  run: |
    export FRED_API_KEY=${{ secrets.FRED_API_KEY }}
    export NEWSAPI_API_KEY=${{ secrets.NEWSAPI_API_KEY }}
    python scripts/test_datasource_collection.py
```

## Best Practices

1. **Run tests regularly** - Catch datasource issues early
2. **Monitor data freshness** - Check latest timestamp ages
3. **Validate schemas** - Ensure schema changes are detected
4. **Test in staging** - Verify datasources before production
5. **Handle rate limits** - Respect API rate limits during testing

## Related Documentation

- [Adding Data Sources Guide](data-source-guide/ADDING_DATA_SOURCES.md)
- [Data Collection Improvements Testing](TESTING_DATA_COLLECTION_IMPROVEMENTS.md)
- [API Reference](API_REFERENCE.md)

## Support

For issues or questions:
- Check connector-specific logs in `logs/` directory
- Review connector implementation in `src/trading_server/src/connectors/`
- Check environment variables and API keys
- Review error messages in verbose mode (`--verbose` flag)
