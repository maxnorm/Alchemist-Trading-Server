#!/bin/bash
# Check collection status and show logs

VM_NAME="${VM_NAME:-dukascopy-collector}"
ZONE="${ZONE:-us-central1-a}"

echo "=== Checking Collection Status ==="
echo ""

# Check if screen session is running
echo "1. Checking if collection is running..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="screen -ls" 2>/dev/null | grep dukascopy-collection && echo "✓ Collection is running" || echo "✗ Collection not found in screen"

echo ""
echo "2. Checking log files..."

# Check Python script log
echo "   Python script log:"
gcloud compute ssh $VM_NAME --zone=$ZONE --command="ls -lh /opt/trading-system/logs/dukascopy_backfill.log 2>/dev/null || echo '  Not found yet'" 2>/dev/null

# Check tee log
echo "   Collection log (tee):"
gcloud compute ssh $VM_NAME --zone=$ZONE --command="ls -lht /data/logs/collection_*.log 2>/dev/null | head -1 || echo '  Not found yet'" 2>/dev/null

echo ""
echo "3. Recent log output (if available):"
echo "   Last 30 lines from Python script:"
gcloud compute ssh $VM_NAME --zone=$ZONE --command="tail -30 /opt/trading-system/logs/dukascopy_backfill.log 2>/dev/null || echo '  Log file not created yet'" 2>/dev/null

echo ""
echo "   Last 30 lines from collection log:"
gcloud compute ssh $VM_NAME --zone=$ZONE --command="tail -30 /data/logs/collection_*.log 2>/dev/null | tail -30 || echo '  Log file not created yet'" 2>/dev/null

echo ""
echo "   Check for errors:"
gcloud compute ssh $VM_NAME --zone=$ZONE --command="grep -i 'error\|exception\|failed\|traceback' /opt/trading-system/logs/dukascopy_backfill.log | tail -10 || echo '  No errors found'" 2>/dev/null

echo ""
echo "4. Check if data disk is mounted:"
gcloud compute ssh $VM_NAME --zone=$ZONE --command="df -h /data 2>/dev/null || echo '  /data not mounted'" 2>/dev/null

echo ""
echo "5. Check running processes:"
gcloud compute ssh $VM_NAME --zone=$ZONE --command="ps aux | grep -E 'backfill|dukascopy' | grep -v grep || echo '  No collection process found'" 2>/dev/null

echo ""
echo "6. Check collected data:"
gcloud compute ssh $VM_NAME --zone=$ZONE --command="ls -lh /data/dukascopy/*/*.parquet 2>/dev/null | head -10 || echo '  No Parquet files found yet'" 2>/dev/null
gcloud compute ssh $VM_NAME --zone=$ZONE --command="du -sh /data/dukascopy/* 2>/dev/null | head -10 || echo '  No data directories found'" 2>/dev/null

echo ""
echo "=== To view live logs ==="
echo "  gcloud compute ssh $VM_NAME --zone=$ZONE"
echo "  screen -r dukascopy-collection"
echo ""
echo "Or check Python log:"
echo "  gcloud compute ssh $VM_NAME --zone=$ZONE --command='tail -f /opt/trading-system/logs/dukascopy_backfill.log'"
