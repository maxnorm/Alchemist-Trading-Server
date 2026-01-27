#!/bin/bash
# Airflow Worker Entrypoint Script
# This script handles log directory setup and starts the Airflow Celery worker

echo "=========================================="
echo "Airflow Worker Entrypoint"
echo "=========================================="

# Fix permissions for log directories
echo "Setting up log directories..."

# Create log directories if they don't exist
LOG_DIRS=(
    "/opt/airflow/logs"
)

for dir in "${LOG_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "  Creating directory: $dir"
        mkdir -p "$dir" 2>/dev/null || {
            echo "  ⚠ Could not create $dir - may need to fix permissions on host"
        }
    fi
done

# Check if we can write to the directory
PERMISSION_ERROR=false

if [ -d "/opt/airflow/logs" ]; then
    # Test if we can write to the directory - this is the critical check
    if touch /opt/airflow/logs/.write_test 2>/dev/null; then
        rm -f /opt/airflow/logs/.write_test
        echo "  ✓ Log directory is writable"
    else
        PERMISSION_ERROR=true
        echo "  ✗ ERROR: Cannot write to /opt/airflow/logs"
        echo "  This usually happens when Docker creates the directory as root."
        echo ""
    fi
    
    # Try to make directories world-writable (may fail if created by Docker as root)
    if ! chmod -R 777 /opt/airflow/logs 2>/dev/null; then
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
    echo "   docker compose stop airflow-worker"
    echo ""
    echo "2. Fix permissions on the host:"
    echo "   ./scripts/init-docker-directories.sh"
    echo ""
    echo "   Or manually:"
    echo "   chmod -R 777 ./airflow_logs"
    echo ""
    echo "3. Restart the container:"
    echo "   docker compose start airflow-worker"
    echo ""
    echo "=========================================="
    exit 1
fi

# Wait for database connection
echo "Waiting for database connection..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # Test database connection without triggering Airflow logging setup
    PYTHON_CHECK_OUTPUT=$(python3 <<EOF 2>&1
import os
from sqlalchemy import create_engine, text
import sys
try:
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
    
    echo "  Database not ready (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES), waiting..."
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "✗ Failed to connect to database after $MAX_RETRIES attempts"
    exit 1
fi

echo "=========================================="
echo "Starting Airflow Celery worker..."
echo "=========================================="

exec airflow celery worker
