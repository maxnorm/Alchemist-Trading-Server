#!/bin/sh
set -e

# Wait for upstream services to be available via DNS
# Health checks in docker-compose ensure services are ready, but we need DNS resolution
echo "Waiting for dashboard service DNS resolution..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if getent hosts dashboard > /dev/null 2>&1; then
        echo "Dashboard DNS resolved"
        break
    fi
    attempt=$((attempt + 1))
    echo "Attempt $attempt/$max_attempts: Dashboard DNS not yet available, waiting..."
    sleep 1
done

if [ $attempt -eq $max_attempts ]; then
    echo "WARNING: Dashboard DNS resolution timeout, but continuing anyway..."
fi

echo "Waiting for api service DNS resolution..."
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if getent hosts api > /dev/null 2>&1; then
        echo "API DNS resolved"
        break
    fi
    attempt=$((attempt + 1))
    echo "Attempt $attempt/$max_attempts: API DNS not yet available, waiting..."
    sleep 1
done

if [ $attempt -eq $max_attempts ]; then
    echo "WARNING: API DNS resolution timeout, but continuing anyway..."
fi

echo "Starting nginx..."

# Execute the original nginx entrypoint
exec /docker-entrypoint.sh "$@"
