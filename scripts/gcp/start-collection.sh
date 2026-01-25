#!/bin/bash
# Start data collection on GCP VM
# Usage: ./start-collection.sh [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

VM_NAME="${VM_NAME:-dukascopy-collector}"
ZONE="${ZONE:-us-central1-a}"
YEARS_BACK="${YEARS_BACK:-5}"

# Parse command-line arguments
START_DATE=""
END_DATE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --start-date)
            START_DATE="$2"
            shift 2
            ;;
        --end-date)
            END_DATE="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]"
            echo ""
            echo "Examples:"
            echo "  # Test with one day"
            echo "  $0 --start-date 2024-01-15 --end-date 2024-01-15"
            echo ""
            echo "  # Collect last 5 years (default)"
            echo "  $0"
            echo ""
            echo "  # Custom date range"
            echo "  $0 --start-date 2020-01-01 --end-date 2024-12-31"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}=== Starting Dukascopy Data Collection ===${NC}"

# Check if VM exists
if ! gcloud compute instances describe $VM_NAME --zone=$ZONE &>/dev/null; then
    echo -e "${YELLOW}VM $VM_NAME not found.${NC}"
    exit 1
fi

# Calculate date range if not provided
if [ -z "$END_DATE" ]; then
    END_DATE=$(date +%Y-%m-%d)
fi

if [ -z "$START_DATE" ]; then
    START_DATE=$(date -d "$YEARS_BACK years ago" +%Y-%m-%d 2>/dev/null || date -v-${YEARS_BACK}y +%Y-%m-%d 2>/dev/null || echo "2019-01-01")
fi

# Validate date format (basic check)
if ! [[ "$START_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || ! [[ "$END_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo -e "${YELLOW}Error: Dates must be in YYYY-MM-DD format${NC}"
    exit 1
fi

echo "Collection parameters:"
echo "  Start date: $START_DATE"
echo "  End date: $END_DATE"
echo "  Output: /data/dukascopy"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# Start collection on VM
echo "Starting collection on VM..."
gcloud compute ssh $VM_NAME --zone=$ZONE <<EOF
set -e

# Check and mount /data if needed
if [ ! -d /data ]; then
    echo "Checking data disk..."
    if [ -b /dev/sdb ]; then
        echo "Data disk found at /dev/sdb, mounting..."
        sudo mkdir -p /data
        if ! mountpoint -q /data; then
            sudo mount -o discard,defaults /dev/sdb /data || {
                echo "Mount failed, attempting to format..."
                sudo mkfs.ext4 -F -m 0 -E lazy_itable_init=0,lazy_journal_init=0,discard /dev/sdb
                sudo mount -o discard,defaults /dev/sdb /data
                echo '/dev/sdb /data ext4 discard,defaults,nofail 0 2' | sudo tee -a /etc/fstab
            }
        fi
        sudo chown -R \$USER:\$USER /data
        sudo chmod -R 755 /data
    else
        echo "Warning: Data disk not found at /dev/sdb"
        echo "Creating /data directory on root filesystem..."
        sudo mkdir -p /data
        sudo chown -R \$USER:\$USER /data
        sudo chmod -R 755 /data
    fi
fi

# Create necessary directories
mkdir -p /data/dukascopy /data/logs

# Verify script exists
if [ ! -f /opt/trading-system/scripts/backfill_dukascopy_data.py ]; then
    echo "Error: Collection script not found at /opt/trading-system/scripts/backfill_dukascopy_data.py"
    echo "Please run upload-files.sh first"
    exit 1
fi

cd /opt/trading-system

echo "Starting collection: $START_DATE to $END_DATE"
echo "Started at: \$(date)"

# Check if screen session already exists
if screen -list | grep -q "dukascopy-collection"; then
    echo "Warning: Screen session 'dukascopy-collection' already exists"
    echo "Killing existing session..."
    screen -S dukascopy-collection -X quit || true
    sleep 1
fi

# Run collection in screen session (runs in background)
# Use exec to ensure screen session persists
screen -dmS dukascopy-collection bash -c "
cd /opt/trading-system && \
LOG_FILE=\"/data/logs/collection_\$(date +%Y%m%d_%H%M%S).log\" && \
exec python3 scripts/backfill_dukascopy_data.py \
    --start-date $START_DATE \
    --end-date $END_DATE \
    --output-dir /data/dukascopy \
    --batch-size 3 \
    --pause-ms 5000 \
    --compression snappy \
    --verbose \
    2>&1 | tee \"\$LOG_FILE\"
"

# Wait a moment and verify screen session was created
sleep 1
if screen -list | grep -q "dukascopy-collection"; then
    echo "Collection started in screen session 'dukascopy-collection'"
    echo "To view: screen -r dukascopy-collection"
    echo "To detach: Ctrl+A, then D"
    echo "Log files: /data/logs/collection_*.log"
else
    echo "Error: Failed to create screen session"
    exit 1
fi
EOF

echo -e "${GREEN}Collection started!${NC}"
echo ""
echo "Monitor progress:"
echo "  # Python script log (detailed):"
echo "  gcloud compute ssh $VM_NAME --zone=$ZONE --command='tail -f /opt/trading-system/logs/dukascopy_backfill.log'"
echo ""
echo "  # Collection log (tee output):"
echo "  gcloud compute ssh $VM_NAME --zone=$ZONE --command='tail -f /data/logs/collection_*.log'"
echo ""
echo "View screen session:"
echo "  gcloud compute ssh $VM_NAME --zone=$ZONE"
echo "  screen -r dukascopy-collection"
