# Data Storage Strategy

**Last Updated:** January 17, 2026  
**Purpose:** Comprehensive strategy for storing and managing historical forex data at rest

---

## Table of Contents

1. [Overview](#overview)
2. [Storage Architecture](#storage-architecture)
3. [Parquet Format Details](#parquet-format-details)
4. [Storage Size Estimates](#storage-size-estimates)
5. [DVC Configuration](#dvc-configuration)
6. [Deployment Seeding](#deployment-seeding)
7. [Backup & Disaster Recovery](#backup--disaster-recovery)
8. [Performance Optimization](#performance-optimization)

---

## Overview

This document outlines the complete strategy for storing Dukascopy historical data efficiently, versioning it with DVC, and seeding it into TimescaleDB for production deployment.

**Key Design Decisions:**

- **Format:** Parquet (columnar, compressed)
- **Partitioning:** Yearly files per symbol
- **Versioning:** DVC with remote storage (S3/GCS/NAS)
- **Seeding:** Automated on Docker deployment (optional flag)

**Benefits:**

- 5-10x compression vs CSV
- Fast bulk loading into database
- Version control for reproducibility
- Efficient incremental updates

---

## Storage Architecture

### Directory Structure

```
data/
└── dukascopy/
    ├── EURUSD/
    │   ├── 2003.parquet
    │   ├── 2004.parquet
    │   ├── ...
    │   ├── 2024.parquet
    │   └── metadata.json
    ├── GBPUSD/
    │   ├── 2003.parquet
    │   ├── ...
    │   └── metadata.json
    ├── ...
    └── metadata.json (global)
```

### Why This Structure?

**Symbol-Level Directories:**
- Easy to add/remove pairs
- Independent versioning per symbol
- Parallel processing capabilities

**Yearly Partitions:**
- Manageable file sizes (~3-10GB each)
- Incremental loading (load specific years)
- Easy to update with new data
- Natural time-based organization

**Metadata Files:**
- Track data quality and coverage
- Record collection parameters
- Aid in validation and debugging

---

## Parquet Format Details

### Schema

```python
import pyarrow as pa

schema = pa.schema([
    ('timestamp', pa.timestamp('ns', tz='UTC')),  # Nanosecond precision, UTC
    ('bid', pa.float64()),                        # Bid price (8 bytes)
    ('ask', pa.float64()),                        # Ask price (8 bytes)
    ('symbol', pa.dictionary(pa.int8(), pa.string()))  # Categorical (1 byte index)
])
```

**Column Details:**

- **timestamp**: Nanosecond precision, UTC timezone
  - Preserves millisecond precision from Dukascopy
  - Ready for TimescaleDB without conversion
  
- **bid/ask**: float64 (double precision)
  - Handles forex precision (5-6 decimal places)
  - Compatible with database DOUBLE PRECISION type
  
- **symbol**: Dictionary-encoded categorical
  - Stores string once, uses integer index
  - Saves space for repeated values

### Compression

**Default: Snappy**
- Fast compression/decompression
- ~3-5x compression ratio
- CPU-friendly for bulk operations

**Alternatives:**

| Codec | Compression Ratio | Speed | Use Case |
|-------|------------------|-------|----------|
| Snappy | 3-5x | ⚡⚡⚡⚡⚡ | **Default** (best balance) |
| Gzip | 5-8x | ⚡⚡⚡ | Maximum compression |
| LZ4 | 2-4x | ⚡⚡⚡⚡⚡⚡ | Ultra-fast, less compression |
| Zstd | 4-7x | ⚡⚡⚡⚡ | Modern, good balance |

**Recommendation:** Stick with Snappy unless storage is extremely constrained.

### Metadata Embedded

Each Parquet file contains metadata:

```json
{
  "symbol": "EURUSD",
  "year": "2024",
  "source": "dukascopy",
  "converted_at": "2026-01-17T14:30:00Z",
  "tick_count": "125843297",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-12-31T23:59:59Z"
}
```

**Access Metadata:**
```python
import pyarrow.parquet as pq

file = pq.ParquetFile('data/dukascopy/EURUSD/2024.parquet')
metadata = file.schema_arrow.metadata
print(metadata)
```

---

## Storage Size Estimates

### Per-Pair Estimates (Full History: 2003-2024)

| Pair Type | Count | Size per Pair | Total Size |
|-----------|-------|---------------|------------|
| Majors (liquid) | 6 | ~30-40GB | ~180-240GB |
| EUR crosses | 6 | ~20-30GB | ~120-180GB |
| GBP crosses | 6 | ~20-25GB | ~120-150GB |
| JPY crosses | 4 | ~15-20GB | ~60-80GB |
| Other crosses | 6 | ~15-20GB | ~90-120GB |
| **Total** | **28** | - | **~570-770GB** |

### Size Breakdown by Format

| Format | Storage | Notes |
|--------|---------|-------|
| Raw JSON (temp) | ~2-3TB | Deleted after conversion |
| Parquet (snappy) | ~570-770GB | **At-rest storage** |
| Parquet (gzip) | ~400-500GB | Higher compression |
| TimescaleDB (uncompressed) | ~600-800GB | Database storage |
| TimescaleDB (compressed) | ~150-300GB | With native compression |

### Growth Rate (New Data)

**Per pair, per year:**
- Major pairs: ~10-15GB/year
- Cross pairs: ~5-10GB/year

**All 28 pairs:**
- ~250-350GB/year growth

**Recommendation:**
- Plan for 1TB initial storage
- Add 500GB/year for new data

---

## DVC Configuration

### Remote Storage Options

**Option 1: AWS S3 (Recommended for Cloud)**

```bash
# Configure S3 remote
dvc remote add -d dukascopy_storage s3://your-bucket/dukascopy

# Set credentials
dvc remote modify dukascopy_storage access_key_id YOUR_KEY
dvc remote modify dukascopy_storage secret_access_key YOUR_SECRET

# Optional: Use specific region
dvc remote modify dukascopy_storage region us-east-1
```

**Cost Estimate (S3):**
- Storage: ~$15-20/month for 700GB (Standard tier)
- Retrieval: ~$5-10/month for occasional pulls
- Total: ~$20-30/month

**Option 2: Google Cloud Storage**

```bash
# Configure GCS remote
dvc remote add -d dukascopy_storage gs://your-bucket/dukascopy

# Authenticate
gcloud auth application-default login

# DVC will use application default credentials
```

**Cost Estimate (GCS):**
- Storage: ~$15-20/month for 700GB (Standard tier)
- Retrieval: ~$5-10/month
- Total: ~$20-30/month

**Option 3: Local/NAS (Development)**

```bash
# Configure local remote
dvc remote add -d dukascopy_storage /mnt/nas/dukascopy

# Or SMB/NFS share
dvc remote add -d dukascopy_storage \\nas\dukascopy
```

**Cost Estimate:**
- One-time NAS hardware: $300-1000
- No recurring costs
- Suitable for development/testing

### Adding Data to DVC

```bash
# After data collection
dvc add data/dukascopy

# This creates:
# - data/dukascopy.dvc (tracking file, ~500 bytes)
# - data/.gitignore (ignores actual data)

# Commit tracking file to git
git add data/dukascopy.dvc data/.gitignore .dvc/.gitignore .dvc/config
git commit -m "Track Dukascopy historical data with DVC"

# Push data to remote
dvc push  # Uploads ~700GB (takes hours on first push)
```

### Pulling Data (New Deployment)

```bash
# Clone repo
git clone https://github.com/your-org/trading-system.git
cd trading-system

# Pull DVC data
dvc pull  # Downloads ~700GB from remote

# Data now available for seeding
ls data/dukascopy/
```

### Updating Data (Incremental)

```bash
# Download 2025 data
python scripts/backfill_dukascopy_data.py \
    --start-date 2025-01-01 \
    --end-date 2025-12-31 \
    --output-dir data/dukascopy

# Update DVC tracking
dvc add data/dukascopy

# DVC only uploads changed/new files (intelligent diffing)
git add data/dukascopy.dvc
git commit -m "Add 2025 historical data"
dvc push  # Only uploads new 2025 files (~20-30GB)
```

---

## Deployment Seeding

### Manual Seeding

**Step 1: Ensure Data Available**

```bash
# Pull from DVC if needed
dvc pull

# Verify files
ls -lh data/dukascopy/EURUSD/
```

**Step 2: Run Seeding Script**

```bash
# Seed all data
python scripts/seed_historical_data.py \
    --data-dir data/dukascopy \
    --batch-size 10000

# Or specific pairs
python scripts/seed_historical_data.py \
    --data-dir data/dukascopy \
    --pairs EURUSD,GBPUSD \
    --years 2022-2024

# Dry run (validation only)
python scripts/seed_historical_data.py \
    --data-dir data/dukascopy \
    --dry-run
```

**Performance:**
- ~10,000 inserts/second
- ~1 year = 10-20 minutes
- Full dataset (~28 pairs, 20 years) = ~8-16 hours

### Automated Docker Seeding

**Step 1: Prepare Data**

```bash
# Pull DVC data
dvc pull

# Verify directory structure
tree data/dukascopy -L 2
```

**Step 2: Configure Environment**

Edit `.env`:

```bash
# Enable historical data seeding
SEED_HISTORICAL_DATA=true

# Other DB settings
DB_USER=forex_user
DB_PASSWORD=your_password
DB_NAME=db_forex
```

**Step 3: Update docker-compose.yml**

Uncomment the volume mount:

```yaml
postgres:
  volumes:
    - "./data/dukascopy:/data/dukascopy:ro"  # Mount data (read-only)
```

**Step 4: Start Containers**

```bash
# Start with seeding enabled
docker compose up -d

# Monitor seeding progress
docker compose logs -f postgres

# Seeding runs automatically on first initialization
# Check logs at logs/seed_historical_data.log
```

**Note:** Seeding only runs on fresh database initialization. To re-seed:

```bash
# Stop containers
docker compose down

# Remove database volume
docker volume rm postgres_data

# Start containers (seeding will run)
docker compose up -d
```

### Conditional Seeding (Production)

**Development/Testing:**
```bash
# .env.development
SEED_HISTORICAL_DATA=false  # Skip seeding, use live collection
```

**Staging:**
```bash
# .env.staging
SEED_HISTORICAL_DATA=true   # Seed recent data only (2023-2024)
```

**Production:**
```bash
# .env.production
SEED_HISTORICAL_DATA=true   # Full historical dataset
```

---

## Backup & Disaster Recovery

### Backup Strategy

**Three-Tier Approach:**

1. **Primary:** DVC remote storage (S3/GCS)
   - Automatic versioning
   - Immutable (can't accidentally delete)
   - Geographically distributed

2. **Secondary:** Local NAS/external drive
   - Fast recovery
   - No cloud egress costs
   - Physical control

3. **Tertiary:** Periodic offline backup
   - External hard drive
   - Stored off-site
   - Annual/quarterly snapshots

### Backup Schedule

| Frequency | What | Where |
|-----------|------|-------|
| Daily | DVC push after new data collection | S3/GCS |
| Weekly | Sync to local NAS | NAS |
| Monthly | Verify backup integrity | All locations |
| Quarterly | Offline snapshot | External drive |

### Disaster Recovery Scenarios

**Scenario 1: Local Data Corruption**

```bash
# Remove corrupted data
rm -rf data/dukascopy

# Pull from DVC remote
dvc pull

# Verify integrity
python scripts/validate_parquet_data.py
```

**Recovery Time:** ~4-8 hours (depends on internet speed)

**Scenario 2: DVC Remote Loss**

```bash
# Re-upload from local NAS
cd /mnt/nas/trading-system
dvc push --remote dukascopy_storage_backup

# Or from offline backup
rsync -av /mnt/external/dukascopy/ data/dukascopy/
dvc add data/dukascopy
dvc push
```

**Recovery Time:** ~8-16 hours

**Scenario 3: Complete Data Loss**

Requires re-collection from Dukascopy:

```bash
# Re-run collection
python scripts/backfill_dukascopy_data.py --output-dir data/dukascopy
```

**Recovery Time:** 2-4 weeks (rate limited)

**Prevention:** Maintain multiple backup locations!

### Validation & Integrity Checks

**After Backup:**

```bash
# Check file counts
expected_files=$(find data/dukascopy -name "*.parquet" | wc -l)
actual_files=$(find /mnt/nas/dukascopy -name "*.parquet" | wc -l)
echo "Files: $actual_files / $expected_files"

# Verify checksums
dvc status  # Should show "Data and pipelines are up to date"

# Test random sample
python scripts/validate_parquet_data.py --sample 10
```

**Before Seeding:**

```bash
# Dry run
python scripts/seed_historical_data.py \
    --data-dir data/dukascopy \
    --dry-run

# Validate Parquet files
python -c "
import pandas as pd
import glob
for file in glob.glob('data/dukascopy/*/*.parquet')[:10]:
    try:
        df = pd.read_parquet(file)
        print(f'✓ {file}: {len(df):,} ticks')
    except Exception as e:
        print(f'✗ {file}: {e}')
"
```

---

## Performance Optimization

### Parquet Read Optimization

**Use Column Pruning:**

```python
import pandas as pd

# Read only needed columns
df = pd.read_parquet(
    'data/dukascopy/EURUSD/2024.parquet',
    columns=['timestamp', 'bid', 'ask']  # Skip 'symbol'
)
```

**Benefit:** 2-3x faster read, less memory

**Use Row Filtering:**

```python
# Read only specific date range
df = pd.read_parquet(
    'data/dukascopy/EURUSD/2024.parquet',
    filters=[('timestamp', '>=', '2024-06-01')]
)
```

**Benefit:** 10-100x faster for small ranges

### Database Seeding Optimization

**Batch Size Tuning:**

```python
# Too small = slow (many round trips)
batch_size = 1000     # ~2,000 inserts/sec

# Optimal = balanced
batch_size = 10000    # ~10,000 inserts/sec  ✓

# Too large = slow (single transaction overhead)
batch_size = 100000   # ~5,000 inserts/sec
```

**Disable Indexes During Bulk Load:**

```sql
-- Before seeding
DROP INDEX IF EXISTS idx_ticks_forex_datetime;
DROP INDEX IF EXISTS idx_ticks_forex_symbol_datetime;

-- Seed data (much faster without indexes)

-- After seeding
CREATE INDEX idx_ticks_forex_datetime ON ticks_forex(datetime);
CREATE INDEX idx_ticks_forex_symbol_datetime ON ticks_forex(forex_pairs_id, datetime);
```

**Benefit:** 3-5x faster seeding

**Use TimescaleDB Compression:**

```sql
-- Enable compression for old data
SELECT add_compression_policy('ticks_forex', INTERVAL '7 days');

-- Manually compress old data
SELECT compress_chunk(c) 
FROM show_chunks('ticks_forex', older_than => INTERVAL '30 days') c;
```

**Benefit:** 5-10x storage reduction, faster queries

### DVC Transfer Optimization

**Parallel Transfers:**

```bash
# Use multiple jobs for faster push/pull
dvc push -j 8   # 8 parallel uploads
dvc pull -j 8   # 8 parallel downloads
```

**Benefit:** 3-5x faster transfers

**Use Cache:**

```bash
# Configure local cache
dvc cache dir /mnt/fast_ssd/.dvc/cache

# Symlink instead of copy
dvc config cache.type symlink
```

**Benefit:** Instant "pull" for local data

---

## Cost Analysis

### Storage Costs (Annual)

| Option | Setup Cost | Annual Cost | Notes |
|--------|------------|-------------|-------|
| **AWS S3** | $0 | ~$180-240 | $15-20/month, scales automatically |
| **Google Cloud Storage** | $0 | ~$180-240 | Similar to S3 |
| **Azure Blob** | $0 | ~$180-240 | Similar to S3 |
| **Local NAS** | $500-1500 | ~$50 | Power + maintenance |
| **External Drive** | $100-300 | $0 | Manual backup only |

### Transfer Costs

| Operation | AWS S3 | GCS | Azure |
|-----------|--------|-----|-------|
| Upload (PUT) | $0.005/1000 | $0.005/1000 | $0.005/1000 |
| Download (GET) | $0.09/GB | $0.12/GB | $0.087/GB |
| Data egress | $0.09/GB | $0.12/GB | $0.087/GB |

**Example: Initial Upload (700GB)**
- AWS: ~$3.50 + ~$0.01 = ~$3.51
- GCS: ~$3.50 + ~$0.01 = ~$3.51

**Example: Full Download (700GB)**
- AWS: ~$63
- GCS: ~$84

**Tip:** Use cloud provider's free egress for intra-region transfers!

---

## Best Practices

### 1. Organize by Symbol/Year

✅ **Do:**
```
data/dukascopy/EURUSD/2024.parquet  # ✓ Clear structure
```

❌ **Don't:**
```
data/eurusd_2024_ticks.parquet      # ✗ Flat structure
```

### 2. Use Consistent Naming

✅ **Do:**
- Uppercase symbols: `EURUSD`, `GBPUSD`
- ISO dates: `2024-01-01`
- Year-based files: `2024.parquet`

❌ **Don't:**
- Mixed case: `EurUsd`, `eurUSD`
- Non-standard dates: `01-01-2024`, `Jan2024`
- Unclear names: `data1.parquet`, `ticks_final_v2.parquet`

### 3. Document Your Schema

✅ **Do:**
- Include metadata.json in each symbol directory
- Embed metadata in Parquet files
- Version control your schema

### 4. Test Before Seeding

✅ **Do:**
```bash
# Always dry-run first
python scripts/seed_historical_data.py --dry-run

# Test with small dataset
python scripts/seed_historical_data.py --pairs EURUSD --years 2024-2024
```

### 5. Monitor Disk Space

✅ **Do:**
```bash
# Check before large operations
df -h

# Clean up temp files regularly
rm -rf /tmp/dukascopy_*

# Use compression
```

---

## Next Steps

1. **Complete Data Collection**
   - Follow [DUKASCOPY_DATA_COLLECTION.md](DUKASCOPY_DATA_COLLECTION.md)
   - Verify all 28 pairs collected

2. **Configure DVC Remote**
   - Choose storage provider (S3/GCS/NAS)
   - Set up credentials
   - Test push/pull

3. **Test Seeding Pipeline**
   - Dry run with validation
   - Seed small dataset
   - Verify database performance

4. **Automate Backups**
   - Schedule DVC pushes
   - Set up NAS sync
   - Create offline snapshots

5. **Monitor & Maintain**
   - Track storage growth
   - Update data monthly
   - Validate integrity regularly

---

**Questions or Issues?**

- Check logs: `logs/seed_historical_data.log`
- Verify storage: `du -sh data/dukascopy/`
- Test integrity: `python scripts/validate_parquet_data.py`
- Create GitHub issue with details
