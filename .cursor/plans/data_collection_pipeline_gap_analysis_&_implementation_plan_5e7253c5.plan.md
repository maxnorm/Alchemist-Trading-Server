---
name: Data Collection Pipeline Gap Analysis & Implementation Plan
overview: Comprehensive gap analysis identifying what's implemented vs planned across all 5 phases, with prioritized action items to complete a working data collection pipeline that can be used immediately.
todos:
  - id: verify-database-methods
    content: "Verify and add missing database methods: insert_forex_bars_batch(), insert_news_articles_batch(), insert_economic_indicators_batch()"
    status: pending
  - id: integrate-schema-registry-contracts
    content: Integrate Schema Registry with Contract Registry - auto-register contracts on startup
    status: pending
  - id: fix-backfill-ohlcv-integration
    content: Ensure backfill_mt5_data.py aggregates ticks to OHLCV and stores bars in database
    status: pending
  - id: create-historical-backfill-dag
    content: Create Airflow DAG for historical backfill (historical_backfill_dag.py) with MT5 and alternative data tasks
    status: pending
  - id: end-to-end-mt5-test
    content: "Test complete MT5 flow: connector → quality gates → database → dashboard"
    status: pending
  - id: create-sentiment-analyzer
    content: Create sentiment_analyzer.py module with FinBERT integration for news sentiment analysis
    status: pending
  - id: integrate-alternative-features
    content: Add extract_news_features() and extract_macro_features() to FeatureEngine
    status: pending
  - id: create-gap-detector
    content: Create gap_detector.py module to detect data gaps in historical data
    status: pending
  - id: create-data-docs-server
    content: Create data_docs_server.py to serve Great Expectations Data Docs via web interface
    status: pending
  - id: add-backfill-monitoring
    content: Add backfill progress monitoring panels to Grafana data quality dashboard
    status: pending
---

# Data Collection Pipeline Gap Analysis & Implementation Plan

## Executive Summary

After reviewing the codebase against the 5-phase implementation plans, here's the status:

**Phase 1 (Foundation)**: ~85% Complete - Schema Registry, Great Expectations, Airflow/Celery infrastructure exists
**Phase 2 (Market Data)**: ~70% Complete - Backfill interface, OHLCV aggregator, progress tracking exist
**Phase 3 (Alternative Data)**: ~60% Complete - Connectors exist but need integration and testing
**Phase 4 (Historical Backfill)**: ~50% Complete - Scripts exist but orchestration incomplete
**Phase 5 (Release Engineering)**: ~0% Complete - Not started

**Critical Gap**: While infrastructure exists, the end-to-end pipeline is not fully operational. Missing integrations, incomplete testing, and missing operational scripts prevent immediate use.

## Phase-by-Phase Gap Analysis

### Phase 1: Foundation (85% Complete)

#### ✅ **Implemented**

- Schema Registry database table (`23_schema_registry.sql`)
- Schema Registry core class (`src/trading_server/src/infrastructure/schema_registry/registry.py`)
- Compatibility checker (`src/trading_server/src/infrastructure/schema_registry/compatibility.py`)
- Schema Registry API endpoints (`src/api/src/routers/schema.py`)
- Great Expectations integration (`src/trading_server/src/infrastructure/data_quality/ge_expectations.py`)
- GE context setup (`src/trading_server/src/infrastructure/data_quality/ge_context.py`)
- Quality gates with GE validation (`src/trading_server/src/data/quality_gates.py`)
- Redis service in docker-compose.yml
- Airflow services (webserver, scheduler, worker) in docker-compose.yml
- Airflow DAG structure (`src/trading_server/src/infrastructure/data_pipeline/airflow/dags/`)
- Celery app (`src/trading_server/src/infrastructure/data_pipeline/celery_app.py`)
- Celery tasks (`market_data_tasks.py`, `news_data_tasks.py`, `economic_data_tasks.py`)
- Grafana data quality dashboard (`src/monitoring/grafana/dashboards/data_quality.json`)
- Prometheus metrics (`src/trading_server/src/monitoring/metrics.py`)

#### ⚠️ **Partially Implemented / Needs Work**

1. **Schema Registry ↔ Contract Registry Integration**

- Location: `src/trading_server/src/data/contracts/registry.py`
- Gap: Contracts don't auto-register with Schema Registry on startup
- Impact: Schema versioning not enforced in data pipeline
- Fix: Add Schema Registry dependency to ContractRegistry, auto-register on init

2. **Great Expectations Data Docs Server**

- Location: Missing
- Gap: No web server to serve GE Data Docs
- Impact: Can't view validation results in browser
- Fix: Add FastAPI endpoint or standalone server for Data Docs

3. **Data Quality Metrics Integration**

- Location: `src/trading_server/src/monitoring/metrics.py`
- Gap: Metrics may not be fully integrated into quality gate pipeline
- Impact: Dashboard may show incomplete data
- Fix: Verify metrics are updated in all quality gate paths

#### ❌ **Missing**

1. **Phase 1 Integration Tests**

- Location: `tests/integration/test_phase1_foundation.py` (exists but may be incomplete)
- Gap: Tests may not cover all scenarios
- Fix: Complete integration tests for Schema Registry, GE, Airflow, metrics

---

### Phase 2: Core Market Data Collection (70% Complete)

#### ✅ **Implemented**

- Backfill interface in base connector (`src/trading_server/src/connectors/base.py`)
- MT5 backfill implementation (`src/trading_server/src/connectors/mt5_tick_connector.py`)
- `bars_forex` database table (`src/database/scripts/25_bars_forex_table.sql`)
- OHLCV aggregator (`src/trading_server/src/utils/ohlcv_aggregator.py`)
- Database methods for bars (`src/trading_server/src/database.py` - needs verification)
- Backfill progress tracker (`src/trading_server/src/infrastructure/backfill/progress_tracker.py`)
- Backfill progress table (`src/database/scripts/24_backfill_progress.sql`)
- Backfill orchestrator (`src/trading_server/src/infrastructure/backfill/orchestrator.py`)
- MT5 backfill script (`scripts/backfill_mt5_data.py`)

#### ⚠️ **Partially Implemented / Needs Work**

1. **OHLCV Database Methods**

- Location: `src/trading_server/src/database.py`
- Gap: Need to verify `insert_forex_bar()` and `insert_forex_bars_batch()` exist
- Impact: Can't store aggregated bars
- Fix: Add methods if missing, verify integration with aggregator

2. **Backfill Script Integration**

- Location: `scripts/backfill_mt5_data.py`
- Gap: Script may not fully integrate OHLCV aggregation with progress tracking
- Impact: Backfill may not generate bars automatically
- Fix: Ensure script aggregates to OHLCV after tick collection

3. **Airflow DAG for Historical Backfill**

- Location: `src/trading_server/src/infrastructure/data_pipeline/airflow/dags/`
- Gap: May not have dedicated historical backfill DAG
- Impact: Can't schedule automated backfills
- Fix: Create `historical_backfill_dag.py` with backfill tasks

#### ❌ **Missing**

1. **Technical Indicators Expansion (50+ indicators)**

- Location: `src/trading_server/src/utils/technical_indicators.py`
- Gap: Only ~14 indicators exist, plan requires 50+
- Impact: Limited feature set for RL training
- Priority: Medium (can work with existing indicators initially)

2. **Regime Detection Features**

- Location: Missing
- Gap: No regime detector module
- Impact: Missing market state features
- Priority: Low (nice to have, not critical for MVP)

3. **Gap Detection & Filling**

- Location: Missing
- Gap: No gap detector or filler modules
- Impact: Can't automatically detect/fill data gaps
- Priority: Medium (important for data quality)

---

### Phase 3: Alternative Data Integration (60% Complete)

#### ✅ **Implemented**

- `news_articles` table (`src/database/scripts/26_news_articles_table.sql`)
- `economic_indicators` table (`src/database/scripts/27_economic_indicators_table.sql`)
- NewsAPI connector (`src/trading_server/src/connectors/news_api_connector.py`)
- RSS feed connector (`src/trading_server/src/connectors/rss_feed_connector.py`)
- Web scraping connector (`src/trading_server/src/connectors/web_scraping_connector.py`)
- FRED connector (`src/trading_server/src/connectors/fred_connector.py`)
- World Bank connector (`src/trading_server/src/connectors/world_bank_connector.py`)
- ECB connector (`src/trading_server/src/connectors/ecb_connector.py`)
- Alternative data backfill script (`scripts/backfill_alternative_data.py`)
- Airflow DAG for alternative data (`src/trading_server/src/infrastructure/data_pipeline/airflow/dags/alternative_data_collection_dag.py`)

#### ⚠️ **Partially Implemented / Needs Work**

1. **Sentiment Analysis Pipeline**

- Location: Missing
- Gap: No `sentiment_analyzer.py` module
- Impact: News data collected but not analyzed
- Fix: Create FinBERT-based sentiment analyzer

2. **Entity Extraction**

- Location: Missing
- Gap: No `entity_extractor.py` module
- Impact: Can't extract currency pairs/events from news
- Fix: Create spaCy/flair-based entity extractor

3. **News Database Methods**

- Location: `src/trading_server/src/database.py`
- Gap: Need to verify `insert_news_article()` and `insert_news_articles_batch()` exist
- Impact: Can't store news data
- Fix: Add methods if missing

4. **Economic Indicators Database Methods**

- Location: `src/trading_server/src/database.py`
- Gap: Need to verify `insert_economic_indicator()` and `insert_economic_indicators_batch()` exist
- Impact: Can't store economic data
- Fix: Add methods if missing

5. **Feature Engine Integration**

- Location: `src/trading_server/src/application/environment/feature_engine.py`
- Gap: Alternative data features not integrated
- Impact: Can't use news/macro data in RL state
- Fix: Add `extract_news_features()`, `extract_macro_features()` methods

#### ❌ **Missing**

1. **Social Media Connectors (Optional)**

- Reddit connector
- Twitter connector
- Priority: Low (optional per plan)

2. **Sentiment Aggregator**

- Multi-source sentiment aggregation
- Priority: Medium

---

### Phase 4: Historical Backfill (50% Complete)

#### ✅ **Implemented**

- Backfill progress tracker (from Phase 2)
- Backfill orchestrator (from Phase 2)
- MT5 backfill script
- Alternative data backfill script

#### ⚠️ **Partially Implemented / Needs Work**

1. **Gap Detection Module**

- Location: Missing
- Gap: No `gap_detector.py`
- Impact: Can't automatically detect data gaps
- Fix: Create gap detection module

2. **Gap Filling Module**

- Location: Missing
- Gap: No `gap_filler.py`
- Impact: Can't automatically fill gaps
- Fix: Create gap filling module

3. **Historical Feature Computation**

- Location: Missing
- Gap: No `historical_feature_computer.py`
- Impact: Can't compute features on historical data
- Fix: Create feature computation pipeline

4. **Backfill Monitoring**

- Location: Missing
- Gap: No dedicated backfill monitoring dashboard
- Impact: Can't track backfill progress visually
- Fix: Add backfill panels to Grafana dashboard

#### ❌ **Missing**

1. **Data Gaps Table**

- Location: Missing migration script
- Gap: No table to store detected gaps
- Fix: Create `22_data_gaps_table.sql` migration

2. **Point-in-Time Validation Script**

- Location: Missing
- Gap: No script to validate no lookahead bias
- Fix: Create `validate_point_in_time.py` script

---

### Phase 5: Release Engineering (0% Complete)

#### ❌ **Missing (All)**

1. Event recorder for data replay
2. Replay engine
3. Replay tests
4. Point-in-time test suite
5. FeatureEngine point-in-time validation
6. Release checklist documentation
7. Release scripts

**Priority**: Low - Can defer for MVP, focus on getting pipeline operational first

---

## Critical Path to Working Pipeline

### Immediate Priorities (Week 1-2)

1. **Fix Database Methods** (P0 - Blocks data storage)

- Verify/add `insert_forex_bars_batch()` in Database class
- Verify/add `insert_news_articles_batch()` in Database class
- Verify/add `insert_economic_indicators_batch()` in Database class
- Test all methods with sample data

2. **Complete Contract ↔ Schema Registry Integration** (P0 - Blocks schema versioning)

- Add Schema Registry dependency to ContractRegistry
- Auto-register contracts on startup
- Test schema versioning in data pipeline

3. **Fix Backfill Script Integration** (P0 - Blocks historical data collection)

- Ensure `backfill_mt5_data.py` aggregates to OHLCV
- Test end-to-end: MT5 backfill → ticks → bars → database
- Verify progress tracking works

4. **Create Airflow Historical Backfill DAG** (P0 - Blocks automation)

- Create `historical_backfill_dag.py`
- Add tasks for MT5 backfill, alternative data backfill
- Test DAG execution

5. **End-to-End Integration Test** (P0 - Validates pipeline works)

- Test: MT5 connector → quality gates → database
- Test: News connector → database
- Test: Economic connector → database
- Verify data appears in database and dashboards

### High Priority (Week 3-4)

6. **Sentiment Analysis Integration** (P1 - Enables news features)

- Create sentiment analyzer module
- Integrate with news connectors
- Test sentiment scoring

7. **Feature Engine Integration** (P1 - Enables alternative data in RL)

- Add news feature extraction
- Add macro feature extraction
- Test point-in-time computation

8. **Gap Detection** (P1 - Improves data quality)

- Create gap detector module
- Add gap detection to backfill pipeline
- Test gap detection accuracy

### Medium Priority (Week 5+)

9. Technical indicators expansion (50+)
10. Regime detection features
11. Gap filling automation
12. Historical feature computation
13. Enhanced monitoring dashboards

---

## Implementation Strategy

### Approach: "Thin Vertical Slice"

Instead of completing each phase fully, implement one complete end-to-end flow:

1. **MT5 Data Flow** (Priority 1)

- MT5 connector → Quality gates → Database → Dashboard
- Includes: real-time streaming + historical backfill
- Verify: Data appears in `ticks_forex` table and Grafana

2. **OHLCV Data Flow** (Priority 2)

- Tick data → OHLCV aggregation → Database
- Verify: Data appears in `bars_forex` table

3. **News Data Flow** (Priority 3)

- RSS connector → Sentiment analysis → Database
- Verify: Data appears in `news_articles` table

4. **Economic Data Flow** (Priority 4)

- FRED connector → Database
- Verify: Data appears in `economic_indicators` table

### Testing Strategy

For each flow:

1. **Unit Tests**: Test individual components
2. **Integration Tests**: Test component interactions
3. **End-to-End Tests**: Test complete pipeline
4. **Manual Verification**: Check database, dashboards, logs

---

## Files to Review/Modify

### Critical Files (Must Fix)

- `src/trading_server/src/database.py` - Verify/add database methods
- `src/trading_server/src/data/contracts/registry.py` - Add Schema Registry integration
- `scripts/backfill_mt5_data.py` - Verify OHLCV integration
- `src/trading_server/src/infrastructure/data_pipeline/airflow/dags/` - Add historical backfill DAG

### New Files to Create

- `src/trading_server/src/utils/sentiment_analyzer.py` - Sentiment analysis
- `src/trading_server/src/utils/entity_extractor.py` - Entity extraction
- `src/trading_server/src/infrastructure/backfill/gap_detector.py` - Gap detection
- `src/trading_server/src/infrastructure/data_quality/data_docs_server.py` - GE Data Docs server
- `src/trading_server/src/infrastructure/data_pipeline/airflow/dags/historical_backfill_dag.py` - Backfill DAG

### Files to Enhance

- `src/trading_server/src/application/environment/feature_engine.py` - Add alternative data features
- `src/monitoring/grafana/dashboards/data_quality.json` - Add backfill monitoring panels

---

## Success Criteria

### MVP (Minimum Viable Pipeline)

- [ ] MT5 tick data flowing end-to-end (connector → database → dashboard)
- [ ] OHLCV bars being generated and stored
- [ ] Historical backfill working (can backfill 1+ months of data)
- [ ] News data being collected and stored (with or without sentiment)
- [ ] Economic indicators being collected and stored
- [ ] Airflow DAGs running successfully
- [ ] Data visible in Grafana dashboards
- [ ] Quality gates validating data

### Production Ready

- [ ] All MVP criteria met
- [ ] Sentiment analysis operational
- [ ] Alternative data features in FeatureEngine
- [ ] Gap detection working
- [ ] Comprehensive monitoring
- [ ] Integration tests passing
- [ ] Documentation complete

---

## Risk Mitigation

1. **Database Methods Missing**: High risk - blocks all data storage

- Mitigation: Verify first, add immediately if missing

2. **Integration Issues**: Medium risk - components exist but don't work together

- Mitigation: Focus on end-to-end testing early

3. **Performance Issues**: Medium risk - backfill may be slow

- Mitigation: Test with small date ranges first, optimize iteratively

4. **Missing Dependencies**: Low risk - most dependencies likely installed

- Mitigation: Check requirements.txt, install missing packages

---

## Next Steps

1. **Immediate**: Review and fix database methods
2. **Day 1**: Complete Contract ↔ Schema Registry integration
3. **Day 2-3**: Fix backfill script, create historical backfill DAG
4. **Day 4-5**: End-to-end testing of MT5 flow
5. **Week 2**: Add sentiment analysis, integrate alternative data features
6. **Week 3+**: Complete remaining gaps based on priorities

This plan prioritizes getting a working pipeline operational quickly, then iteratively improving it.