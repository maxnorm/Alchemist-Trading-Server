#!/bin/bash
# Start data collection on GCP VM

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

VM_NAME="${VM_NAME:-dukascopy-collector}"
ZONE="${ZONE:-us-central1-a}"
YEARS_BACK="${YEARS_BACK:-5}"

echo -e "${GREEN}=== Starting Dukascopy Data Collection ===${NC}"

# Check if VM exists
if ! gcloud compute instances describe $VM_NAME --zone=$ZONE &>/dev/null; then
    echo -e "${YELLOW}VM $VM_NAME not found.${NC}"
    exit 1
fi

# Calculate date range
END_DATE=$(date +%Y-%m-%d)
START_DATE=$(date -d "$YEARS_BACK years ago" +%Y-%m-%d 2>/dev/null || date -v-${YEARS_BACK}y +%Y-%m-%d 2>/dev/null || echo "2019-01-01")

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

# Create collection script on VM
echo "Creating collection script on VM..."
gcloud compute ssh $VM_NAME --zone=$ZONE <<EOF
cat > /tmp/start-collection.sh <<'SCRIPT_EOF'
#!/bin/bash
set -e

cd /opt/trading-system

# Calculate dates
END_DATE=\$(date +%Y-%m-%d)
START_DATE=\$(date -d "5 years ago" +%Y-%m-%d 2>/dev/null || echo "2019-01-01")

echo "Starting collection: \$START_DATE to \$END_DATE"
echo "Started at: \$(date)"

# Run collection in screen session
screen -dmS dukascopy-collection bash -c "
cd /opt/trading-system && \
python3 scripts/backfill_dukascopy_data.py \
    --start-date \$START_DATE \
    --end-date \$END_DATE \
    --output-dir /data/dukascopy \
    --batch-size 3 \
    --pause-ms 5000 \
    --compression snappy \
    --verbose \
    2>&1 | tee /data/logs/collection_\$(date +%Y%m%d_%H%M%S).log
"

echo "Collection started in screen session 'dukascopy-collection'"
echo "To view: screen -r dukascopy-collection"
echo "To detach: Ctrl+A, then D"
SCRIPT_EOF

chmod +x /tmp/start-collection.sh
/tmp/start-collection.sh
EOF

echo -e "${GREEN}Collection started!${NC}"
echo ""
echo "Monitor progress:"
echo "  gcloud compute ssh $VM_NAME --zone=$ZONE --command='tail -f /data/logs/dukascopy_backfill.log'"
echo ""
echo "View screen session:"
echo "  gcloud compute ssh $VM_NAME --zone=$ZONE"
echo "  screen -r dukascopy-collection"
