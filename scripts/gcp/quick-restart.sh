#!/bin/bash
# Quick restart script - run this directly on the VPS
# This will resume from where it left off

set -e

cd /opt/trading-system

# Calculate 5 years back from today
END_DATE=$(date +%Y-%m-%d)
START_DATE=$(date -d "5 years ago" +%Y-%m-%d 2>/dev/null || date -v-5y +%Y-%m-%d 2>/dev/null || echo "2020-01-01")

echo "=== Restarting Dukascopy Collection ==="
echo "Date range: $START_DATE to $END_DATE"
echo "This will resume from progress file and skip already completed work"
echo ""

# Ensure /data is writable and create dirs for cache/temp on /data
sudo chown -R $USER:$USER /data 2>/dev/null || true
LOG_FILE="/data/logs/collection_$(date +%Y%m%d_%H%M%S).log"
mkdir -p /data/logs /data/tmp /data/.dukascopy-cache

# Kill any existing screen session
if screen -list | grep -q "dukascopy-collection"; then
    echo "Killing existing screen session..."
    screen -S dukascopy-collection -X quit || true
    sleep 2
fi

# Start collection in screen
echo "Starting collection in screen session 'dukascopy-collection'..."
screen -dmS dukascopy-collection bash -c "
export TMPDIR=/data/tmp && \
cd /opt/trading-system && \
exec python3 scripts/backfill_dukascopy_data.py \
    --start-date $START_DATE \
    --end-date $END_DATE \
    --output-dir /data/dukascopy \
    --cache-dir /data/.dukascopy-cache \
    --temp-dir /data/tmp \
    --progress-file /data/.dukascopy_progress.json \
    --batch-size 3 \
    --pause-ms 5000 \
    --compression snappy \
    --verbose \
    --resume \
    2>&1 | tee '$LOG_FILE'
"

sleep 2

if screen -list | grep -q "dukascopy-collection"; then
    echo "✓ Collection started successfully!"
    echo ""
    echo "To view: screen -r dukascopy-collection"
    echo "To detach: Ctrl+A, then D"
    echo "Log file: $LOG_FILE"
    echo "Python log: /opt/trading-system/logs/dukascopy_backfill.log"
else
    echo "✗ Failed to start collection"
    exit 1
fi
