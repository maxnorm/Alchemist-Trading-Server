# Running Tests

This directory contains unit tests for the trading system.

## Prerequisites

Install test dependencies:
```bash
pip install pytest pytest-cov
```

Or add to `requirements.txt`:
```
pytest>=7.0.0
pytest-cov>=4.0.0
```

## Running Tests

### Option 1: Using pytest (Recommended)

Run all tests:
```bash
# From project root
pytest tests/

# Or with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_data_validation.py

# Run specific test class
pytest tests/test_data_validation.py::TestDataValidation

# Run specific test method
pytest tests/test_data_validation.py::TestDataValidation::test_validate_tick_valid
```

### Option 2: Using unittest (Python standard library)

Run all tests:
```bash
# From project root
python -m unittest discover tests

# Or with verbose output
python -m unittest discover tests -v

# Run specific test file
python -m unittest tests.test_data_validation

# Run specific test class
python -m unittest tests.test_data_validation.TestDataValidation

# Run specific test method
python -m unittest tests.test_data_validation.TestDataValidation.test_validate_tick_valid
```

### Option 3: Direct execution

Run a test file directly:
```bash
python tests/test_data_validation.py
```

## Test Coverage

Generate coverage report with pytest:
```bash
pytest tests/ --cov=src/mt5-python_server/src --cov-report=html --cov-report=term
```

This will:
- Run all tests
- Generate coverage report in terminal
- Create HTML coverage report in `htmlcov/` directory

## Test Structure

- `test_data_validation.py` - Tests for tick data validation
- `test_risk_management.py` - Tests for risk management calculations
- `test_feature_engineering.py` - Tests for feature engineering and technical indicators
- `test_feature_drift_detector.py` - Tests for feature drift detection

## Notes

- Tests use mocks to avoid requiring actual database or MT5 connections
- Some tests may have probabilistic results (e.g., drift detection) due to random data generation
- Make sure you're in the project root directory when running tests
