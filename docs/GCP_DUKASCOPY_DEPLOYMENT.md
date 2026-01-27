# Google Cloud Deployment Guide: Dukascopy Data Collection

**Last Updated:** January 17, 2026  
**Purpose:** Complete guide for deploying Dukascopy historical data collection to Google Cloud Platform

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Cost Estimates](#cost-estimates)
4. [Prerequisites](#prerequisites)
5. [Step-by-Step Deployment](#step-by-step-deployment)
6. [Automation Scripts](#automation-scripts)
7. [Monitoring & Offloading](#monitoring--offloading)
8. [Troubleshooting](#troubleshooting)
9. [Cleanup](#cleanup)

---

## Overview

This guide covers deploying the Dukascopy historical data collection script to Google Cloud Platform to collect **5 years of historical data for all 28 supported currency pairs**.

**What You'll Deploy:**
- GCP Compute Engine VM (Ubuntu 22.04)
- Automated data collection script
- Google Cloud Storage bucket for data offloading
- Monitoring and progress tracking

**Collection Scope:**
- **28 currency pairs** (6 majors + 22 crosses)
- **5 years of history** (2020-2024, or last 5 years from today)
- **Estimated time:** 2-3 days (sequential download)
- **Final data size:** ~130-175GB (compressed Parquet)

**Why Google Cloud?**
- Use existing GCP credits
- High-bandwidth connection for fast downloads
- Persistent storage with GCS
- Easy automation and monitoring
- Cost-effective for one-time bulk collection

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Google Cloud Platform                 │
│                                                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │     Compute Engine VM (e2-standard-4)           │   │
│  │  ┌────────────────────────────────────────────┐  │   │
│  │  │  Ubuntu 22.04 LTS                         │  │   │
│  │  │  - Python 3.11+                           │  │   │
│  │  │  - Node.js 20+                            │  │   │
│  │  │  - dukascopy-node CLI                      │  │   │
│  │  │  - Collection script                       │  │   │
│  │  └────────────────────────────────────────────┘  │   │
│  │                                                  │   │
│  │  ┌────────────────────────────────────────────┐  │   │
│  │  │  500GB Persistent Disk (SSD)               │  │   │
│  │  │  - Temp JSON files (~200-300GB)            │  │   │
│  │  │  - Final Parquet files (~130-175GB)        │  │   │
│  │  │  - Logs and progress files                 │  │   │
│  │  └────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Google Cloud Storage Bucket                     │   │
│  │  - Final Parquet files (offloaded)                │   │
│  │  - Progress snapshots                             │   │
│  │  - Collection logs                                │   │
│  └──────────────────────────────────────────────────┘   │
│                                                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Cloud Logging & Monitoring                        │   │
│  │  - Collection progress                            │   │
│  │  - Error alerts                                   │   │
│  │  - Resource usage                                 │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**Data Flow:**
1. VM downloads data from Dukascopy → Temp JSON files
2. Script converts JSON → Parquet files
3. Parquet files uploaded to GCS bucket
4. Cleanup: Delete temp files and VM (optional)

---

## Cost Estimates

### One-Time Collection (2-3 days)

| Resource | Specification | Duration | Cost |
|----------|--------------|----------|------|
| **Compute Engine** | e2-standard-4 (4 vCPU, 16GB RAM) | 3 days | ~$15-20 |
| **Persistent Disk** | 500GB SSD | 3 days | ~$7-10 |
| **Network Egress** | ~200GB to GCS (free within GCP) | - | $0 |
| **GCS Storage** | 200GB Standard storage | 1 month | ~$5 |
| **Total One-Time** | | | **~$27-35** |

### Ongoing Storage (Optional)

| Resource | Monthly Cost |
|----------|--------------|
| GCS Storage (200GB Standard) | ~$5/month |
| GCS Operations (minimal) | ~$0.10/month |
| **Total Monthly** | **~$5/month** |

### Cost Optimization Tips

1. **Use Preemptible VMs** (if available): Save ~80% on compute costs
2. **Delete VM after collection**: Only pay for storage
3. **Use Nearline/Coldline storage**: Cheaper for long-term archival
4. **Regional storage**: Keep data in same region as VM (free egress)

**Estimated Total with GCP Credits:** Effectively **$0** if you have sufficient credits!

---

## Prerequisites

### 1. Google Cloud Account Setup

```bash
# Install Google Cloud SDK (if not already installed)
# https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth login

# Set default project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable compute.googleapis.com
gcloud services enable storage-component.googleapis.com
gcloud services enable logging.googleapis.com
```

### 2. Local Requirements

- Google Cloud SDK (`gcloud` CLI)
- Git (to clone repository)
- SSH key pair (for VM access)

### 3. GCP Project Setup

```bash
# Create project (if needed)
gcloud projects create dukascopy-data-collection \
    --name="Dukascopy Data Collection"

# Set billing account
gcloud billing projects link dukascopy-data-collection \
    --billing-account=YOUR_BILLING_ACCOUNT_ID

# Set as default project
gcloud config set project dukascopy-data-collection
```

---

## Step-by-Step Deployment

### Step 1: Create GCS Bucket

```bash
# Set variables
PROJECT_ID=$(gcloud config get-value project)
BUCKET_NAME="dukascopy-data-${PROJECT_ID}"
REGION="us-central1"  # Choose your preferred region

# Create bucket
gsutil mb -p ${PROJECT_ID} -c STANDARD -l ${REGION} gs://${BUCKET_NAME}

# Set lifecycle policy (optional: auto-delete after 90 days)
cat > lifecycle.json <<EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 90}
      }
    ]
  }
}
EOF
gsutil lifecycle set lifecycle.json gs://${BUCKET_NAME}
rm lifecycle.json

echo "Bucket created: gs://${BUCKET_NAME}"
```

### Step 2: Create Startup Script

Create a startup script that will automatically set up the VM:

```bash
# Save as: scripts/gcp/startup-script.sh
cat > scripts/gcp/startup-script.sh <<'SCRIPT_EOF'
#!/bin/bash
set -e

# Log everything
exec > >(tee -a /var/log/dukascopy-setup.log)
exec 2>&1

echo "=== Dukascopy Data Collection Setup ==="
echo "Started at: $(date)"

# Update system
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3.11 python3-pip python3-venv nodejs npm git curl

# Install Node.js 20+ (if not latest)
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# Verify installations
python3 --version
node --version
npm --version

# Clone repository (or copy files)
# Option 1: Clone from GitHub
# git clone https://github.com/YOUR_REPO/trading-system.git /opt/trading-system

# Option 2: Copy from local machine (see Step 3)
# Files should be in /tmp/repo-files/

# Install Python dependencies
cd /opt/trading-system || cd /tmp/repo-files
pip3 install pandas pyarrow numpy

# Install dukascopy-node
npm install dukascopy-node

# Create data directories
mkdir -p /data/dukascopy
mkdir -p /data/logs
chmod 755 /data/dukascopy
chmod 755 /data/logs

# Create collection script wrapper
cat > /usr/local/bin/run-collection.sh <<'EOF'
#!/bin/bash
cd /opt/trading-system || cd /tmp/repo-files

# Calculate date range (5 years back)
END_DATE=$(date +%Y-%m-%d)
START_DATE=$(date -d "5 years ago" +%Y-%m-%d)

# Run collection
python3 scripts/backfill_dukascopy_data.py \
    --start-date ${START_DATE} \
    --end-date ${END_DATE} \
    --output-dir /data/dukascopy \
    --batch-size 3 \
    --pause-ms 5000 \
    --compression snappy \
    --verbose

echo "Collection completed at: $(date)"
EOF

chmod +x /usr/local/bin/run-collection.sh

# Create offload script
cat > /usr/local/bin/offload-to-gcs.sh <<'EOF'
#!/bin/bash
BUCKET_NAME="${BUCKET_NAME:-dukascopy-data}"
REGION="${REGION:-us-central1}"

echo "Offloading data to gs://${BUCKET_NAME}..."

# Upload Parquet files
gsutil -m cp -r /data/dukascopy/*.parquet gs://${BUCKET_NAME}/parquet/ || true
gsutil -m cp -r /data/dukascopy/*/*.parquet gs://${BUCKET_NAME}/parquet/ || true

# Upload logs
gsutil cp /data/logs/*.log gs://${BUCKET_NAME}/logs/ || true
gsutil cp /data/.dukascopy_progress.json gs://${BUCKET_NAME}/logs/ || true

# Upload progress file
if [ -f /data/.dukascopy_progress.json ]; then
    gsutil cp /data/.dukascopy_progress.json gs://${BUCKET_NAME}/logs/
fi

echo "Offload completed at: $(date)"
EOF

chmod +x /usr/local/bin/offload-to-gcs.sh

# Set bucket name in environment
echo "export BUCKET_NAME=${BUCKET_NAME}" >> /etc/environment

echo "=== Setup completed at: $(date) ==="
SCRIPT_EOF

chmod +x scripts/gcp/startup-script.sh
```

### Step 3: Create VM Instance

```bash
# Set variables
PROJECT_ID=$(gcloud config get-value project)
BUCKET_NAME="dukascopy-data-${PROJECT_ID}"
REGION="us-central1"
ZONE="us-central1-a"
VM_NAME="dukascopy-collector"
IMAGE_FAMILY="ubuntu-2204-lts"
IMAGE_PROJECT="ubuntu-os-cloud"

# Create startup script with bucket name
cat > /tmp/startup-script.sh <<EOF
#!/bin/bash
set -e
exec > >(tee -a /var/log/dukascopy-setup.log)
exec 2>&1

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3.11 python3-pip python3-venv nodejs npm git curl

curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# Install dependencies
pip3 install pandas pyarrow numpy
npm install -g dukascopy-node

# Create directories
mkdir -p /data/dukascopy /data/logs
chmod 755 /data/dukascopy /data/logs

# Download repository (you'll upload files separately)
# Or clone from GitHub if public
EOF

# Create VM with startup script
gcloud compute instances create ${VM_NAME} \
    --project=${PROJECT_ID} \
    --zone=${ZONE} \
    --machine-type=e2-standard-4 \
    --network-interface=network-tier=PREMIUM,stack-type=IPV4_ONLY,subnet=default \
    --maintenance-policy=MIGRATE \
    --provisioning-model=STANDARD \
    --service-account=$(gcloud iam service-accounts list --filter="displayName:Compute Engine default service account" --format="value(email)") \
    --scopes=https://www.googleapis.com/auth/cloud-platform \
    --tags=http-server,https-server \
    --create-disk=auto-delete=yes,boot=yes,device-name=${VM_NAME},image=projects/${IMAGE_PROJECT}/global/images/family/${IMAGE_FAMILY},mode=rw,size=50,type=projects/${PROJECT_ID}/zones/${ZONE}/diskTypes/pd-standard \
    --create-disk=auto-delete=yes,device-name=data-disk,mode=rw,size=500,type=projects/${PROJECT_ID}/zones/${ZONE}/diskTypes/pd-ssd \
    --metadata-from-file=startup-script=/tmp/startup-script.sh \
    --metadata=BUCKET_NAME=${BUCKET_NAME}

echo "VM created: ${VM_NAME}"
echo "Waiting for VM to be ready..."
sleep 30
```

### Step 4: Upload Repository Files

```bash
# Get VM external IP
VM_IP=$(gcloud compute instances describe ${VM_NAME} \
    --zone=${ZONE} \
    --format="get(networkInterfaces[0].accessConfigs[0].natIP)")

# Create SSH key if needed
if [ ! -f ~/.ssh/gcp_dukascopy ]; then
    ssh-keygen -t rsa -b 4096 -f ~/.ssh/gcp_dukascopy -N ""
fi

# Add SSH key to VM (one-time setup)
gcloud compute instances add-metadata ${VM_NAME} \
    --zone=${ZONE} \
    --metadata-from-file=ssh-keys=<(echo "$(cat ~/.ssh/gcp_dukascopy.pub)")

# Upload project files
# Option 1: Use gcloud compute scp
gcloud compute scp \
    --zone=${ZONE} \
    --recurse \
    scripts/ \
    params.yaml \
    package.json \
    requirements.txt \
    ${VM_NAME}:/opt/trading-system/

# Option 2: Use rsync over SSH (after initial setup)
# rsync -avz -e "gcloud compute ssh ${VM_NAME} --zone=${ZONE} --command" \
#     --exclude='.git' \
#     --exclude='node_modules' \
#     --exclude='__pycache__' \
#     ./ ${VM_NAME}:/opt/trading-system/
```

### Step 5: SSH into VM and Complete Setup

```bash
# SSH into VM
gcloud compute ssh ${VM_NAME} --zone=${ZONE}

# Once inside VM:
cd /opt/trading-system

# Install dukascopy-node locally (if not global)
npm install dukascopy-node

# Verify installation
npx dukascopy-node --help

# Test with small download
python3 scripts/backfill_dukascopy_data.py \
    --pairs EURUSD \
    --start-date 2024-01-01 \
    --end-date 2024-01-02 \
    --output-dir /data/dukascopy \
    --dry-run
```

### Step 6: Mount Data Disk

```bash
# Inside VM, mount the 500GB data disk
sudo mkfs.ext4 -m 0 -E lazy_itable_init=0,lazy_journal_init=0,discard /dev/disk/by-id/google-data-disk
sudo mkdir -p /data
sudo mount -o discard,defaults /dev/disk/by-id/google-data-disk /data
sudo chmod a+w /data

# Add to /etc/fstab for persistence
echo UUID=$(sudo blkid -s UUID -o value /dev/disk/by-id/google-data-disk) /data ext4 discard,defaults,nofail 0 2 | sudo tee -a /etc/fstab

# Create directories
sudo mkdir -p /data/dukascopy /data/logs
sudo chown $USER:$USER /data/dukascopy /data/logs
```

### Step 7: Start Collection

```bash
# Calculate 5 years back from today
END_DATE=$(date +%Y-%m-%d)
START_DATE=$(date -d "5 years ago" +%Y-%m-%d)

# Start collection in screen/tmux session
screen -S dukascopy-collection

# Run collection
cd /opt/trading-system
python3 scripts/backfill_dukascopy_data.py \
    --start-date ${START_DATE} \
    --end-date ${END_DATE} \
    --output-dir /data/dukascopy \
    --batch-size 3 \
    --pause-ms 5000 \
    --compression snappy \
    --verbose

# Detach: Ctrl+A, then D
# Reattach later: screen -r dukascopy-collection
```

### Step 8: Monitor Progress

```bash
# From local machine, SSH and check progress
gcloud compute ssh ${VM_NAME} --zone=${ZONE} --command="tail -f /data/logs/dukascopy_backfill.log"

# Or check progress file
gcloud compute ssh ${VM_NAME} --zone=${ZONE} --command="cat /data/.dukascopy_progress.json | python3 -m json.tool"

# Check disk usage
gcloud compute ssh ${VM_NAME} --zone=${ZONE} --command="df -h /data"

# Check collection status
gcloud compute ssh ${VM_NAME} --zone=${ZONE} --command="ls -lh /data/dukascopy/*/*.parquet | wc -l"
```

---

## Automation Scripts

### Automated Collection Script

Create a script that handles the entire collection and offloading process:

```bash
# Save as: scripts/gcp/automated-collection.sh
cat > scripts/gcp/automated-collection.sh <<'SCRIPT_EOF'
#!/bin/bash
set -e

# Configuration
BUCKET_NAME="${BUCKET_NAME:-dukascopy-data}"
PROJECT_DIR="/opt/trading-system"
DATA_DIR="/data/dukascopy"
LOG_DIR="/data/logs"

# Calculate date range (5 years)
END_DATE=$(date +%Y-%m-%d)
START_DATE=$(date -d "5 years ago" +%Y-%m-%d)

echo "=== Starting Dukascopy Data Collection ==="
echo "Date range: ${START_DATE} to ${END_DATE}"
echo "Started at: $(date)"

# Function to offload to GCS
offload_to_gcs() {
    echo "Offloading data to gs://${BUCKET_NAME}..."
    
    # Upload Parquet files
    gsutil -m cp -r ${DATA_DIR}/*/*.parquet gs://${BUCKET_NAME}/parquet/ 2>/dev/null || true
    
    # Upload logs
    gsutil -m cp ${LOG_DIR}/*.log gs://${BUCKET_NAME}/logs/ 2>/dev/null || true
    
    # Upload progress
    if [ -f ${DATA_DIR}/.dukascopy_progress.json ]; then
        gsutil cp ${DATA_DIR}/.dukascopy_progress.json gs://${BUCKET_NAME}/logs/
    fi
    
    echo "Offload completed at: $(date)"
}

# Function to send notification (optional)
send_notification() {
    local status=$1
    local message=$2
    echo "[${status}] ${message}"
    # Add email/Slack notification here if needed
}

# Run collection
cd ${PROJECT_DIR}

python3 scripts/backfill_dukascopy_data.py \
    --start-date ${START_DATE} \
    --end-date ${END_DATE} \
    --output-dir ${DATA_DIR} \
    --batch-size 3 \
    --pause-ms 5000 \
    --compression snappy \
    --verbose \
    2>&1 | tee ${LOG_DIR}/collection_$(date +%Y%m%d_%H%M%S).log

COLLECTION_EXIT_CODE=$?

if [ ${COLLECTION_EXIT_CODE} -eq 0 ]; then
    echo "Collection completed successfully!"
    send_notification "SUCCESS" "Dukascopy data collection completed"
    
    # Offload to GCS
    offload_to_gcs
    
    # Verify offload
    echo "Verifying GCS upload..."
    gsutil ls gs://${BUCKET_NAME}/parquet/ | head -5
    
    send_notification "SUCCESS" "Data offloaded to GCS successfully"
else
    echo "Collection failed with exit code: ${COLLECTION_EXIT_CODE}"
    send_notification "FAILED" "Collection failed. Check logs."
    
    # Still try to offload what we have
    offload_to_gcs
    exit ${COLLECTION_EXIT_CODE}
fi

echo "=== Process completed at: $(date) ==="
SCRIPT_EOF

chmod +x scripts/gcp/automated-collection.sh
```

### Scheduled Offload Script

Create a script to periodically offload data during collection:

```bash
# Save as: scripts/gcp/scheduled-offload.sh
cat > scripts/gcp/scheduled-offload.sh <<'SCRIPT_EOF'
#!/bin/bash
BUCKET_NAME="${BUCKET_NAME:-dukascopy-data}"
DATA_DIR="/data/dukascopy"
LOG_DIR="/data/logs"

echo "=== Scheduled Offload $(date) ==="

# Upload new Parquet files (only new files)
gsutil -m rsync -r ${DATA_DIR}/ gs://${BUCKET_NAME}/parquet/ \
    --exclude="*.json" \
    --exclude="*.tmp"

# Upload latest logs
gsutil -m cp ${LOG_DIR}/*.log gs://${BUCKET_NAME}/logs/ 2>/dev/null || true

# Upload progress file
if [ -f ${DATA_DIR}/.dukascopy_progress.json ]; then
    gsutil cp ${DATA_DIR}/.dukascopy_progress.json gs://${BUCKET_NAME}/logs/
fi

echo "Offload completed at: $(date)"
SCRIPT_EOF

chmod +x scripts/gcp/scheduled-offload.sh

# Add to crontab (offload every 6 hours)
# (crontab -l 2>/dev/null; echo "0 */6 * * * /usr/local/bin/scheduled-offload.sh >> /var/log/offload.log 2>&1") | crontab -
```

---

## Monitoring & Offloading

### Real-Time Monitoring

```bash
# Monitor collection progress
watch -n 60 'gcloud compute ssh dukascopy-collector --zone=us-central1-a --command="tail -20 /data/logs/dukascopy_backfill.log"'

# Check disk usage
gcloud compute ssh dukascopy-collector --zone=us-central1-a --command="df -h /data"

# Check running processes
gcloud compute ssh dukascopy-collector --zone=us-central1-a --command="ps aux | grep backfill"

# Check network usage
gcloud compute ssh dukascopy-collector --zone=us-central1-a --command="iftop -t -s 10"
```

### GCS Monitoring

```bash
# List uploaded files
gsutil ls -lh gs://${BUCKET_NAME}/parquet/

# Check total size
gsutil du -sh gs://${BUCKET_NAME}/parquet/

# Download progress file
gsutil cp gs://${BUCKET_NAME}/logs/.dukascopy_progress.json /tmp/
cat /tmp/.dukascopy_progress.json | python3 -m json.tool
```

### Cloud Monitoring Dashboard

Create a monitoring dashboard in GCP Console:

1. Go to **Monitoring > Dashboards**
2. Create custom dashboard with:
   - VM CPU/Memory usage
   - Disk I/O
   - Network egress
   - GCS bucket size

---

## Troubleshooting

### Issue: VM Won't Start

**Symptoms:** VM stuck in "Starting" state

**Solution:**
```bash
# Check startup script logs
gcloud compute instances get-serial-port-output ${VM_NAME} --zone=${ZONE}

# Try recreating with simpler startup script
```

### Issue: dukascopy-node Not Found

**Symptoms:** `ERROR: dukascopy-node CLI not found`

**Solution:**
```bash
# SSH into VM
gcloud compute ssh ${VM_NAME} --zone=${ZONE}

# Install globally
sudo npm install -g dukascopy-node

# Or use npx
npx dukascopy-node --help

# Verify in script
which dukascopy-node || which npx
```

### Issue: Disk Space Running Out

**Symptoms:** `No space left on device`

**Solution:**
```bash
# Check disk usage
df -h /data

# Clean up temp JSON files (if --keep-json was used)
find /data/dukascopy -name "*.json" -delete

# Offload completed Parquet files to GCS
gsutil -m cp -r /data/dukascopy/*/*.parquet gs://${BUCKET_NAME}/parquet/

# Delete uploaded files locally
# (Only after verifying GCS upload!)
```

### Issue: Collection Interrupted

**Symptoms:** Script stopped mid-collection

**Solution:**
```bash
# Resume from last checkpoint
python3 scripts/backfill_dukascopy_data.py \
    --resume \
    --output-dir /data/dukascopy \
    --start-date ${START_DATE} \
    --end-date ${END_DATE}
```

### Issue: Rate Limiting (429 Errors)

**Symptoms:** Frequent HTTP 429 errors in logs

**Solution:**
```bash
# Stop collection
# Wait 1-2 hours
# Resume with more conservative settings
python3 scripts/backfill_dukascopy_data.py \
    --resume \
    --batch-size 2 \
    --pause-ms 8000 \
    --output-dir /data/dukascopy
```

### Issue: GCS Upload Fails

**Symptoms:** `AccessDeniedException` or upload errors

**Solution:**
```bash
# Verify service account permissions
gcloud projects get-iam-policy ${PROJECT_ID} \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:$(gcloud iam service-accounts list --filter="displayName:Compute Engine default service account" --format="value(email)")"

# Grant Storage Admin role if needed
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:$(gcloud iam service-accounts list --filter="displayName:Compute Engine default service account" --format="value(email)")" \
    --role="roles/storage.admin"

# Test upload
echo "test" | gsutil cp - gs://${BUCKET_NAME}/test.txt
```

---

## Cleanup

### After Successful Collection

Once data is collected and offloaded:

```bash
# 1. Verify all data is in GCS
gsutil ls -lh gs://${BUCKET_NAME}/parquet/ | wc -l
gsutil du -sh gs://${BUCKET_NAME}/parquet/

# 2. Download a sample file to verify
gsutil cp gs://${BUCKET_NAME}/parquet/EURUSD/2024.parquet /tmp/
python3 -c "import pandas as pd; df = pd.read_parquet('/tmp/2024.parquet'); print(f'Rows: {len(df):,}')"

# 3. Stop VM (to save costs)
gcloud compute instances stop ${VM_NAME} --zone=${ZONE}

# 4. Delete VM (if you don't need it)
gcloud compute instances delete ${VM_NAME} --zone=${ZONE} --quiet

# 5. Keep or delete data disk
# Option A: Keep disk (for future use)
# Option B: Delete disk
gcloud compute disks delete data-disk --zone=${ZONE} --quiet
```

### Download Data to Local Machine

```bash
# Download all data
gsutil -m cp -r gs://${BUCKET_NAME}/parquet/ ./data/dukascopy/

# Download specific pairs
gsutil -m cp -r gs://${BUCKET_NAME}/parquet/EURUSD/ ./data/dukascopy/EURUSD/
gsutil -m cp -r gs://${BUCKET_NAME}/parquet/GBPUSD/ ./data/dukascopy/GBPUSD/

# Download logs
gsutil -m cp -r gs://${BUCKET_NAME}/logs/ ./logs/gcp-collection/
```

### Cost Optimization

```bash
# Stop VM when not in use
gcloud compute instances stop ${VM_NAME} --zone=${ZONE}

# Use preemptible VM (if re-running)
gcloud compute instances create ${VM_NAME}-preemptible \
    --preemptible \
    --machine-type=e2-standard-4 \
    # ... other options

# Move data to Nearline storage (cheaper for long-term)
gsutil -m mv gs://${BUCKET_NAME}/parquet/ gs://${BUCKET_NAME}-nearline/parquet/
gsutil storageclass set NEARLINE gs://${BUCKET_NAME}-nearline/parquet/
```

---

## Quick Reference

### Essential Commands

```bash
# Start collection
gcloud compute ssh dukascopy-collector --zone=us-central1-a
screen -S collection
python3 scripts/backfill_dukascopy_data.py --start-date 2020-01-01 --end-date 2024-12-31 --output-dir /data/dukascopy

# Monitor progress
gcloud compute ssh dukascopy-collector --zone=us-central1-a --command="tail -f /data/logs/dukascopy_backfill.log"

# Offload to GCS
gcloud compute ssh dukascopy-collector --zone=us-central1-a --command="gsutil -m cp -r /data/dukascopy/*/*.parquet gs://dukascopy-data/parquet/"

# Download to local
gsutil -m cp -r gs://dukascopy-data/parquet/ ./data/dukascopy/

# Stop VM
gcloud compute instances stop dukascopy-collector --zone=us-central1-a

# Delete VM
gcloud compute instances delete dukascopy-collector --zone=us-central1-a --quiet
```

### Environment Variables

```bash
export PROJECT_ID=$(gcloud config get-value project)
export BUCKET_NAME="dukascopy-data-${PROJECT_ID}"
export VM_NAME="dukascopy-collector"
export ZONE="us-central1-a"
export REGION="us-central1"
```

---

## Next Steps

After successful collection:

1. **Validate Data Quality**
   ```bash
   python scripts/validate_parquet_data.py --data-dir data/dukascopy --summary
   ```

2. **Configure DVC** (if using version control)
   ```bash
   dvc remote add -d dukascopy_storage gs://${BUCKET_NAME}/dvc
   dvc add data/dukascopy
   dvc push
   ```

3. **Seed into Database** (optional)
   ```bash
   python scripts/seed_historical_data.py --data-dir data/dukascopy
   ```

4. **Set Up Incremental Updates**
   - Schedule monthly collection for new data
   - Automate GCS offloading
   - Monitor data freshness

---

## Additional Resources

- [GCP Compute Engine Documentation](https://cloud.google.com/compute/docs)
- [Google Cloud Storage Documentation](https://cloud.google.com/storage/docs)
- [Dukascopy Data Collection Guide](./DUKASCOPY_DATA_COLLECTION.md)
- [Data Storage Strategy](./DATA_STORAGE_STRATEGY.md)

---

**Questions or Issues?**

- Check VM logs: `gcloud compute instances get-serial-port-output ${VM_NAME} --zone=${ZONE}`
- Review collection logs: `gsutil cat gs://${BUCKET_NAME}/logs/dukascopy_backfill.log`
- Create GitHub issue with error details and log excerpts
