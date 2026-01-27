# Dukascopy Historical Data Collection Guide

**Last Updated:** January 17, 2026  
**Purpose:** Comprehensive guide for collecting historical tick data from Dukascopy

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Detailed Collection Process](#detailed-collection-process)
5. [Rate Limiting Strategy](#rate-limiting-strategy)
6. [DVC Workflow](#dvc-workflow)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)

---

## Overview

This guide covers the complete process of collecting historical forex tick data from Dukascopy, converting it to Parquet format, and managing it with DVC (Data Version Control) for reproducible deployment.

**What You'll Collect:**
- 28 currency pairs (6 majors + 22 crosses)
- Historical data from 2003 to present (~20+ years)
- Tick-level granularity (bid/ask prices with millisecond timestamps)
- Total storage: ~560-900GB compressed Parquet format

**Timeline Estimate:**
- Setup: 1-2 hours
- Data collection: 2-4 weeks (overnight downloads)
- DVC configuration: 1-2 hours

---

## Prerequisites

### Required Software

1. **Python 3.11+** with minimal dependencies
   ```bash
   # Check Python version
   python --version
   
   # Install ONLY required packages (no trading server dependencies)
   pip install pandas pyarrow numpy
   ```

2. **Node.js** (v14+ recommended)
   ```bash
   # Check if installed
   node --version
   
   # Install from https://nodejs.org if needed
   ```

3. **dukascopy-node CLI**
   ```bash
   # Option 1: Install locally in project (recommended)
   npm install dukascopy-node
   
   # Option 2: Install globally
   npm install -g dukascopy-node
   
   # Option 3: Use npx (no installation required)
   npx dukascopy-node --help
   ```

4. **DVC (Data Version Control)** - Optional for versioning
   ```bash
   # Install DVC
   pip install dvc dvc-s3  # or dvc-gs, dvc-azure
   ```

### Storage Requirements

- **Local disk space:** 1-2TB free (temporary JSON files + final Parquet files)
- **Remote storage:** 600GB-1TB for Parquet files (S3, GCS, or NAS)

### Network

- Stable internet connection (10+ Mbps recommended)
- No restrictive firewalls blocking Dukascopy API

---

## Quick Start

### 1. Install Dependencies

```bash
# Python dependencies (standalone - no trading server needed)
pip install pandas pyarrow numpy

# Node.js package (local installation recommended)
npm install dukascopy-node
```

### 2. Test with Single Pair (Recommended)

Start with one pair and recent data to validate the setup:

```bash
# Download EURUSD for 2024 only (quick test)
python scripts/backfill_dukascopy_data.py \
    --pairs EURUSD \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --output-dir data/dukascopy \
    --batch-size 3 \
    --pause-ms 5000
```

**Expected Results:**
- Download time: ~2-4 hours
- Output: `data/dukascopy/EURUSD/*.parquet` (multiple yearly files)
- Size: ~10-20GB
- Progress file: `data/.dukascopy_progress.json`

### 3. Validate Output

```bash
# Validate the collected data
python scripts/validate_parquet_data.py \
    --data-dir data/dukascopy \
    --summary

# Generate detailed report
python scripts/validate_parquet_data.py \
    --data-dir data/dukascopy \
    --report data/validation_report.json
```

**Expected Output:**
```
================================================================================
VALIDATION SUMMARY
================================================================================
Total Symbols: 1
  PASS: 1
  WARN: 0
  FAIL: 0

✓ EURUSD: PASS     | 125,843,297 ticks | 0 issues, 0 warnings
================================================================================
```

### 4. Seed into Database (Optional)

```bash
# Seed into database (requires Docker running with all dependencies)
docker compose up -d postgres

python scripts/seed_historical_data.py \
    --data-dir data/dukascopy \
    --pairs EURUSD \
    --years 2024-2024 \
    --batch-size 10000
```

---

## Detailed Collection Process

### Step 1: Plan Your Collection

**Decision Points:**

1. **Which pairs?**
   - Start with major pairs (EURUSD, GBPUSD, USDJPY, etc.)
   - Add crosses later (EURGBP, EURJPY, etc.)
   - See [`params.yaml`](../params.yaml) for full list of 28 supported pairs

2. **Which time period?**
   - MVP: Last 2-3 years (2022-present)
   - Full history: 2003-present
   - Balance: Last 5 years

3. **Sequential vs. Parallel?**
   - Recommended: Sequential (one pair at a time) to respect rate limits
   - Advanced: 2 workers max with careful monitoring

### Step 2: Configure Parameters

Edit [`params.yaml`](../params.yaml):

```yaml
dukascopy:
  pairs:
    - EURUSD  # Start with majors
    - GBPUSD
    - USDJPY
    # Add more pairs as needed
  
  start_date: "2022-01-01"  # Adjust based on needs
  end_date: "2024-12-31"
  
  rate_limit:
    batch_size: 3        # Conservative (3 days at a time)
    pause_ms: 5000       # 5 seconds between batches
```

### Step 3: Run Collection

**Option A: DVC Pipeline (Recommended)**

```bash
# Run DVC pipeline
dvc repro collect_dukascopy

# DVC will execute backfill script with params from params.yaml
# Progress tracked in logs/dukascopy_backfill.log
```

**Option B: Direct Script Execution**

```bash
# All pairs from params.yaml
python scripts/backfill_dukascopy_data.py \
    --output-dir data/dukascopy

# Specific pairs
python scripts/backfill_dukascopy_data.py \
    --pairs EURUSD,GBPUSD,USDJPY \
    --start-date 2022-01-01 \
    --end-date 2024-12-31 \
    --output-dir data/dukascopy \
    --batch-size 3 \
    --pause-ms 5000

# Resume failed download
python scripts/backfill_dukascopy_data.py \
    --resume \
    --output-dir data/dukascopy
```

### Step 4: Monitor Progress

```bash
# Watch log file
tail -f logs/dukascopy_backfill.log

# Check created files
find data/dukascopy -name "*.parquet" | wc -l

# Check total size
du -sh data/dukascopy/
```

### Step 5: Verify Data Quality

```bash
# Validate collected data
python scripts/validate_parquet_data.py \
    --data-dir data/dukascopy \
    --summary

# Generate detailed validation report
python scripts/validate_parquet_data.py \
    --data-dir data/dukascopy \
    --report data/validation_report.json

# Validate specific pair
python scripts/validate_parquet_data.py \
    --data-dir data/dukascopy \
    --pair EURUSD
```

**What Gets Validated:**
- Basic checks (nulls, required columns, timestamp order)
- Price validation (bid < ask, reasonable ranges)
- Spread analysis (mean/std, outlier detection)
- Gap detection (missing days, large time gaps)
- Volume analysis (ticks per hour, low activity periods)

**Validation Status:**
- **PASS** - No issues, data ready for seeding
- **WARN** - Minor warnings, review before seeding
- **FAIL** - Critical issues, DO NOT seed

---

## Rate Limiting Strategy

### Why Rate Limiting Matters

Dukascopy doesn't publish official rate limits, but aggressive downloading can lead to:
- HTTP 429 (Too Many Requests) errors
- IP bans (temporary or permanent)
- Download failures

### Conservative Settings (Recommended)

```python
--batch-size 3      # Download 3 days at a time
--pause-ms 5000     # 5 seconds between batches
```

**Result:**
- ~250 requests/hour
- ~6,000 requests/day
- Safe for 24/7 operation

### Calculation

```
Requests per hour = (3600 seconds / pause_ms) * 1000
                  = (3600 / 5) = 720 max batches/hour

With batch_size=3:
  Days per hour = 720 * 3 = 2,160 days/hour
  
For 20 years (7,300 days):
  Time required = 7,300 / 2,160 ≈ 3.4 hours per pair
  
For 28 pairs:
  Total time = 28 * 3.4 ≈ 95 hours ≈ 4 days (sequential)
```

### Aggressive Settings (Use with Caution)

```python
--batch-size 5      # 5 days at a time
--pause-ms 3000     # 3 seconds between batches
```

**Result:**
- ~600 requests/hour
- ~14,000 requests/day
- Higher risk of rate limiting

### Handling Rate Limit Errors

The script includes automatic retry with exponential backoff:

```python
# On 429 error:
Attempt 1: Wait 60 seconds
Attempt 2: Wait 120 seconds
Attempt 3: Wait 180 seconds
```

If you see repeated rate limit errors:
1. Stop all running downloads
2. Wait 1 hour
3. Restart with more conservative settings
4. Consider spreading downloads over multiple days

---

## DVC Workflow

### Initial Setup

```bash
# Initialize DVC (if not already done)
dvc init

# Configure remote storage
dvc remote add -d dukascopy_storage s3://your-bucket/dukascopy

# Or use local storage
dvc remote add -d dukascopy_storage /mnt/nas/dukascopy

# Configure credentials (for S3)
dvc remote modify dukascopy_storage access_key_id YOUR_KEY
dvc remote modify dukascopy_storage secret_access_key YOUR_SECRET
```

### Add Data to DVC

```bash
# After collection completes
dvc add data/dukascopy

# This creates data/dukascopy.dvc file
# Commit to git
git add data/dukascopy.dvc data/.gitignore
git commit -m "Add Dukascopy historical data (2003-2024)"

# Push data to remote
dvc push
```

### Retrieving Data on New Machine

```bash
# Clone repository
git clone <your-repo>

# Pull data from DVC remote
dvc pull

# Data now available in data/dukascopy/
```

### Updating Data (Incremental)

```bash
# Download new data (e.g., 2025)
python scripts/backfill_dukascopy_data.py \
    --start-date 2025-01-01 \
    --end-date 2025-12-31 \
    --output-dir data/dukascopy

# Update DVC tracking
dvc add data/dukascopy

# Push changes
git add data/dukascopy.dvc
git commit -m "Update Dukascopy data: add 2025"
dvc push
```

---

## Troubleshooting

### Issue: dukascopy-node not found

**Symptoms:**
```
ERROR: dukascopy-node CLI not found
```

**Solution:**
```bash
# Option 1: Install globally
npm install -g dukascopy-node

# Option 2: Use npx (automatic)
# Script already uses npx, so just ensure Node.js is installed
node --version  # Should show v14+
```

### Issue: Download times out

**Symptoms:**
```
ERROR: Download timed out after 4 hours
```

**Solution:**
```bash
# Reduce date range (download smaller chunks)
python scripts/backfill_dukascopy_data.py \
    --pairs EURUSD \
    --start-date 2024-01-01 \
    --end-date 2024-06-30  # 6 months instead of full year
    
# Then download next 6 months
```

### Issue: Rate limited (429 errors)

**Symptoms:**
```
ERROR: Rate limited, waiting 60s before retry
```

**Solution:**
```bash
# Stop current download
Ctrl+C

# Wait 1-2 hours

# Resume with more conservative settings
python scripts/backfill_dukascopy_data.py \
    --resume \
    --batch-size 2 \      # Slower
    --pause-ms 8000       # Longer pause
```

### Issue: Disk space exhausted

**Symptoms:**
```
ERROR: No space left on device
```

**Solution:**
```bash
# Check disk space
df -h

# Delete temporary JSON files
rm -rf /tmp/dukascopy_*

# Use external disk
python scripts/backfill_dukascopy_data.py \
    --output-dir /mnt/external/dukascopy
```

### Issue: Parquet conversion fails

**Symptoms:**
```
ERROR: Failed to convert JSON to Parquet
```

**Solution:**
```bash
# Check Python dependencies
pip install --upgrade pandas pyarrow

# Verify JSON file integrity
python -c "import json; json.load(open('file.json'))"

# Re-download if corrupted
python scripts/backfill_dukascopy_data.py \
    --pairs EURUSD \
    --start-date 2024-01-01 \
    --end-date 2024-12-31
```

---

## Best Practices

### 1. Start Small, Scale Up

✅ **Do:**
- Test with 1 pair, 1 year first
- Verify output quality
- Then scale to multiple pairs

❌ **Don't:**
- Start with all 28 pairs immediately
- Skip validation steps
- Ignore errors

### 2. Run Overnight

✅ **Do:**
- Schedule long downloads for overnight
- Use screen/tmux for persistent sessions
- Monitor logs in the morning

```bash
# Use screen for persistent session
screen -S dukascopy_download

# Run collection
python scripts/backfill_dukascopy_data.py --output-dir data/dukascopy

# Detach: Ctrl+A, then D
# Reattach later: screen -r dukascopy_download
```

### 3. Backup Regularly

✅ **Do:**
- Push to DVC remote daily
- Keep local backups before large operations
- Verify data integrity regularly

```bash
# Backup before risky operation
cp -r data/dukascopy data/dukascopy_backup

# Verify integrity
python scripts/validate_parquet_data.py
```

### 4. Monitor Progress

✅ **Do:**
- Check logs regularly
- Track download rates
- Note any errors immediately

```bash
# Create monitoring script
cat > monitor_progress.sh << 'EOF'
#!/bin/bash
while true; do
    clear
    echo "=== Dukascopy Download Progress ==="
    echo "Files created: $(find data/dukascopy -name '*.parquet' | wc -l)"
    echo "Total size: $(du -sh data/dukascopy)"
    echo "Latest log entries:"
    tail -n 10 logs/dukascopy_backfill.log
    sleep 60
done
EOF
chmod +x monitor_progress.sh
./monitor_progress.sh
```

### 5. Document Your Setup

✅ **Do:**
- Record parameters used
- Note any issues encountered
- Document custom configurations

```markdown
## Collection Log - EURUSD

**Date:** 2026-01-17
**Parameters:**
- Date range: 2003-2024
- Batch size: 3
- Pause: 5000ms
**Results:**
- Download time: 3.2 hours
- Files created: 22 yearly Parquet files
- Total size: 95GB
- Issues: None
```

---

## Next Steps

After completing data collection:

1. **Verify Data Quality**
   - Run validation scripts
   - Check for gaps
   - Verify tick counts

2. **Seed into Database**
   - See [`DATA_STORAGE_STRATEGY.md`](DATA_STORAGE_STRATEGY.md)
   - Test with small dataset first
   - Monitor database performance

3. **Configure DVC Remote**
   - Set up S3/GCS bucket
   - Push data to remote
   - Test retrieval on new machine

4. **Set Up Continuous Updates**
   - Schedule monthly incremental downloads
   - Automate DVC push/pull
   - Monitor data freshness

---

## Additional Resources

- [Dukascopy-node Documentation](https://www.dukascopy-node.app/)
- [DVC Documentation](https://dvc.org/doc)
- [Parquet Format Specification](https://parquet.apache.org/docs/)
- [TimescaleDB Documentation](https://docs.timescale.com/)

---

**Need Help?**

Check the logs first:
```bash
tail -f logs/dukascopy_backfill.log
```

If issues persist, create a GitHub issue with:
- Command used
- Error message
- Relevant log excerpts
- System information (OS, Python version, Node version)
