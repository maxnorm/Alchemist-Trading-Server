#!/bin/bash
# Diagnostic script to check why Dukascopy collection stopped
# Run this on the GCP VPS directly

set -e

echo "=== Dukascopy Collection Diagnostic ==="
echo ""

# 1. Check screen sessions
echo "1. Screen sessions:"
screen -ls || echo "  No screen sessions found"
echo ""

# 2. Check if collection process is running
echo "2. Running processes:"
ps aux | grep -E 'backfill_dukascopy|python.*backfill' | grep -v grep || echo "  No collection process found"
echo ""

# 3. Check log files
echo "3. Log files:"
echo "   Python script log:"
if [ -f /opt/trading-system/logs/dukascopy_backfill.log ]; then
    ls -lh /opt/trading-system/logs/dukascopy_backfill.log
    echo "   Last 50 lines:"
    tail -50 /opt/trading-system/logs/dukascopy_backfill.log
else
    echo "   Not found at /opt/trading-system/logs/dukascopy_backfill.log"
fi
echo ""

echo "   Collection logs (tee):"
LATEST_LOG=$(ls -t /data/logs/collection_*.log 2>/dev/null | head -1)
if [ -n "$LATEST_LOG" ]; then
    echo "   Latest: $LATEST_LOG"
    ls -lh "$LATEST_LOG"
    echo "   Last 50 lines:"
    tail -50 "$LATEST_LOG"
else
    echo "   No collection logs found in /data/logs/"
fi
echo ""

# 4. Check for errors
echo "4. Recent errors:"
if [ -f /opt/trading-system/logs/dukascopy_backfill.log ]; then
    grep -i 'error\|exception\|failed\|traceback\|fatal' /opt/trading-system/logs/dukascopy_backfill.log | tail -20 || echo "   No errors found"
fi
echo ""

# 5. Check disk space
echo "5. Disk space:"
df -h /data 2>/dev/null || df -h /
echo ""

# 6. Check data directory
echo "6. Collected data:"
if [ -d /data/dukascopy ]; then
    echo "   Directory exists"
    echo "   Total size:"
    du -sh /data/dukascopy 2>/dev/null || echo "   Could not calculate size"
    echo "   Pair directories:"
    ls -lh /data/dukascopy/ | head -10
    echo "   Parquet files:"
    find /data/dukascopy -name "*.parquet" -type f | wc -l | xargs echo "   Total:"
    find /data/dukascopy -name "*.parquet" -type f -exec ls -lh {} \; | head -5
else
    echo "   /data/dukascopy does not exist"
fi
echo ""

# 7. Check progress file
echo "7. Progress tracking:"
if [ -f /data/.dukascopy_progress.json ]; then
    echo "   Progress file exists:"
    cat /data/.dukascopy_progress.json | python3 -m json.tool 2>/dev/null || cat /data/.dukascopy_progress.json
elif [ -f /opt/trading-system/data/.dukascopy_progress.json ]; then
    echo "   Progress file exists (alternative location):"
    cat /opt/trading-system/data/.dukascopy_progress.json | python3 -m json.tool 2>/dev/null || cat /opt/trading-system/data/.dukascopy_progress.json
else
    echo "   No progress file found"
fi
echo ""

# 8. Check script location
echo "8. Script availability:"
if [ -f /opt/trading-system/scripts/backfill_dukascopy_data.py ]; then
    echo "   ✓ Script found at /opt/trading-system/scripts/backfill_dukascopy_data.py"
    ls -lh /opt/trading-system/scripts/backfill_dukascopy_data.py
elif [ -f ~/trading-system/scripts/backfill_dukascopy_data.py ]; then
    echo "   ✓ Script found at ~/trading-system/scripts/backfill_dukascopy_data.py"
    ls -lh ~/trading-system/scripts/backfill_dukascopy_data.py
else
    echo "   ✗ Script not found"
    echo "   Searching..."
    find /opt /home -name "backfill_dukascopy_data.py" 2>/dev/null | head -5 || echo "   Not found"
fi
echo ""

# 9. Check Python and dependencies
echo "9. Python environment:"
python3 --version
which python3
echo "   Checking dukascopy-node:"
which dukascopy-node || which npx || echo "   dukascopy-node not found in PATH"
npx dukascopy-node --version 2>/dev/null || echo "   npx dukascopy-node not available"
echo ""

# 10. Check system resources
echo "10. System resources:"
echo "   Memory:"
free -h
echo "   Load average:"
uptime
echo ""

echo "=== Diagnostic Complete ==="
echo ""
echo "To restart collection, run:"
echo "  cd /opt/trading-system"
echo "  screen -dmS dukascopy-collection bash -c 'python3 scripts/backfill_dukascopy_data.py --resume --start-date YYYY-MM-DD --end-date YYYY-MM-DD --output-dir /data/dukascopy --batch-size 3 --pause-ms 5000 --compression snappy --verbose 2>&1 | tee /data/logs/collection_\$(date +%Y%m%d_%H%M%S).log'"
echo ""
echo "Or use the start-collection.sh script from your local machine"
