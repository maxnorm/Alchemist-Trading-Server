# Test Suite Documentation

This directory contains the comprehensive test suite for The Alchemist trading platform, organized by component for better maintainability and alignment with CI workflows.

## Test Structure

Tests are organized in a **component-first** structure:

```
tests/
├── api/                    # FastAPI API tests
│   ├── unit/               # Unit tests (mocked dependencies)
│   ├── integration/        # Integration tests (API + DB, API + Redis)
│   └── e2e/                # End-to-end API workflows
├── trading_server/         # Trading Server tests
│   ├── unit/               # Unit tests (mocked dependencies)
│   ├── integration/        # Integration tests (Server + DB, connectors)
│   └── e2e/                # Trading Server workflows
├── shared/                 # Cross-component tests
│   ├── e2e/                # Cross-component E2E tests
│   ├── fixtures/           # Shared fixtures (database, mocks)
│   └── helpers/            # Test utilities
├── performance/            # Performance tests
└── stress/                 # Stress tests
```

## Test Classification

### Unit Tests
- **Isolated functions/classes** with all dependencies mocked
- **No database**, no network calls
- **Fast execution** (< 1 second per test)
- **Location**: `tests/{component}/unit/`

### Integration Tests
- **Component + real PostgreSQL/TimescaleDB** (via testcontainers)
- **Component + multiple services** (DB + Redis + message queues)
- **Multiple components** working together
- May use mocks for external services (MT5, external APIs)
- **Location**: `tests/{component}/integration/`

### E2E Tests
- **Full user workflows** spanning components
- **Docker Compose or testcontainers** for infrastructure
- **Complete business flows**
- **Location**: `tests/{component}/e2e/` or `tests/shared/e2e/`

## Prerequisites

Install test dependencies:

```bash
pip install -r tests/requirements-test.txt
```

Or install individually:

```bash
pip install pytest pytest-cov pytest-asyncio pytest-mock pytest-timeout \
  freezegun faker responses pytest-env testcontainers[postgres]
```

## Running Tests

### Run All Tests

```bash
# From project root
pytest tests/ -v
```

### Run Component-Specific Tests

```bash
# API tests only
pytest tests/api/ -v

# Trading Server tests only
pytest tests/trading_server/ -v
```

### Run by Test Type

```bash
# All unit tests
pytest tests/ -m unit -v

# All integration tests
pytest tests/ -m integration -v

# All E2E tests
pytest tests/ -m e2e -v
```

### Run Specific Test Suites

```bash
# API unit tests
pytest tests/api/unit/ -v

# Trading Server integration tests
pytest tests/trading_server/integration/ -v

# Cross-component E2E tests
pytest tests/shared/e2e/ -v
```

### Run Specific Test Files

```bash
# Specific test file
pytest tests/trading_server/unit/test_kill_switch.py -v

# Specific test class
pytest tests/trading_server/unit/test_kill_switch.py::TestKillSwitch -v

# Specific test method
pytest tests/trading_server/unit/test_kill_switch.py::TestKillSwitch::test_file_trigger -v
```

## Test Coverage

Generate coverage report:

```bash
# API coverage
pytest tests/api/unit/ --cov=src/backend/api/src --cov-report=html --cov-report=term

# Trading Server coverage
pytest tests/trading_server/unit/ --cov=src/backend/trading_server/src --cov-report=html --cov-report=term

# Combined coverage
pytest tests/ --cov=src/backend/api/src --cov=src/backend/trading_server/src --cov-report=html --cov-report=term
```

Coverage reports:
- Terminal output: `--cov-report=term`
- HTML report: `--cov-report=html` (generates `htmlcov/` directory)

## CI/CD Integration

Tests run automatically in CI:

- **API Tests**: `.github/workflows/test_api.yml`
  - Runs `tests/api/unit/` and `tests/api/integration/`
  
- **Trading Server Tests**: `.github/workflows/test_server.yml`
  - Runs `tests/trading_server/unit/`, `tests/trading_server/integration/`, and `tests/trading_server/e2e/`

## Test Fixtures

### Shared Fixtures

Located in `tests/shared/fixtures/`:

- **`database.py`**: PostgreSQL testcontainer fixtures
- **`mocks.py`**: Mock factories (MT5 terminal, Redis, data providers)

### Component-Specific Fixtures

- **API**: `tests/api/conftest.py` - FastAPI TestClient, mock database
- **Trading Server**: `tests/trading_server/conftest.py` - Trading server fixtures

### Using Fixtures

```python
import pytest

def test_example(test_database):
    """Test using database fixture"""
    # test_database is a SQLAlchemy session
    pass

def test_with_mock(create_mock_mt5_terminal):
    """Test using mock factory"""
    terminal = create_mock_mt5_terminal()
    # Use mocked terminal
    pass
```

## Path Utilities

All tests use centralized path utilities from `tests/shared/helpers/path_utils.py`:

```python
from tests.shared.helpers.path_utils import setup_api_path, setup_trading_server_path

# In API tests
setup_api_path()

# In Trading Server tests
setup_trading_server_path()
```

## Test Markers

Pytest markers for test categorization:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.stress` - Stress tests
- `@pytest.mark.performance` - Performance tests
- `@pytest.mark.slow` - Slow running tests

Example:

```python
@pytest.mark.integration
def test_database_integration():
    """Integration test with database"""
    pass
```

Run marked tests:

```bash
pytest -m integration tests/
pytest -m "not slow" tests/  # Exclude slow tests
```

## Writing New Tests

### Unit Test Example

```python
"""Unit test for Trading Server component"""
import pytest
from unittest.mock import Mock

from tests.shared.helpers.path_utils import setup_trading_server_path
setup_trading_server_path()

from risk.kill_switch import KillSwitch

def test_kill_switch_activation():
    """Test kill switch activation"""
    kill_switch = KillSwitch()
    # Test implementation
    assert kill_switch.state == KillSwitchState.ACTIVE
```

### Integration Test Example

```python
"""Integration test with database"""
import pytest

from tests.shared.helpers.path_utils import setup_trading_server_path
setup_trading_server_path()

from tests.shared.fixtures.database import test_database

@pytest.mark.integration
def test_experiment_workflow(test_database):
    """Test experiment workflow with real database"""
    # Test implementation using test_database fixture
    pass
```

## Notes

- Tests use mocks to avoid requiring actual database or MT5 connections in unit tests
- Integration tests use testcontainers for PostgreSQL/TimescaleDB
- Some tests may have probabilistic results (e.g., drift detection) due to random data generation
- Always run tests from the project root directory
- Test timeouts are set to 300 seconds (configurable in `pytest.ini`)

## Troubleshooting

### Import Errors

If you see import errors, ensure:
1. You're running from the project root
2. Path utilities are imported correctly
3. Component paths are set up in conftest.py

### Database Connection Issues

For integration tests:
1. Ensure Docker is running (for testcontainers)
2. Check PostgreSQL service is available in CI
3. Verify environment variables are set correctly

### Test Failures

1. Check test logs for detailed error messages
2. Verify all dependencies are installed: `pip install -r tests/requirements-test.txt`
3. Ensure test data fixtures are correct
4. Check for time-sensitive tests that may fail due to timing issues
