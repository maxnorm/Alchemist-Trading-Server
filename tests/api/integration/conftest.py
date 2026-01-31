"""
Pytest fixtures for API integration tests with real database
"""
import os
import sys
import pytest
import psycopg2
from pathlib import Path
from typing import Generator
from urllib.parse import urlparse
from fastapi.testclient import TestClient
from fastapi import Request
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Set required environment variables before importing app
os.environ.setdefault("MLFLOW_TRACKING_URI", "file:///tmp/mlflow_test")

from tests.shared.helpers.path_utils import setup_api_path
from tests.shared.fixtures.database import postgres_container, db_connection_string

# Setup API path
setup_api_path()

# Mock infrastructure modules before importing app (same as unit tests)
import types
from unittest.mock import MagicMock

# Create mock AlertConsumer class
class MockAlertConsumer:
    def __init__(self, *args, **kwargs):
        pass
    async def start(self):
        pass
    async def stop(self):
        pass

# Create mock CredentialManager class
class MockCredentialManager:
    def __init__(self, *args, **kwargs):
        pass

# Create mock ExperimentPublisher
class MockExperimentPublisher:
    @staticmethod
    def get_instance():
        return MockExperimentPublisher()
    def publish_experiment_start(self, experiment_id):
        return True

# Create infrastructure modules
alert_consumer_module = types.ModuleType('infrastructure.messaging.alert_consumer')
alert_consumer_module.AlertConsumer = MockAlertConsumer

experiment_publisher_module = types.ModuleType('infrastructure.messaging.experiment_publisher')
experiment_publisher_module.ExperimentPublisher = MockExperimentPublisher

messaging_module = types.ModuleType('infrastructure.messaging')
messaging_module.alert_consumer = alert_consumer_module
messaging_module.AlertConsumer = MockAlertConsumer
messaging_module.experiment_publisher = experiment_publisher_module
messaging_module.ExperimentPublisher = MockExperimentPublisher

credential_manager_module = types.ModuleType('infrastructure.security.credential_manager')
credential_manager_module.CredentialManager = MockCredentialManager

security_module = types.ModuleType('infrastructure.security')
security_module.credential_manager = credential_manager_module
security_module.CredentialManager = MockCredentialManager

infrastructure_module = types.ModuleType('infrastructure')
infrastructure_module.messaging = messaging_module
infrastructure_module.security = security_module

# Add to sys.modules
sys.modules['infrastructure'] = infrastructure_module
sys.modules['infrastructure.messaging'] = messaging_module
sys.modules['infrastructure.messaging.alert_consumer'] = alert_consumer_module
sys.modules['infrastructure.messaging.experiment_publisher'] = experiment_publisher_module
sys.modules['infrastructure.security'] = security_module
sys.modules['infrastructure.security.credential_manager'] = credential_manager_module

# For integration tests, we need REAL models, not mocks
# Remove any mocked models that might have been set up by tests/api/conftest.py
# and import the real models before importing the app
if 'models.mt5_accounts' in sys.modules:
    # Remove the mocked module to allow real models to be imported
    del sys.modules['models.mt5_accounts']
if 'models' in sys.modules:
    # Remove the mocked models module
    if hasattr(sys.modules['models'], 'mt5_accounts'):
        delattr(sys.modules['models'], 'mt5_accounts')
    # Also remove from sys.modules if it's a mock
    if isinstance(sys.modules['models'], MagicMock):
        del sys.modules['models']

# Import app after mocks are set up
# The real models will be imported when services import them
from main import app
from dependencies import get_db


def get_migration_scripts() -> list[tuple[int, Path]]:
    """Get all migration scripts in order"""
    project_root = Path(__file__).parent.parent.parent.parent
    scripts_dir = project_root / 'src' / 'backend' / 'database' / 'scripts'
    
    if not scripts_dir.exists():
        # Try alternative path
        scripts_dir = project_root / 'src' / 'database' / 'scripts'
    
    migrations = []
    
    for script_file in sorted(scripts_dir.glob('*.sql')):
        # Extract number from filename (e.g., "06_safety_infrastructure.sql" -> 6)
        try:
            number = int(script_file.stem.split('_')[0])
            migrations.append((number, script_file))
        except (ValueError, IndexError):
            # Skip files that don't start with a number
            continue
    
    return sorted(migrations, key=lambda x: x[0])


def run_migration(conn, script_path: Path) -> bool:
    """Run a single migration script"""
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        cursor = conn.cursor()
        
        # Execute the SQL script
        try:
            cursor.execute(sql_content)
            conn.commit()
        except psycopg2.ProgrammingError:
            # Some statements might need to be executed separately
            conn.rollback()
            # Split by semicolon but preserve DO blocks and function definitions
            statements = []
            current_statement = ""
            in_function = False
            in_do_block = False
            
            for line in sql_content.split('\n'):
                line_stripped = line.strip()
                if line_stripped.upper().startswith('DO $$'):
                    in_do_block = True
                if line_stripped.endswith('$$;') or line_stripped.endswith('$$ LANGUAGE'):
                    in_do_block = False
                if line_stripped.upper().startswith('CREATE OR REPLACE FUNCTION'):
                    in_function = True
                if in_function and line_stripped.endswith('$$ LANGUAGE'):
                    in_function = False
                
                current_statement += line + '\n'
                
                if not in_function and not in_do_block and line_stripped.endswith(';'):
                    if current_statement.strip():
                        statements.append(current_statement.strip())
                    current_statement = ""
            
            if current_statement.strip():
                statements.append(current_statement.strip())
            
            for statement in statements:
                if statement and not statement.startswith('--'):
                    cursor.execute(statement)
            
            conn.commit()
        
        cursor.close()
        return True
        
    except psycopg2.Error as e:
        conn.rollback()
        raise RuntimeError(f"Error running migration {script_path.name}: {e}")
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"Unexpected error running migration {script_path.name}: {e}")


def run_all_migrations(connection_string: str) -> None:
    """Run all database migrations"""
    # Parse connection string
    # testcontainers returns postgresql://user:password@host:port/dbname
    parsed = urlparse(connection_string)
    
    # Connect using psycopg2
    conn = psycopg2.connect(
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        user=parsed.username or "test",
        password=parsed.password or "test",
        database=parsed.path.lstrip('/') if parsed.path else "test"
    )
    
    try:
        migrations = get_migration_scripts()
        
        if not migrations:
            raise RuntimeError("No migration scripts found")
        
        for number, script_path in migrations:
            run_migration(conn, script_path)
    finally:
        conn.close()


@pytest.fixture(scope="function")
def migrated_database(postgres_container, db_connection_string):
    """Database with all migrations applied"""
    # Run migrations
    run_all_migrations(db_connection_string)
    
    yield db_connection_string


def get_real_db_session(connection_string: str) -> Generator[Session, None, None]:
    """Get a real database session for testing"""
    # Parse connection string and convert to SQLAlchemy format
    parsed = urlparse(connection_string)
    sqlalchemy_url = (
        f"postgresql+psycopg2://{parsed.username}:{parsed.password}@"
        f"{parsed.hostname}:{parsed.port or 5432}{parsed.path}"
    )
    
    engine = create_engine(sqlalchemy_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


async def override_get_current_user(request: Request):
    """Override authentication dependency for testing"""
    user_data = {"id": "user_123", "email": "test@example.com"}
    # Set request state for access in route handlers
    request.state.user_id = "user_123"
    request.state.roles = []  # Regular user, not admin
    return user_data


@pytest.fixture
def api_client_integration(migrated_database):
    """TestClient with real database connection"""
    # Set environment variables for database connection
    parsed = urlparse(migrated_database)
    os.environ["DB_HOST"] = parsed.hostname or "localhost"
    os.environ["DB_PORT"] = str(parsed.port or 5432)
    os.environ["DB_USER"] = parsed.username or "test"
    os.environ["DB_PASSWORD"] = parsed.password or "test"
    os.environ["DB_NAME"] = parsed.path.lstrip('/') or "test"
    
    # Override get_db to use real database
    def override_get_db_integration() -> Generator[Session, None, None]:
        yield from get_real_db_session(migrated_database)
    
    # Override dependencies
    app.dependency_overrides[get_db] = override_get_db_integration
    
    from middleware.auth import get_current_user
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    # Mock database initialization to prevent lifespan from trying to connect
    from unittest.mock import patch
    with patch('services.database.init_db'), patch('services.database.close_db'):
        client = TestClient(app)
        yield client
    
    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def db_session(migrated_database):
    """Direct database session for test data setup"""
    yield from get_real_db_session(migrated_database)


# Helper functions for test data setup
def create_test_experiment_via_sql(db: Session, **kwargs) -> int:
    """Create experiment directly in database (for test setup)"""
    import json
    
    name = kwargs.get('name', 'test_experiment')
    description = kwargs.get('description', 'Test experiment')
    features = kwargs.get('features', ['price_bid_EURUSD'])
    currency_pairs = kwargs.get('currency_pairs', ['EURUSD'])
    training_mode = kwargs.get('training_mode', 'historical')
    hyperparameters = kwargs.get('hyperparameters', {'learning_rate': 0.001})
    status = kwargs.get('status', 'created')
    
    query = text("""
        INSERT INTO experiments (name, description, features, currency_pairs, training_mode, hyperparameters, status)
        VALUES (:name, :description, :features, :currency_pairs, :training_mode, :hyperparameters, :status)
        RETURNING id
    """)
    
    result = db.execute(query, {
        "name": name,
        "description": description,
        "features": json.dumps(features),
        "currency_pairs": json.dumps(currency_pairs),
        "training_mode": training_mode,
        "hyperparameters": json.dumps(hyperparameters),
        "status": status
    })
    db.commit()
    
    row = result.fetchone()
    return row[0] if row else None


def create_test_model_via_sql(db: Session, experiment_id: int = None, **kwargs) -> int:
    """Create model directly in database (models are created by trading server)"""
    import json
    
    version = kwargs.get('version', '1.0.0')
    stage = kwargs.get('stage', 'staging')
    features = kwargs.get('features', ['price_bid_EURUSD'])
    hyperparameters = kwargs.get('hyperparameters', {'learning_rate': 0.001})
    metrics = kwargs.get('metrics', {})
    
    query = text("""
        INSERT INTO models (version, experiment_id, stage, features, hyperparameters, metrics)
        VALUES (:version, :experiment_id, :stage, :features, :hyperparameters, :metrics)
        RETURNING id
    """)
    
    result = db.execute(query, {
        "version": version,
        "experiment_id": experiment_id,
        "stage": stage,
        "features": json.dumps(features),
        "hyperparameters": json.dumps(hyperparameters),
        "metrics": json.dumps(metrics) if metrics else None
    })
    db.commit()
    
    row = result.fetchone()
    return row[0] if row else None


def create_test_account_via_sql(db: Session, user_id: str = "user_123", **kwargs) -> int:
    """Create MT5 account directly in database"""
    account_login = kwargs.get('account_login', 12345678)
    account_type = kwargs.get('account_type', 'demo')
    broker_name = kwargs.get('broker_name', 'Test Broker')
    broker_server = kwargs.get('broker_server', 'Test-Server')
    account_currency = kwargs.get('account_currency', 'USD')
    account_leverage = kwargs.get('account_leverage', 100)
    account_name = kwargs.get('account_name', 'Test Account')
    
    query = text("""
        INSERT INTO mt5_accounts 
        (account_login, account_type, broker_name, broker_server, account_currency, 
         account_leverage, account_name, user_id, created_by, is_active)
        VALUES (:account_login, :account_type, :broker_name, :broker_server, :account_currency,
                :account_leverage, :account_name, :user_id, :created_by, :is_active)
        RETURNING id
    """)
    
    result = db.execute(query, {
        "account_login": account_login,
        "account_type": account_type,
        "broker_name": broker_name,
        "broker_server": broker_server,
        "account_currency": account_currency,
        "account_leverage": account_leverage,
        "account_name": account_name,
        "user_id": user_id,
        "created_by": user_id,
        "is_active": True
    })
    db.commit()
    
    row = result.fetchone()
    return row[0] if row else None


def create_test_paper_session_via_sql(db: Session, model_id: int, **kwargs) -> int:
    """Create paper trading session directly in database"""
    start_balance = kwargs.get('start_balance', 10000.0)
    status = kwargs.get('status', 'running')
    
    query = text("""
        INSERT INTO paper_trading_sessions
        (model_id, status, start_balance, current_balance, started_at)
        VALUES (:model_id, :status, :start_balance, :start_balance, NOW())
        RETURNING id
    """)
    
    result = db.execute(query, {
        "model_id": model_id,
        "status": status,
        "start_balance": start_balance
    })
    db.commit()
    
    row = result.fetchone()
    return row[0] if row else None


# Assertion helpers
def assert_experiment_in_db(db: Session, experiment_id: int, **expected):
    """Verify experiment record matches expected values"""
    result = db.execute(
        text("SELECT * FROM experiments WHERE id = :id"),
        {"id": experiment_id}
    )
    row = result.fetchone()
    
    assert row is not None, f"Experiment {experiment_id} not found in database"
    
    row_dict = dict(row._mapping)
    
    for key, value in expected.items():
        if key in ['features', 'currency_pairs', 'hyperparameters']:
            import json
            # Parse JSONB fields for comparison
            if isinstance(row_dict[key], str):
                row_dict[key] = json.loads(row_dict[key])
        assert row_dict[key] == value, f"Expected {key}={value}, got {row_dict[key]}"


def assert_model_in_db(db: Session, model_id: int, **expected):
    """Verify model record matches expected values"""
    result = db.execute(
        text("SELECT * FROM models WHERE id = :id"),
        {"id": model_id}
    )
    row = result.fetchone()
    
    assert row is not None, f"Model {model_id} not found in database"
    
    row_dict = dict(row._mapping)
    
    for key, value in expected.items():
        if key in ['features', 'hyperparameters', 'metrics', 'paper_trading_results']:
            import json
            # Parse JSONB fields for comparison
            if isinstance(row_dict[key], str):
                row_dict[key] = json.loads(row_dict[key])
        assert row_dict[key] == value, f"Expected {key}={value}, got {row_dict[key]}"


def assert_foreign_key_cascade(db: Session, table: str, fk_field: str, 
                                parent_id: int, expected_value):
    """Verify FK cascade behavior"""
    result = db.execute(
        text(f"SELECT {fk_field} FROM {table} WHERE {fk_field} = :parent_id"),
        {"parent_id": parent_id}
    )
    rows = result.fetchall()
    
    for row in rows:
        value = row[0] if isinstance(row, tuple) else row._mapping[fk_field]
        assert value == expected_value, (
            f"Expected {fk_field}={expected_value} after cascade, got {value}"
        )
