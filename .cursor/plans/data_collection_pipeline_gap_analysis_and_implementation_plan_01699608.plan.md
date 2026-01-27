---
name: Data Collection Pipeline Gap Analysis and Implementation Plan
overview: Comprehensive gap analysis between current codebase and the 5-phase data collection pipeline plans. Identifies what's implemented, what's missing, and provides an actionable plan to complete the pipeline with working, production-ready components.
todos:
  - id: verify-schema-registry-integration
    content: Verify Schema Registry integration with Contract Registry - test auto-registration and schema version checking
    status: completed
  - id: implement-data-docs-server
    content: Implement Great Expectations Data Docs web server - FastAPI endpoint to serve Data Docs HTML
    status: completed
  - id: complete-phase1-tests
    content: Complete Phase 1 integration tests - verify all tests pass and add missing coverage
    status: completed
    dependencies:
      - verify-schema-registry-integration
      - implement-data-docs-server
  - id: verify-technical-indicators
    content: Verify technical indicators expansion - check if 50+ indicators exist, add missing ones, update FeatureEngine
    status: in_progress
  - id: implement-regime-detection
    content: Implement regime detection features - create regime_detector.py with volatility, trend, and market state classifiers
    status: pending
    dependencies:
      - verify-technical-indicators
  - id: integrate-regime-features
    content: Integrate regime detection into FeatureEngine - add regime features to state vector
    status: pending
    dependencies:
      - implement-regime-detection
  - id: implement-sentiment-analyzer
    content: Implement sentiment analyzer module - create sentiment_analyzer.py with FinBERT model and batch processing
    status: pending
  - id: implement-entity-extractor
    content: Implement entity extractor module - create entity_extractor.py with spaCy/flair for currency pairs and events
    status: pending
  - id: integrate-sentiment-connectors
    content: Integrate sentiment analysis with news connectors - update RSSFeedConnector and WebScrapingConnector
    status: pending
    dependencies:
      - implement-sentiment-analyzer
      - implement-entity-extractor
  - id: integrate-alternative-features
    content: Integrate alternative data into FeatureEngine - add extract_news_features() and extract_macro_features() methods
    status: pending
    dependencies:
      - integrate-sentiment-connectors
  - id: implement-gap-detector
    content: Implement gap detection module - create gap_detector.py for all data types with time-based and frequency-based detection
    status: pending
  - id: implement-gap-filler
    content: Implement gap filling module - create gap_filler.py with multiple filling strategies
    status: pending
    dependencies:
      - implement-gap-detector
  - id: implement-historical-feature-computer
    content: Implement historical feature computation - create historical_feature_computer.py with point-in-time validation
    status: pending
  - id: create-point-in-time-validation
    content: Create point-in-time validation script - validate_point_in_time.py to check for lookahead bias
    status: pending
    dependencies:
      - implement-historical-feature-computer
---

# Data Collection Pipeline Gap Analysis and Implementation Plan

## Executive Summary

This plan analyzes the gaps between the current codebase and the 5-phase data collection pipeline plans. The analysis shows **significant progress** on Phase 1 (Foundation) and Phase 2 (Market Data), with **partial implementation** of Phase 3 (Alternative Data) and Phase 4 (Historical Backfill). The plan prioritizes completing critical missing components to deliver a working, production-ready data collection pipeline.

## Current State Assessment

### ✅ **Phase 1: Foundation - MOSTLY COMPLETE**

**Implemented:**

- ✅ Schema Registry: Core class, database table, API endpoints, compatibility checker
- ✅ Great Expectations: Context setup, expectation suites, quality gate integration
- ✅ Airflow: Services configured in docker-compose, DAGs created (data_collection_pipeline, historical_backfill_dag, alternative_data_collection_dag)
- ✅ Celery: Task structure exists (market_data_tasks.py)
- ✅ Redis: Configured in docker-compose
- ✅ Observability: Grafana dashboards (data_quality.json), Prometheus metrics defined
- ✅ Database migrations: All Phase 1 tables exist (schema_registry, backfill_progress)

**Missing/Incomplete:**

- ⚠️ Schema Registry integration with Contract Registry (Task 1.4) - partially done but needs verification
- ⚠️ Great Expectations Data Docs web server (Task 2.4) - not implemented
- ⚠️ Phase 1 integration tests - exist but need verification

### ✅ **Phase 2: Market Data Collection - MOSTLY COMPLETE**

**Implemented:**

- ✅ Backfill interface: `backfill()` and `get_available_range()` methods in base connector
- ✅ MT5 backfill: Implemented in MT5TickConnector
- ✅ OHLCV aggregator: TickToOHLCVAggregator class exists
- ✅ Bars table: Migration script exists (25_bars_forex_table.sql)
- ✅ Database methods: `insert_forex_bars_batch()` exists
- ✅ Backfill scripts: `backfill_mt5_data.py` exists with progress tracking
- ✅ Airflow DAG: `historical_backfill_dag.py` exists

**Missing/Incomplete:**

- ⚠️ Technical indicators expansion (50+ indicators) - needs verification
- ⚠️ Regime detection features - not implemented
- ⚠️ FeatureEngine integration with expanded indicators - needs verification

### ⚠️ **Phase 3: Alternative Data - PARTIALLY COMPLETE**

**Implemented:**

- ✅ News table: Migration exists (26_news_articles_table.sql)
- ✅ Economic indicators table: Migration exists (27_economic_indicators_table.sql)
- ✅ Database methods: `insert_news_article()`, `insert_news_articles_batch()`, `insert_economic_indicator()`, `insert_economic_indicators_batch()` exist
- ✅ Connectors: RSSFeedConnector, WebScrapingConnector, FREDConnector, WorldBankConnector, ECBConnector exist
- ✅ Backfill script: `backfill_alternative_data.py` exists
- ✅ Airflow DAG: `alternative_data_collection_dag.py` exists

**Missing/Incomplete:**

- ❌ Sentiment analyzer module - not implemented
- ❌ Entity extractor module - not implemented
- ❌ Sentiment integration with news connectors - not done
- ❌ FeatureEngine integration for alternative data features - not done

### ⚠️ **Phase 4: Historical Backfill - PARTIALLY COMPLETE**

**Implemented:**

- ✅ Backfill progress tracker: Database table exists (24_backfill_progress.sql)
- ✅ Backfill orchestrator: Class exists
- ✅ Gap detection: Not implemented
- ✅ Gap filling: Not implemented
- ✅ Historical feature computation: Not implemented

**Missing/Incomplete:**

- ❌ Gap detector module - not implemented
- ❌ Gap filler module - not implemented
- ❌ Historical feature computer - not implemented
- ❌ Point-in-time validation script - not implemented

### ❌ **Phase 5: Release Engineering - NOT STARTED**

**Missing:**

- ❌ Event recorder - not implemented
- ❌ Replay engine - not implemented
- ❌ Point-in-time test suite - not implemented
- ❌ Release checklist and scripts - not implemented

## Critical Gaps Analysis

### High Priority (Blocks Production Use)

1. **Great Expectations Data Docs Server** (Phase 1)

- Impact: Cannot view validation results
- Effort: Low (1-2 days)
- Files: `src/trading_server/src/infrastructure/data_quality/data_docs_server.py`

2. **Sentiment Analysis Pipeline** (Phase 3)

- Impact: News data incomplete without sentiment
- Effort: Medium (3-5 days)
- Files: `src/trading_server/src/utils/sentiment_analyzer.py`, `src/trading_server/src/utils/entity_extractor.py`

3. **FeatureEngine Alternative Data Integration** (Phase 3)

- Impact: Alternative data not usable in RL training
- Effort: Medium (2-3 days)
- Files: `src/trading_server/src/application/environment/feature_engine.py`

4. **Gap Detection and Filling** (Phase 4)

- Impact: Data quality issues may go undetected
- Effort: Medium (3-4 days)
- Files: `src/trading_server/src/infrastructure/backfill/gap_detector.py`, `gap_filler.py`

### Medium Priority (Enhances Production Readiness)

5. **Regime Detection Features** (Phase 2)

- Impact: Missing advanced features for RL state space
- Effort: Medium (3-4 days)
- Files: `src/trading_server/src/utils/regime_detector.py`

6. **Historical Feature Computation** (Phase 4)

- Impact: Cannot compute features on historical data
- Effort: Medium (2-3 days)
- Files: `src/trading_server/src/infrastructure/backfill/historical_feature_computer.py`

7. **Point-in-Time Validation** (Phase 4)

- Impact: Risk of lookahead bias in features
- Effort: Medium (2-3 days)
- Files: `scripts/validate_point_in_time.py`

### Low Priority (Nice to Have)

8. **Social Media Connectors** (Phase 3) - Optional
9. **Release Engineering** (Phase 5) - Can be deferred
10. **Event Replay System** (Phase 5) - Can be deferred

## Implementation Plan

### Phase 1 Completion (1-2 weeks)

**Goal:** Complete all Phase 1 foundation components

1. **Verify Schema Registry Integration** (1 day)

- Verify Contract Registry auto-registers schemas
- Test schema version checking in data pipeline
- Fix any integration issues

2. **Implement Data Docs Web Server** (1-2 days)

- Create FastAPI endpoint for Data Docs
- Serve static HTML from GE Data Docs store
- Add navigation to dashboard

3. **Complete Phase 1 Integration Tests** (1 day)

- Verify all Phase 1 tests pass
- Add missing test coverage
- Document test results

### Phase 2 Completion (1 week)

**Goal:** Complete market data collection features

1. **Verify Technical Indicators Expansion** (1 day)

- Check if 50+ indicators exist
- Add missing indicators if needed
- Update FeatureEngine integration

2. **Implement Regime Detection** (3-4 days)

- Create regime_detector.py module
- Implement volatility, trend, and market state classifiers
- Integrate into FeatureEngine

### Phase 3 Completion (2 weeks)

**Goal:** Complete alternative data integration

1. **Implement Sentiment Analysis** (3-4 days)

- Create sentiment_analyzer.py with FinBERT
- Create entity_extractor.py with spaCy/flair
- Add batch processing support

2. **Integrate Sentiment with Connectors** (2 days)

- Update RSSFeedConnector to use sentiment analyzer
- Update WebScrapingConnector to use sentiment analyzer
- Store sentiment scores in database

3. **Integrate Alternative Data into FeatureEngine** (2-3 days)

- Add `extract_news_features()` method
- Add `extract_macro_features()` method
- Ensure point-in-time computation
- Update FeatureCatalog

### Phase 4 Completion (1-2 weeks)

**Goal:** Complete historical backfill infrastructure

1. **Implement Gap Detection** (2-3 days)

- Create gap_detector.py module
- Implement gap detection for all data types
- Store gap information in database

2. **Implement Gap Filling** (2 days)

- Create gap_filler.py module
- Implement multiple filling strategies
- Integrate with backfill orchestrator

3. **Implement Historical Feature Computation** (2-3 days)

- Create historical_feature_computer.py
- Ensure point-in-time computation
- Add progress tracking

4. **Create Point-in-Time Validation** (2 days)

- Create validate_point_in_time.py script
- Test with historical data
- Generate validation reports

## Success Criteria

### Phase 1 Complete

- [ ] Schema Registry fully integrated with Contract Registry
- [ ] Data Docs accessible via web UI
- [ ] All Phase 1 integration tests pass

### Phase 2 Complete

- [ ] 50+ technical indicators available
- [ ] Regime detection features working
- [ ] All indicators integrated into FeatureEngine

### Phase 3 Complete

- [ ] Sentiment analysis working on news articles
- [ ] Entity extraction working
- [ ] Alternative data features in FeatureEngine
- [ ] Point-in-time computation verified

### Phase 4 Complete

- [ ] Gap detection working for all data types
- [ ] Gap filling operational
- [ ] Historical features computable
- [ ] Point-in-time validation passing

## Risk Mitigation

1. **Sentiment Analysis Performance**

- Use batch processing
- Cache model loading (singleton)
- Consider GPU acceleration if needed

2. **Gap Detection Accuracy**

- Start with simple time-based gap detection
- Iterate based on data patterns
- Allow manual gap marking

3. **Feature Computation Performance**

- Process in batches
- Use incremental computation
- Monitor memory usage

## Next Steps

1. **Immediate (This Week)**

- Complete Phase 1 Data Docs server
- Verify Schema Registry integration
- Start sentiment analyzer implementation

2. **Short Term (Next 2 Weeks)**

- Complete Phase 3 sentiment integration
- Implement gap detection
- Integrate alternative data into FeatureEngine

3. **Medium Term (Next Month)**

- Complete Phase 4 backfill infrastructure
- Implement regime detection
- Full end-to-end testing

## Files to Create/Modify

### New Files

- `src/trading_server/src/infrastructure/data_quality/data_docs_server.py`
- `src/trading_server/src/utils/sentiment_analyzer.py`
- `src/trading_server/src/utils/entity_extractor.py`
- `src/trading_server/src/utils/regime_detector.py`
- `src/trading_server/src/infrastructure/backfill/gap_detector.py`
- `src/trading_server/src/infrastructure/backfill/gap_filler.py`
- `src/trading_server/src/infrastructure/backfill/historical_feature_computer.py`
- `scripts/validate_point_in_time.py`

### Files to Modify

- `src/trading_server/src/data/contracts/registry.py` (verify Schema Registry integration)
- `src/trading_server/src/connectors/rss_feed_connector.py` (add sentiment)
- `src/trading_server/src/connectors/web_scraping_connector.py` (add sentiment)
- `src/trading_server/src/application/environment/feature_engine.py` (add alternative data features)
- `src/api/src/main.py` (add Data Docs endpoint)

## Dependencies

- **Phase 1** → Required for all other phases
- **Phase 2** → Required before Phase 4 historical features
- **Phase 3** → Can proceed in parallel with Phase 2
- **Phase 4** → Requires Phases 1-3 complete

## Estimated Timeline

- **Phase 1 Completion**: 1-2 weeks
- **Phase 2 Completion**: 1 week
- **Phase 3 Completion**: 2 weeks
- **Phase 4 Completion**: 1-2 weeks
- **Total**: 5-7 weeks for production-ready pipeline

This plan prioritizes delivering a **working, usable data collection pipeline** by focusing on critical gaps that block production use, while deferring Phase 5 (Release Engineering) which can be added later.