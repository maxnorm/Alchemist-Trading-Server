# GCP Deployment Scripts

Helper scripts to automate Google Cloud Platform deployment for Dukascopy data collection.

**Reliability & cost:** See [RELIABILITY_AND_COST.md](./RELIABILITY_AND_COST.md) for cost control (e.g. staying within free credit) and a checklist so collection runs reliably without filling the root disk.

## Prerequisites

1. **Google Cloud SDK installed**
   ```bash
   # Verify installation
   gcloud --version
   ```

2. **Authenticated with GCP**
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```

3. **Required APIs enabled**
   ```bash
   gcloud services enable compute.googleapis.com storage-component.googleapis.com
   ```

## Scripts Overview

### 1. `setup-vm.sh` - Initial Setup
Creates the VM, GCS bucket, and installs required software.

**Usage:**
```bash
./scripts/gcp/setup-vm.sh
```

**What it does:**
- Enables required GCP APIs
- Creates GCS bucket for data storage
- Creates VM with 500GB data disk
- Installs Python, Node.js, and dependencies
- Sets up data directories

**Time:** ~5-10 minutes

---

### 2. `upload-files.sh` - Upload Collection Script
Uploads only the essential collection script to the VM.

**Usage:**
```bash
./scripts/gcp/upload-files.sh
```

**What it uploads:**
- `scripts/backfill_dukascopy_data.py` (required)
- `scripts/utils/parquet_converter.py` (if exists, utility used by script)

**Note:** The script doesn't need `params.yaml` or other config files - it uses command-line arguments.

**Time:** ~30 seconds

---

### 3. `start-collection.sh` - Start Data Collection
Starts the data collection process on the VM.

**Usage:**
```bash
# Default: Last 5 years, all pairs
./scripts/gcp/start-collection.sh

# Test with one day (recommended first!)
./scripts/gcp/start-collection.sh --start-date 2024-01-15 --end-date 2024-01-15

# Test with custom date range
./scripts/gcp/start-collection.sh --start-date 2024-01-01 --end-date 2024-01-07

# Specific pairs only (comma-separated, no spaces)
./scripts/gcp/start-collection.sh --pairs EURUSD,GBPUSD,USDJPY --start-date 2024-01-01 --end-date 2024-12-31

# Custom date range for full collection
./scripts/gcp/start-collection.sh --start-date 2020-01-01 --end-date 2024-12-31

# Show help
./scripts/gcp/start-collection.sh --help
```

**What it does:**
- Calculates date range (5 years back by default, or uses provided dates)
- Starts collection in a screen session (runs in background)
- Saves logs to `/data/logs/`

**Time:** 
- 1 day: ~10-30 minutes
- 1 week: ~2-4 hours
- 5 years: 2-3 days

**Monitor progress:**
```bash
gcloud compute ssh dukascopy-collector --zone=us-central1-a \
    --command="tail -f /data/logs/dukascopy_backfill.log"

gcloud compute ssh dukascopy-collector --zone=us-central1-a
screen -r dukascopy-collection
```

---

### 4. `upload-to-gcs.sh` - Upload to GCS Storage (Optional)
Uploads collected data from VM to GCS bucket. Run this after collection or periodically during long collections.

**Usage:**
```bash
./scripts/gcp/upload-to-gcs.sh
```

**What it does:**
- Uploads Parquet files from VM to GCS
- Uploads logs and progress files
- Uses `gsutil rsync` (only uploads new/changed files)

**When to use:**
- After collection completes
- Periodically during long collections (backup)
- Before downloading data

**Time:** Depends on data size (~5-10 minutes for one day, ~1-2 hours for 5 years)

### 5. `download-data.sh` - Download Data
Downloads collected data from GCS storage to your local machine.

**Usage:**
```bash
# Download all data from GCS (~130-175GB)
./scripts/gcp/download-data.sh

# Download specific pair (for testing)
./scripts/gcp/download-data.sh --pair EURUSD

# Show help
./scripts/gcp/download-data.sh --help
```

**Alternative: Download directly from VM (faster for small tests)**
```bash
gcloud compute scp --zone=us-central1-a --recurse \
    dukascopy-collector:/data/dukascopy/ ./data/dukascopy/
```

**What it downloads:**
- Parquet files (all or specific pair)
- Collection logs

**Output:** `./data/dukascopy/` (or custom `LOCAL_DIR`)

**Time:** 
- One pair: ~5-10 minutes
- Full download: ~1-3 hours for 175GB

---

### 6. `cleanup.sh` - Clean Up Resources
Stops/deletes VM and optionally deletes GCS bucket.

**Usage:**
```bash
./scripts/gcp/cleanup.sh
```

**What it does:**
- Stops or deletes the VM
- Optionally deletes GCS bucket (WARNING: deletes all data!)

**When to use:**
- After downloading data locally
- To stop paying for VM
- To clean up test deployments

---

## Complete Workflow

### Quick Start (Recommended: Test First!)

```bash
# 1. Setup VM and bucket (~5 minutes)
./scripts/gcp/setup-vm.sh

# 2. Wait 2-3 minutes for VM setup, then upload script (~30 seconds)
./scripts/gcp/upload-files.sh

# 3. TEST with one day first! (~10-30 minutes)
./scripts/gcp/start-collection.sh --start-date 2024-01-15 --end-date 2024-01-15

# 4. After test completes, verify data works, then start full collection
./scripts/gcp/start-collection.sh

# 5. Monitor progress (optional)
gcloud compute ssh dukascopy-collector --zone=us-central1-a \
    --command="tail -f /data/logs/dukascopy_backfill.log"

# 6. After collection completes, upload to GCS (optional, ~1-2 hours)
./scripts/gcp/upload-to-gcs.sh

# 7. Download data (from GCS or directly from VM)
./scripts/gcp/download-data.sh  # From GCS
# OR download directly from VM:
# gcloud compute scp --zone=us-central1-a --recurse \
#     dukascopy-collector:/data/dukascopy/ ./data/dukascopy/

# 8. Clean up resources (optional)
./scripts/gcp/cleanup.sh
```

**What gets uploaded?**
- Only the collection script (`backfill_dukascopy_data.py`)
- No config files needed - script uses command-line arguments

### Testing Workflow

**Before running 5 years of collection, test with a small date range:**

```bash
# Test with one day
./scripts/gcp/start-collection.sh --start-date 2024-01-15 --end-date 2024-01-15

# Or test with one week
./scripts/gcp/start-collection.sh --start-date 2024-01-01 --end-date 2024-01-07

# Wait for completion, then verify data
# Option 1: Download from VM directly (faster for testing)
gcloud compute scp --zone=us-central1-a --recurse \
    dukascopy-collector:/data/dukascopy/ ./data/dukascopy/

# Option 2: Upload to GCS then download (tests full pipeline)
./scripts/gcp/upload-to-gcs.sh
./scripts/gcp/download-data.sh --pair EURUSD

# Verify data
python3 -c "import pandas as pd; df = pd.read_parquet('data/dukascopy/EURUSD/2024.parquet'); print(f'Rows: {len(df):,}')"
```

### Manual Steps (If Scripts Don't Work)

See the detailed guide: `docs/GCP_DUKASCOPY_DEPLOYMENT_BEGINNER.md`

---

## Configuration

### Environment Variables

You can customize behavior with environment variables:

```bash
# VM configuration
export VM_NAME="my-custom-vm"
export ZONE="europe-west1-a"
export MACHINE_TYPE="e2-standard-8"

# Disk configuration (to avoid quota issues)
export DATA_DISK_SIZE=500        # Size in GB (default: 500)
export DATA_DISK_TYPE=pd-standard  # pd-standard or pd-ssd (default: pd-standard)

# Collection configuration
export YEARS_BACK=10  # Collect 10 years instead of 5

# Download configuration
export LOCAL_DIR="./my-data"  # Custom download location
```

### Example: Custom Zone

```bash
export ZONE="europe-west1-a"
./scripts/gcp/setup-vm.sh
```

---

## Cloud VM: Avoiding root disk fill

On a cloud VM, the **root disk** (e.g. 50GB) can fill up if the Dukascopy backfill writes cache and temp files there. Use these mitigations so all bulk I/O goes to the **data disk** (`/data`).

| Mitigation | What it does |
|------------|--------------|
| **Separate data disk** | Attach a large disk as `/data` (e.g. 500GB). Keep root small; never put bulk data on root. |
| **`--cache-dir /data/.dukascopy-cache`** | Puts dukascopy-node’s .bi5 cache on `/data`. Scripts pass this by default. |
| **`--temp-dir /data/tmp`** | Puts download temp (JSON) on `/data`. Scripts pass this by default. |
| **`TMPDIR=/data/tmp`** | Ensures Node/npm and other subprocesses use `/data` for temp. Set in start/restart scripts. |
| **Create dirs before run** | `mkdir -p /data/dukascopy /data/logs /data/tmp /data/.dukascopy-cache` so everything exists on `/data`. |

**Checklist when starting collection on a VM:**

1. Ensure `/data` is mounted (separate disk) and has space: `df -h /data`
2. Use the provided scripts (`start-collection.sh`, `quick-restart.sh`, `restart-collection.sh`) — they set `TMPDIR`, `--cache-dir`, and `--temp-dir` for you
3. (Optional) Monitor root usage: `df -h /` — if it grows during collection, something is still writing to root; fix with the options above

**If root already filled:** free space (remove/move `.dukascopy-cache` and `/tmp/dukascopy_*`), then redeploy the script and restart with the scripts above so future runs use `/data`.

---

## Troubleshooting

### Script Fails: "Permission denied"

**Solution:**
```bash
# Make scripts executable (Linux/Mac)
chmod +x scripts/gcp/*.sh

# Or run with bash explicitly
bash scripts/gcp/setup-vm.sh
```

### Script Fails: "VM already exists"

**Solution:**
- Script will ask if you want to delete and recreate
- Or manually delete: `gcloud compute instances delete dukascopy-collector --zone=us-central1-a`

### Script Fails: "Bucket already exists"

**Solution:**
- Script will skip bucket creation if it exists
- This is safe - existing bucket will be used

### Can't Connect to VM

**Solution:**
```bash
# Check VM status
gcloud compute instances describe dukascopy-collector --zone=us-central1-a

# Check if VM is running
gcloud compute instances list

# Start VM if stopped
gcloud compute instances start dukascopy-collector --zone=us-central1-a
```

---

## Cost Monitoring

### Check Current Costs

```bash
# View VM usage
gcloud compute instances describe dukascopy-collector --zone=us-central1-a \
    --format="get(status, creationTimestamp)"

# View bucket size
gsutil du -sh gs://dukascopy-data-$(gcloud config get-value project)
```

### Estimated Costs

- **VM (3 days):** ~$30-40
- **GCS Storage (200GB):** ~$5/month
- **Network egress:** $0 (within GCP), ~$20-30 (to your computer)

**Total:** ~$30-40 one-time + $5/month (if keeping bucket)

---

## Next Steps

After downloading data:

1. **Validate data:**
   ```bash
   python scripts/validate_parquet_data.py --data-dir ./data/dukascopy --summary
   ```

2. **Upload to another provider** (if needed):
   - See `docs/GCP_DUKASCOPY_DEPLOYMENT_BEGINNER.md` section "Future: Re-uploading to Another Provider"

3. **Use in your system:**
   - Seed into database: `python scripts/seed_historical_data.py --data-dir ./data/dukascopy`

---

## Additional Resources

- **Beginner Guide:** `docs/GCP_DUKASCOPY_DEPLOYMENT_BEGINNER.md`
- **Advanced Guide:** `docs/GCP_DUKASCOPY_DEPLOYMENT.md`
- **GCP Documentation:** https://cloud.google.com/docs

---

## Support

If scripts fail:
1. Check error messages
2. Review troubleshooting section
3. See detailed guide: `docs/GCP_DUKASCOPY_DEPLOYMENT_BEGINNER.md`
4. Check GCP console: https://console.cloud.google.com
