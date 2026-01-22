#!/bin/bash
# Clean up GCP resources (VM, optional: bucket)

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

VM_NAME="${VM_NAME:-dukascopy-collector}"
ZONE="${ZONE:-us-central1-a}"
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
BUCKET_NAME="dukascopy-data-${PROJECT_ID}"

echo -e "${YELLOW}=== GCP Resource Cleanup ===${NC}"
echo ""
echo "This will:"
echo "  1. Stop/Delete VM: $VM_NAME"
echo "  2. Optionally delete GCS bucket: $BUCKET_NAME"
echo ""

read -p "Delete VM? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if gcloud compute instances describe $VM_NAME --zone=$ZONE &>/dev/null; then
        echo "Stopping VM..."
        gcloud compute instances stop $VM_NAME --zone=$ZONE || true
        
        read -p "Delete VM permanently? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Deleting VM..."
            gcloud compute instances delete $VM_NAME --zone=$ZONE --quiet
            echo -e "${GREEN}VM deleted.${NC}"
        else
            echo -e "${GREEN}VM stopped (not deleted).${NC}"
        fi
    else
        echo -e "${YELLOW}VM not found.${NC}"
    fi
fi

echo ""
read -p "Delete GCS bucket? (WARNING: This deletes all data!) (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if gsutil ls -b gs://${BUCKET_NAME} &>/dev/null; then
        echo "Deleting bucket..."
        gsutil rm -r gs://${BUCKET_NAME}
        echo -e "${GREEN}Bucket deleted.${NC}"
    else
        echo -e "${YELLOW}Bucket not found.${NC}"
    fi
else
    echo -e "${GREEN}Bucket kept. Cost: ~\$5/month for 200GB${NC}"
fi

echo ""
echo -e "${GREEN}Cleanup complete!${NC}"
