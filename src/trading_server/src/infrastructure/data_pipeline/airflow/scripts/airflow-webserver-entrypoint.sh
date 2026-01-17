#!/bin/bash
# Airflow Webserver Entrypoint Script
# This script handles database initialization and starts the Airflow webserver

echo "=========================================="
echo "Airflow Webserver Entrypoint"
echo "=========================================="

# Wait for database connection to be ready
echo "Waiting for database connection..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # Try to connect to database using a simple SQL query
    if airflow db check >/dev/null 2>&1 || python3 <<EOF 2>/dev/null
from airflow.configuration import conf
from sqlalchemy import create_engine, text
try:
    conn_str = conf.get('database', 'sql_alchemy_conn')
    engine = create_engine(conn_str, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    exit(0)
except Exception as e:
    exit(1)
EOF
    then
        echo "✓ Database connection established"
        break
    fi
    echo "  Database not ready (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES), waiting..."
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "✗ Failed to connect to database after $MAX_RETRIES attempts"
    exit 1
fi

# Check if Airflow database is initialized by checking for the 'dag' table
echo "Checking if Airflow database is initialized..."
DB_INITIALIZED=false

if python3 <<EOF 2>/dev/null
from airflow.configuration import conf
from sqlalchemy import create_engine, inspect
try:
    conn_str = conf.get('database', 'sql_alchemy_conn')
    engine = create_engine(conn_str, pool_pre_ping=True)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if 'dag' in tables:
        exit(0)
    else:
        exit(1)
except Exception:
    exit(1)
EOF
then
    echo "✓ Airflow database already initialized"
    DB_INITIALIZED=true
else
    echo "⚠ Airflow database not initialized"
fi

# Initialize database if needed
if [ "$DB_INITIALIZED" != "true" ]; then
    echo "Initializing Airflow database..."
    if airflow db init 2>&1; then
        echo "✓ Database initialized successfully"
        
        echo "Creating admin user..."
        airflow users create \
            --username admin \
            --firstname Admin \
            --lastname User \
            --role Admin \
            --email admin@example.com \
            --password admin 2>&1 || echo "⚠ Admin user already exists or creation failed"
    else
        echo "✗ Failed to initialize database"
        exit 1
    fi
fi

# Final verification - ensure database is truly ready by checking for required tables
echo "Verifying Airflow database is ready..."
VERIFY_RETRIES=10
VERIFY_COUNT=0

while [ $VERIFY_COUNT -lt $VERIFY_RETRIES ]; do
    if python3 <<EOF 2>/dev/null
from airflow.configuration import conf
from sqlalchemy import create_engine, inspect
try:
    conn_str = conf.get('database', 'sql_alchemy_conn')
    engine = create_engine(conn_str, pool_pre_ping=True)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    # Check for key Airflow tables
    required_tables = ['dag', 'users', 'connection', 'variable']
    if all(table in tables for table in required_tables):
        exit(0)
    else:
        exit(1)
except Exception:
    exit(1)
EOF
    then
        echo "✓ Airflow database ready (all required tables present)"
        break
    fi
    echo "  Verification failed (attempt $((VERIFY_COUNT + 1))/$VERIFY_RETRIES), retrying..."
    sleep 2
    VERIFY_COUNT=$((VERIFY_COUNT + 1))
done

if [ $VERIFY_COUNT -eq $VERIFY_RETRIES ]; then
    echo "✗ Database verification failed after $VERIFY_RETRIES attempts"
    echo "Attempting to initialize database again..."
    airflow db init
    if [ $? -ne 0 ]; then
        echo "✗ Failed to initialize database"
        exit 1
    fi
fi

echo "=========================================="
echo "Starting Airflow webserver..."
echo "=========================================="

exec airflow webserver
