---
name: Production Data Collection Pipeline Implementation
overview: Comprehensive implementation plan for building a production-grade data collection pipeline with Schema Registry, Great Expectations, Airflow orchestration, historical backfill, alternative data sources, observability, lineage tracking, and release engineering gates. This plan breaks down the 5-phase roadmap into detailed, actionable tasks with clear dependencies and acceptance criteria.
todos:
  - id: schema_registry_table
    content: Create schema_registry database table migration (23_schema_registry.sql)
    status: pending
  - id: schema_registry_class
    content: Implement SchemaRegistry core class with register_schema(), get_schema(), validate_compatibility() methods
    status: pending
    dependencies:
      - schema_registry_table
  - id: compatibility_checker
    content: Implement compatibility checking logic for BACKWARD, FORWARD, FULL modes
    status: pending
    dependencies:
      - schema_registry_class
  - id: integrate_contract_validators
    content: Integrate Schema Registry with existing ContractRegistry and validators
    status: pending
    dependencies:
      - schema_registry_class
      - compatibility_checker
  - id: schema_registry_api
    content: Add FastAPI endpoints for schema management (GET, POST, list versions)
    status: pending
    dependencies:
      - schema_registry_class
  - id: install_great_expectations
    content: Install and configure Great Expectations with Data Docs store
    status: pending
  - id: create_expectation_suites
    content: Create Great Expectations expectation suites from contract validators (tick, bar, news, economic)
    status: pending
    dependencies:
      - install_great_expectations
      - integrate_contract_validators
  - id: integrate_ge_quality_gates
    content: Integrate Great Expectations validation into QualityGate pipeline
    status: pending
    dependencies:
      - create_expectation_suites
  - id: data_docs_server
    content: Set up web server to serve Great Expectations Data Docs
    status: pending
    dependencies:
      - integrate_ge_quality_gates
  - id: add_redis_docker
    content: Add Redis service to docker-compose.yml for Celery broker
    status: pending
  - id: add_airflow_docker
    content: Add Airflow webserver, scheduler, and worker services to docker-compose.yml
    status: pending
    dependencies:
      - add_redis_docker
  - id: create_airflow_structure
    content: Create Airflow DAG directory structure (dags/, plugins/, config/)
    status: pending
    dependencies:
      - add_airflow_docker
  - id: create_data_collection_dag
    content: Create initial Airflow DAG for hourly data collection with retry logic
    status: pending
    dependencies:
      - create_airflow_structure
  - id: create_celery_app
    content: Create Celery application with task modules (market_data, news, economic)
    status: pending
    dependencies:
      - add_redis_docker
      - create_data_collection_dag
  - id: create_grafana_dashboard
    content: Create data quality Grafana dashboard with freshness, volume, quality score, quarantine rate panels
    status: pending
    dependencies:
      - integrate_ge_quality_gates
  - id: add_dq_prometheus_metrics
    content: Add data quality Prometheus metrics (freshness, volume, quality_score, quarantine_rate)
    status: pending
    dependencies:
      - create_grafana_dashboard
  - id: phase1_integration_tests
    content: Create Phase 1 integration tests (Schema Registry, Great Expectations, Airflow, metrics)
    status: pending
    dependencies:
      - add_dq_prometheus_metrics
      - create_celery_app
  - id: add_backfill_interface
    content: Add backfill() and get_available_range() abstract methods to IDataSourceConnector interface
    status: pending
  - id: implement_mt5_backfill
    content: Implement MT5 historical backfill using MetaTrader5.copy_ticks_range() API
    status: pending
    dependencies:
      - add_backfill_interface
  - id: create_progress_tracker
    content: Create backfill progress tracker with database storage and resume capability
    status: pending
    dependencies:
      - implement_mt5_backfill
  - id: create_bars_table
    content: Create bars_forex database table migration with TimescaleDB hypertable
    status: pending
  - id: add_ohlcv_db_methods
    content: Add insert_forex_bar() and insert_forex_bars_batch() methods to Database class
    status: pending
    dependencies:
      - create_bars_table
  - id: create_ohlcv_aggregator
    content: Create TickToOHLCVAggregator utility for M1, M5, M15, H1, H4, D1 timeframes
    status: pending
    dependencies:
      - add_ohlcv_db_methods
  - id: integrate_ohlcv_backfill
    content: Create backfill script that collects ticks and aggregates to OHLCV with progress tracking
    status: pending
    dependencies:
      - implement_mt5_backfill
      - create_ohlcv_aggregator
  - id: create_backfill_dag
    content: Create Airflow DAG for historical backfill with progress tracking
    status: pending
    dependencies:
      - create_progress_tracker
      - integrate_ohlcv_backfill
  - id: create_backfill_orchestrator
    content: Create backfill orchestrator to coordinate backfills across multiple symbols
    status: pending
    dependencies:
      - create_progress_tracker
      - create_backfill_dag
  - id: phase2_integration_tests
    content: Create Phase 2 integration tests (backfill, OHLCV, progress tracking)
    status: pending
    dependencies:
      - create_backfill_orchestrator
  - id: validate_backfilled_data
    content: Create validation script to check backfilled data quality and gaps
    status: pending
    dependencies:
      - phase2_integration_tests
  - id: create_economic_indicators_table
    content: Create economic_indicators database table migration with TimescaleDB hypertable
    status: pending
  - id: add_economic_db_methods
    content: Add insert_economic_indicator() and insert_economic_indicators_batch() methods to Database class
    status: pending
    dependencies:
      - create_economic_indicators_table
  - id: create_fred_connector
    content: Create FREDConnector for US economic indicators with historical backfill (FREE - Priority)
    status: pending
    dependencies:
      - add_economic_db_methods
  - id: create_world_bank_connector
    content: Create WorldBankConnector for global economic indicators (FREE - Priority)
    status: pending
    dependencies:
      - add_economic_db_methods
  - id: create_ecb_connector
    content: Create ECBConnector for Eurozone economic indicators (FREE - Priority)
    status: pending
    dependencies:
      - add_economic_db_methods
  - id: create_news_table
    content: Create news_articles database table migration with TimescaleDB hypertable
    status: pending
  - id: add_news_db_methods
    content: Add insert_news_article() and insert_news_articles_batch() methods to Database class
    status: pending
    dependencies:
      - create_news_table
  - id: create_ai_scraper_framework
    content: Create AI-assisted web scraping framework for extracting structured data from financial websites (FREE - High Priority)
    status: pending
  - id: create_website_scrapers
    content: Create website-specific scrapers for TradingEconomics, Investing.com, ForexFactory, central banks, government sites
    status: pending
    dependencies:
      - create_ai_scraper_framework
  - id: create_web_scraping_connector
    content: Create WebScrapingConnector implementing IDataSourceConnector interface for AI scrapers
    status: pending
    dependencies:
      - create_website_scrapers
      - add_news_db_methods
  - id: enhance_existing_scrapers
    content: Enhance existing scrapers (forexlive, myfxbook) with AI-assisted extraction
    status: pending
    dependencies:
      - create_ai_scraper_framework
  - id: create_rss_connector
    content: Create RSSFeedConnector for multiple RSS feeds (Reuters, Bloomberg, FT) - FREE (Priority)
    status: pending
    dependencies:
      - add_news_db_methods
  - id: create_sentiment_analyzer
    content: Create SentimentAnalyzer module using FinBERT model with batch processing (FREE, open-source)
    status: pending
  - id: create_entity_extractor
    content: Create EntityExtractor module for extracting currency pairs and events from news (FREE, open-source)
    status: pending
  - id: integrate_sentiment_scrapers
    content: Integrate sentiment analysis and entity extraction with web scrapers and RSS connector
    status: pending
    dependencies:
      - create_web_scraping_connector
      - create_rss_connector
      - create_sentiment_analyzer
      - create_entity_extractor
  - id: create_newsapi_connector
    content: Create NewsAPIConnector (OPTIONAL - free tier limited to 100 requests/day)
    status: pending
    dependencies:
      - add_news_db_methods
      - create_sentiment_analyzer
      - create_entity_extractor
  - id: integrate_alternative_features
    content: Integrate news sentiment (web scraping + RSS) and macro indicators (FRED, World Bank, ECB) into FeatureEngine
    status: pending
    dependencies:
      - create_web_scraping_connector
      - create_rss_connector
      - create_fred_connector
  - id: create_alternative_data_dag
    content: Create Airflow DAG for alternative data collection (web scraping, RSS news, economic indicators)
    status: pending
    dependencies:
      - create_web_scraping_connector
      - create_rss_connector
      - create_fred_connector
      - create_backfill_dag
  - id: phase3_integration_tests
    content: Create Phase 3 integration tests (news, economic data, feature integration)
    status: pending
    dependencies:
      - create_alternative_data_dag
      - integrate_alternative_features
  - id: install_openlineage
    content: Install OpenLineage Python client and configure backend
    status: pending
  - id: instrument_connectors_lineage
    content: Instrument all connectors to emit OpenLineage events (RunEvent, DatasetEvent, JobEvent)
    status: pending
    dependencies:
      - install_openlineage
  - id: create_lineage_api
    content: Create API endpoints for lineage queries (dataset, job, run lineage)
    status: pending
    dependencies:
      - instrument_connectors_lineage
  - id: create_drift_detector
    content: Implement DistributionDriftDetector with KS test and PSI for feature drift detection
    status: pending
  - id: integrate_drift_quality_gates
    content: Integrate drift detection into quality gate pipeline with alerting
    status: pending
    dependencies:
      - create_drift_detector
  - id: add_drift_dashboard
    content: Add drift detection panels to Grafana dashboard
    status: pending
    dependencies:
      - integrate_drift_quality_gates
  - id: enhance_observability_dashboard
    content: Enhance data quality dashboard with lineage visualization and comprehensive metrics
    status: pending
    dependencies:
      - create_lineage_api
      - add_drift_dashboard
  - id: create_dq_alerts
    content: Create Prometheus alert rules for data quality (freshness, quarantine rate, drift, schema violations)
    status: pending
    dependencies:
      - add_dq_prometheus_metrics
      - integrate_drift_quality_gates
  - id: phase4_integration_tests
    content: Create Phase 4 integration tests (lineage, drift detection, alerts)
    status: pending
    dependencies:
      - enhance_observability_dashboard
      - create_dq_alerts
  - id: create_event_recorder
    content: Create event recorder to store raw events before normalization for replay
    status: pending
  - id: create_replay_engine
    content: Create replay engine to replay recorded events deterministically
    status: pending
    dependencies:
      - create_event_recorder
  - id: create_replay_tests
    content: Create replay tests for deterministic testing (can run locally or in test suite)
    status: pending
    dependencies:
      - create_replay_engine
  - id: create_point_in_time_tests
    content: Create test suite to verify features at time T only use data ≤ T (prevent lookahead bias) - can run locally
    status: pending
    dependencies:
      - integrate_alternative_features
  - id: enhance_feature_engine_validation
    content: Add explicit point-in-time validation checks to FeatureEngine with lookahead detection
    status: pending
    dependencies:
      - create_point_in_time_tests
  - id: create_release_checklist
    content: Document release process with pre-release checks, steps, and rollback procedure (CI/CD deferred)
    status: pending
  - id: create_release_scripts
    content: Create manual release scripts for quality gates and testing (CI/CD automation deferred)
    status: pending
    dependencies:
      - create_release_checklist
  - id: phase5_integration_tests
    content: Create Phase 5 integration tests (replay, point-in-time validation, release process)
    status: pending
    dependencies:
      - create_release_scripts
      - enhance_feature_engine_validation
  - id: final_documentation_update
    content: Update all documentation (architecture, guides, troubleshooting) for complete pipeline
    status: pending
    dependencies:
      - phase5_integration_tests
---

# Production Data Collection Pipeline Implementation Plan

## Overview

This plan implements a production-grade data collection pipeline following the roadmap in `docs/generated/PRODUCTION_DATA_PIPELINE_ROADMAP.md`. The implementation is organized into 5 phases over 20 weeks, with each phase building on the previous one.

## Architecture Principles

1. **Data Contracts + Schema Evolution**: Schema Registry with compatibility checks (Confluent pattern)
2. **Data Quality Gates**: Great Expectations with human-readable Data Docs
3. **Data Observability**: Freshness, volume, distribution drift monitoring
4. **Lineage Tracking**: OpenLineage standard for data provenance
5. **Release Engineering**: CI/CD gates for data quality tests

## Implementation Sequence

The plan follows a "thin vertical slice" approach: implement one complete data source end-to-end (MT5) before adding others, ensuring the architecture is validated early.

---

## Phase 1: Foundation (Weeks 1-4)

### Goal

Establish production-grade infrastructure foundation: Schema Registry, Great Expectations, Airflow orchestration, and basic observability.

### Week 1: Schema Registry Implementation

#### Task 1.1: Create Schema Registry Database Table

**File**: `src/database/scripts/23_schema_registry.sql`

Create database table to store schema definitions:

- `schema_registry` table with columns: `id`, `data_type`, `version`, `schema_json`, `compatibility_mode`, `status`, `created_at`, `updated_at`
- Indexes on `(data_type, version)` and `(data_type, status)`
- Support for semantic versioning (MAJOR.MINOR.PATCH)

**Acceptance Criteria:**

- [ ] Migration script created and tested
- [ ] Table created with proper indexes
- [ ] Can store schema definitions as JSON

**Dependencies:** None

---

#### Task 1.2: Implement SchemaRegistry Core Class

**File**: `src/trading_server/src/infrastructure/schema_registry/registry.py`

Implement `SchemaRegistry` class with:

- `register_schema(data_type, version, schema, compatibility_mode)` - Register with compatibility check
- `get_schema(data_type, version=None)` - Retrieve schema (latest if version not specified)
- `validate_compatibility(old_schema, new_schema, mode)` - Check compatibility
- `list_versions(data_type)` - List all versions for a data type
- Database-backed persistence (not in-memory)

**Compatibility Modes:**

- `BACKWARD`: New schema can read old data (can add optional fields, cannot remove required fields)
- `FORWARD`: Old schema can read new data (can remove optional fields, cannot add required fields)
- `FULL`: Both directions compatible
- `NONE`: No compatibility checks

**Acceptance Criteria:**

- [ ] Can register schemas with version
- [ ] Compatibility checks prevent breaking changes
- [ ] Can retrieve schemas by version
- [ ] Unit tests for all methods
- [ ] Integration tests with database

**Dependencies:** Task 1.1

---

#### Task 1.3: Implement Compatibility Checker

**File**: `src/trading_server/src/infrastructure/schema_registry/compatibility.py`

Implement compatibility checking logic:

- Field addition/removal detection
- Type change detection
- Required/optional field changes
- Enum value changes
- Default value changes

**Acceptance Criteria:**

- [ ] BACKWARD compatibility: Detects breaking changes (removed required fields)
- [ ] FORWARD compatibility: Detects breaking changes (added required fields)
- [ ] FULL compatibility: Both checks
- [ ] Unit tests for all compatibility scenarios
- [ ] Clear error messages for incompatible changes

**Dependencies:** Task 1.2

---

#### Task 1.4: Integrate Schema Registry with Contract Validators

**File**: `src/trading_server/src/data/contracts/registry.py` (enhance existing)

Enhance existing `ContractRegistry` to:

- Register contracts with Schema Registry on startup
- Validate against registered schema before contract validation
- Store schema version in data records (`schema_version`, `schema_type` columns)

**Acceptance Criteria:**

- [ ] Contracts auto-register with Schema Registry
- [ ] Schema version checked before contract validation
- [ ] Data records include schema version
- [ ] Backward compatible with existing code

**Dependencies:** Task 1.2, Task 1.3

---

#### Task 1.5: Add Schema Registry API Endpoints

**File**: `src/api/src/routers/schema.py` (new)

Create FastAPI endpoints for schema management:

- `GET /api/schema/{data_type}` - Get latest schema
- `GET /api/schema/{data_type}/{version}` - Get specific version
- `POST /api/schema/{data_type}` - Register new schema version
- `GET /api/schema/{data_type}/versions` - List all versions
- `POST /api/schema/{data_type}/validate-compatibility` - Check compatibility

**Acceptance Criteria:**

- [ ] All endpoints implemented and tested
- [ ] OpenAPI documentation generated
- [ ] Authentication/authorization (if needed)
- [ ] Integration tests pass

**Dependencies:** Task 1.2

---

### Week 2: Great Expectations Integration

#### Task 2.1: Install and Configure Great Expectations

**File**: `src/trading_server/requirements.txt` (update)

Add Great Expectations to requirements:

- `great-expectations==0.18.0`
- Configure GE context and data context
- Set up Data Docs store (local filesystem or S3)

**Acceptance Criteria:**

- [ ] Great Expectations installed
- [ ] Data context configured
- [ ] Data Docs store accessible

**Dependencies:** None

---

#### Task 2.2: Create Expectation Suites from Contract Validators

**File**: `src/trading_server/src/infrastructure/data_quality/ge_expectations.py` (new)

Convert existing contract validators to Great Expectations expectations:

- Create expectation suite for each data type (tick, bar, news, economic)
- Map contract validation rules to GE expectations:
  - Required fields → `expect_column_to_exist()`
  - Type checks → `expect_column_values_to_be_of_type()`
  - Range checks → `expect_column_values_to_be_between()`
  - Format checks → `expect_column_values_to_match_regex()`
  - Business rules → Custom expectations

**Acceptance Criteria:**

- [ ] Expectation suites created for all data types
- [ ] All contract rules converted to expectations
- [ ] Suites validate same rules as contract validators
- [ ] Unit tests verify expectation correctness

**Dependencies:** Task 2.1, Task 1.4

---

#### Task 2.3: Integrate Great Expectations into Quality Gates

**File**: `src/trading_server/src/data/quality_gates.py` (enhance existing)

Enhance `QualityGate` class to:

- Run Great Expectations validation after contract validation
- Store validation results
- Generate Data Docs after validation
- Track validation metrics (pass rate, failure reasons)

**Acceptance Criteria:**

- [ ] GE validation runs in quality gate pipeline
- [ ] Data Docs generated after validation
- [ ] Validation results stored
- [ ] Metrics tracked in Prometheus

**Dependencies:** Task 2.2

---

#### Task 2.4: Set Up Data Docs Web Server

**File**: `src/trading_server/src/infrastructure/data_quality/data_docs_server.py` (new)

Create web server to serve Data Docs:

- Serve static HTML files from GE Data Docs store
- Or integrate with existing API/dashboard
- Auto-refresh on new validations

**Acceptance Criteria:**

- [ ] Data Docs accessible via web UI
- [ ] Auto-updates on new validations
- [ ] Can view historical validation results
- [ ] Accessible from dashboard or standalone

**Dependencies:** Task 2.3

---

### Week 3: Airflow & Celery Setup

#### Task 3.1: Add Redis Service to docker-compose.yml

**File**: `docker-compose.yml` (update)

Add Redis service for Celery broker:

- Redis container with persistence
- Health checks
- Volume for data persistence

**Acceptance Criteria:**

- [ ] Redis service added to docker-compose.yml
- [ ] Service starts successfully
- [ ] Health checks pass
- [ ] Data persists across restarts

**Dependencies:** None

---

#### Task 3.2: Add Airflow Services to docker-compose.yml

**File**: `docker-compose.yml` (update)

Add Airflow services:

- `airflow-webserver` - Web UI
- `airflow-scheduler` - DAG scheduler
- `airflow-worker` - Celery worker
- Configure to use PostgreSQL as metadata database
- Set up volume mounts for DAGs and logs
- Environment variables for service communication

**Acceptance Criteria:**

- [ ] All Airflow services added
- [ ] Services start successfully
- [ ] Airflow UI accessible
- [ ] Scheduler running
- [ ] Workers processing tasks

**Dependencies:** Task 3.1, PostgreSQL (existing)

---

#### Task 3.3: Create Airflow DAG Structure

**File**: `src/trading_server/src/infrastructure/data_pipeline/airflow/dags/` (new directory)

Create directory structure:

- `dags/` - DAG definitions
- `plugins/` - Custom operators (if needed)
- `config/` - Airflow configuration

**Acceptance Criteria:**

- [ ] Directory structure created
- [ ] DAGs directory mounted in docker-compose
- [ ] Airflow can discover DAGs

**Dependencies:** Task 3.2

---

#### Task 3.4: Create Initial Data Collection DAG

**File**: `src/trading_server/src/infrastructure/data_pipeline/airflow/dags/data_collection_pipeline.py`

Create DAG for hourly data collection:

- Task for MT5 data collection (placeholder, will use real connector in Phase 2)
- Task for economic calendar collection
- Retry logic (3 retries, exponential backoff)
- Error notifications
- Task dependencies

**Acceptance Criteria:**

- [ ] DAG created and visible in Airflow UI
- [ ] DAG runs on schedule (hourly)
- [ ] Tasks retry on failure
- [ ] Alerts sent on failure
- [ ] Integration tests verify DAG execution

**Dependencies:** Task 3.3

---

#### Task 3.5: Create Celery Task Structure

**File**: `src/trading_server/src/infrastructure/data_pipeline/celery_app.py` (new)

Create Celery application:

- Configure Redis as broker
- Configure Redis as result backend
- Create task modules:
  - `tasks/market_data_tasks.py` - MT5 data collection tasks
  - `tasks/news_data_tasks.py` - News collection tasks (placeholder)
  - `tasks/economic_data_tasks.py` - Economic data tasks

**Acceptance Criteria:**

- [ ] Celery app configured
- [ ] Tasks can be queued and executed
- [ ] Results stored in Redis
- [ ] Integration with Airflow DAGs

**Dependencies:** Task 3.1, Task 3.4

---

### Week 4: Basic Observability Dashboard

#### Task 4.1: Create Data Quality Grafana Dashboard

**File**: `src/monitoring/grafana/dashboards/data_quality.json` (new)

Create Grafana dashboard with panels:

- **Freshness**: Time since last data (per source/symbol)
- **Volume**: Records per hour/day (per source/symbol)
- **Quality Score**: 0-1 score based on validation results
- **Quarantine Rate**: Percentage of rejected data
- **Distribution Drift**: Statistical tests (placeholder, full implementation in Phase 4)

**Acceptance Criteria:**

- [ ] Dashboard created and accessible
- [ ] All metrics displayed correctly
- [ ] Dashboard auto-refreshes
- [ ] Can filter by source, symbol, time range

**Dependencies:** Prometheus metrics (existing), Task 2.3

---

#### Task 4.2: Add Data Quality Prometheus Metrics

**File**: `src/trading_server/src/monitoring/metrics.py` (enhance existing)

Enhance existing metrics to include:

- `data_freshness_seconds` - Gauge (time since last data)
- `data_volume_total` - Counter (records per source/symbol)
- `data_quality_score` - Gauge (0-1, per source/symbol)
- `data_quarantine_rate` - Gauge (percentage, per source/symbol)

**Acceptance Criteria:**

- [ ] All metrics defined
- [ ] Metrics exposed via `/metrics` endpoint
- [ ] Prometheus scraping metrics
- [ ] Metrics appear in Grafana

**Dependencies:** Task 4.1

---

#### Task 4.3: Create Phase 1 Integration Tests

**File**: `tests/integration/test_phase1_foundation.py` (new)

Create integration tests for Phase 1:

- Test Schema Registry end-to-end (register → retrieve → compatibility check)
- Test Great Expectations validation pipeline
- Test Airflow DAG execution
- Test data quality metrics collection

**Acceptance Criteria:**

- [ ] All integration tests pass
- [ ] Tests cover critical paths
- [ ] Tests run in CI/CD

**Dependencies:** All Phase 1 tasks

---

## Phase 2: Historical Backfill (Weeks 5-8)

### Goal

Enable historical data collection for RL training: MT5 backfill, OHLCV aggregation, progress tracking.

### Week 5: Backfill Interface & MT5 Implementation

#### Task 5.1: Add backfill() Method to IDataSourceConnector

**File**: `src/trading_server/src/connectors/base.py` (update)

Add abstract methods to `IDataSourceConnector`:

- `backfill(start_time, end_time, batch_size=1000) -> Iterator[Dict]` - Historical data from source API
- `get_available_range() -> Tuple[datetime, datetime]` - Available data range

**Acceptance Criteria:**

- [ ] Abstract methods added
- [ ] Interface documentation updated
- [ ] Existing connectors still work (backward compatible)

**Dependencies:** None

---

#### Task 5.2: Implement MT5 Historical Backfill

**File**: `src/trading_server/src/connectors/mt5_tick_connector.py` (enhance existing)

Implement `backfill()` method:

- Use `MetaTrader5.copy_ticks_range()` for historical tick data
- Process in daily batches to avoid memory issues
- Integrate with existing `insert_forex_ticks_batch()` for storage
- Add rate limiting (0.1s delay between batches)
- Handle MT5 connection failures with retry logic

**Acceptance Criteria:**

- [ ] `backfill()` method implemented
- [ ] Can backfill 5+ years of historical data
- [ ] Data stored in `ticks_forex` table
- [ ] Rate limiting prevents API throttling
- [ ] Integration tests verify backfill correctness

**Dependencies:** Task 5.1

---

#### Task 5.3: Create Backfill Progress Tracker

**File**: `src/trading_server/src/infrastructure/backfill/progress_tracker.py` (new)

Create progress tracking system:

- Track backfill progress per connector, symbol, time range
- Store progress in database table `backfill_progress`
- Support resume capability (skip already backfilled ranges)
- Track statistics: records collected, time taken, errors

**Database Table**: `src/database/scripts/24_backfill_progress.sql`

**Acceptance Criteria:**

- [ ] Progress tracker implemented
- [ ] Can track progress per symbol/time range
- [ ] Can resume failed backfills
- [ ] Statistics tracked and queryable

**Dependencies:** Task 5.2

---

### Week 6: OHLCV Aggregation

#### Task 6.1: Create bars_forex Database Table

**File**: `src/database/scripts/25_bars_forex_table.sql`

Create `bars_forex` table:

- Columns: `symbol`, `datetime`, `open`, `high`, `low`, `close`, `volume`, `timeframe`, `receive_time`
- Convert to TimescaleDB hypertable (1-day chunk interval)
- Indexes: `(symbol, timeframe, datetime)`, `(datetime)`
- Foreign key to `forex_pairs` table

**Acceptance Criteria:**

- [ ] Table created and migrated
- [ ] Hypertable conversion successful
- [ ] Indexes created
- [ ] Foreign key constraints added

**Dependencies:** None

---

#### Task 6.2: Add OHLCV Database Methods

**File**: `src/trading_server/src/database.py` (enhance existing)

Add methods for OHLCV data:

- `insert_forex_bar(symbol, datetime, open, high, low, close, volume, timeframe)` - Single bar
- `insert_forex_bars_batch(bars)` - Batch insert
- `get_bars_by_timeframe(symbol, timeframe, start_time, end_time)` - Query bars

**Acceptance Criteria:**

- [ ] Methods implemented
- [ ] Batch insert efficient (uses transactions)
- [ ] Query methods support point-in-time queries
- [ ] Unit tests for all methods

**Dependencies:** Task 6.1

---

#### Task 6.3: Create OHLCV Aggregation Utility

**File**: `src/trading_server/src/utils/ohlcv_aggregator.py` (new)

Create `TickToOHLCVAggregator` class:

- Aggregate tick data to OHLCV bars for multiple timeframes (M1, M5, M15, M30, H1, H4, D1)
- Use mid-price (average of bid/ask) for OHLC calculations
- Handle gaps in tick data gracefully
- Support point-in-time aggregation (no future data)
- Batch processing for efficiency

**Methods:**

- `aggregate_ticks(ticks, timeframe)` - Convert tick list to OHLCV bars
- `aggregate_timeframe(ticks, timeframe, start_time, end_time)` - Aggregate specific range
- `aggregate_all_timeframes(ticks, timeframes)` - Generate all timeframes at once

**Acceptance Criteria:**

- [ ] Aggregator class created
- [ ] All timeframes supported
- [ ] OHLCV calculations correct (verified against known data)
- [ ] Point-in-time aggregation verified
- [ ] Unit tests for aggregation logic

**Dependencies:** Task 6.2

---

#### Task 6.4: Integrate OHLCV Aggregation into Backfill Pipeline

**File**: `scripts/backfill_mt5_data.py` (new)

Create backfill script that:

- Collects tick data via MT5 backfill
- Aggregates to OHLCV for all timeframes
- Stores both ticks and bars
- Tracks progress and supports resume

**Acceptance Criteria:**

- [ ] Script can backfill ticks and generate OHLCV
- [ ] All timeframes generated correctly
- [ ] Progress tracking works
- [ ] Can resume from checkpoint

**Dependencies:** Task 5.2, Task 6.3

---

### Week 7: Backfill Orchestration

#### Task 7.1: Create Airflow DAG for Historical Backfill

**File**: `src/trading_server/src/infrastructure/data_pipeline/airflow/dags/historical_backfill_dag.py`

Create DAG for historical backfill:

- Task for MT5 tick backfill
- Task for OHLCV aggregation
- Task dependencies (aggregation after backfill)
- Progress tracking integration
- Error handling and retry logic

**Acceptance Criteria:**

- [ ] DAG created and visible in Airflow UI
- [ ] Can trigger backfill on-demand
- [ ] Tasks execute in correct order
- [ ] Progress tracked in database

**Dependencies:** Task 3.4, Task 6.4

---

#### Task 7.2: Create Backfill Orchestrator

**File**: `src/trading_server/src/infrastructure/backfill/orchestrator.py` (new)

Create orchestrator to coordinate backfills:

- Manage dependencies (e.g., compute features after data backfill)
- Parallel execution where possible
- Error handling and retry logic
- Progress reporting

**Acceptance Criteria:**

- [ ] Can orchestrate backfill across multiple symbols
- [ ] Parallel execution works
- [ ] Error handling robust
- [ ] Progress reporting accurate

**Dependencies:** Task 5.3, Task 7.1

---

### Week 8: Phase 2 Testing & Validation

#### Task 8.1: Create Phase 2 Integration Tests

**File**: `tests/integration/test_phase2_backfill.py` (new)

Test backfill end-to-end:

- Test MT5 backfill for 1 month of data
- Test OHLCV aggregation correctness
- Test progress tracking and resume
- Test data quality validation on backfilled data

**Acceptance Criteria:**

- [ ] All integration tests pass
- [ ] Backfill produces correct data
- [ ] OHLCV aggregation verified
- [ ] Resume capability tested

**Dependencies:** All Phase 2 tasks

---

#### Task 8.2: Validate Backfilled Data Quality

**File**: `scripts/validate_backfilled_data.py` (new)

Create validation script:

- Check for gaps in backfilled data
- Verify data quality (spreads, prices, timestamps)
- Compare with known good data (if available)
- Generate validation report

**Acceptance Criteria:**

- [ ] Script validates backfilled data
- [ ] Detects data quality issues
- [ ] Generates human-readable report
- [ ] Can run in CI/CD

**Dependencies:** Task 8.1

---

## Phase 3: Alternative Data Sources (Weeks 9-13)

### Goal

Integrate news, sentiment, and macroeconomic data sources. **Priority: Free data sources first** (FRED, World Bank, ECB, RSS feeds).

### Week 9: Economic Indicators (Free Sources First)

**Priority:** Start with completely free economic data sources (FRED, World Bank, ECB) that provide decades of historical data.

#### Task 9.1: Create economic_indicators Database Table

**File**: `src/database/scripts/27_economic_indicators_table.sql`

Create `economic_indicators` table:

- Columns: `id`, `timestamp`, `series_id`, `value`, `source`, `country`, `frequency`, `receive_time`, `created_at`
- Convert to TimescaleDB hypertable (1-month chunk interval)
- Indexes: `(series_id, timestamp)`, `(source, timestamp)`, `(country, timestamp)`

**Acceptance Criteria:**

- [ ] Table created and migrated
- [ ] Hypertable conversion successful
- [ ] Indexes created

**Dependencies:** None

---

#### Task 9.2: Add Economic Indicators Database Methods

**File**: `src/trading_server/src/database.py` (enhance existing)

Add methods:

- `insert_economic_indicator(indicator)` - Single indicator
- `insert_economic_indicators_batch(indicators)` - Batch insert
- `get_economic_indicators(series_id=None, start_time=None, end_time=None)` - Query indicators
- `get_latest_indicator(series_id)` - Get latest value

**Acceptance Criteria:**

- [ ] Methods implemented
- [ ] Batch insert efficient
- [ ] Query methods support time ranges
- [ ] Unit tests for all methods

**Dependencies:** Task 9.1

---

#### Task 9.3: Create FRED Connector (Free - Priority)

**File**: `src/trading_server/src/connectors/fred_connector.py` (new)

Create `FREDConnector`:

- Use `pandas_datareader` or `fredapi` library (free API key required)
- Key indicators: FEDFUNDS, UNRATE, CPIAUCSL, GDP, PAYEMS, INDPRO
- `stream()` - Poll FRED API for latest data (daily)
- `backfill()` - Fetch historical data (decades available, completely free)
- Rate limiting (120 requests/minute free tier)

**Acceptance Criteria:**

- [ ] Connector implemented
- [ ] Can fetch key US economic indicators
- [ ] Historical backfill works (decades of data)
- [ ] Rate limiting respected
- [ ] Integration tests pass

**Dependencies:** Task 9.2

---

#### Task 9.4: Create World Bank Connector (Free - Priority)

**File**: `src/trading_server/src/connectors/world_bank_connector.py` (new)

Create `WorldBankConnector`:

- Use `wbdata` or `pandas_datareader` library (completely free, no API key)
- Key indicators: GDP growth, inflation, trade balance
- Support multiple countries (US, EU, UK, Japan, etc.)
- Historical data: 50+ years (completely free)

**Acceptance Criteria:**

- [ ] Connector implemented
- [ ] Can fetch global economic indicators
- [ ] Historical backfill works
- [ ] Integration tests pass

**Dependencies:** Task 9.2

---

#### Task 9.5: Create ECB Connector (Free - Priority)

**File**: `src/trading_server/src/connectors/ecb_connector.py` (new)

Create `ECBConnector`:

- Use ECB Statistical Data Warehouse (SDW) API (completely free, no API key)
- Key indicators: ECB interest rates, Eurozone inflation (HICP), Eurozone GDP, unemployment
- Historical data: 20+ years (completely free)

**Acceptance Criteria:**

- [ ] Connector implemented
- [ ] Can fetch Eurozone indicators
- [ ] Historical backfill works
- [ ] Integration tests pass

**Dependencies:** Task 9.2

---

### Week 10: RSS Feed Connector (Free News Source)

**Priority:** RSS feeds are completely free and provide good news coverage.

#### Task 10.1: Create news_articles Database Table

**File**: `src/database/scripts/26_news_articles_table.sql`

Create `news_articles` table:

- Columns: `id`, `timestamp`, `source`, `title`, `content`, `url`, `symbol`, `sentiment_score`, `sentiment_label`, `entities` (JSONB), `receive_time`, `created_at`
- Convert to TimescaleDB hypertable (1-day chunk interval)
- Indexes: `(timestamp)`, `(symbol, timestamp)`, `(source, timestamp)`
- Foreign key to `forex_pairs` table (nullable)

**Acceptance Criteria:**

- [ ] Table created and migrated
- [ ] Hypertable conversion successful
- [ ] Indexes created
- [ ] Schema matches contract definition

**Dependencies:** None

---

#### Task 10.4: Add News Database Methods

**File**: `src/trading_server/src/database.py` (enhance existing)

Add methods for news data:

- `insert_news_article(article)` - Single article
- `insert_news_articles_batch(articles)` - Batch insert
- `get_recent_news(symbol=None, hours=24, limit=100)` - Query recent news
- `get_news_by_timeframe(start_time, end_time, symbol=None)` - Historical query

**Acceptance Criteria:**

- [ ] Methods implemented
- [ ] Batch insert efficient
- [ ] Query methods support point-in-time queries
- [ ] Unit tests for all methods

**Dependencies:** Task 10.1

---

#### Task 10.5: Create RSS Feed Connector (Free - Priority)

**File**: `src/trading_server/src/connectors/rss_feed_connector.py` (new)

Create `RSSFeedConnector`:

- Support multiple RSS feeds (Reuters, Bloomberg, FT, ForexFactory) - all free
- Use `feedparser` library for RSS parsing
- Poll feeds every 15-30 minutes
- Normalize RSS items to news event format
- Deduplicate articles by URL
- No API keys or rate limits (completely free)

**Acceptance Criteria:**

- [ ] Connector implemented
- [ ] Multiple RSS feeds supported
- [ ] Deduplication works
- [ ] Integration tests pass

**Dependencies:** Task 10.2

---

### Week 11: Integrate AI Scraping with Data Pipeline

#### Task 11.1: Create Web Scraping Connector Interface

**File**: `src/trading_server/src/connectors/web_scraping_connector.py` (new)

Create connector that implements `IDataSourceConnector`:

- `stream()` - Poll multiple websites for new data
- `backfill()` - Scrape historical data (if available)
- Integrate with AI scraper framework
- Normalize scraped data using `EventNormalizer`
- Apply sentiment analysis and entity extraction

**Acceptance Criteria:**

- [ ] Connector implements IDataSourceConnector interface
- [ ] Can scrape multiple websites in parallel
- [ ] Data normalized and stored correctly
- [ ] Integration tests pass

**Dependencies:** Task 10.2, Task 10.4

---

#### Task 11.2: Enhance Existing Scrapers with AI

**File**: `src/trading_server/src/web_scraper/` (enhance existing)

Enhance existing scrapers (`web_scraper_forexlive.py`, `web_scraper_myfxbook.py`):

- Integrate with AI scraper framework
- Use AI for content extraction instead of hardcoded CSS selectors
- Make scrapers more resilient to website changes
- Add more websites to scraping list

**Acceptance Criteria:**

- [ ] Existing scrapers enhanced with AI
- [ ] More resilient to website changes
- [ ] Can scrape additional websites
- [ ] Backward compatible with existing code

**Dependencies:** Task 10.1

---

### Week 12: Sentiment Analysis & Entity Extraction

#### Task 12.1: Create Sentiment Analyzer Module

**File**: `src/trading_server/src/utils/sentiment_analyzer.py` (new)

Create `SentimentAnalyzer` class:

- Use `transformers` library with FinBERT model (`ProsusAI/finbert`) - free, open-source
- Batch processing for efficiency
- Support both title-only and full-content analysis
- Cache model loading (singleton pattern)

**Methods:**

- `analyze_sentiment(text) -> Dict` - Analyze single text
- `analyze_batch(texts) -> List[Dict]` - Batch analysis
- Returns: `{"score": float, "label": str, "confidence": float}`

**Acceptance Criteria:**

- [ ] Sentiment analyzer implemented
- [ ] FinBERT model loaded successfully
- [ ] Batch processing works
- [ ] Performance acceptable (<1s per article)
- [ ] Unit tests with sample financial texts

**Dependencies:** None (but requires transformers library)

---

#### Task 12.2: Create Entity Extractor Module

**File**: `src/trading_server/src/utils/entity_extractor.py` (new)

Create `EntityExtractor` class:

- Use spaCy NER or `flair` library for named entity recognition (free, open-source)
- Extract: currency pairs (EUR, USD, GBP, etc.), company names, economic events
- Match currency pairs to trading symbols
- Extract event types (rate decisions, GDP, employment, etc.)

**Methods:**

- `extract_entities(text) -> Dict` - Extract all entities
- `extract_currency_pairs(text) -> List[str]` - Extract currency mentions
- `extract_events(text) -> List[str]` - Extract economic event types

**Acceptance Criteria:**

- [ ] Entity extractor implemented
- [ ] Currency pairs extracted correctly
- [ ] Events extracted correctly
- [ ] Unit tests with sample news articles

**Dependencies:** None

---

#### Task 12.3: Integrate Sentiment & Entity Extraction with Scrapers

**File**: `src/trading_server/src/connectors/rss_feed_connector.py` (enhance existing)

Enhance RSS connector to:

- Apply sentiment analysis to articles
- Extract entities and currency pairs
- Store sentiment scores and entities in database

**Acceptance Criteria:**

- [ ] Sentiment analysis integrated
- [ ] Entity extraction integrated
- [ ] Data stored correctly
- [ ] Integration tests pass

**Dependencies:** Task 10.3, Task 11.1, Task 11.2

---

### Week 13: Optional NewsAPI & Feature Integration

#### Task 13.1: Create NewsAPI Connector (Optional - Free Tier Limited)

**File**: `src/trading_server/src/connectors/news_api_connector.py` (new)

**Note:** This is optional. NewsAPI free tier is limited (100 requests/day). RSS feeds are preferred for free usage.

Create `NewsAPIConnector` implementing `IDataSourceConnector`:

- `stream()` - Poll NewsAPI for real-time news (every 15-30 minutes)
- `backfill()` - Fetch historical news (limited by API tier)
- Integrate sentiment analysis and entity extraction
- Rate limiting (100 requests/day free tier)
- Normalize events using `EventNormalizer`

**Acceptance Criteria:**

- [ ] Connector implemented
- [ ] Real-time news collection works
- [ ] Sentiment analysis integrated
- [ ] Entity extraction integrated
- [ ] Rate limiting respected
- [ ] Integration tests pass

**Dependencies:** Task 10.2, Task 11.1, Task 11.2

---

#### Task 13.2: Integrate Alternative Data into FeatureEngine

**File**: `src/trading_server/src/application/environment/feature_engine.py` (enhance existing)

Add methods to `FeatureEngine`:

- `extract_news_features(symbol, current_time)` - News sentiment features (from RSS)
- `extract_macro_features(symbol, current_time)` - Macroeconomic indicator features (from FRED, World Bank, ECB)

**Features to extract:**

- News: `news_sentiment_1h`, `news_sentiment_24h`, `news_volume_24h`, `high_impact_news_count_24h`
- Macro: `fed_funds_rate`, `unemployment_rate`, `cpi_yoy`, `gdp_growth_rate`, `interest_rate_differential`, `ecb_rate`, `world_bank_gdp_growth`

**Acceptance Criteria:**

- [ ] All feature extraction methods implemented
- [ ] Point-in-time computation verified (no lookahead bias)
- [ ] Features integrated into state vector
- [ ] Unit tests for feature extraction

**Dependencies:** Task 10.3, Task 9.3

---

#### Task 13.3: Create Airflow DAG for Alternative Data Collection

**File**: `src/trading_server/src/infrastructure/data_pipeline/airflow/dags/alternative_data_collection_dag.py`

Create DAG for alternative data:

- Hourly RSS news collection task
- Daily economic indicators collection task (FRED, World Bank, ECB)
- Historical backfill tasks for all sources
- Optional: NewsAPI task (if enabled)

**Acceptance Criteria:**

- [ ] DAG created and visible in Airflow UI
- [ ] Tasks run on schedule
- [ ] Historical backfill tasks work
- [ ] Integration tests pass

**Dependencies:** Task 10.3, Task 9.3, Task 7.1

---

#### Task 13.4: Create Phase 3 Integration Tests

**File**: `tests/integration/test_phase3_alternative_data.py` (new)

Test alternative data end-to-end:

- Test news collection → sentiment analysis → database storage
- Test economic indicator collection → database storage
- Test feature extraction with alternative data
- Test point-in-time constraints

**Acceptance Criteria:**

- [ ] All integration tests pass
- [ ] Alternative data flows correctly
- [ ] Features computed correctly
- [ ] Point-in-time validated

**Dependencies:** All Phase 3 tasks

---

## Phase 4: Observability & Lineage (Weeks 13-16)

### Goal

Complete observability and lineage tracking: OpenLineage integration, distribution drift detection, enhanced monitoring.

### Week 13: OpenLineage Integration

#### Task 13.1: Install OpenLineage Python Client

**File**: `src/trading_server/requirements.txt` (update)

Add OpenLineage dependencies:

- `openlineage-python==1.0.0` (or latest)
- Configure OpenLineage backend (database or external service)

**Acceptance Criteria:**

- [ ] OpenLineage installed
- [ ] Backend configured
- [ ] Can emit lineage events

**Dependencies:** None

---

#### Task 13.2: Instrument Connectors with Lineage

**File**: `src/trading_server/src/connectors/` (enhance all connectors)

Add lineage tracking to connectors:

- Emit `RunEvent` when connector starts
- Emit `DatasetEvent` when data is produced
- Emit `JobEvent` for job completion
- Track: job name, dataset name, run ID, timestamps

**Acceptance Criteria:**

- [ ] All connectors emit lineage events
- [ ] Events include required metadata
- [ ] Lineage stored in backend
- [ ] Integration tests verify lineage tracking

**Dependencies:** Task 13.1

---

#### Task 13.3: Create Lineage Visualization

**File**: `src/api/src/routers/lineage.py` (new)

Create API endpoints for lineage:

- `GET /api/lineage/dataset/{dataset_name}` - Get dataset lineage
- `GET /api/lineage/job/{job_name}` - Get job lineage
- `GET /api/lineage/run/{run_id}` - Get run details

**Acceptance Criteria:**

- [ ] Endpoints implemented
- [ ] Can query lineage graph
- [ ] Visualization available (or integrate with existing dashboard)
- [ ] Integration tests pass

**Dependencies:** Task 13.2

---

### Week 14: Distribution Drift Detection

#### Task 14.1: Implement Distribution Drift Detector

**File**: `src/trading_server/src/infrastructure/data_quality/drift_detector.py` (new)

Create `DriftDetector` class:

- Kolmogorov-Smirnov (KS) test for distribution changes
- Population Stability Index (PSI) for feature drift
- Monitor feature distributions over time
- Alert on significant drift (configurable thresholds)

**Methods:**

- `detect_drift(feature_name, baseline_data, current_data) -> Dict` - Detect drift
- `monitor_feature(feature_name, window_days=30)` - Monitor feature over time
- `get_drift_report(symbol, start_time, end_time)` - Generate drift report

**Acceptance Criteria:**

- [ ] Drift detector implemented
- [ ] KS test and PSI calculations correct
- [ ] Can detect significant drift
- [ ] Unit tests with known distributions

**Dependencies:** None

---

#### Task 14.2: Integrate Drift Detection into Quality Gates

**File**: `src/trading_server/src/data/quality_gates.py` (enhance existing)

Add drift detection to quality gate pipeline:

- Run drift detection on feature distributions
- Alert on significant drift
- Store drift metrics in database

**Acceptance Criteria:**

- [ ] Drift detection runs in quality gates
- [ ] Alerts generated on drift
- [ ] Metrics stored and queryable
- [ ] Integration tests pass

**Dependencies:** Task 14.1

---

#### Task 14.3: Add Drift Metrics to Grafana Dashboard

**File**: `src/monitoring/grafana/dashboards/data_quality.json` (update)

Add drift detection panels:

- Drift score per feature
- Drift alerts
- Historical drift trends

**Acceptance Criteria:**

- [ ] Drift metrics displayed
- [ ] Alerts visible
- [ ] Historical trends shown

**Dependencies:** Task 14.2, Task 4.1

---

### Week 15: Enhanced Observability

#### Task 15.1: Enhance Data Quality Dashboard

**File**: `src/monitoring/grafana/dashboards/data_quality.json` (update)

Enhance dashboard with:

- Lineage visualization (if possible)
- Drift detection panels
- Source-specific quality metrics
- Historical quality trends

**Acceptance Criteria:**

- [ ] Dashboard enhanced with new panels
- [ ] All metrics displayed correctly
- [ ] Dashboard is comprehensive and useful

**Dependencies:** Task 13.3, Task 14.3

---

#### Task 15.2: Create Automated Alerts

**File**: `src/monitoring/prometheus/alerts/data_quality_alerts.yml` (new)

Create Prometheus alert rules:

- Data freshness > threshold
- Quarantine rate > threshold
- Distribution drift detected
- Schema compatibility violation
- Data volume drop

**Acceptance Criteria:**

- [ ] Alert rules created
- [ ] Alerts trigger correctly
- [ ] Notifications sent (email/Slack/etc.)
- [ ] Alert rules tested

**Dependencies:** Task 4.2, Task 14.2

---

### Week 16: Phase 4 Testing

#### Task 16.1: Create Phase 4 Integration Tests

**File**: `tests/integration/test_phase4_observability.py` (new)

Test observability end-to-end:

- Test lineage tracking across multiple jobs
- Test drift detection on known distributions
- Test alert generation
- Test dashboard data collection

**Acceptance Criteria:**

- [ ] All integration tests pass
- [ ] Lineage tracking verified
- [ ] Drift detection verified
- [ ] Alerts tested

**Dependencies:** All Phase 4 tasks

---

## Phase 5: Release Engineering & Replay (Weeks 17-20)

### Goal

Production-ready release process: data replay, point-in-time validation, release documentation. **Note: CI/CD integration deferred for now.**

### Week 17: Data Replay System

#### Task 18.1: Create Event Recorder

**File**: `src/trading_server/src/infrastructure/replay/event_recorder.py` (new)

Create system to record raw events:

- Store raw events before normalization
- Support multiple storage backends (filesystem, S3, database)
- Record metadata: timestamp, source, event type
- Efficient storage format (Parquet, compressed JSON)

**Acceptance Criteria:**

- [ ] Event recorder implemented
- [ ] Can record events from all sources
- [ ] Storage efficient
- [ ] Can query recorded events by time range

**Dependencies:** None

---

#### Task 18.2: Create Replay System

**File**: `src/trading_server/src/infrastructure/replay/replay_engine.py` (new)

Create replay system:

- Read recorded events
- Replay events in chronological order
- Support replay from specific time ranges
- Deterministic replay (same events, same order)

**Acceptance Criteria:**

- [ ] Replay system implemented
- [ ] Can replay events deterministically
- [ ] Supports time range filtering
- [ ] Performance acceptable

**Dependencies:** Task 18.1

---

#### Task 17.3: Create Replay Tests

**File**: `tests/integration/test_replay.py` (new)

Create replay tests:

- Record test events
- Replay events
- Verify ingestion logic produces same results
- Can run locally or in test suite (CI/CD deferred)

**Acceptance Criteria:**

- [ ] Replay tests created
- [ ] Tests verify deterministic replay
- [ ] Tests can run locally
- [ ] All tests pass

**Dependencies:** Task 17.2

---

### Week 18: Point-in-Time Validation

#### Task 18.1: Create Point-in-Time Test Suite

**File**: `tests/integration/test_point_in_time.py` (new)

Create tests that verify:

- Features at time T only use data ≤ T
- No lookahead bias in feature computation
- Point-in-time constraints enforced

**Test Approach:**

- Create test dataset with known timestamps
- Compute features at various time points
- Verify no future data leaks into features
- Test with historical data

**Acceptance Criteria:**

- [ ] Test suite created
- [ ] Tests catch lookahead bias
- [ ] All existing features pass tests
- [ ] Tests can run locally (CI/CD deferred)

**Dependencies:** Task 12.2

---

#### Task 18.2: Add Point-in-Time Validation to FeatureEngine

**File**: `src/trading_server/src/application/environment/feature_engine.py` (enhance existing)

Enhance FeatureEngine with:

- Explicit point-in-time validation checks
- Logging when potential lookahead detected
- Assertions in debug mode

**Acceptance Criteria:**

- [ ] Validation checks added
- [ ] Lookahead detection works
- [ ] Performance impact minimal
- [ ] Unit tests verify validation

**Dependencies:** Task 18.1

---

### Week 19: Release Process & Documentation

#### Task 19.1: Create Release Checklist

**File**: `docs/RELEASE_CHECKLIST.md` (new)

Document release process:

- Pre-release checks (data quality, schema compatibility)
- Release steps
- Post-release validation
- Rollback procedure
- Manual testing procedures (CI/CD deferred)

**Acceptance Criteria:**

- [ ] Checklist created
- [ ] All steps documented
- [ ] Checklist is actionable

**Dependencies:** All previous tasks

---

#### Task 19.2: Create Release Scripts (Optional - Manual Process)

**File**: `scripts/release.sh` (new)

Create manual release scripts:

- Run all quality gates locally
- Run all tests locally
- Generate release notes
- Tag release
- Deployment instructions

**Note:** CI/CD automation deferred. This provides manual release process.

**Acceptance Criteria:**

- [ ] Release scripts created
- [ ] All gates can be run manually
- [ ] Release process documented
- [ ] Documentation updated

**Dependencies:** Task 19.1

---

#### Task 19.3: Create Phase 5 Integration Tests

**File**: `tests/integration/test_phase5_release_engineering.py` (new)

Test release engineering:

- Test CI/CD gates
- Test replay system
- Test point-in-time validation
- Test release process

**Acceptance Criteria:**

- [ ] All integration tests pass
- [ ] Release process verified
- [ ] All gates tested

**Dependencies:** All Phase 5 tasks

---

#### Task 19.4: Final Documentation Update

**File**: `docs/` (update multiple files)

Update documentation:

- Architecture overview
- Data pipeline guide
- Schema evolution guide
- Troubleshooting guide

**Acceptance Criteria:**

- [ ] All documentation updated
- [ ] Architecture diagrams current
- [ ] Guides are complete and accurate

**Dependencies:** All phases

---

## Implementation Dependencies

### Critical Path

```
Phase 1 (Foundation)
  ├─> Schema Registry (Week 1)
  ├─> Great Expectations (Week 2)
  ├─> Airflow Setup (Week 3)
  └─> Observability Dashboard (Week 4)
       │
       ▼
Phase 2 (Historical Backfill)
  ├─> Backfill Interface (Week 5)
  ├─> MT5 Backfill (Week 5)
  ├─> OHLCV Aggregation (Week 6)
  └─> Backfill Orchestration (Week 7)
       │
       ▼
Phase 3 (Alternative Data)
  ├─> Economic Indicators (Week 9)
  ├─> AI Web Scraping Framework (Week 10)
  ├─> Scraper Integration (Week 11)
  ├─> Sentiment & Entity Extraction (Week 12)
  └─> Feature Integration (Week 13)
       │
       ▼
Phase 4 (Observability & Lineage)
  ├─> OpenLineage (Week 13)
  ├─> Drift Detection (Week 14)
  └─> Enhanced Dashboard (Week 15)
       │
       ▼
Phase 5 (Release Engineering)
  ├─> Replay System (Week 17)
  ├─> Point-in-Time Validation (Week 18)
  └─> Release Process & Documentation (Week 19)
```

### Key Dependencies

- **Schema Registry** → Required for all data sources (prevents breaking changes)
- **Great Expectations** → Required for quality monitoring
- **Airflow** → Required for orchestrated data collection
- **Historical Backfill** → Required before alternative data backfill
- **OHLCV Aggregation** → Required for feature engineering
- **Lineage Tracking** → Requires all data sources operational

---

## Success Criteria Summary

### Phase 1

- [ ] Schema Registry operational with compatibility checks
- [ ] Great Expectations Data Docs accessible
- [ ] Airflow DAGs running hourly
- [ ] Data quality dashboard showing key metrics

### Phase 2

- [ ] Can backfill 5+ years of MT5 tick data
- [ ] OHLCV aggregation working for all timeframes
- [ ] Progress tracking and resume capability operational
- [ ] Backfill orchestration via Airflow

### Phase 3

- [ ] Economic indicators collected from FRED, World Bank, ECB (free sources)
- [ ] AI-assisted web scraping framework operational (free, high priority)
- [ ] Web scrapers collecting data from 5+ financial websites (free)
- [ ] RSS news collection with sentiment analysis operational (free)
- [ ] Alternative data features integrated into FeatureEngine
- [ ] All alternative data passes quality gates
- [ ] Optional: NewsAPI connector (if free tier sufficient)

### Phase 4

- [ ] Lineage tracking operational (can trace data from source to training)
- [ ] Distribution drift detection working
- [ ] Comprehensive data quality dashboard
- [ ] Automated alerts for quality issues

### Phase 5

- [ ] Data replay system operational
- [ ] Point-in-time validation catches lookahead bias
- [ ] Release process documented (manual, CI/CD deferred)

---

## Risk Mitigation

1. **Schema Registry Complexity**: Start with simple compatibility checks, iterate based on needs
2. **Great Expectations Learning Curve**: Use existing contract validators as starting point
3. **MT5 API Rate Limits**: Implement aggressive rate limiting, batch processing
4. **Large Data Volumes**: Process in batches, monitor disk space, implement data archival
5. **OpenLineage Complexity**: Start with simple job/dataset tracking, iterate
6. **Drift Detection False Positives**: Tune thresholds, use multiple tests, allow manual override

---

## Next Steps

1. **Review and Approve Plan**: Stakeholder review of this implementation plan
2. **Set Up Project Management**: Create GitHub issues from this plan
3. **Begin Phase 1**: Start with Schema Registry implementation (Week 1, Task 1.1)
4. **Weekly Reviews**: Review progress weekly, adjust plan as needed

---

**Plan Version:** 1.1

**Created:** 2026-01-08

**Updated:** 2026-01-08

**Changes:**

- Removed CI/CD integration tasks (deferred for now)
- Reordered Phase 3 to prioritize free data sources (FRED, World Bank, ECB, RSS first)
- Made NewsAPI connector optional (free tier limited)
- Updated Phase 5 to focus on replay and point-in-time validation (CI/CD deferred)

**Status:** Ready for Implementation