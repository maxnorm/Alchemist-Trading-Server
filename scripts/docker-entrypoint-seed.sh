#!/bin/bash
# Docker Entrypoint Hook for Historical Data Seeding
# This script is called during container initialization to optionally seed historical data

set -e

echo "========================================" echo "Historical Data Seeding Hook"
echo "========================================"

# Check if seeding is enabled
if [ "${SEED_HISTORICAL_DATA:-false}" = "true" ]; then
    echo "Historical data seeding ENABLED"
    
    # Check if data directory exists
    if [ ! -d "/data/dukascopy" ]; then
        echo "ERROR: Data directory /data/dukascopy not found"
        echo "Make sure to mount the data directory with: -v ./data/dukascopy:/data/dukascopy:ro"
        exit 1
    fi
    
    echo "Data directory found: /data/dukascopy"
    
    # Count Parquet files
    file_count=$(find /data/dukascopy -name "*.parquet" | wc -l)
    echo "Found $file_count Parquet files"
    
    if [ "$file_count" -eq 0 ]; then
        echo "WARNING: No Parquet files found in /data/dukascopy"
        echo "Skipping historical data seeding"
        exit 0
    fi
    
    echo "Starting historical data seeding..."
    echo "This may take several hours for large datasets"
    
    # Run seeding script
    python /app/scripts/seed_historical_data.py \
        --data-dir /data/dukascopy \
        --batch-size 10000 \
        --skip-existing \
        2>&1 | tee /app/logs/seed_historical_data.log
    
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo "✓ Historical data seeding completed successfully"
    else
        echo "✗ Historical data seeding failed with exit code $exit_code"
        echo "Check logs at /app/logs/seed_historical_data.log"
        exit $exit_code
    fi
else
    echo "Historical data seeding DISABLED (set SEED_HISTORICAL_DATA=true to enable)"
fi

echo "========================================"
