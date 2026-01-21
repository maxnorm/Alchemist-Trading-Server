#!/bin/bash
# Download collected data from GCS to local machine

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
BUCKET_NAME="dukascopy-data-${PROJECT_ID}"
LOCAL_DIR="${LOCAL_DIR:-./data/dukascopy}"

echo -e "${GREEN}=== Downloading Data from GCS ===${NC}"

# Check if bucket exists
if ! gsutil ls -b gs://${BUCKET_NAME} &>/dev/null; then
    echo -e "${YELLOW}Bucket ${BUCKET_NAME} not found.${NC}"
    echo "Make sure collection has started and data has been uploaded to GCS."
    exit 1
fi

# Create local directory
mkdir -p "$LOCAL_DIR"

echo "Configuration:"
echo "  Bucket: gs://${BUCKET_NAME}"
echo "  Local directory: $LOCAL_DIR"
echo ""
echo "This will download ~130-175GB of data."
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# Download data
echo "Downloading Parquet files..."
gsutil -m cp -r gs://${BUCKET_NAME}/parquet/* "$LOCAL_DIR/"

# Download logs (optional)
if gsutil ls gs://${BUCKET_NAME}/logs/ &>/dev/null; then
    echo "Downloading logs..."
    mkdir -p ./logs/gcp-collection
    gsutil -m cp -r gs://${BUCKET_NAME}/logs/* ./logs/gcp-collection/ || true
fi

echo -e "${GREEN}Download complete!${NC}"
echo ""
echo "Data location: $LOCAL_DIR"
echo "Total size:"
du -sh "$LOCAL_DIR" 2>/dev/null || echo "Run: du -sh $LOCAL_DIR"
