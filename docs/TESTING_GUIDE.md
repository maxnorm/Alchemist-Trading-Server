# Testing Guide: Multi-Source Data & Multi-Broker Refactoring

This guide covers how to test the refactored connector and broker adapter architecture.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Unit Tests](#unit-tests)
3. [Integration Tests](#integration-tests)
4. [End-to-End Tests](#end-to-end-tests)
5. [Manual Testing](#manual-testing)
6. [Test Coverage](#test-coverage)

## Quick Start

### Run All Tests

```bash
# From project root
pytest tests/ -v

# With coverage
pytest tests/ --cov=src/trading_server/src --cov-report=html --cov-report=term
```

### Run Specific Test Suites

```bash
# Test connectors only
pytest tests/unit/test_connectors.py -v

# Test broker adapters
pytest tests/unit/test_broker_adapters.py -v

# Test integration
pytest tests/integration/test_connector_interface.py -v
```

## Unit Tests

### 1. Connector Tests

**File:** `tests/unit/test_connectors.py`

Tests for:
- `ConnectorRegistry` - registration, discovery, health checks
- `MT5PriceConnector` - connection, streaming, schema
- Feature discovery from connector schemas

**Run:**
```bash
pytest tests/unit/test_connectors.py -v
```

**Example test:**
```python
def test_connector_registration():
    registry = ConnectorRegistry()
    connector = MT5PriceConnector(...)
    registry.register_connector("test", connector)
    assert registry.get_connector_count() == 1
```

### 2. Broker Adapter Tests

**File:** `tests/unit/test_broker_adapters.py` (to be created)

Tests for:
- `IBrokerAdapter` interface compliance
- `MT5BrokerAdapter` - order submission, position retrieval
- `BrokerFactory` - adapter creation from config

**Run:**
```bash
pytest tests/unit/test_broker_adapters.py -v
```

## Integration Tests

### 1. Connector Integration

**File:** `tests/integration/test_connector_interface.py`

Tests for:
- Connector interface compliance
- Normalization integration
- Connection management
- Multi-connector scenarios

**Run:**
```bash
pytest tests/integration/test_connector_interface.py -v
```

### 2. Data Flow Integration

**Test:** Connector → PriceHistoryManager → FeatureEngine → StateBuilder

**Create test file:** `tests/integration/test_data_flow.py`

```python
def test_connector_to_state_builder():
    # Create connector
    connector = MT5PriceConnector(...)
    connector.connect()
    
    # Create price history manager
    price_manager = PriceHistoryManager(window_size=50, connectors=[connector])
    
    # Wait for data
    time.sleep(2)
    
    # Create state builder
    state_builder = StateBuilder(
        price_history_manager=price_manager,
        feature_engine=feature_engine,
        window_size=50,
        connectors=[connector]
    )
    
    # Build state
    state = state_builder.build_state()
    assert state is not None
    assert state.shape[0] == 50  # window_size
```

**Run:**
```bash
pytest tests/integration/test_data_flow.py -v
```

### 3. Broker Execution Integration

**Test:** TradingController → Account → BrokerAdapter → MT5Terminal

**Create test file:** `tests/integration/test_broker_execution.py`

```python
def test_order_submission_flow():
    # Create broker adapter
    terminal = MT5Terminal(mock_socket)
    adapter = MT5BrokerAdapter.from_terminal(terminal)
    
    # Create account
    account = Account(login=12345, broker_adapter=adapter)
    
    # Submit order
    order = Order(...)
    status = adapter.submit_order(order, idempotency_key="test-123")
    
    assert status.state in [OrderState.FILLED, OrderState.NEW]
```

## End-to-End Tests

### 1. Complete Trading Environment

**Test:** Full environment with connectors and broker adapter

**Create test file:** `tests/e2e/test_refactored_environment.py`

```python
def test_live_trading_env_with_connectors():
    # Create connectors
    connector = MT5PriceConnector(...)
    connector.connect()
    
    # Create broker adapter
    adapter = MT5BrokerAdapter.from_terminal(terminal)
    
    # Create account
    account = Account(login=12345, broker_adapter=adapter)
    
    # Create environment
    env = LiveTradingEnv(
        account=account,
        connectors=[connector],
        window_size=50
    )
    
    # Get state
    state = env.get_state()
    assert state is not None
    
    # Execute action
    action = 1  # BUY
    result = env.step(action)
    assert result is not None
```

**Run:**
```bash
pytest tests/e2e/test_refactored_environment.py -v
```

## Manual Testing

### 1. Test Connector Registration

**Steps:**
1. Start the server
2. Connect a streamer (MT5 EA)
3. Verify connector is registered in `ConnectorRegistry`
4. Check feature discovery

**Code:**
```python
from server import Server
from connectors.registry import ConnectorRegistry

server = Server(verbose=True)
# After streamer connects...
registry = server._connector_registry
print(f"Connectors: {registry.list_connectors()}")
print(f"Features: {len(registry.discover_features())}")
```

### 2. Test Data Flow

**Steps:**
1. Connect streamer
2. Wait for price updates
3. Verify `PriceHistoryManager` receives data
4. Check state builder produces valid states

**Code:**
```python
# In server, after environment creation
env = server.__environments[account_login]
print(f"Price history status: {env.state_builder.get_data_status()}")
state = env.get_state()
print(f"State shape: {state.shape if state is not None else None}")
```

### 3. Test Broker Adapter

**Steps:**
1. Create account with broker adapter
2. Submit test order
3. Verify order status
4. Check account info

**Code:**
```python
from trading.brokers.mt5_adapter import MT5BrokerAdapter
from risk.oms import Order, OrderSide

adapter = MT5BrokerAdapter.from_terminal(terminal)

# Get account info
info = adapter.get_account_info()
print(f"Balance: {info.balance}, Equity: {info.equity}")

# Submit order
order = Order(
    symbol="EURUSD",
    side="BUY",
    quantity=0.01,
    order_type="MARKET"
)
status = adapter.submit_order(order, idempotency_key="test-1")
print(f"Order status: {status.state.value}")
```

### 4. Test Multi-Source Scenario

**Steps:**
1. Connect multiple streamers (different symbols)
2. Verify all connectors work independently
3. Check state builder handles multiple symbols

**Code:**
```python
# Connect EURUSD and GBPUSD
# Verify both connectors registered
connectors = server._connector_registry.get_all_connectors()
assert len(connectors) == 2

# Verify state includes both symbols
state = env.get_state()
# State should have features for both pairs
```

## Test Coverage

### Generate Coverage Report

```bash
# Full coverage report
pytest tests/ \
    --cov=src/trading_server/src \
    --cov-report=html \
    --cov-report=term \
    --cov-report=xml

# View HTML report
# Open htmlcov/index.html in browser
```

### Coverage Targets

- **Connectors:** > 80% coverage
- **Broker Adapters:** > 75% coverage
- **Integration:** > 70% coverage

### Key Files to Test

**Connectors:**
- `src/connectors/base.py` - Interface definition
- `src/connectors/mt5_price_connector.py` - MT5 implementation
- `src/connectors/registry.py` - Registry management

**Brokers:**
- `src/trading/brokers/base.py` - Interface definition
- `src/trading/brokers/mt5_adapter.py` - MT5 implementation
- `src/trading/brokers/factory.py` - Factory pattern

**Integration:**
- `src/application/environment/price_history_manager.py`
- `src/application/environment/state_builder.py`
- `src/models/account.py`
- `src/application/trading/trade_executor.py`

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure Python path includes src
   export PYTHONPATH="${PYTHONPATH}:$(pwd)/src/trading_server/src"
   ```

2. **Mock Issues**
   - Use `unittest.mock` for mocking
   - Mock database connections
   - Mock MT5 terminal connections

3. **Async Issues**
   - Use `asyncio.run()` for async functions
   - Mock async methods properly

### Debug Mode

```bash
# Run with debug output
pytest tests/ -v -s --log-cli-level=DEBUG

# Run single test with pdb
pytest tests/unit/test_connectors.py::TestMT5PriceConnector::test_stream -v --pdb
```

## Next Steps

1. **Add Missing Tests:**
   - Broker adapter unit tests
   - End-to-end environment tests
   - Performance tests

2. **Improve Coverage:**
   - Add edge case tests
   - Add error handling tests
   - Add concurrent access tests

3. **CI/CD Integration:**
   - Add to GitHub Actions
   - Set coverage thresholds
   - Add performance benchmarks
