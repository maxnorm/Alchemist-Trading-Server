#!/bin/bash
# Airflow Webserver Entrypoint Script
# This script handles database initialization and starts the Airflow webserver

echo "=========================================="
echo "Airflow Webserver Entrypoint"
echo "=========================================="

# Fix permissions for log directories
echo "Setting up log directories..."

# Create log directories if they don't exist
LOG_DIRS=(
    "/opt/airflow/logs"
    "/opt/airflow/logs/scheduler"
    "/opt/airflow/logs/webserver"
    "/opt/airflow/logs/dag_processor_manager"
)

for dir in "${LOG_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "  Creating directory: $dir"
        mkdir -p "$dir" 2>/dev/null || {
            echo "  ⚠ Could not create $dir - may need to fix permissions on host"
        }
    fi
done

# Try to make directories writable (works if we have permission)
# For bind mounts, this may fail if Docker created the directory as root
PERMISSION_ERROR=false

if [ -d "/opt/airflow/logs" ]; then
    # Test if we can write to the directory - this is the critical check
    if touch /opt/airflow/logs/.write_test 2>/dev/null; then
        rm -f /opt/airflow/logs/.write_test
        echo "  ✓ Log directory is writable"
        # Directory is writable, so we're good - chmod failure is not critical
    else
        PERMISSION_ERROR=true
        echo "  ✗ ERROR: Cannot write to /opt/airflow/logs"
        echo "  This usually happens when Docker creates the directory as root."
        echo ""
    fi
    
    # Try to make directories world-writable (may fail if created by Docker as root)
    # This is just a best-effort attempt - failure is only a problem if we can't write
    if ! chmod -R 777 /opt/airflow/logs 2>/dev/null; then
        # Only treat as error if we also can't write
        if [ "$PERMISSION_ERROR" != "true" ]; then
            echo "  ⚠ Could not change permissions from inside container (directory is writable, so this is OK)"
        else
            echo "  ✗ Could not change permissions from inside container"
            echo "  Directory was likely created by Docker as root."
        fi
    fi
fi

# Only exit if we actually can't write (not just if chmod failed)
if [ "$PERMISSION_ERROR" = "true" ]; then
    echo ""
    echo "=========================================="
    echo "PERMISSION ERROR - ACTION REQUIRED"
    echo "=========================================="
    echo ""
    echo "The Airflow log directory has incorrect permissions."
    echo "This must be fixed on the HOST before the container can start."
    echo ""
    echo "SOLUTION:"
    echo ""
    echo "1. Stop the container:"
    echo "   docker compose stop airflow-webserver"
    echo ""
    echo "2. Fix permissions on the host:"
    echo "   ./scripts/fix-airflow-permissions.sh"
    echo ""
    echo "   Or manually:"
    echo "   mkdir -p ./airflow_logs ./airflow_plugins"
    echo "   chmod -R 777 ./airflow_logs ./airflow_plugins"
    echo ""
    echo "3. Restart the container:"
    echo "   docker compose start airflow-webserver"
    echo ""
    echo "=========================================="
    exit 1
fi

# Verify environment variables are set
echo "Checking environment variables..."
if [ -z "$AIRFLOW__DATABASE__SQL_ALCHEMY_CONN" ]; then
    echo "✗ AIRFLOW__DATABASE__SQL_ALCHEMY_CONN is not set"
    echo "  This should be set in docker-compose.yml environment section"
    exit 1
fi

# Wait for database connection to be ready
echo "Waiting for database connection..."

# Show connection string (without password) for debugging
echo "Connection details:"
# Read connection string directly from environment to avoid Airflow config initialization
CONN_STR="${AIRFLOW__DATABASE__SQL_ALCHEMY_CONN}"

if [ -n "$CONN_STR" ]; then
    # Extract connection details using Python (without importing Airflow)
    CONN_INFO=$(python3 <<EOF 2>/dev/null
import re
import os
conn_str = os.environ.get('AIRFLOW__DATABASE__SQL_ALCHEMY_CONN', '')
if conn_str:
    # Extract host and port
    match = re.search(r'@([^:]+):(\d+)/(.+)', conn_str)
    if match:
        host = match.group(1)
        port = match.group(2)
        db = match.group(3)
        print(f"  Host: {host}")
        print(f"  Port: {port}")
        print(f"  Database: {db}")
    # Mask password
    if ':' in conn_str.split('@')[0]:
        parts = conn_str.split('@')
        user_pass = parts[0].split('://')[1] if '://' in parts[0] else parts[0]
        if ':' in user_pass:
            user = user_pass.split(':')[0]
            masked = f"{conn_str.split('://')[0]}://{user}:***@{'@'.join(parts[1:])}"
            print(f"  Connection: {masked}")
    else:
        print(f"  {conn_str}")
else:
    print("  No connection string found in environment")
EOF
)
    echo "$CONN_INFO"
    
    # Extract host and port for network check
    DB_HOST=$(echo "$CONN_INFO" | grep "Host:" | awk '{print $2}' || echo "")
    DB_PORT=$(echo "$CONN_INFO" | grep "Port:" | awk '{print $2}' || echo "5432")
else
    echo "  ⚠ Connection string not found"
    DB_HOST=""
    DB_PORT="5432"
fi

if [ -n "$DB_HOST" ]; then
    echo "Checking network connectivity to $DB_HOST:$DB_PORT..."
    if command -v nc >/dev/null 2>&1; then
        if nc -z -w 2 "$DB_HOST" "${DB_PORT:-5432}" 2>/dev/null; then
            echo "✓ Network connectivity to database host confirmed"
        else
            echo "⚠ Cannot reach database host $DB_HOST:$DB_PORT via network"
            echo "  This might indicate:"
            echo "    - Database container is not running"
            echo "    - Network configuration issue"
            echo "    - DB_HOST should be 'postgres' (the service name in docker-compose)"
        fi
    fi
fi

MAX_RETRIES=30
RETRY_COUNT=0
LAST_ERROR=""

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # Try Python-based connection check (without Airflow config to avoid logging setup)
    # This reads directly from environment variable to avoid permission issues
    PYTHON_CHECK_OUTPUT=$(python3 <<EOF 2>&1
import os
from sqlalchemy import create_engine, text
import sys
try:
    # Read connection string directly from environment (not from Airflow config)
    conn_str = os.environ.get('AIRFLOW__DATABASE__SQL_ALCHEMY_CONN')
    if not conn_str:
        print("Connection string not found in environment", file=sys.stderr)
        sys.exit(1)
    
    engine = create_engine(conn_str, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        result.fetchone()
    sys.exit(0)
except Exception as e:
    print(f"Connection error: {e}", file=sys.stderr)
    sys.exit(1)
EOF
)
    PYTHON_CHECK_EXIT=$?
    
    if [ $PYTHON_CHECK_EXIT -eq 0 ]; then
        echo "✓ Database connection established"
        break
    fi
    
    # Store the last error for final reporting
    if [ -n "$PYTHON_CHECK_OUTPUT" ]; then
        LAST_ERROR="$PYTHON_CHECK_OUTPUT"
    fi
    
    # Also try airflow db check (may fail due to logging permissions, but worth trying)
    DB_CHECK_OUTPUT=$(airflow db check 2>&1)
    DB_CHECK_EXIT=$?
    
    if [ $DB_CHECK_EXIT -eq 0 ]; then
        echo "✓ Database connection established"
        break
    fi
    
    # Update error if airflow check provided more details
    if [ -n "$DB_CHECK_OUTPUT" ] && [ -z "$LAST_ERROR" ]; then
        LAST_ERROR="$DB_CHECK_OUTPUT"
    fi
    
    echo "  Database not ready (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES), waiting..."
    
    # Show error details every 5 attempts
    if [ $((RETRY_COUNT % 5)) -eq 4 ] && [ -n "$LAST_ERROR" ]; then
        echo "  Last error: ${LAST_ERROR:0:200}"
    fi
    
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "✗ Failed to connect to database after $MAX_RETRIES attempts"
    if [ -n "$LAST_ERROR" ]; then
        echo "  Last error details:"
        echo "$LAST_ERROR" | head -20 | sed 's/^/    /'
    fi
    echo ""
    echo "Troubleshooting steps:"
    
    # Check if error is related to permissions
    if echo "$LAST_ERROR" | grep -q "Permission denied\|PermissionError"; then
        echo "  ⚠ PERMISSION ERROR DETECTED"
        echo ""
        echo "  Fix log directory permissions on the host:"
        echo "    mkdir -p ./airflow_logs"
        echo "    chmod -R 777 ./airflow_logs"
        echo ""
        echo "  Or set proper ownership (Airflow uses UID 50000):"
        echo "    sudo chown -R 50000:50000 ./airflow_logs"
        echo ""
    fi
    
    echo "  1. Verify DB_HOST environment variable is set to 'postgres'"
    echo "  2. Check that postgres container is running: docker compose ps postgres"
    echo "  3. Check postgres logs: docker compose logs postgres"
    echo "  4. Verify database credentials in .env file"
    echo "  5. Check log directory permissions: ls -la ./airflow_logs"
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
