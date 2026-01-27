# Dukascopy Historical Data Collection - Quick Start

This README provides a quick reference for collecting Dukascopy historical data using **standalone scripts** (no trading server dependencies).

For comprehensive documentation, see:
- **[DUKASCOPY_DATA_COLLECTION.md](../docs/DUKASCOPY_DATA_COLLECTION.md)** - Complete collection guide
- **[DATA_STORAGE_STRATEGY.md](../docs/DATA_STORAGE_STRATEGY.md)** - Storage and deployment strategy

---

## Prerequisites

```bash
# 1. Install Python dependencies (standalone - NO trading server needed)
pip install pandas pyarrow numpy

# 2. Install dukascopy-node (local installation recommended)
npm install dukascopy-node

# Alternative: Install globally
# npm install -g dukascopy-node
```

---

## Quick Test (Recommended First Step)

Test with a single pair and recent data:

```bash
# Step 1: Download EURUSD for 2024 (test run)
python scripts/backfill_dukascopy_data.py \
    --pairs EURUSD \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --output-dir data/dukascopy

# Expected:
# - Runtime: 2-4 hours
# - Output: data/dukascopy/EURUSD/*.parquet
# - Size: ~10-20GB
# - Progress: data/.dukascopy_progress.json

# Step 2: Validate the data
python scripts/validate_parquet_data.py \
    --data-dir data/dukascopy \
    --summary

# Expected:
# ✓ EURUSD: PASS | 125,843,297 ticks | 0 issues, 0 warnings
```

**Verify Output:**

```bash
# Check files
ls data/dukascopy/EURUSD/

# Count ticks
python -c "import pandas as pd; df = pd.read_parquet('data/dukascopy/EURUSD/2024.parquet'); print(f'{len(df):,} ticks')"

# Check progress
cat data/.dukascopy_progress.json
```

---

## Full Collection (All 28 Pairs, All History)

**Warning:** This will take 2-4 weeks and download ~600-900GB of data!

```bash
# Run full collection (overnight recommended)
python scripts/backfill_dukascopy_data.py \
    --output-dir data/dukascopy \
    --batch-size 3 \
    --pause-ms 5000

# Or use DVC pipeline
dvc repro collect_dukascopy
```

**Monitor Progress:**

```bash
# Watch logs
tail -f logs/dukascopy_backfill.log

# Check files created
find data/dukascopy -name "*.parquet" | wc -l

# Check total size
du -sh data/dukascopy/
```

---

## Resume After Failure

The script uses JSON-based progress tracking:

```bash
# Progress is saved in data/.dukascopy_progress.json

# Resume from last checkpoint (automatic)
python scripts/backfill_dukascopy_data.py \
    --resume \
    --output-dir data/dukascopy

# Check progress file
cat data/.dukascopy_progress.json
```

**Progress File Format:**
```json
{
  "EURUSD": {
    "2024": {
      "status": "completed",
      "file_path": "data/dukascopy/EURUSD/2024.parquet",
      "completed_at": "2026-01-17T15:30:00Z"
    }
  }
}
```

---

## Seed Data into Database

**Important:** Seeding requires the full Docker environment with all trading server dependencies.

The collection script runs **standalone** (minimal dependencies), but seeding requires Docker.

```bash
# Ensure database is running
docker compose up -d postgres

# Seed all data (runs in Docker environment)
python scripts/seed_historical_data.py \
    --data-dir data/dukascopy

# Or specific pairs/years
python scripts/seed_historical_data.py \
    --data-dir data/dukascopy \
    --pairs EURUSD,GBPUSD \
    --years 2022-2024

# Dry run (validation only)
python scripts/seed_historical_data.py \
    --data-dir data/dukascopy \
    --dry-run
```

**Note:** If you get import errors, the seeding script needs to run inside Docker or with the full trading server environment installed.

**Performance:**
- ~10,000 inserts/second
- Full dataset (~28 pairs, 20 years) = ~8-16 hours

---

## DVC Workflow

### Setup

```bash
# Configure remote storage
dvc remote add -d dukascopy_storage s3://your-bucket/dukascopy

# Set credentials
dvc remote modify dukascopy_storage access_key_id YOUR_KEY
dvc remote modify dukascopy_storage secret_access_key YOUR_SECRET
```

### Track Data

```bash
# Add data to DVC
dvc add data/dukascopy

# Commit tracking file
git add data/dukascopy.dvc data/.gitignore
git commit -m "Add Dukascopy historical data"

# Push to remote
dvc push  # Uploads ~700GB (first time)
```

### Retrieve Data

```bash
# On new machine
git clone <repo>
dvc pull  # Downloads ~700GB

# Data now in data/dukascopy/
```

---

## Docker Deployment with Seeding

### Step 1: Configure Environment

```bash
# Edit .env
SEED_HISTORICAL_DATA=true
```

### Step 2: Update docker-compose.yml

Uncomment the volume mount:

```yaml
postgres:
  volumes:
    - "./data/dukascopy:/data/dukascopy:ro"
```

### Step 3: Start Containers

```bash
# Start with seeding enabled
docker compose up -d

# Monitor progress
docker compose logs -f postgres
tail -f logs/seed_historical_data.log
```

**Note:** Seeding runs once on database initialization. To re-seed, remove the postgres volume.

---

## Troubleshooting

### dukascopy-node not found

```bash
# Install globally
npm install -g dukascopy-node

# Or just ensure Node.js is installed (script uses npx)
node --version
```

### Rate limited (429 errors)

```bash
# Stop download
Ctrl+C

# Wait 1 hour

# Resume with slower settings
python scripts/backfill_dukascopy_data.py \
    --resume \
    --batch-size 2 \
    --pause-ms 8000
```

### Out of disk space

```bash
# Check space
df -h

# Clean temp files
rm -rf /tmp/dukascopy_*

# Use external drive
python scripts/backfill_dukascopy_data.py \
    --output-dir /mnt/external/dukascopy
```

---

## File Structure

```
scripts/
├── backfill_dukascopy_data.py    # STANDALONE: Data collection (no trading server deps)
├── validate_parquet_data.py      # STANDALONE: Statistical validation
├── seed_historical_data.py        # DOCKER: Database seeding (full environment)
├── docker-entrypoint-seed.sh      # Docker seeding hook
└── utils/
    └── parquet_converter.py       # STANDALONE: JSON to Parquet converter

data/
├── .dukascopy_progress.json       # Progress tracking (JSON file)
├── validation_report.json         # Validation results (optional)
└── dukascopy/
    ├── EURUSD/
    │   ├── 2003.parquet
    │   ├── 2004.parquet
    │   ├── ...
    │   ├── 2024.parquet
    │   └── metadata.json
    └── GBPUSD/
        └── ...

docs/
├── DUKASCOPY_DATA_COLLECTION.md   # Comprehensive guide
└── DATA_STORAGE_STRATEGY.md       # Storage strategy
```

**Key Point:** Collection/validation run standalone. Seeding runs in Docker.

---

## Common Commands Reference

```bash
# === COLLECTION (Standalone - minimal deps) ===

# Test with single pair
python scripts/backfill_dukascopy_data.py \
    --pairs EURUSD \
    --start-date 2024-01-01 \
    --end-date 2024-12-31

# Full collection (all 28 pairs)
python scripts/backfill_dukascopy_data.py \
    --output-dir data/dukascopy

# Resume after failure
python scripts/backfill_dukascopy_data.py --resume

# Dry run (validate parameters)
python scripts/backfill_dukascopy_data.py --dry-run


# === VALIDATION (Standalone - minimal deps) ===

# Validate all data
python scripts/validate_parquet_data.py \
    --data-dir data/dukascopy \
    --summary

# Generate detailed report
python scripts/validate_parquet_data.py \
    --data-dir data/dukascopy \
    --report validation_report.json

# Validate specific pair
python scripts/validate_parquet_data.py \
    --data-dir data/dukascopy \
    --pair EURUSD


# === SEEDING (Requires Docker) ===

# Seed into database
python scripts/seed_historical_data.py \
    --data-dir data/dukascopy

# Seed specific pairs/years
python scripts/seed_historical_data.py \
    --data-dir data/dukascopy \
    --pairs EURUSD,GBPUSD \
    --years 2022-2024


# === DVC WORKFLOW (Optional) ===

# Track data with DVC
dvc add data/dukascopy && dvc push

# Pull on new machine
dvc pull
```

---

## Support

- **Full Documentation:** [DUKASCOPY_DATA_COLLECTION.md](../docs/DUKASCOPY_DATA_COLLECTION.md)
- **Storage Guide:** [DATA_STORAGE_STRATEGY.md](../docs/DATA_STORAGE_STRATEGY.md)
- **Logs:** `logs/dukascopy_backfill.log` and `logs/seed_historical_data.log`
- **Issues:** Create GitHub issue with command, error, and log excerpts

---

## Next Steps

1. ✅ Install minimal dependencies: `pip install pandas pyarrow numpy`
2. ✅ Install dukascopy-node: `npm install dukascopy-node`
3. ✅ Test with single pair: `python scripts/backfill_dukascopy_data.py --pairs EURUSD --start-date 2024-01-01 --end-date 2024-12-31`
4. ✅ Validate data: `python scripts/validate_parquet_data.py --data-dir data/dukascopy --summary`
5. ⏳ Configure DVC remote storage (optional)
6. ⏳ Run full collection (overnight, 2-4 weeks for all pairs)
7. ⏳ Seed data into database (Docker environment)
8. ⏳ Test deployment with Docker seeding

**Ready to start?** Begin with step 3 above!
