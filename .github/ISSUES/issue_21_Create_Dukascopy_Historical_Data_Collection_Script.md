Create Dukascopy Historical Data Collection Script

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: data-collection, backfill, historical-data, P1
Milestone: Phase 2 - Data Infrastructure
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #21: Create Dukascopy Historical Data Collection Script

## Problem Statement

The system currently lacks a comprehensive solution for collecting large volumes of historical forex data for training and backtesting:

1. **Limited Historical Data Sources**: Currently only MT5 connector exists (`scripts/backfill_mt5_data.py`), which requires active MT5 connection and may have data limitations or rate restrictions.

2. **No Alternative Data Source**: Dukascopy provides free, high-quality historical tick data going back to 2000, but there's no integration to collect this data.

3. **Manual Data Collection**: No automated way to bulk download and seed historical data from external sources like Dukascopy.

4. **Missing Infrastructure for External Sources**: While `BackfillProgressTracker` and quality gates exist, they're only integrated with MT5. Need reusable pattern for external data sources.

5. **No Resume Capability for External Downloads**: If a large download fails, there's no way to resume from where it left off when using external tools like `dukascopy-node` CLI.

**Impact:**
- Cannot efficiently collect years of historical data for training
- Limited to MT5 data availability and connection requirements
- Manual, error-prone process for acquiring historical data
- No standardized way to integrate additional data sources
- Missing data gaps cannot be easily backfilled from alternative sources

**Existing Infrastructure:**
- `BackfillProgressTracker` at `src/trading_server/src/infrastructure/backfill/progress_tracker.py` (424 lines, fully implemented)
- `QualityGate` at `src/trading_server/src/data/quality_gates.py` (764 lines, fully implemented)
- `Database.insert_forex_ticks_batch()` at `src/trading_server/src/database/database.py` (batch insert method)
- MT5 backfill script at `scripts/backfill_mt5_data.py` (343 lines, reference implementation)

**External Tool:**
- `dukascopy-node` CLI tool available at https://www.dukascopy-node.app/
- Free historical data from Dukascopy (https://www.dukascopy.com/trading-tools/widgets/quotes/historical_data_feed)
- Supports tick data and OHLCV bars
- Rate limiting built-in via batch size and pause configuration

## Proposed Solution

Create a comprehensive script that integrates `dukascopy-node` CLI tool with existing backfill infrastructure to download and seed historical tick data into the PostgreSQL database.

### Architecture Overview

The solution consists of three main modules:

1. **Download Module**: Executes `dukascopy-node` CLI to download data to temporary JSON files
2. **Parsing Module**: Converts Dukascopy JSON format to database-compatible format
3. **Seeding Module**: Validates, batches, and inserts data using existing infrastructure

### Implementation Steps

#### 1. Create Main Script Structure

**File:** `scripts/backfill_dukascopy_data.py` (new, ~600-800 lines)

**Key Components:**
- CLI argument parsing using `argparse`
- Integration with `BackfillProgressTracker` for progress tracking
- Integration with `QualityGate` for data validation
- Batch processing with configurable batch sizes
- Error handling and resume capability
- Comprehensive logging

**Script Structure:**
```python
#!/usr/bin/env python3
"""
Dukascopy Historical Data Backfill Script
Downloads tick data from Dukascopy using dukascopy-node CLI and stores in database
"""

import argparse
import subprocess
import tempfile
import shutil
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Optional, Dict, Any

# Add src/trading_server/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "trading_server", "src"))

from database import Database
from infrastructure.backfill.progress_tracker import BackfillProgressTracker
from data.quality_gates import QualityGate
from utils.logging_config import get_logger
```

#### 2. Implement CLI Argument Parsing

**Required Arguments:**
- None (uses sensible defaults)

**Optional Arguments:**
- `--symbols`: Comma-separated list of symbols (default: `EURUSD,GBPUSD,USDJPY,AUDUSD`)
- `--start-time`: Start date in ISO format `YYYY-MM-DD` (default: `2000-01-01` or earliest available)
- `--end-time`: End date in ISO format `YYYY-MM-DD` (default: today)
- `--resume`: Resume from last successful checkpoint
- `--batch-size`: Download batch size for dukascopy-node (default: `5` for conservative rate limiting)
- `--pause-ms`: Pause between download batches in milliseconds (default: `3000`)
- `--db-batch-size`: Database insert batch size (default: `1000`)
- `--temp-dir`: Temporary directory for downloads (default: system temp directory)
- `--keep-files`: Keep downloaded JSON files after seeding (default: `False`)

**Example Usage:**
```bash
# Basic usage (default symbols, all available dates)
python scripts/backfill_dukascopy_data.py

# Specific symbols
python scripts/backfill_dukascopy_data.py --symbols EURUSD,GBPUSD

# Specific date range
python scripts/backfill_dukascopy_data.py --start-time 2020-01-01 --end-time 2024-01-01

# Resume failed backfill
python scripts/backfill_dukascopy_data.py --resume

# Custom rate limiting (more conservative)
python scripts/backfill_dukascopy_data.py --batch-size 3 --pause-ms 5000
```

#### 3. Implement Download Module

**Function: `download_dukascopy_data()`**

**Location:** `scripts/backfill_dukascopy_data.py`

**Responsibilities:**
- Execute `npx dukascopy-node` CLI command via `subprocess.run()`
- Construct command with proper parameters:
  - `-i`: Instrument symbol (lowercase)
  - `-from`: Start date
  - `-to`: End date
  - `-t`: Data type (`ticks` for tick data)
  - `-f`: Format (`json`)
  - `-o`: Output directory
  - `-bs`: Batch size
  - `-bp`: Pause between batches
- Create and manage temporary directory
- Handle subprocess errors and retries
- Return path to downloaded JSON files
- Log download progress

**Implementation Notes:**
- Use `subprocess.run()` with `capture_output=True` for error handling
- Check return code and stderr for failures
- Create temp directory with `tempfile.mkdtemp()` or use provided `--temp-dir`
- Ensure cleanup with try/finally blocks

**Function: `get_dukascopy_date_range()`**

**Responsibilities:**
- Determine available date range from Dukascopy
- Default to `2000-01-01` to today if not queryable
- Return tuple of `(start_date, end_date)`
- Can be enhanced later with actual API query if available

#### 4. Implement Parsing Module

**Function: `load_dukascopy_json()`**

**Responsibilities:**
- Load JSON file from disk
- Handle both array format `[{...}, {...}]` and object format `{"data": [{...}]}`
- Return list of tick records
- Handle file encoding (UTF-8)
- Log file loading progress

**Function: `parse_dukascopy_tick()`**

**Responsibilities:**
- Parse single Dukascopy tick record to database format
- Handle Dukascopy JSON structure:
  ```json
  {
    "time": 1234567890000,  // Unix timestamp in milliseconds
    "ask": 1.1000,
    "bid": 1.0999,
    "askVolume": 1000,
    "bidVolume": 1000
  }
  ```
- Convert timestamp from milliseconds to `datetime` object
- Normalize to UTC timezone
- Return tuple: `(symbol, datetime, ask, bid)` matching `insert_forex_ticks_batch()` format
- Validate required fields (time, ask, bid)
- Handle missing or invalid data gracefully

**Error Handling:**
- Skip records with missing required fields
- Log warnings for invalid records
- Continue processing on parse errors

#### 5. Implement Seeding Module

**Function: `seed_dukascopy_ticks()`**

**Responsibilities:**
- Main seeding function following pattern from `backfill_ticks()` in `scripts/backfill_mt5_data.py`
- Process ticks in batches
- Validate each tick with `QualityGate.validate_tick()`
- Batch insert using `Database.insert_forex_ticks_batch()`
- Update `BackfillProgressTracker` periodically
- Track statistics (inserted, skipped, errors)
- Handle errors gracefully (continue on batch failures)

**Implementation Pattern:**
```python
def seed_dukascopy_ticks(
    db: Database,
    progress_tracker: BackfillProgressTracker,
    progress_id: int,
    json_files: List[Path],
    symbol: str,
    batch_size: int = 1000,
) -> int:
    """
    Seed tick data from Dukascopy JSON files
    
    :param db: Database instance
    :param progress_tracker: Progress tracker
    :param progress_id: Progress record ID
    :param json_files: List of JSON file paths
    :param symbol: Trading symbol
    :param batch_size: Database batch size
    :return: Number of ticks successfully inserted
    """
    quality_gate = QualityGate()
    ticks_collected = 0
    last_successful_time = None
    tick_batch = []
    
    for json_file in json_files:
        records = load_dukascopy_json(json_file)
        for record in records:
            try:
                tick = parse_dukascopy_tick(record, symbol)
                symbol, dt, ask, bid = tick
                
                # Validate with quality gate
                is_valid, error_msg = quality_gate.validate_tick(
                    symbol=symbol,
                    tick_datetime=dt,
                    bid=bid,
                    ask=ask
                )
                
                if not is_valid:
                    continue  # Skip invalid ticks
                
                tick_batch.append(tick)
                
                # Insert when batch is full
                if len(tick_batch) >= batch_size:
                    inserted = db.insert_forex_ticks_batch(tick_batch)
                    ticks_collected += inserted
                    last_successful_time = tick_batch[-1][1]  # Last timestamp
                    tick_batch = []
                    
                    # Update progress
                    progress_tracker.update_progress(
                        progress_id, last_successful_time, ticks_collected
                    )
            except Exception as e:
                logger.warning(f"Error processing record: {e}")
                continue
    
    # Insert remaining batch
    if tick_batch:
        inserted = db.insert_forex_ticks_batch(tick_batch)
        ticks_collected += inserted
    
    return ticks_collected
```

**Function: `process_symbol()`**

**Responsibilities:**
- Orchestrate download + seed for a single symbol
- Create progress tracking record using `BackfillProgressTracker.start_backfill()`
- Handle resume logic using `BackfillProgressTracker.get_resume_point()`
- Call `download_dukascopy_data()` and `seed_dukascopy_ticks()`
- Mark progress as completed or failed
- Return statistics dictionary

**Resume Logic:**
```python
# Check for existing progress if --resume flag
if args.resume:
    existing_progress = progress_tracker.get_progress(
        "dukascopy_tick", symbol, start_time, end_time
    )
    if existing_progress:
        resume_point = progress_tracker.get_resume_point(existing_progress["id"])
        if resume_point:
            start_time = resume_point  # Resume from last successful point
```

#### 6. Implement Multi-Symbol Orchestration

**Function: `backfill_multiple_symbols()`**

**Responsibilities:**
- Process multiple symbols sequentially (to avoid rate limiting)
- Use `BackfillProgressTracker` for each symbol independently
- Aggregate results and statistics across all symbols
- Handle partial failures gracefully (continue with other symbols)
- Return comprehensive statistics

**Implementation:**
```python
def backfill_multiple_symbols(
    symbols: List[str],
    start_time: datetime,
    end_time: datetime,
    progress_tracker: BackfillProgressTracker,
    db: Database,
    download_batch_size: int = 5,
    pause_ms: int = 3000,
    db_batch_size: int = 1000,
    temp_dir: Optional[str] = None,
    keep_files: bool = False,
) -> Dict[str, Dict]:
    """
    Backfill multiple symbols sequentially
    
    :return: Dictionary mapping symbol to result statistics
    """
    results = {}
    
    for symbol in symbols:
        try:
            result = process_symbol(
                symbol, start_time, end_time, progress_tracker, db,
                download_batch_size, pause_ms, db_batch_size, temp_dir, keep_files
            )
            results[symbol] = result
        except Exception as e:
            logger.error(f"Failed to backfill {symbol}: {e}")
            results[symbol] = {
                "status": "failed",
                "error": str(e),
                "ticks_inserted": 0
            }
    
    return results
```

#### 7. Integration Points

**BackfillProgressTracker Integration:**
- Use `connector_type="dukascopy_tick"` for tracking
- Create progress records per symbol/date range combination
- Support resume from `last_successful_time`
- Update progress during seeding (every batch)
- Mark as completed or failed appropriately

**QualityGate Integration:**
- Validate each tick before insertion using `QualityGate.validate_tick()`
- Log skipped records with validation error messages
- Track validation statistics (total validated, skipped, reasons)

**Database Integration:**
- Use existing `Database.insert_forex_ticks_batch()` method
- Format: List of tuples `(symbol, datetime, ask, bid)`
- Handle duplicate prevention (database unique constraints)
- Track insertion metrics via database metrics

#### 8. Error Handling & Resilience

**Rate Limiting:**
- Default to conservative settings: `batch_size=5`, `pause_ms=3000`
- Allow user configuration via CLI arguments
- Log rate limiting configuration

**Resume Capability:**
- Use `BackfillProgressTracker.get_resume_point()` to resume from last successful timestamp
- Skip already processed files if identifiable
- Update progress tracker on each batch insert

**Partial Failures:**
- Continue processing other symbols if one fails
- Log errors but don't stop entire process
- Return partial results with error information

**Cleanup:**
- Always cleanup temp directories using try/finally blocks
- Option to keep files with `--keep-files` flag
- Handle cleanup on script interruption (Ctrl+C)

**Logging:**
- Comprehensive logging at each step:
  - Download start/completion
  - File processing progress
  - Batch insert progress
  - Error conditions
  - Final statistics

#### 9. Date Range Detection

**Function: `get_dukascopy_date_range()`**

**Initial Implementation:**
- Use sensible defaults: `2000-01-01` to today
- Can be enhanced later with actual Dukascopy API query if available
- Allow override via CLI arguments

**Future Enhancement:**
- Query Dukascopy API for actual available date ranges per symbol
- Handle symbols with different availability dates

### Data Flow

```
1. Parse CLI arguments
2. Initialize Database, ProgressTracker, QualityGate
3. Determine date range (from args or defaults)
4. For each symbol:
   a. Check for existing progress (if --resume)
   b. Create progress tracking record
   c. Download data using dukascopy-node CLI → JSON files in temp dir
   d. Load and parse JSON files → List of (symbol, datetime, ask, bid) tuples
   e. Validate with QualityGate
   f. Batch insert into database
   g. Update progress tracker periodically
   h. Mark progress as completed
5. Aggregate statistics and report
6. Cleanup temporary files (unless --keep-files)
```

### Testing Strategy

1. **Unit Tests:**
   - `parse_dukascopy_tick()` with various JSON formats
   - `load_dukascopy_json()` with array and object formats
   - Date range parsing and validation
   - Error handling for invalid data

2. **Integration Tests:**
   - End-to-end download + seed for single symbol
   - Resume functionality with partial data
   - Multi-symbol processing
   - Progress tracking integration
   - Quality gate validation

3. **Manual Testing:**
   - Test with small date range first (e.g., 1 day)
   - Test with single symbol
   - Test resume functionality
   - Test error handling (network failures, invalid JSON)
   - Verify data quality in database

4. **Performance Testing:**
   - Test with large date ranges (months/years)
   - Monitor memory usage during processing
   - Verify batch insert performance
   - Test rate limiting effectiveness

### Dependencies

**External Requirements:**
- Node.js installed on system
- `dukascopy-node` package (installed via `npx` or `npm install -g dukascopy-node`)
- Python 3.8+ with existing project dependencies

**Internal Dependencies:**
- `src/trading_server/src/database/database.py` - Database class with `insert_forex_ticks_batch()`
- `src/trading_server/src/infrastructure/backfill/progress_tracker.py` - Progress tracking
- `src/trading_server/src/data/quality_gates.py` - Data validation
- `src/trading_server/src/utils/logging_config.py` - Logging utilities

**No Code Changes Required:**
- All existing infrastructure is used as-is
- No modifications to database schema
- No changes to existing backfill infrastructure

### Configuration & Defaults

**Default Symbols:** `["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]`

**Default Date Range:**
- Start: `2000-01-01` (or earliest available from Dukascopy)
- End: Today (`datetime.now()`)

**Default Rate Limiting:**
- Download batch size: `5` (conservative to avoid rate limits)
- Pause between batches: `3000ms` (3 seconds)
- Database batch size: `1000` (optimized for insert performance)

**Temporary Directory:**
- Default: System temp directory (`tempfile.gettempdir()`)
- Can be overridden with `--temp-dir` argument

## Metadata

- **Effort:** M (5 story points / 3-5 days)
  - Phase 1 (Core Script): 1-2 days
  - Phase 2 (Integration & Testing): 1-2 days
  - Phase 3 (Error Handling & Polish): 1 day
- **Dependencies:** 
  - Requires Node.js and `dukascopy-node` (external, user installs)
  - Uses existing infrastructure (no code changes needed)
- **Owner Role:** Data Engineering / Backend
- **Related Issues:**
  - Issue #20: Enable Paper Trading and Historical Environments (uses historical data)
  - Plan: `c:\Users\maxno\.cursor\plans\dukascopy_historical_data_collection_script_ba8f6d69.plan.md`

## Open Questions

1. **Date Range Detection**: Should we implement actual Dukascopy API query for available date ranges, or use fixed defaults? (Start with defaults, enhance later)

2. **OHLCV Bar Generation**: Should the script also generate OHLCV bars from ticks using existing `aggregate_ohlcv()` function, or keep it focused on ticks only? (Start with ticks only, can add bars later)

3. **Parallel Processing**: Should we support parallel symbol processing, or keep sequential to avoid rate limiting? (Start sequential, can enhance later)

4. **Dukascopy Connector**: Should we create a full `DukascopyConnector` class implementing `IDataSourceConnector`, or is the script sufficient? (Script is sufficient for now, connector can be future enhancement)

## Acceptance Criteria

- [ ] `scripts/backfill_dukascopy_data.py` created with full CLI interface
- [ ] Download module executes `dukascopy-node` CLI successfully
- [ ] Parsing module converts Dukascopy JSON to database format correctly
- [ ] Seeding module integrates with `BackfillProgressTracker`
- [ ] Seeding module integrates with `QualityGate` for validation
- [ ] Batch inserts use `Database.insert_forex_ticks_batch()` correctly
- [ ] Resume functionality works via `BackfillProgressTracker`
- [ ] Multi-symbol processing works sequentially
- [ ] Error handling for network failures, invalid data, missing files
- [ ] Comprehensive logging at all steps
- [ ] Temporary file cleanup works correctly
- [ ] CLI arguments all functional and validated
- [ ] Unit tests for parsing functions
- [ ] Integration test for end-to-end flow
- [ ] Manual testing with real Dukascopy data
- [ ] Documentation in script docstrings and README

## Files to Create

1. `scripts/backfill_dukascopy_data.py` - Main script (new, ~600-800 lines)

## Files to Reference (No Changes)

1. `scripts/backfill_mt5_data.py` - Reference implementation pattern
2. `src/trading_server/src/database/database.py` - Database batch insert methods
3. `src/trading_server/src/infrastructure/backfill/progress_tracker.py` - Progress tracking
4. `src/trading_server/src/data/quality_gates.py` - Data validation

## Future Enhancements (Out of Scope)

- OHLCV bar generation from ticks (can use existing `aggregate_ohlcv()` function from `scripts/backfill_mt5_data.py`)
- Parallel symbol processing (rate limiting concerns)
- Direct Dukascopy API integration (bypass CLI)
- Dukascopy connector class implementing `IDataSourceConnector`
- Automatic date range detection via Dukascopy API
- Support for additional data types (bars, order book, etc.)
