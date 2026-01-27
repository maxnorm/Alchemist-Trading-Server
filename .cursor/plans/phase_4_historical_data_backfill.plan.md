# Phase 4: Historical Data Backfill (Weeks 13-16)

## Overview

Phase 4 builds on Phases 1-3 infrastructure to perform comprehensive historical data backfill for all data sources. This phase focuses on collecting maximum available historical data, detecting and filling gaps, computing features on historical data, and establishing robust progress tracking with resume capability.

## Week 13-14: Market Data Historical Backfill

### 4.1 MT5 Historical Data Backfill

**Current State:**

- ✅ `MT5TickConnector` exists with `stream()` and `batch()` methods
- ✅ `ticks_forex` table exists with TimescaleDB hypertable
- ✅ `insert_forex_tick()` and `insert_forex_ticks_batch()` methods exist
- ❌ No `backfill()` method in connector interface
- ❌ No direct MT5 API historical data collection
- ❌ No progress tracking for backfill operations

**Implementation Tasks:**

1. **Add backfill interface to connector base class**

- Enhance `src/trading_server/src/connectors/base.py`:
  - Add abstract `backfill(start_time: datetime, end_time: datetime, batch_size: int = 1000) -> Iterator[Dict[str, Any]]` method
  - Add abstract `get_available_range() -> Tuple[datetime, datetime]` method
  - Add optional `get_backfill_metadata() -> Dict[str, Any]` method for connector-specific backfill info

2. **Implement MT5 tick data backfill**

- Enhance `src/trading_server/src/connectors/mt5_tick_connector.py`:
  - Implement `backfill()` using `MetaTrader5.copy_ticks_range()` API
  - Use `mt5.COPY_TICKS_ALL` flag for comprehensive tick data
  - Process in daily batches to avoid memory issues
  - Integrate with existing `insert_forex_ticks_batch()` for efficient storage
  - Add rate limiting (0.1s delay between batches) to respect MT5 API limits
  - Implement `get_available_range()` using MT5 API to query available historical range
  - Handle MT5 connection failures gracefully with retry logic

3. **Implement MT5 OHLCV data backfill**

- Enhance `src/trading_server/src/connectors/mt5_tick_connector.py` or create separate OHLCV connector:
  - Implement `backfill()` for OHLCV using `MetaTrader5.copy_rates_range()`
  - Support multiple timeframes: M1, M5, M15, M30, H1, H4, D1
  - Batch processing for large historical ranges
  - Store in `bars_forex` table (from Phase 2)
  - Use `insert_forex_bars_batch()` for efficient storage

4. **Create backfill progress tracker**

- Create `src/trading_server/src/infrastructure/backfill/backfill_progress_tracker.py`:
  - Track backfill progress per connector, symbol, and time range
  - Store progress in Redis or database table
  - Support resume capability (skip already backfilled ranges)
  - Track statistics: records collected, time taken, errors encountered
  - Methods:
    - `get_backfill_status(connector_name: str, symbol: str, start_time: datetime, end_time: datetime) -> Dict`
    - `update_backfill_progress(connector_name: str, symbol: str, current_time: datetime, records_count: int) -> None`
    - `get_completed_ranges(connector_name: str, symbol: str) -> List[Tuple[datetime, datetime]]`
    - `mark_range_complete(connector_name: str, symbol: str, start_time: datetime, end_time: datetime) -> None`

5. **Create MT5 backfill script**

- Create `scripts/backfill_mt5_data.py`:
  - Support backfilling 5-10 years of historical data
  - Progress tracking and resume capability
  - Parallel backfill across multiple symbols
  - Integration with progress tracker
  - Error handling and logging
  - Command-line interface for configuration

### 4.2 Gap Detection and Filling

**Implementation Tasks:**

1. **Create gap detector module**

- Create `src/trading_server/src/infrastructure/backfill/gap_detector.py`:
  - Detect gaps in historical data across all tables
  - Support multiple gap detection strategies:
    - Time-based gaps (missing time periods)
    - Frequency-based gaps (expected data points missing)
    - Statistical gaps (unusual data patterns)
  - Methods:
    - `detect_gaps(table_name: str, symbol: Optional[str], start_time: datetime, end_time: datetime, expected_frequency: timedelta) -> List[Tuple[datetime, datetime]]`
    - `detect_tick_gaps(symbol: str, start_time: datetime, end_time: datetime) -> List[Tuple[datetime, datetime]]`
    - `detect_bar_gaps(symbol: str, timeframe: str, start_time: datetime, end_time: datetime) -> List[Tuple[datetime, datetime]]`
    - `detect_news_gaps(start_time: datetime, end_time: datetime) -> List[Tuple[datetime, datetime]]`
    - `detect_economic_gaps(series_id: str, start_time: datetime, end_time: datetime) -> List[Tuple[datetime, datetime]]`
  - Store gap information in database for tracking

2. **Create gap filler module**

- Create `src/trading_server/src/infrastructure/backfill/gap_filler.py`:
  - Automatically fill detected gaps using available data sources
  - Support multiple filling strategies:
    - Re-query from source API if available
    - Interpolation for small gaps
    - Forward/backward fill for missing values
    - Mark gaps as unfillable if no data available
  - Methods:
    - `fill_gaps(gaps: List[Tuple[datetime, datetime]], connector: IDataSourceConnector, symbol: Optional[str]) -> int`
    - `fill_tick_gaps(symbol: str, gaps: List[Tuple[datetime, datetime]]) -> int`
    - `fill_bar_gaps(symbol: str, timeframe: str, gaps: List[Tuple[datetime, datetime]]) -> int`
  - Log all gap-filling operations for audit

3. **Create gap analysis report**

- Create `scripts/analyze_data_gaps.py`:
  - Generate comprehensive gap analysis report
  - Identify data quality issues
  - Prioritize gaps for backfill
  - Export gap information to CSV/JSON

## Week 15-16: Alternative Data Historical Backfill & Feature Computation

### 4.3 Alternative Data Historical Backfill

**Current State:**

- ✅ Phase 3 created news connectors (NewsAPI, RSS)
- ✅ Phase 3 created economic indicator connectors (FRED, World Bank, ECB)
- ✅ `news_articles` and `economic_indicators` tables should exist (from Phase 3)
- ❌ No historical backfill implemented for alternative data sources

**Implementation Tasks:**

1. **Implement news data backfill**

- Enhance `src/trading_server/src/connectors/news_api_connector.py`:
  - Implement `backfill()` method
  - Note: NewsAPI free tier has limited historical data (7 days)
  - For paid tier: Use NewsAPI historical endpoints
  - For free tier: Use web scraping of news archives as fallback
  - Integrate with sentiment analysis pipeline (from Phase 3)
  - Batch processing with rate limiting

- Enhance `src/trading_server/src/connectors/rss_feed_connector.py`:
  - Implement `backfill()` method
  - RSS feeds have limited historical data
  - Use web scraping of news site archives
  - Support multiple RSS sources (Reuters, Bloomberg, FT)

2. **Implement economic indicator backfill**

- Enhance `src/trading_server/src/connectors/fred_connector.py`:
  - Implement `backfill()` method using FRED API
  - FRED supports decades of historical data
  - Batch requests for multiple series
  - Handle different frequencies (daily, monthly, quarterly)

- Enhance `src/trading_server/src/connectors/world_bank_connector.py`:
  - Implement `backfill()` method using World Bank API
  - 50+ years of historical data available
  - Support multiple countries and indicators

- Enhance `src/trading_server/src/connectors/ecb_connector.py`:
  - Implement `backfill()` method using ECB SDW API
  - 20+ years of historical data available
  - Support Eurozone indicators

3. **Create alternative data backfill script**

- Create `scripts/backfill_alternative_data.py`:
  - Coordinate backfill for all alternative data sources
  - Prioritize sources with most historical data (FRED > World Bank > ECB > News)
  - Parallel processing where possible
  - Progress tracking per source

### 4.4 Historical Feature Computation

**Implementation Tasks:**

1. **Create historical feature computer**

- Create `src/trading_server/src/infrastructure/backfill/historical_feature_computer.py`:
  - Compute all features for historical data in batches
  - Ensure point-in-time computation (no lookahead bias)
  - Support incremental computation (resume from last computed point)
  - Methods:
    - `compute_features_for_period(symbol: str, start_time: datetime, end_time: datetime, features: List[str]) -> int`
    - `compute_all_features_for_symbol(symbol: str, start_time: datetime, end_time: datetime) -> int`
    - `compute_features_incremental(symbol: str, last_computed_time: datetime, end_time: datetime) -> int`
  - Store computed features in feature store or database
  - Support feature versioning (from Phase 1)

2. **Create feature computation pipeline**

- Create `scripts/compute_historical_features.py`:
  - Orchestrate feature computation for all symbols and time periods
  - Parallel computation across symbols
  - Progress tracking
  - Validation of computed features
  - Integration with FeatureEngine from Phase 2

3. **Validate point-in-time computation**

- Create `scripts/validate_point_in_time.py`:
  - Verify no lookahead bias in historical features
  - Check that features at time T only use data up to time T
  - Generate validation report
  - Flag any violations for manual review

### 4.5 Backfill Orchestration

**Implementation Tasks:**

1. **Create backfill orchestrator**

- Create `src/trading_server/src/infrastructure/backfill/backfill_orchestrator.py`:
  - Coordinate backfill across all connectors
  - Manage dependencies (e.g., compute features after data backfill)
  - Parallel execution where possible
  - Error handling and retry logic
  - Progress reporting
  - Methods:
    - `backfill_all_sources(start_time: datetime, end_time: datetime, sources: Optional[List[str]] = None) -> Dict[str, Any]`
    - `backfill_source(source_name: str, start_time: datetime, end_time: datetime, symbols: Optional[List[str]] = None) -> Dict[str, Any]`
    - `get_backfill_status() -> Dict[str, Any]`
    - `resume_failed_backfills() -> int`

2. **Create Airflow DAG for backfill**

- Create `src/trading_server/src/infrastructure/data_pipeline/airflow/dags/historical_backfill_dag.py`:
  - Scheduled backfill tasks (daily/weekly)
  - Dependency management between tasks
  - Parallel execution of independent backfills
  - Error handling and alerting
  - Integration with progress tracker

3. **Create backfill monitoring**

- Create `src/trading_server/src/infrastructure/backfill/backfill_monitor.py`:
  - Monitor backfill progress in real-time
  - Track metrics: records collected, time taken, success rate
  - Generate alerts for failures or slow progress
  - Integration with Prometheus metrics
  - Create Grafana dashboard for backfill monitoring

## Implementation Details

### Backfill Progress Tracking Schema

Create `src/database/scripts/21_backfill_progress_table.sql`:

```sql
CREATE TABLE IF NOT EXISTS backfill_progress (
    id BIGSERIAL PRIMARY KEY,
    connector_name VARCHAR(100) NOT NULL,
    symbol VARCHAR(10),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    current_time TIMESTAMPTZ,
    records_collected BIGINT DEFAULT 0,
    status VARCHAR(20) NOT NULL, -- 'pending', 'in_progress', 'completed', 'failed'
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(connector_name, symbol, start_time, end_time)
);

CREATE INDEX idx_backfill_connector_symbol ON backfill_progress(connector_name, symbol);
CREATE INDEX idx_backfill_status ON backfill_progress(status);
CREATE INDEX idx_backfill_time_range ON backfill_progress(start_time, end_time);
```

### Gap Detection Schema

Create `src/database/scripts/22_data_gaps_table.sql`:

```sql
CREATE TABLE IF NOT EXISTS data_gaps (
    id BIGSERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    symbol VARCHAR(10),
    gap_start TIMESTAMPTZ NOT NULL,
    gap_end TIMESTAMPTZ NOT NULL,
    gap_duration INTERVAL GENERATED ALWAYS AS (gap_end - gap_start) STORED,
    severity VARCHAR(20) NOT NULL, -- 'low', 'medium', 'high', 'critical'
    status VARCHAR(20) NOT NULL, -- 'detected', 'filling', 'filled', 'unfillable'
    fill_strategy VARCHAR(50),
    filled_at TIMESTAMPTZ,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT
);

CREATE INDEX idx_gaps_table_symbol ON data_gaps(table_name, symbol);
CREATE INDEX idx_gaps_status ON data_gaps(status);
CREATE INDEX idx_gaps_time_range ON data_gaps(gap_start, gap_end);
```

### Backfill Orchestrator Structure

```
src/trading_server/src/infrastructure/backfill/
├── __init__.py
├── backfill_progress_tracker.py    # Progress tracking
├── gap_detector.py                  # Gap detection
├── gap_filler.py                    # Gap filling
├── backfill_orchestrator.py         # Main orchestrator
├── historical_feature_computer.py   # Feature computation
└── backfill_monitor.py              # Monitoring
```

### Backfill Scripts Structure

```
scripts/
├── backfill_mt5_data.py             # MT5 data backfill
├── backfill_alternative_data.py     # Alternative data backfill
├── compute_historical_features.py    # Feature computation
├── analyze_data_gaps.py             # Gap analysis
└── validate_point_in_time.py        # Point-in-time validation
```

### Requirements Updates

Add to `src/trading_server/requirements.txt`:

- `tqdm==4.66.0` - Progress bars for backfill scripts
- `joblib==1.3.0` - Parallel processing
- `pandas==2.1.0` - Data manipulation for gap detection
- `numpy==1.24.0` - Numerical operations

### Airflow DAG Structure

```python
# src/trading_server/src/infrastructure/data_pipeline/airflow/dags/historical_backfill_dag.py

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'retries': 3,
    'retry_delay': timedelta(hours=1)
}

dag = DAG(
    'historical_backfill',
    default_args=default_args,
    description='Historical data backfill for all sources',
    schedule_interval='@weekly',  # Run weekly
    catchup=False
)

# Define tasks
backfill_mt5_ticks = PythonOperator(
    task_id='backfill_mt5_ticks',
    python_callable=backfill_mt5_ticks_task,
    dag=dag
)

backfill_mt5_bars = PythonOperator(
    task_id='backfill_mt5_bars',
    python_callable=backfill_mt5_bars_task,
    dag=dag
)

backfill_news = PythonOperator(
    task_id='backfill_news',
    python_callable=backfill_news_task,
    dag=dag
)

backfill_economic = PythonOperator(
    task_id='backfill_economic',
    python_callable=backfill_economic_task,
    dag=dag
)

detect_gaps = PythonOperator(
    task_id='detect_gaps',
    python_callable=detect_gaps_task,
    dag=dag
)

fill_gaps = PythonOperator(
    task_id='fill_gaps',
    python_callable=fill_gaps_task,
    dag=dag
)

compute_features = PythonOperator(
    task_id='compute_features',
    python_callable=compute_features_task,
    dag=dag
)

# Task dependencies
[backfill_mt5_ticks, backfill_mt5_bars] >> detect_gaps
[backfill_news, backfill_economic] >> detect_gaps
detect_gaps >> fill_gaps
[backfill_mt5_ticks, backfill_mt5_bars, fill_gaps] >> compute_features
```

## Success Criteria

- [ ] `backfill()` method added to `IDataSourceConnector` interface
- [ ] `get_available_range()` method added to `IDataSourceConnector` interface
- [ ] MT5 tick data backfill working (5-10 years of data)
- [ ] MT5 OHLCV data backfill working (all timeframes)
- [ ] News data backfill working (where available)
- [ ] Economic indicator backfill working (FRED, World Bank, ECB - decades of data)
- [ ] Backfill progress tracker operational
- [ ] Gap detection working for all data types
- [ ] Gap filling working with multiple strategies
- [ ] Historical feature computation working with point-in-time validation
- [ ] Backfill orchestrator coordinating all sources
- [ ] Airflow DAG for scheduled backfill operational
- [ ] Monitoring dashboard showing backfill progress
- [ ] Data quality validation passing for all backfilled data
- [ ] Resume capability working (can resume failed backfills)

## Dependencies

- Phase 1 infrastructure (Airflow, Celery, Redis) must be operational
- Phase 2 market data collection (MT5 connector, OHLCV aggregation)
- Phase 3 alternative data integration (news connectors, economic connectors)
- Database connection pool from Phase 1
- Existing database methods for data insertion
- FeatureEngine from Phase 2 for feature computation

## Testing Strategy

- **Unit Tests:**
  - Test backfill progress tracker (tracking, resume)
  - Test gap detector (various gap scenarios)
  - Test gap filler (different filling strategies)
  - Test historical feature computer (point-in-time validation)

- **Integration Tests:**
  - Test MT5 backfill end-to-end (collect → store → validate)
  - Test alternative data backfill end-to-end
  - Test gap detection and filling pipeline
  - Test feature computation on historical data
  - Test backfill orchestrator with multiple sources

- **Data Quality Tests:**
  - Verify no data loss during backfill
  - Verify data completeness (no unexpected gaps)
  - Verify point-in-time correctness (no lookahead bias)
  - Verify data consistency (no duplicate records)

- **Performance Tests:**
  - Test backfill speed (records/second)
  - Test parallel backfill performance
  - Test memory usage during large backfills
  - Test resume capability performance

## Risk Mitigation

1. **API Rate Limits:**

   - Implement aggressive rate limiting
   - Use multiple API keys where possible
   - Cache API responses in Redis
   - Respect API terms of service

2. **Data Volume:**

   - Process in batches to avoid memory issues
   - Use streaming for large datasets
   - Monitor disk space usage
   - Implement data compression where appropriate

3. **Backfill Failures:**

   - Implement robust error handling
   - Support resume capability
   - Log all errors for analysis
   - Alert on critical failures

4. **Data Quality:**

   - Validate all backfilled data
   - Detect and report gaps
   - Verify point-in-time correctness
   - Monitor data freshness

5. **Storage Costs:**

   - Monitor database growth
   - Implement data archival for old data
   - Use compression for historical data
   - Consider tiered storage (hot/warm/cold)

## Implementation Examples

### MT5 Backfill Implementation

```python
# src/trading_server/src/connectors/mt5_tick_connector.py (enhancement)

from typing import Iterator, Dict, Any, Tuple
from datetime import datetime, timedelta
import MetaTrader5 as mt5
import logging

logger = logging.getLogger(__name__)

class MT5TickConnector(IDataSourceConnector):
    """Enhanced MT5 connector with historical backfill"""
    
    def backfill(
        self, 
        start_time: datetime, 
        end_time: datetime,
        batch_size: int = 1000
    ) -> Iterator[Dict[str, Any]]:
        """
        Backfill historical tick data from MT5 API
        
        :param start_time: Start time for historical data
        :param end_time: End time for historical data
        :param batch_size: Number of records per batch
        :return: Iterator of normalized tick events
        """
        if not self._is_connected:
            if not self.connect():
                raise ConnectionError("Failed to connect to MT5")
        
        try:
            current = start_time
            
            while current < end_time:
                # Process in daily batches
                batch_end = min(current + timedelta(days=1), end_time)
                
                logger.info(f"Backfilling {self.symbol} from {current} to {batch_end}")
                
                # Fetch tick data from MT5
                ticks = mt5.copy_ticks_range(
                    self.symbol,
                    current,
                    batch_end,
                    mt5.COPY_TICKS_ALL
                )
                
                if ticks is None or len(ticks) == 0:
                    logger.warning(f"No ticks found for {self.symbol} from {current} to {batch_end}")
                    current = batch_end
                    continue
                
                # Normalize and yield ticks
                for tick in ticks:
                    normalized = self._normalize_mt5_tick(tick)
                    yield normalized
                
                # Rate limiting
                time.sleep(0.1)
                current = batch_end
                
        except Exception as e:
            logger.error(f"Error during backfill: {e}", exc_info=True)
            raise
    
    def get_available_range(self) -> Tuple[datetime, datetime]:
        """
        Get available historical data range from MT5
        
        :return: (start_time, end_time) tuple
        """
        if not self._is_connected:
            if not self.connect():
                raise ConnectionError("Failed to connect to MT5")
        
        try:
            # Get symbol info to determine available range
            symbol_info = mt5.symbol_info(self.symbol)
            if symbol_info is None:
                raise ValueError(f"Symbol {self.symbol} not found")
            
            # MT5 typically has 5-10 years of historical data
            # Use symbol creation time or a conservative estimate
            end_time = datetime.now()
            start_time = end_time - timedelta(days=3650)  # 10 years
            
            return (start_time, end_time)
        except Exception as e:
            logger.error(f"Error getting available range: {e}", exc_info=True)
            raise
```

### Backfill Progress Tracker Implementation

```python
# src/trading_server/src/infrastructure/backfill/backfill_progress_tracker.py

from typing import Dict, List, Tuple, Optional
from datetime import datetime
import redis
import json
import logging

logger = logging.getLogger(__name__)

class BackfillProgressTracker:
    """Track backfill progress for resume capability"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client or redis.Redis(host='redis', port=6379, db=0)
        self.db = None  # Database for persistent storage
    
    def get_backfill_status(
        self, 
        connector_name: str, 
        symbol: str, 
        start_time: datetime, 
        end_time: datetime
    ) -> Dict[str, Any]:
        """Get current backfill status"""
        key = f"backfill:{connector_name}:{symbol}:{start_time.isoformat()}:{end_time.isoformat()}"
        
        status = self.redis.get(key)
        if status:
            return json.loads(status)
        
        # Check database for persistent status
        if self.db:
            status = self.db.get_backfill_progress(connector_name, symbol, start_time, end_time)
            if status:
                return status
        
        return {
            "status": "pending",
            "current_time": None,
            "records_collected": 0,
            "progress_percent": 0.0
        }
    
    def update_backfill_progress(
        self, 
        connector_name: str, 
        symbol: str, 
        current_time: datetime, 
        records_count: int,
        start_time: datetime,
        end_time: datetime
    ) -> None:
        """Update backfill progress"""
        key = f"backfill:{connector_name}:{symbol}:{start_time.isoformat()}:{end_time.isoformat()}"
        
        total_duration = (end_time - start_time).total_seconds()
        current_duration = (current_time - start_time).total_seconds()
        progress_percent = min(100.0, (current_duration / total_duration) * 100) if total_duration > 0 else 0.0
        
        status = {
            "status": "in_progress",
            "current_time": current_time.isoformat(),
            "records_collected": records_count,
            "progress_percent": progress_percent,
            "updated_at": datetime.now().isoformat()
        }
        
        # Store in Redis (TTL: 7 days)
        self.redis.setex(key, 7 * 24 * 3600, json.dumps(status))
        
        # Store in database for persistence
        if self.db:
            self.db.update_backfill_progress(connector_name, symbol, start_time, end_time, current_time, records_count)
    
    def mark_range_complete(
        self, 
        connector_name: str, 
        symbol: str, 
        start_time: datetime, 
        end_time: datetime,
        records_count: int
    ) -> None:
        """Mark a backfill range as complete"""
        key = f"backfill:{connector_name}:{symbol}:{start_time.isoformat()}:{end_time.isoformat()}"
        
        status = {
            "status": "completed",
            "current_time": end_time.isoformat(),
            "records_collected": records_count,
            "progress_percent": 100.0,
            "completed_at": datetime.now().isoformat()
        }
        
        self.redis.setex(key, 30 * 24 * 3600, json.dumps(status))  # Keep for 30 days
        
        if self.db:
            self.db.mark_backfill_complete(connector_name, symbol, start_time, end_time, records_count)
    
    def get_completed_ranges(
        self, 
        connector_name: str, 
        symbol: str
    ) -> List[Tuple[datetime, datetime]]:
        """Get list of completed backfill ranges"""
        if self.db:
            return self.db.get_completed_backfill_ranges(connector_name, symbol)
        return []
```

### Gap Detector Implementation

```python
# src/trading_server/src/infrastructure/backfill/gap_detector.py

from typing import List, Tuple, Optional
from datetime import datetime, timedelta
import pandas as pd
from database import Database
import logging

logger = logging.getLogger(__name__)

class GapDetector:
    """Detect gaps in historical data"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def detect_tick_gaps(
        self, 
        symbol: str, 
        start_time: datetime, 
        end_time: datetime,
        expected_frequency: timedelta = timedelta(seconds=1)
    ) -> List[Tuple[datetime, datetime]]:
        """
        Detect gaps in tick data
        
        :param symbol: Trading symbol
        :param start_time: Start time for analysis
        :param end_time: End time for analysis
        :param expected_frequency: Expected frequency of ticks
        :return: List of (gap_start, gap_end) tuples
        """
        # Query tick data
        ticks = self.db.get_ticks_by_timeframe(symbol, start_time, end_time)
        
        if len(ticks) == 0:
            return [(start_time, end_time)]  # Entire range is a gap
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(ticks)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.sort_values('datetime')
        
        gaps = []
        for i in range(len(df) - 1):
            current_time = df.iloc[i]['datetime']
            next_time = df.iloc[i + 1]['datetime']
            gap_duration = next_time - current_time
            
            # If gap is significantly larger than expected frequency, it's a gap
            if gap_duration > expected_frequency * 10:  # 10x threshold
                gaps.append((current_time, next_time))
        
        return gaps
    
    def detect_bar_gaps(
        self, 
        symbol: str, 
        timeframe: str, 
        start_time: datetime, 
        end_time: datetime
    ) -> List[Tuple[datetime, datetime]]:
        """Detect gaps in OHLCV bar data"""
        # Map timeframe to timedelta
        timeframe_map = {
            'M1': timedelta(minutes=1),
            'M5': timedelta(minutes=5),
            'M15': timedelta(minutes=15),
            'H1': timedelta(hours=1),
            'H4': timedelta(hours=4),
            'D1': timedelta(days=1)
        }
        
        expected_frequency = timeframe_map.get(timeframe, timedelta(minutes=1))
        
        # Query bar data
        bars = self.db.get_bars_by_timeframe(symbol, timeframe, start_time, end_time)
        
        if len(bars) == 0:
            return [(start_time, end_time)]
        
        # Convert to DataFrame
        df = pd.DataFrame(bars)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.sort_values('datetime')
        
        gaps = []
        for i in range(len(df) - 1):
            current_time = df.iloc[i]['datetime']
            next_time = df.iloc[i + 1]['datetime']
            gap_duration = next_time - current_time
            
            # Expected next bar time
            expected_next = current_time + expected_frequency
            
            # If next bar is not at expected time, there's a gap
            if abs((next_time - expected_next).total_seconds()) > expected_frequency.total_seconds() * 0.5:
                gaps.append((current_time, next_time))
        
        return gaps
```

## Next Steps After Phase 4

- **Phase 5: AI-Powered Data Extraction (Weeks 17-20)**
  - Web crawling infrastructure for unstructured data
  - Document analysis (PDF, OCR) for financial reports
  - NLP pipelines for earnings call transcripts
  - Central bank statement analysis

- **Phase 6: Scale & Optimization (Weeks 21-24)**
  - Performance optimization for backfill operations
  - Horizontal scaling for data collection
  - Advanced caching strategies
  - Cost optimization for storage and API usage
  - Data archival and tiered storage