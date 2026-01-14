# Developer Guide

## Adding Data Sources

### Step 1: Create Provider Class

Create a new file in `src/trading_server/src/data_providers/`:

```python
from data_providers.base_provider import DataProvider, Feature

class MyDataProvider(DataProvider):
    """Provider for my custom data source"""
    
    def __init__(self, config):
        self.config = config
        self.features = [
            Feature(
                name="my_feature",
                data_type=float,
                source="my_source",
                description="My custom feature",
                category="custom"
            )
        ]
    
    def get_features(self) -> List[Feature]:
        return self.features
    
    def get_current_data(self) -> Dict[str, Any]:
        # Fetch and return current data
        return {
            "my_feature": 123.45
        }
    
    def subscribe(self, callback: Callable):
        # Subscribe to data updates
        pass
```

### Step 2: Register Provider

In `src/trading_server/src/server.py`, register your provider:

```python
from data_providers.my_provider import MyDataProvider

# In Server.__init__()
my_provider = MyDataProvider(config={})
self.provider_registry.register_provider("my_source", my_provider)
```

### Step 3: Restart Server

After restarting, your features will automatically appear in the Feature Catalog.

## Extending Features

### Adding New Indicators

1. Add calculation function to `src/trading_server/src/features/technical_indicators.py`
2. Add feature declaration to `IndicatorProvider.get_features()`
3. Restart server

Example:
```python
def calculate_my_indicator(prices: List[float], period: int = 14) -> float:
    # Your calculation logic
    return value

# In IndicatorProvider
Feature(
    name=f"my_indicator_{period}_{symbol}",
    data_type=float,
    source="indicator",
    description=f"My indicator (period={period})",
    category="technical"
)
```

## Testing

### Running Tests

```bash
# All tests
pytest tests/

# Unit tests only
pytest tests/unit/

# Integration tests
pytest tests/integration/

# API tests
pytest tests/api/

# With coverage
pytest tests/ --cov=src/trading_server/src --cov-report=html
```

### Writing Tests

#### Unit Test Example
```python
import pytest
from my_module import MyClass

def test_my_function():
    result = MyClass().my_function()
    assert result == expected_value
```

#### Integration Test Example
```python
import pytest
from unittest.mock import Mock

def test_integration_flow():
    mock_db = Mock()
    component = MyComponent(mock_db)
    result = component.do_something()
    assert result is not None
```

## Local Development Setup

### Seeding Clerk User Account

For local development, you can automatically create a Clerk user account with default credentials using the seed script:

```bash
# With defaults (dev@localhost / dev123)
python scripts/seed_clerk_user.py

# With custom credentials via environment variables
CLERK_SEED_EMAIL=admin@localhost CLERK_SEED_PASSWORD=admin123 python scripts/seed_clerk_user.py

# With custom roles
CLERK_SEED_ROLES=admin,user python scripts/seed_clerk_user.py
```

**Environment Variables:**
- `CLERK_SEED_EMAIL`: Email address for the seed user (default: `dev@localhost`)
- `CLERK_SEED_PASSWORD`: Password for the seed user (default: `dev123`)
- `CLERK_SEED_ROLES`: Comma-separated list of roles (default: `admin,user`)

**Requirements:**
- `CLERK_SECRET_KEY` must be set in your environment or `.env` file
- The script is idempotent - safe to run multiple times
- If the user already exists, it will update roles if needed

**Using Docker Compose:**

You can also run the seed script via Docker Compose. Uncomment the `clerk-seed` service in `docker-compose.yml` and run:

```bash
docker-compose up clerk-seed
```

## Database Schema

### Key Tables

- **features**: Feature catalog
- **experiments**: Experiment configurations
- **optuna_studies**: Optuna hyperparameter studies
- **optuna_trials**: Optuna trial results
- **model_trades**: Trade history
- **equity_curve**: Equity snapshots
- **performance_metrics**: Calculated metrics

### Running Migrations

```bash
# Run all migrations
# Use the migration script instead
python scripts/run-migrations.py

# Or connect to PostgreSQL directly
psql -h localhost -U forex_user -d db_forex -f src/database/scripts/06_features.sql
psql -h localhost -U forex_user -d db_forex -f src/database/scripts/07_experiments.sql
# ... etc
```

## Architecture Overview

### Component Interactions

```
Server (server.py)
├── DataProviderRegistry
│   └── Discovers features from providers
├── FeatureCatalog
│   └── Stores features in database
├── ExperimentBuilder
│   └── Creates and validates experiments
├── ExperimentRunner
│   └── Executes experiments
└── TradingController
    ├── KillSwitch (safety)
    ├── CircuitBreaker (safety)
    └── OMS (order management)
```

### Data Flow

1. **Feature Discovery**: Providers → Registry → Catalog → Database
2. **Experiment Creation**: Builder → Validation → Database
3. **Experiment Execution**: Runner → Agent → Environment → Training Loop
4. **Trading**: Training Loop → Action Executor → OMS → MT5
5. **Performance**: Trade Logger → Metrics Calculator → API → Dashboard

## Code Style

### Python
- Follow PEP 8
- Use type hints
- Document with docstrings
- Maximum line length: 120 characters

### Formatting
```bash
black src/
flake8 src/
mypy src/
```

## API Development

### Adding New Endpoint

1. Create router in `src/api/src/routers/`
2. Create schema in `src/api/src/schemas/`
3. Create service in `src/api/src/services/`
4. Add to main app in `src/api/src/main.py`
5. Write tests in `tests/api/`

### Example Endpoint

```python
# routers/my_endpoint.py
from fastapi import APIRouter, Depends
from schemas.my_schema import MyRequest, MyResponse
from services.my_service import my_function

router = APIRouter()

@router.post("/my-endpoint", response_model=MyResponse)
async def my_endpoint(request: MyRequest):
    result = my_function(request.data)
    return MyResponse(result=result)
```

## Debugging

### Logging
- Use structured logging
- Log levels: DEBUG, INFO, WARNING, ERROR
- Check logs in `logs/` directory

### Common Issues
- **Database connection errors**: Check `.env` configuration
- **MT5 connection errors**: Verify MT5 terminal is running
- **Feature not found**: Check provider registration
- **Experiment won't start**: Check validation errors in logs
