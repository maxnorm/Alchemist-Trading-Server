#!/bin/bash
# Restart Dukascopy collection on GCP VPS
# Run this directly on the VPS: bash restart-collection.sh

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Restarting Dukascopy Collection ===${NC}"
echo ""

# Default parameters (5 years back)
YEARS_BACK="${YEARS_BACK:-5}"
END_DATE=$(date +%Y-%m-%d)
START_DATE=$(date -d "$YEARS_BACK years ago" +%Y-%m-%d 2>/dev/null || date -v-${YEARS_BACK}y +%Y-%m-%d 2>/dev/null || echo "2019-01-01")

# Check if script exists
SCRIPT_PATH=""
if [ -f /opt/trading-system/scripts/backfill_dukascopy_data.py ]; then
    SCRIPT_PATH="/opt/trading-system/scripts/backfill_dukascopy_data.py"
    WORK_DIR="/opt/trading-system"
elif [ -f ~/trading-system/scripts/backfill_dukascopy_data.py ]; then
    SCRIPT_PATH="~/trading-system/scripts/backfill_dukascopy_data.py"
    WORK_DIR="~/trading-system"
else
    echo -e "${RED}Error: backfill_dukascopy_data.py not found${NC}"
    echo "Searching for script..."
    FOUND=$(find /opt /home -name "backfill_dukascopy_data.py" 2>/dev/null | head -1)
    if [ -n "$FOUND" ]; then
        SCRIPT_PATH="$FOUND"
        WORK_DIR=$(dirname "$(dirname "$FOUND")")
        echo "Found at: $SCRIPT_PATH"
    else
        echo -e "${RED}Script not found. Please check installation.${NC}"
        exit 1
    fi
fi

# Ensure /data is mounted
if [ ! -d /data ]; then
    echo -e "${YELLOW}Warning: /data directory not found${NC}"
    echo "Checking for data disk..."
    if [ -b /dev/sdb ]; then
        echo "Mounting /dev/sdb to /data..."
        sudo mkdir -p /data
        if ! mountpoint -q /data; then
            sudo mount -o discard,defaults /dev/sdb /data || {
                echo "Mount failed, attempting to format..."
                sudo mkfs.ext4 -F -m 0 -E lazy_itable_init=0,lazy_journal_init=0,discard /dev/sdb
                sudo mount -o discard,defaults /dev/sdb /data
            }
        fi
        sudo chown -R $USER:$USER /data
        sudo chmod -R 755 /data
    else
        echo "Creating /data on root filesystem..."
        sudo mkdir -p /data
        sudo chown -R $USER:$USER /data
        sudo chmod -R 755 /data
    fi
fi

# Ensure /data is writable by current user
sudo chown -R $USER:$USER /data 2>/dev/null || true
sudo chmod -R 755 /data 2>/dev/null || true

# Create directories (cache and temp on /data to avoid filling root disk)
mkdir -p /data/dukascopy /data/logs /data/tmp /data/.dukascopy-cache

# Check if screen session already exists
if screen -list | grep -q "dukascopy-collection"; then
    echo -e "${YELLOW}Warning: Screen session 'dukascopy-collection' already exists${NC}"
    read -p "Kill existing session and restart? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        screen -S dukascopy-collection -X quit || true
        sleep 2
    else
        echo "Aborted. To attach to existing session: screen -r dukascopy-collection"
        exit 0
    fi
fi

# Check for progress file to determine if we should resume
RESUME_FLAG=""
if [ -f /data/.dukascopy_progress.json ] || [ -f "$WORK_DIR/data/.dukascopy_progress.json" ]; then
    echo -e "${GREEN}Progress file found - will resume from checkpoint${NC}"
    RESUME_FLAG="--resume"
else
    echo "No progress file found - starting fresh collection"
fi

# Show parameters
echo ""
echo "Collection parameters:"
echo "  Start date: $START_DATE"
echo "  End date: $END_DATE"
echo "  Output: /data/dukascopy"
echo "  Resume: $([ -n "$RESUME_FLAG" ] && echo "Yes" || echo "No")"
echo "  Script: $SCRIPT_PATH"
echo ""

read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 0
fi

# Change to work directory
cd "$WORK_DIR"

# Create log file name
LOG_FILE="/data/logs/collection_$(date +%Y%m%d_%H%M%S).log"

# Start collection in screen session
echo ""
echo -e "${GREEN}Starting collection in screen session...${NC}"
echo "  Session name: dukascopy-collection"
echo "  Log file: $LOG_FILE"
echo ""

screen -dmS dukascopy-collection bash -c "
export TMPDIR=/data/tmp && \
cd '$WORK_DIR' && \
exec python3 '$SCRIPT_PATH' \
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
    $RESUME_FLAG \
    2>&1 | tee '$LOG_FILE'
"

# Wait a moment and verify
sleep 2
if screen -list | grep -q "dukascopy-collection"; then
    echo -e "${GREEN}✓ Collection started successfully!${NC}"
    echo ""
    echo "To view the collection:"
    echo "  screen -r dukascopy-collection"
    echo ""
    echo "To detach from screen:"
    echo "  Press Ctrl+A, then D"
    echo ""
    echo "To view logs:"
    echo "  tail -f $LOG_FILE"
    echo "  tail -f /opt/trading-system/logs/dukascopy_backfill.log"
else
    echo -e "${RED}✗ Failed to create screen session${NC}"
    echo "Check for errors above"
    exit 1
fi
