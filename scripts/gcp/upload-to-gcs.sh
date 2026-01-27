#!/bin/bash
# Upload collected data from VM to GCS bucket
# This can be run manually or scheduled to backup data during collection

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

VM_NAME="${VM_NAME:-dukascopy-collector}"
ZONE="${ZONE:-us-central1-a}"
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
BUCKET_NAME="dukascopy-data-${PROJECT_ID}"

echo -e "${GREEN}=== Uploading Data to GCS ===${NC}"

# Check if VM exists
if ! gcloud compute instances describe $VM_NAME --zone=$ZONE &>/dev/null; then
    echo -e "${YELLOW}VM $VM_NAME not found.${NC}"
    exit 1
fi

# Check if bucket exists
if ! gsutil ls -b gs://${BUCKET_NAME} &>/dev/null; then
    echo -e "${YELLOW}Bucket ${BUCKET_NAME} not found.${NC}"
    echo "Run setup-vm.sh first to create the bucket."
    exit 1
fi

echo "Configuration:"
echo "  VM: $VM_NAME"
echo "  Bucket: gs://${BUCKET_NAME}"
echo "  Source: /data/dukascopy/"
echo ""

# Upload data from VM to GCS
echo "Uploading Parquet files to GCS..."
gcloud compute ssh $VM_NAME --zone=$ZONE <<EOF
BUCKET_NAME="${BUCKET_NAME}"
echo "Syncing /data/dukascopy/ to gs://\${BUCKET_NAME}/parquet/..."

# Use rsync to only upload new/changed files
gsutil -m rsync -r /data/dukascopy/ gs://\${BUCKET_NAME}/parquet/ \
    --exclude="*.json" \
    --exclude="*.tmp" \
    --exclude=".dukascopy_progress.json"

echo ""
echo "Uploading logs..."
gsutil -m cp /data/logs/*.log gs://\${BUCKET_NAME}/logs/ 2>/dev/null || true

# Upload progress file if it exists
if [ -f /data/.dukascopy_progress.json ]; then
    gsutil cp /data/.dukascopy_progress.json gs://\${BUCKET_NAME}/logs/ 2>/dev/null || true
fi

echo ""
echo "Verifying upload..."
echo "Files in bucket:"
gsutil ls gs://\${BUCKET_NAME}/parquet/ | head -10
echo ""
echo "Total size:"
gsutil du -sh gs://\${BUCKET_NAME}/parquet/ 2>/dev/null || echo "Calculating..."
EOF

echo ""
echo -e "${GREEN}Upload complete!${NC}"
echo ""
echo "Verify upload:"
echo "  gsutil ls gs://${BUCKET_NAME}/parquet/"
echo ""
echo "Download data:"
echo "  ./scripts/gcp/download-data.sh"
