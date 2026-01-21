---
name: Week 6 Event Normalization and Connector Interface
overview: Implement event normalization layer with canonical schema and timestamp alignment, then create unified data source connector interface to enable plug-and-play data sources while ensuring data correctness.
todos:
  - id: week6_day17_schema_registry
    content: Create events/schema_registry.py with canonical event schema definition and source-specific schema registration
    status: pending
  - id: week6_day17_quality_gates
    content: Create events/quality_gates.py with event-level quality checks (timestamp validation, required fields, value ranges)
    status: pending
  - id: week6_day18_normalizer
    content: Implement events/normalizer.py with IEventNormalizer interface, MT5 normalization, and timestamp alignment validation
    status: pending
    dependencies:
      - week6_day17_schema_registry
      - week6_day17_quality_gates
  - id: week6_day18_tick_streamer_integration
    content: Integrate EventNormalizer with mt5_connection/tick_streamer.py to normalize ticks before storage
    status: pending
    dependencies:
      - week6_day18_normalizer
  - id: week6_day19_normalization_tests
    content: Create tests/integration/test_event_normalizer.py with normalization, validation, and timestamp alignment tests
    status: pending
    dependencies:
      - week6_day18_normalizer
  - id: week6_day20_connector_interface
    content: Create connectors/base.py with IDataSourceConnector interface and ConnectorConfig dataclass
    status: pending
  - id: week6_day21_mt5_connector
    content: Implement connectors/mt5_tick_connector.py wrapping MT5TickStreamer and integrating with EventNormalizer
    status: pending
    dependencies:
      - week6_day20_connector_interface
      - week6_day18_normalizer
  - id: week6_day21_streamer_manager_update
    content: Update infrastructure/connections/streamer_manager.py to create and manage connectors alongside streamers
    status: pending
    dependencies:
      - week6_day21_mt5_connector
  - id: week6_day21_connector_tests
    content: Create tests/integration/test_connector_interface.py with interface compliance, MT5 connector, and integration tests
    status: pending
    dependencies:
      - week6_day21_mt5_connector
---

# Week 6: Event Normalization & Data Source Connector Interface

## Overview

Week 6 focuses on **data correctness** and **modularity** by implementing:

1. **Event Normalization Layer** - Canonical schema for all data sources with timestamp alignment validation
2. **Data Source Connector Interface** - Unified interface enabling plug-and-play data sources

This week addresses **P1 issues**: "No event normalization layer" and "High coupling for data sources" from the audit plan.

## Dependencies

- **Week 5** (Market Impact & Stress Tests) must be completed
- Uses existing `utils/time_utils.py` for UTC normalization
- Integrates with existing `data_providers/` structure
- Builds on `mt5_connection/tick_streamer.py` validation logic

---

## Task 6.1: Event Normalization Layer (Days 17-19)

### Goal

Create a canonical event schema and normalization layer that ensures data correctness across all sources, with timestamp alignment validation to prevent temporal misalignment.

### Files to Create

#### 1. `src/mt5-python_server/src/events/__init__.py`

```python
"""Event normalization layer for data correctness"""
from .normalizer import EventNormalizer, IEventNormalizer
from .schema_registry import CanonicalEventSchema, SchemaRegistry
from .quality_gates import EventQualityGates

__all__ = [
    "EventNormalizer",
    "IEventNormalizer",
    "CanonicalEventSchema",
    "SchemaRegistry",
    "EventQualityGates",
]
```

#### 2. `src/mt5-python_server/src/events/schema_registry.py`

**Purpose**: Define canonical event schema and source-specific schemas

**Key Components**:

- `CanonicalEventSchema` class with schema definition:
  ```python
  {
      "timestamp": datetime,  # UTC normalized, timezone-aware
      "source": str,          # "mt5", "api", "scraper", "news"
      "symbol": str,          # "EURUSD", "GBPUSD", etc.
      "data_type": str,       # "tick", "bar", "news", "economic"
      "payload": Dict[str, Any]  # Source-specific data
  }
  ```

- `SchemaRegistry` class to register source-specific schemas
- Schema validation methods

**Success Criteria**:

- Canonical schema enforces UTC timestamps
- Schema validation rejects malformed events
- Source-specific schemas can be registered

#### 3. `src/mt5-python_server/src/events/quality_gates.py`

**Purpose**: Event-level quality checks integrated with normalization

**Key Components**:

- `EventQualityGates` class with checks:
  - Timestamp validation (not future, not too stale)
  - Required fields present
  - Data type validation
  - Value range checks (e.g., bid < ask for ticks)
- Integration with existing `data/quality_gates.py` (from Week 1)

**Success Criteria**:

- Invalid events rejected before normalization
- Quality metrics logged
- Integration with Week 1 quality gates

#### 4. `src/mt5-python_server/src/events/normalizer.py`

**Purpose**: Core normalization logic converting raw events to canonical format

**Key Components**:

- `IEventNormalizer` abstract base class:
  ```python
  class IEventNormalizer(ABC):
      @abstractmethod
      def normalize(self, raw_event: Dict, source: str) -> Dict:
          """Convert raw event to canonical format"""
          pass
      
      @abstractmethod
      def validate(self, event: Dict) -> bool:
          """Validate event quality and schema"""
          pass
      
      @abstractmethod
      def align_timestamps(self, events: List[Dict]) -> List[Dict]:
          """Align timestamps across sources"""
          pass
  ```

- `EventNormalizer` implementation:
  - `normalize()` - Convert MT5, API, scraped data to canonical format
  - `validate()` - Schema and quality validation
  - `align_timestamps()` - Cross-source timestamp alignment with validation
  - Source-specific normalizers: `_normalize_mt5()`, `_normalize_api()`, `_normalize_scraped()`

**Implementation Details**:

- Use `utils/time_utils.normalize_to_utc()` for timestamp normalization
- Validate no future timestamps (reject if timestamp > current_time + buffer)
- Sort events chronologically in `align_timestamps()`
- Log normalization failures for debugging

**Success Criteria**:

- All MT5 ticks normalized to canonical format
- Timestamp alignment validates cross-source consistency
- Invalid events rejected with logging

### Files to Modify

#### 5. `src/mt5-python_server/src/mt5_connection/tick_streamer.py`

**Changes**:

- Import `EventNormalizer` from `events.normalizer`
- After tick validation (line 550), normalize tick to canonical format:
  ```python
  # After line 559: self.__add_tick_to_buffer(...)
  normalized_tick = event_normalizer.normalize(tick_info, source="mt5")
  # Store normalized tick instead of raw tick
  ```

- Pass normalized events to database/consumers

**Note**: This is a bridge step - full refactoring happens in Task 6.2

### Tests to Create

#### 6. `tests/integration/test_event_normalizer.py`

**Test Cases**:

1. **Normalization Tests**:

   - MT5 tick normalization to canonical format
   - API event normalization
   - Scraped data normalization
   - Invalid source rejection

2. **Validation Tests**:

   - Future timestamp rejection
   - Missing required fields rejection
   - Invalid data type rejection
   - Quality gate integration

3. **Timestamp Alignment Tests**:

   - Cross-source timestamp alignment
   - Chronological sorting
   - Timezone normalization (all to UTC)
   - Alignment validation (max drift threshold)

4. **Integration Tests**:

   - End-to-end: Raw MT5 tick → Normalized event → Database
   - Multiple sources alignment
   - Quality gate rejection flow

**Success Criteria**:

- All normalization tests pass
- Timestamp alignment validates correctly
- Invalid events rejected appropriately

---

## Task 6.2: Data Source Connector Interface (Days 19-21)

### Goal

Create unified `IDataSourceConnector` interface enabling plug-and-play data sources, reducing coupling from 6+ files to 1 connector implementation.

### Files to Create

#### 1. `src/mt5-python_server/src/connectors/__init__.py`

```python
"""Data source connector interface for modular data sources"""
from .base import IDataSourceConnector, ConnectorConfig
from .mt5_tick_connector import MT5TickConnector

__all__ = [
    "IDataSourceConnector",
    "ConnectorConfig",
    "MT5TickConnector",
]
```

#### 2. `src/mt5-python_server/src/connectors/base.py`

**Purpose**: Define unified connector interface

**Key Components**:

- `ConnectorConfig` dataclass for connector configuration
- `IDataSourceConnector` abstract base class:
  ```python
  class IDataSourceConnector(ABC):
      @abstractmethod
      def stream(self, start_time: Optional[datetime] = None) -> Iterator[Dict[str, Any]]:
          """Stream events in real-time, yielding normalized events"""
          pass
      
      @abstractmethod
      def batch(self, start_time: datetime, end_time: datetime) -> Iterator[Dict[str, Any]]:
          """Fetch historical data in batches, yielding normalized events"""
          pass
      
      @abstractmethod
      def get_schema(self) -> Dict[str, Any]:
          """Return source schema definition"""
          pass
      
      @abstractmethod
      def get_latest_timestamp(self) -> Optional[datetime]:
          """Get timestamp of most recent data"""
          pass
      
      @abstractmethod
      def connect(self) -> bool:
          """Establish connection to data source"""
          pass
      
      @abstractmethod
      def disconnect(self) -> None:
          """Close connection to data source"""
          pass
  ```


**Design Principles**:

- All methods return **normalized events** (canonical format)
- Connectors handle their own normalization internally
- Interface is source-agnostic

**Success Criteria**:

- Interface clearly defined
- All methods documented
- Type hints complete

#### 3. `src/mt5-python_server/src/connectors/mt5_tick_connector.py`

**Purpose**: Refactor MT5 tick streaming to use connector interface

**Key Components**:

- `MT5TickConnector` class implementing `IDataSourceConnector`
- Wraps existing `MT5TickStreamer` functionality
- Integrates with `EventNormalizer` for normalization
- Handles socket connection, authentication, tick reception

**Implementation Details**:

```python
class MT5TickConnector(IDataSourceConnector):
    def __init__(self, socket, symbol: str, config: ConnectorConfig):
        self.socket = socket
        self.symbol = symbol
        self.config = config
        self.normalizer = EventNormalizer()
        self.streamer = None  # MT5TickStreamer instance
    
    def stream(self, start_time: Optional[datetime] = None):
        """Stream normalized MT5 ticks"""
        for raw_tick in self._receive_raw_ticks():
            normalized = self.normalizer.normalize(raw_tick, source="mt5")
            if self.normalizer.validate(normalized):
                yield normalized
    
    def batch(self, start_time: datetime, end_time: datetime):
        """Fetch historical ticks from database"""
        # Query database for historical ticks
        # Normalize and yield
        pass
```

**Migration Strategy**:

- Keep `MT5TickStreamer` as internal implementation detail
- `MT5TickConnector` wraps `MT5TickStreamer` and adds normalization
- Gradual migration: new code uses connector, old code still works

**Success Criteria**:

- MT5 connector implements all interface methods
- Normalized events yielded from `stream()`
- Historical batch fetch works
- Backward compatible with existing code

### Files to Modify

#### 4. `src/mt5-python_server/src/infrastructure/connections/streamer_manager.py`

**Changes**:

- Add connector creation in `authenticate_streamer()`:
  ```python
  # After line 62: streamer = MT5TickStreamer(...)
  connector = MT5TickConnector(client, symbol, config)
  self.connectors[symbol] = connector
  ```

- Add method `get_connectors() -> List[IDataSourceConnector]`
- Optionally: Use connectors instead of direct streamers

**Note**: Keep backward compatibility - both connectors and streamers can coexist during migration

#### 5. `src/mt5-python_server/src/server.py`

**Changes**:

- Import connector interface
- Optionally register connectors in addition to streamers
- No breaking changes - gradual migration

#### 6. `src/mt5-python_server/src/data_providers/price_provider.py`

**Future Enhancement** (optional this week):

- Consider using connector interface for data fetching
- Keep existing `DataProvider` interface for now (different abstraction level)

**Note**: `DataProvider` is for feature-level abstraction, `IDataSourceConnector` is for raw data streaming. They serve different purposes and can coexist.

### Tests to Create

#### 7. `tests/integration/test_connector_interface.py`

**Test Cases**:

1. **Interface Compliance Tests**:

   - All connectors implement required methods
   - Method signatures match interface
   - Type hints correct

2. **MT5 Connector Tests**:

   - Real-time streaming produces normalized events
   - Historical batch fetch works
   - Schema definition correct
   - Latest timestamp retrieval

3. **Normalization Integration Tests**:

   - Connector yields normalized events
   - Events pass validation
   - Timestamp alignment works

4. **Connection Management Tests**:

   - Connect/disconnect lifecycle
   - Error handling on connection failure
   - Reconnection logic

5. **Multi-Source Tests** (future):

   - Multiple connectors can run simultaneously
   - Events from different sources align correctly

**Success Criteria**:

- All interface tests pass
- MT5 connector fully functional
- Normalized events produced correctly

---

## Implementation Timeline

### Day 17 (Event Normalization - Part 1)

- [ ] Create `events/` directory structure
- [ ] Implement `schema_registry.py` with canonical schema
- [ ] Implement `quality_gates.py` with event quality checks
- [ ] Write unit tests for schema registry and quality gates

### Day 18 (Event Normalization - Part 2)

- [ ] Implement `normalizer.py` with `IEventNormalizer` interface
- [ ] Implement MT5 normalization logic
- [ ] Implement timestamp alignment validation
- [ ] Integrate with `tick_streamer.py` (bridge step)
- [ ] Write integration tests

### Day 19 (Event Normalization - Part 3)

- [ ] Complete normalization tests
- [ ] Fix any issues found in testing
- [ ] Document normalization layer usage
- [ ] Verify timestamp alignment works correctly

### Day 20 (Connector Interface - Part 1)

- [ ] Create `connectors/` directory structure
- [ ] Implement `base.py` with `IDataSourceConnector` interface
- [ ] Design `ConnectorConfig` dataclass
- [ ] Write interface compliance tests

### Day 21 (Connector Interface - Part 2)

- [ ] Implement `mt5_tick_connector.py` wrapping `MT5TickStreamer`
- [ ] Integrate with `EventNormalizer`
- [ ] Update `streamer_manager.py` to use connectors
- [ ] Write connector integration tests
- [ ] Verify backward compatibility

---

## Success Criteria (Week 6 Completion)

### Event Normalization Layer

- ✅ All sources normalized to canonical format
- ✅ Timestamp alignment validates cross-source consistency
- ✅ Invalid events rejected with proper logging
- ✅ Integration tests pass (100% pass rate)
- ✅ Documentation complete

### Data Source Connector Interface

- ✅ `IDataSourceConnector` interface defined and documented
- ✅ MT5 connector implements interface correctly
- ✅ Connector yields normalized events
- ✅ Historical batch fetch works
- ✅ Backward compatibility maintained
- ✅ Integration tests pass

### Code Quality

- ✅ Type hints complete
- ✅ Docstrings for all public methods
- ✅ No linter errors
- ✅ Test coverage > 80% for new code

---

## Risk Mitigation

### Risk 1: Breaking Existing Functionality

**Mitigation**:

- Keep `MT5TickStreamer` as internal implementation
- Gradual migration approach
- Backward compatibility maintained
- Comprehensive integration tests

### Risk 2: Performance Impact of Normalization

**Mitigation**:

- Normalization is lightweight (dict transformation)
- Batch processing for historical data
- Performance benchmarks in tests
- Optional caching for repeated normalizations

### Risk 3: Timestamp Alignment Complexity

**Mitigation**:

- Use existing `time_utils.normalize_to_utc()`
- Clear validation rules (max drift threshold)
- Comprehensive test cases
- Logging for debugging alignment issues

---

## Dependencies & Integration Points

### Uses Existing Code

- `utils/time_utils.py` - UTC normalization
- `mt5_connection/tick_streamer.py` - MT5 tick reception (wrapped)
- `database.py` - Event storage (normalized events)
- `data/quality_gates.py` (Week 1) - Quality check integration

### Enables Future Work

- **Week 7**: Feature versioning can use normalized events
- **Weeks 13-14**: Broker modularity can follow same pattern
- **Multi-source support**: New sources just implement connector interface

---

## Documentation Deliverables

1. **API Documentation**: Docstrings for all public classes/methods
2. **Usage Guide**: How to add new data sources using connector interface
3. **Architecture Diagram**: Event normalization flow
4. **Migration Guide**: How to migrate existing code to use connectors

---

## Next Steps (Week 7 Preview)

Week 7 will build on Week 6 by:

- Using normalized events for feature versioning
- Storing feature metadata with normalized event schemas
- Tracking feature pipeline versions with event schemas