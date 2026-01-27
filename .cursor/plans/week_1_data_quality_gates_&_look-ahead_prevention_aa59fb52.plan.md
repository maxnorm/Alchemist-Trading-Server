---
name: "Week 1: Data Quality Gates & Look-Ahead Prevention"
overview: Implement systematic data quality gates for tick validation and add point-in-time constraints to feature extraction to prevent look-ahead bias. This establishes the foundation for data correctness and evaluation realism.
todos:
  - id: week1_task1_quality_gate_class
    content: Create QualityGate class in src/mt5-python_server/src/data/quality_gates.py with outlier, duplicate, staleness, and missing data checks
    status: pending
  - id: week1_task1_integrate_streamer
    content: Integrate QualityGate with mt5_connection/tick_streamer.py validation pipeline
    status: pending
    dependencies:
      - week1_task1_quality_gate_class
  - id: week1_task1_tests
    content: Create tests/integration/test_data_quality_gates.py with comprehensive test cases
    status: pending
    dependencies:
      - week1_task1_quality_gate_class
  - id: week1_task2_timestamp_tracking
    content: Enhance PriceHistoryManager to track timestamps alongside prices
    status: pending
  - id: week1_task2_feature_timestamp_param
    content: Modify FeatureEngine.extract_features() to accept current_time parameter and enforce point-in-time constraints
    status: pending
    dependencies:
      - week1_task2_timestamp_tracking
  - id: week1_task2_economic_latency
    content: Add 5-minute latency buffer to extract_economic_features() for economic calendar data
    status: pending
    dependencies:
      - week1_task2_feature_timestamp_param
  - id: week1_task2_update_call_sites
    content: Update all call sites (StateBuilder, environments) to pass current_time to feature extraction
    status: pending
    dependencies:
      - week1_task2_economic_latency
  - id: week1_task2_tests
    content: Create tests/unit/test_feature_timestamps.py to verify no look-ahead bias
    status: pending
    dependencies:
      - week1_task2_update_call_sites
---

# Week 1: Data Quality Gates & Look-Ahead Prevention

## Overview

Week 1 focuses on two critical tasks that establish the foundation for data correctness and evaluation realism:

1. **Data Quality Gates**: Systematic quality pipeline for tick validation
2. **Feature Point-in-Time Constraints**: Prevent look-ahead bias in feature extraction

## Task 1.1: Data Quality Gates (Days 1-2)

### Files to Create

- `src/mt5-python_server/src/data/quality_gates.py` - Systematic quality pipeline
- `tests/integration/test_data_quality_gates.py` - Quality gate tests

### Implementation Details

#### 1.1.1 Create QualityGate Class

Create `src/mt5-python_server/src/data/quality_gates.py` with a `QualityGate` class that implements systematic quality checks:

**Quality Checks:**

- **Outliers**: Statistical bounds using z-score (default: |z| > 3) or IQR method
  - Check bid/ask prices against historical distribution
  - Check spread (ask - bid) for unrealistic values
- **Duplicates**: Timestamp + symbol uniqueness
  - Reject ticks with identical (symbol, datetime) within tolerance window (e.g., 1 second)
- **Staleness**: Max age threshold
  - Reject ticks older than threshold (default: 300 seconds / 5 minutes)
  - Compare tick timestamp to current time
- **Missing Data**: Required fields validation
  - Ensure symbol, datetime, ask, bid are present and non-null
  - Validate data types

**Quality Metrics Logging:**

- Track counts per check type (outliers_rejected, duplicates_rejected, stale_rejected, missing_data_rejected)
- Track total ticks processed vs accepted
- Log quality scores (acceptance rate)
- Use structured logging compatible with existing `utils/logging_config.py`

**Interface:**

```python
class QualityGate:
    def __init__(self, config: Optional[Dict] = None):
        # Configurable thresholds
        self.outlier_z_threshold = config.get('outlier_z_threshold', 3.0)
        self.staleness_threshold_seconds = config.get('staleness_threshold_seconds', 300)
        self.duplicate_tolerance_seconds = config.get('duplicate_tolerance_seconds', 1)
        
    def validate(self, tick: Dict[str, Any], symbol: str, current_time: datetime) -> Tuple[bool, Optional[str]]:
        """
        Validate tick quality
        Returns: (is_valid, rejection_reason)
        """
        pass
        
    def get_metrics(self) -> Dict[str, Any]:
        """Return quality metrics"""
        pass
```

#### 1.1.2 Integrate with Tick Streamer

Modify `src/mt5-python_server/src/mt5_connection/tick_streamer.py`:

1. **Import QualityGate** at the top
2. **Initialize QualityGate** in `__init__()`:
   ```python
   from data.quality_gates import QualityGate
   self.quality_gate = QualityGate()
   ```

3. **Integrate validation** in `receive_tick()` method after existing `__validate_tick()` and `__validate_tick_order()`:
   ```python
   # After line 555 (after __validate_tick_order)
   # Quality gate validation
   is_valid, rejection_reason = self.quality_gate.validate(
       tick_info, symbol, get_utc_time()
   )
   if not is_valid:
       self.__logger.log_event(
           event_type="quality_gate_rejection",
           message=f"Tick rejected by quality gate: {rejection_reason}",
           symbol=symbol,
           metrics={"rejection_reason": rejection_reason},
           level="WARNING"
       )
       continue
   ```

4. **Log quality metrics** periodically (e.g., every 1000 ticks) in `receive_tick()`:
   ```python
   if tick_count % 1000 == 0:
       metrics = self.quality_gate.get_metrics()
       self.__logger.log_event(
           event_type="quality_metrics",
           message="Quality gate metrics",
           metrics=metrics
       )
   ```


#### 1.1.3 Create Tests

Create `tests/integration/test_data_quality_gates.py`:

**Test Cases:**

1. **Outlier Detection**:

   - Test with price 10x normal (should reject)
   - Test with normal price (should accept)
   - Test with spread > 10 pips (should reject for major pairs)

2. **Duplicate Detection**:

   - Test with identical timestamp + symbol (should reject)
   - Test with different timestamps (should accept)
   - Test with timestamps within tolerance window (should reject)

3. **Staleness Detection**:

   - Test with tick older than threshold (should reject)
   - Test with recent tick (should accept)
   - Test with tick exactly at threshold boundary

4. **Missing Data Detection**:

   - Test with missing symbol (should reject)
   - Test with missing ask/bid (should reject)
   - Test with None values (should reject)

5. **Integration Test**:

   - Test QualityGate with actual tick streamer flow
   - Verify metrics are tracked correctly
   - Verify rejected ticks are logged

**Success Criteria:**

- Invalid ticks rejected with appropriate reason
- Quality metrics logged correctly
- All tests pass
- Integration with tick_streamer works without breaking existing functionality

---

## Task 1.2: Feature Point-in-Time Constraints (Days 2-3)

### Files to Modify

- `src/mt5-python_server/src/application/environment/feature_engine.py` - Add timestamp validation
- `src/mt5-python_server/src/application/environment/price_history_manager.py` - Track timestamps with prices
- `src/mt5-python_server/src/application/environment/state_builder.py` - Pass current_time to feature extraction

### Files to Create

- `tests/unit/test_feature_timestamps.py` - Verify no look-ahead bias

### Implementation Details

#### 1.2.1 Enhance PriceHistoryManager to Track Timestamps

Modify `src/mt5-python_server/src/application/environment/price_history_manager.py`:

**Current State**: `price_history_by_pair` is `Dict[str, List[float]]` (prices only)

**Change to**: Store prices with timestamps:

```python
# Option 1: Store tuples (timestamp, price)
self.price_history_by_pair: Dict[str, List[Tuple[datetime, float]]] = {}

# Option 2: Separate dicts (maintain backward compatibility)
self.price_history_by_pair: Dict[str, List[float]] = {}  # Keep for backward compat
self.price_timestamps: Dict[str, List[datetime]] = {}  # New: track timestamps
```

**Modify `add_price()` method**:

```python
def add_price(self, symbol: str, price: float, timestamp: Optional[datetime] = None):
    """
    Add price to history with timestamp
    :param symbol: Currency pair symbol
    :param price: Price value
    :param timestamp: Timestamp (defaults to current time if None)
    """
    if timestamp is None:
        timestamp = datetime.utcnow()
    
    # Store price
    if symbol not in self.price_history_by_pair:
        self.price_history_by_pair[symbol] = []
        self.price_timestamps[symbol] = []
    
    self.price_history_by_pair[symbol].append(price)
    self.price_timestamps[symbol].append(timestamp)
    self.last_update_time[symbol] = time.time()
    
    # Prune both lists together
    if len(self.price_history_by_pair[symbol]) > self.window_size * 2:
        self.price_history_by_pair[symbol].pop(0)
        self.price_timestamps[symbol].pop(0)
```

**Add method to get filtered history**:

```python
def get_history_up_to(self, symbol: str, max_timestamp: datetime) -> List[float]:
    """
    Get price history filtered to only include prices <= max_timestamp
    :param symbol: Currency pair symbol
    :param max_timestamp: Maximum timestamp (point-in-time constraint)
    :return: List of prices with timestamp <= max_timestamp
    """
    if symbol not in self.price_history_by_pair:
        return []
    
    prices = self.price_history_by_pair[symbol]
    timestamps = self.price_timestamps.get(symbol, [])
    
    # If no timestamps tracked, return all (backward compatibility)
    if not timestamps or len(timestamps) != len(prices):
        return prices
    
    # Filter by timestamp
    filtered = [
        price for price, ts in zip(prices, timestamps)
        if ts <= max_timestamp
    ]
    return filtered
```

#### 1.2.2 Modify FeatureEngine.extract_features()

Modify `src/mt5-python_server/src/application/environment/feature_engine.py`:

**Change signature**:

```python
def extract_features(
    self, 
    price_history: List[float], 
    symbol: str,
    current_time: Optional[datetime] = None  # NEW: point-in-time constraint
) -> Optional[np.ndarray]:
```

**Add timestamp filtering** (after line 49):

```python
# Point-in-time constraint: filter price_history to only include data <= current_time
if current_time is not None:
    # If price_history comes from PriceHistoryManager, it should already be filtered
    # But we add defensive check here
    # For now, we assume price_history is already filtered by caller
    # This will be enforced by PriceHistoryManager.get_history_up_to()
    pass  # Placeholder - actual filtering done by PriceHistoryManager
```

**Note**: The actual filtering happens in `PriceHistoryManager.get_history_up_to()`, but we add the parameter for explicit point-in-time awareness.

#### 1.2.3 Modify extract_economic_features() for Latency Buffer

Modify `extract_economic_features()` in `feature_engine.py` (around line 112):

**Add latency buffer** (5 minutes) for economic calendar features:

```python
def extract_economic_features(
    self, symbol: str, current_time: datetime
) -> Dict[str, float]:
    """
    Extract economic calendar features for a symbol
    :param symbol: Currency pair symbol
    :param current_time: Current datetime (point-in-time constraint)
    :return: Dictionary of economic features
    """
    # Apply latency buffer: only use events published at least 5 minutes ago
    LATENCY_BUFFER_MINUTES = 5
    effective_time = current_time - timedelta(minutes=LATENCY_BUFFER_MINUTES)
    
    # ... existing code ...
    
    # Modify event query to use effective_time instead of current_time
    # In get_upcoming_events(), filter events where datetime < effective_time
    events = self.database.get_upcoming_events(hours_ahead=24)
    
    # Filter events to only include those published before effective_time
    available_events = [
        e for e in events
        if e["datetime"] < effective_time  # Only use events published before effective_time
    ]
    
    # ... rest of existing code using available_events instead of events ...
```

**Note**: This requires checking if `database.get_upcoming_events()` supports timestamp filtering. If not, filter in this method.

#### 1.2.4 Update All Call Sites

**Modify `extract_features_for_all_pairs()`** in `feature_engine.py` (around line 193):

```python
def extract_features_for_all_pairs(
    self, 
    price_histories: Dict[str, List[float]], 
    data_providers,
    current_time: Optional[datetime] = None  # NEW parameter
) -> Optional[np.ndarray]:
    # ... existing code ...
    
    # In the loop (around line 222):
    pair_features = self.extract_features(
        price_history, 
        symbol,
        current_time=current_time  # Pass current_time
    )
```

**Modify `StateBuilder.build_state()`** in `state_builder.py` (around line 37):

```python
def build_state(self, current_time: Optional[datetime] = None) -> Optional[np.ndarray]:
    """
    Build state vector from current data
    :param current_time: Current datetime for point-in-time constraint (defaults to now)
    :return: State array or None if insufficient data
    """
    if current_time is None:
        from datetime import datetime
        current_time = datetime.utcnow()
    
    # ... existing code ...
    
    # Get price histories with point-in-time filtering
    # Modify to use get_history_up_to() if available
    price_histories = self.price_manager.get_all_histories()
    
    # If PriceHistoryManager supports get_history_up_to(), use it:
    # price_histories = {
    #     symbol: self.price_manager.get_history_up_to(symbol, current_time)
    #     for symbol in price_histories.keys()
    # }
    
    # Extract features for all pairs
    state = self.feature_engine.extract_features_for_all_pairs(
        price_histories, 
        self.data_providers,
        current_time=current_time  # Pass current_time
    )
```

**Update environment call sites**:

- `src/mt5-python_server/src/environments/live_env.py`: Update `StateBuilder.build_state()` calls to pass `current_time=datetime.utcnow()`
- `src/mt5-python_server/src/environments/historical_env.py`: Update to pass historical timestamps
- `src/mt5-python_server/src/environments/paper_env.py`: Update to pass current time

#### 1.2.5 Create Tests

Create `tests/unit/test_feature_timestamps.py`:

**Test Cases:**

1. **Point-in-Time Filtering**:

   - Test with price_history containing future timestamps (should filter out)
   - Test with price_history containing only past timestamps (should accept all)
   - Test with mixed timestamps (should only use <= current_time)

2. **Economic Calendar Latency Buffer**:

   - Test with event published 1 minute ago (should reject - too recent)
   - Test with event published 10 minutes ago (should accept)
   - Test with event published exactly 5 minutes ago (should reject - boundary)

3. **Look-Ahead Bias Detection**:

   - Test that features computed at time T don't use data from time T+1
   - Test with sequential timestamps to verify temporal ordering
   - Test that cached indicators respect timestamp constraints

4. **Backward Compatibility**:

   - Test that extract_features() works without current_time parameter (defaults to no filtering)
   - Test that existing code still works

**Success Criteria:**

- All features pass timestamp validation
- No look-ahead bias in tests (automated detection)
- Economic calendar features respect 5-minute latency buffer
- All call sites updated
- Backward compatibility maintained

---

## Dependencies & Sequencing

1. **Task 1.1 → Task 1.2**: Data quality gates should be in place before feature extraction modifications
2. Both tasks can be developed in parallel after initial design, but integration should be sequential

## Testing Strategy

- **Unit Tests**: Test each quality gate check independently
- **Integration Tests**: Test quality gates with actual tick streamer
- **Look-Ahead Tests**: Automated tests that verify no future data is used
- **Backward Compatibility Tests**: Ensure existing code still works

## Success Metrics

- **Task 1.1**: 
  - Invalid ticks rejected with appropriate logging
  - Quality metrics tracked and logged
  - All tests pass

- **Task 1.2**:
  - All features respect point-in-time constraints
  - No look-ahead bias detected in tests
  - Economic calendar features respect latency buffer
  - All call sites updated

## Risk Mitigation

1. **Backward Compatibility**: Maintain default parameters to allow gradual migration
2. **Performance**: Quality gates should be fast (< 1ms per tick) - use efficient algorithms
3. **False Positives**: Quality gates should be configurable to avoid rejecting legitimate market events
4. **Testing**: Comprehensive test coverage to catch regressions

## Notes

- Quality gates should be configurable via environment variables or config file
- Consider adding Prometheus metrics for quality gate statistics (future enhancement)
- Point-in-time constraints are critical for preventing look-ahead bias in backtesting
- Economic calendar latency buffer accounts for publication delay and processing time