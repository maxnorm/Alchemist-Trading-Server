---
name: Phase 2 Core Market Data Collection
overview: Implement comprehensive market data collection including MT5 historical backfill, multi-timeframe OHLCV data collection, expansion of technical indicators from 14 to 50+, and regime detection features for RL training.
todos:
  - id: add-backfill-interface
    content: Add backfill() and get_available_range() abstract methods to IDataSourceConnector base class
    status: pending
  - id: implement-mt5-backfill
    content: Implement backfill() method in MT5TickConnector using MetaTrader5.copy_ticks_range() API
    status: pending
    dependencies:
      - add-backfill-interface
  - id: create-bars-table
    content: Create bars_forex database table migration script with TimescaleDB hypertable conversion
    status: pending
  - id: add-ohlcv-db-methods
    content: Add insert_forex_bar() and insert_forex_bars_batch() methods to Database class
    status: pending
    dependencies:
      - create-bars-table
  - id: create-ohlcv-aggregator
    content: Create ohlcv_aggregator.py utility to aggregate tick data to OHLCV bars for multiple timeframes
    status: pending
    dependencies:
      - add-ohlcv-db-methods
  - id: create-backfill-scripts
    content: Create backfill_mt5_ticks.py script with progress tracking and OHLCV aggregation pipeline
    status: pending
    dependencies:
      - implement-mt5-backfill
      - create-ohlcv-aggregator
  - id: expand-technical-indicators
    content: Add 30+ new technical indicators to TechnicalIndicators class (ATR, Stochastic, Williams %R, CCI, etc.)
    status: pending
  - id: update-calculate-all-indicators
    content: Update calculate_all_indicators() to accept OHLCV data and return 50+ indicators
    status: pending
    dependencies:
      - expand-technical-indicators
  - id: integrate-indicators-feature-engine
    content: Update FeatureEngine to use expanded indicators and OHLCV data when available
    status: pending
    dependencies:
      - update-calculate-all-indicators
  - id: create-regime-detector
    content: Create regime_detector.py module with volatility, trend, and market state classifiers
    status: pending
    dependencies:
      - expand-technical-indicators
  - id: integrate-regime-features
    content: Integrate regime detection features into FeatureEngine pipeline
    status: pending
    dependencies:
      - create-regime-detector
  - id: add-indicator-tests
    content: Add unit tests for all new technical indicators and regime detection features
    status: pending
    dependencies:
      - expand-technical-indicators
      - create-regime-detector
---

# Phase 2: Core Market Data Collection (Weeks 5-8)

## Overview

Phase 2 builds on Phase 1 infrastructure to collect comprehensive market data for RL state space. This phase focuses on historical data backfill, multi-timeframe data collection, expanded feature engineering, and regime detection.

## Week 5-6: Enhanced Market Data Collection

### 2.1 MT5 Historical Data Backfill

**Current State:**

- `MT5TickConnector` exists at [src/trading_server/src/connectors/mt5_tick_connector.py](src/trading_server/src/connectors/mt5_tick_connector.py)
- `batch()` method only reads from database, not MT5 API
- Database has `insert_forex_tick()` and `insert_forex_ticks_batch()` methods in [src/trading_server/src/database.py](src/trading_server/src/database.py)
- Base connector interface at [src/trading_server/src/connectors/base.py](src/trading_server/src/connectors/base.py) needs `backfill()` method

**Implementation Tasks:**

1. **Add `backfill()` method to base connector interface**

- Enhance [src/trading_server/src/connectors/base.py](src/trading_server/src/connectors/base.py)
- Add abstract `backfill(start_time, end_time, batch_size)` method to `IDataSourceConnector`
- Add abstract `get_available_range()` method to query data availability

2. **Implement MT5 historical backfill in MT5TickConnector**

- Enhance [src/trading_server/src/connectors/mt5_tick_connector.py](src/trading_server/src/connectors/mt5_tick_connector.py)
- Implement `backfill()` using `MetaTrader5.copy_ticks_range()` API
- Use `mt5.COPY_TICKS_ALL` flag for comprehensive tick data
- Process in daily batches to avoid memory issues
- Integrate with existing `insert_forex_ticks_batch()` for efficient storage
- Add rate limiting (0.1s delay between batches) to respect MT5 API limits
- Implement `get_available_range()` using MT5 API to query available historical range

3. **Create backfill orchestration script**

- Create `scripts/backfill_mt5_ticks.py`
- Support backfilling 5+ years of historical data
- Add progress tracking and resume capability
- Integrate with Airflow DAGs from Phase 1 for scheduled backfills

4. **Add database methods for OHLCV data**

- Enhance [src/trading_server/src/database.py](src/trading_server/src/database.py)
- Add `insert_forex_bar()` method for single bar insertion
- Add `insert_forex_bars_batch()` method for bulk bar insertion
- Support bitemporal timestamps (event_time, receive_time) like tick data

### 2.2 Multi-Timeframe OHLCV Data Collection

**Current State:**

- Schema contract exists in [docs/SCHEMA_CONTRACTS.md](docs/SCHEMA_CONTRACTS.md) defining `bars_forex` table structure
- No `bars_forex` table exists yet in database
- Tick data will be collected via MT5 `copy_ticks_range()` API (from section 2.1)

**Approach:**

**Use MT5 tick data and build OHLCV ourselves** - This provides:

- Single source of truth (all OHLCV from same tick data)
- Full control over aggregation logic (consistent with feature engineering)
- Flexibility to create any timeframe
- Point-in-time aggregation aligned with RL training needs
- Fewer API calls (only need `copy_ticks_range()`, not `copy_rates_range()` per timeframe)

**Implementation Tasks:**

1. **Create bars_forex database table**

- Create migration script: `src/database/scripts/20_bars_forex_table.sql`
- Table structure: `symbol`, `datetime`, `open`, `high`, `low`, `close`, `volume`, `timeframe`, `receive_time`
- Convert to TimescaleDB hypertable with 1-day chunk interval
- Add indexes: `(symbol, timeframe, datetime)`, `(datetime)` for efficient queries
- Foreign key to `forex_pairs` table

2. **Create OHLCV aggregation utility**

- Create `src/trading_server/src/utils/ohlcv_aggregator.py`
- Implement `TickToOHLCVAggregator` class:
- Aggregate tick data to OHLCV bars for multiple timeframes
- Support timeframes: M1, M5, M15, M30, H1, H4, D1
- Use mid-price (average of bid/ask) for OHLC calculations
- Handle gaps in tick data gracefully
- Support point-in-time aggregation (no future data)
- Batch processing for efficiency
- Methods:
- `aggregate_ticks(ticks, timeframe)` - Convert tick list to OHLCV bars
- `aggregate_timeframe(ticks, timeframe, start_time, end_time)` - Aggregate specific range
- `aggregate_all_timeframes(ticks, timeframes)` - Generate all timeframes at once

3. **Integrate OHLCV aggregation into backfill pipeline**

- Enhance `scripts/backfill_mt5_ticks.py`:
- After collecting tick data, automatically aggregate to OHLCV
- Generate all required timeframes (M1, M5, M15, H1, H4, D1)
- Use `insert_forex_bars_batch()` for efficient storage
- Progress tracking for both tick collection and OHLCV aggregation
- Resume capability for partial backfills

4. **Add real-time OHLCV aggregation (optional)**

- Enhance tick streaming to maintain OHLCV state
- Update bars in real-time as ticks arrive
- Flush completed bars to database periodically

**Timeframes for RL Training:**

- **M1 (1-minute)**: High-frequency strategies
- **M5 (5-minute)**: Intraday strategies  
- **M15 (15-minute)**: Short-term strategies
- **H1 (1-hour)**: Medium-term strategies
- **H4 (4-hour)**: Swing strategies
- **D1 (1-day)**: Position strategies

## Week 7-8: Feature Engineering Pipeline

### 2.3 Technical Indicators Expansion

**Current State:**

- `TechnicalIndicators` class at [src/trading_server/src/utils/technical_indicators.py](src/trading_server/src/utils/technical_indicators.py)
- Currently has: SMA, EMA, RSI, MACD, Bollinger Bands (~14 features)
- `FeatureEngine` at [src/trading_server/src/application/environment/feature_engine.py](src/trading_server/src/application/environment/feature_engine.py) uses these indicators
- Point-in-time computation already implemented

**Implementation Tasks:**

1. **Expand TechnicalIndicators class**

- Enhance [src/trading_server/src/utils/technical_indicators.py](src/trading_server/src/utils/technical_indicators.py)
- Add volatility indicators:
- `atr()` - Average True Range (requires high, low, close)
- `realized_volatility()` - Rolling standard deviation of returns
- `parkinson_volatility()` - High-low volatility estimator
- Add momentum indicators:
- `stochastic()` - Stochastic Oscillator (K%, D%)
- `williams_r()` - Williams %R
- `cci()` - Commodity Channel Index
- `roc()` - Rate of Change
- `momentum()` - Price momentum
- Add volume indicators (when volume data available):
- `obv()` - On-Balance Volume
- `vwap()` - Volume Weighted Average Price
- `chaikin_mf()` - Chaikin Money Flow
- `ad()` - Accumulation/Distribution
- Add statistical features:
- `skewness()` - Price distribution skewness
- `kurtosis()` - Price distribution kurtosis
- `autocorrelation()` - Lag-1 autocorrelation
- `hurst_exponent()` - Long-term memory measure
- Add trend indicators:
- `adx()` - Average Directional Index
- `aroon()` - Aroon Indicator (up/down)
- `parabolic_sar()` - Parabolic SAR
- `ichimoku()` - Ichimoku Cloud components
- Add oscillator indicators:
- `awesome_oscillator()` - Awesome Oscillator
- `ultimate_oscillator()` - Ultimate Oscillator
- `trix()` - TRIX indicator

2. **Update calculate_all_indicators() method**

- Modify `calculate_all_indicators()` to accept OHLCV data (high, low, close, volume)
- Add all new indicators to the calculation pipeline
- Maintain backward compatibility with price-only input
- Return 50+ indicator features

3. **Update FeatureEngine integration**

- Enhance [src/trading_server/src/application/environment/feature_engine.py](src/trading_server/src/application/environment/feature_engine.py)
- Update `extract_features()` to pass OHLCV data when available
- Update `_generate_feature_list()` to include all new indicators
- Ensure point-in-time computation for all new indicators

4. **Add indicator tests**

- Expand [tests/test_feature_engineering.py](tests/test_feature_engineering.py)
- Add unit tests for each new indicator
- Verify indicator ranges and edge cases
- Test with OHLCV data

### 2.4 Regime Detection Features

**Implementation Tasks:**

1. **Create regime detection module**

- Create `src/trading_server/src/utils/regime_detector.py`
- Implement `VolatilityRegimeDetector`:
- Classify high/low volatility using ATR percentiles
- Rolling window analysis (e.g., 20-day ATR vs 200-day ATR)
- Return regime labels: "high_volatility", "low_volatility", "normal"
- Implement `TrendRegimeDetector`:
- Classify trending vs mean-reverting using ADX
- Moving average slope analysis
- Return regime labels: "trending", "mean_reverting", "sideways"
- Implement `MarketStateClassifier`:
- Combine volatility and trend regimes
- Classify: "bull_trending", "bear_trending", "bull_sideways", "bear_sideways", "high_volatility", "low_volatility"
- Implement `RegimeTransitionAnalyzer`:
- Calculate transition probabilities between regimes
- Detect regime change points
- Return transition features for RL state

2. **Integrate regime features into FeatureEngine**

- Enhance [src/trading_server/src/application/environment/feature_engine.py](src/trading_server/src/application/environment/feature_engine.py)
- Add regime features to feature extraction pipeline
- Include regime labels and transition probabilities in state vector
- Ensure point-in-time regime detection (no lookahead)

3. **Add regime detection tests**

- Create `tests/test_regime_detection.py`
- Test regime classification accuracy
- Test transition detection
- Verify point-in-time constraints

## Success Criteria

- [ ] `backfill()` method implemented in MT5TickConnector using MT5 API
- [ ] 5+ years of historical tick data collected via backfill
- [ ] `bars_forex` table created and converted to TimescaleDB hypertable
- [ ] OHLCV aggregation utility working to convert ticks to bars for all timeframes (M1, M5, M15, H1, H4, D1)
- [ ] TechnicalIndicators expanded to 50+ indicators
- [ ] All new indicators integrated into FeatureEngine
- [ ] Regime detection features working (volatility, trend, market state)
- [ ] Point-in-time computation verified for all features
- [ ] Unit tests added for new indicators and regime detection

## Dependencies

- Phase 1 infrastructure (Airflow, Celery, Redis) must be operational
- MT5 terminal must be accessible for historical data API calls
- Database connection pool from Phase 1
- Existing `insert_forex_ticks_batch()` method for efficient storage

## Testing Strategy

- Unit tests for each new technical indicator
- Integration test: Backfill 1 month of tick data from MT5
- Integration test: Aggregate ticks to OHLCV for all timeframes and verify correctness
- Integration test: Verify regime detection on historical data
- Point-in-time validation: Ensure no lookahead bias in features
- Performance test: Verify backfill can handle 5+ years efficiently