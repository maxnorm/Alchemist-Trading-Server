# GCP Deployment Scripts

Helper scripts to automate Google Cloud Platform deployment for Dukascopy data collection.

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

### 2. `upload-files.sh` - Upload Project Files
Uploads your collection script and config files to the VM.

**Usage:**
```bash
./scripts/gcp/upload-files.sh
```

**What it uploads:**
- `scripts/backfill_dukascopy_data.py`
- `params.yaml`
- `package.json`
- `requirements.txt` (if exists)

**Time:** ~1-2 minutes

---

### 3. `start-collection.sh` - Start Data Collection
Starts the data collection process on the VM.

**Usage:**
```bash
./scripts/gcp/start-collection.sh
```

**What it does:**
- Calculates date range (5 years back by default)
- Starts collection in a screen session (runs in background)
- Saves logs to `/data/logs/`

**Time:** Collection runs for 2-3 days

**Monitor progress:**
```bash
gcloud compute ssh dukascopy-collector --zone=us-central1-a \
    --command="tail -f /data/logs/dukascopy_backfill.log"
```

---

### 4. `download-data.sh` - Download to Local
Downloads collected data from GCS to your local machine.

**Usage:**
```bash
./scripts/gcp/download-data.sh
```

**What it downloads:**
- All Parquet files from GCS bucket
- Collection logs

**Output:** `./data/dukascopy/` (or custom `LOCAL_DIR`)

**Time:** Depends on your internet speed (~1-3 hours for 175GB)

---

### 5. `cleanup.sh` - Clean Up Resources
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

### Quick Start (Automated)

```bash
# 1. Setup VM and bucket
./scripts/gcp/setup-vm.sh

# 2. Wait 2-3 minutes for VM setup, then upload files
./scripts/gcp/upload-files.sh

# 3. Start collection
./scripts/gcp/start-collection.sh

# 4. Monitor (optional, collection runs in background)
gcloud compute ssh dukascopy-collector --zone=us-central1-a \
    --command="tail -f /data/logs/dukascopy_backfill.log"

# 5. After 2-3 days, download data
./scripts/gcp/download-data.sh

# 6. Clean up (optional)
./scripts/gcp/cleanup.sh
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
