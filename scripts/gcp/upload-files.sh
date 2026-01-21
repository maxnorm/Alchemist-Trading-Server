#!/bin/bash
# Upload project files to GCP VM

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

VM_NAME="${VM_NAME:-dukascopy-collector}"
ZONE="${ZONE:-us-central1-a}"

echo -e "${GREEN}=== Uploading Files to VM ===${NC}"

# Check if VM exists
if ! gcloud compute instances describe $VM_NAME --zone=$ZONE &>/dev/null; then
    echo -e "${YELLOW}VM $VM_NAME not found. Run setup-vm.sh first.${NC}"
    exit 1
fi

# Get project root directory (assuming script is in scripts/gcp/)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

echo "Project root: $PROJECT_ROOT"
echo "VM: $VM_NAME"
echo "Zone: $ZONE"
echo ""

# Create directory on VM
echo "Creating directory on VM..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="mkdir -p /opt/trading-system && sudo chown -R \$USER:\$USER /opt/trading-system" || true

# Upload files
echo "Uploading files..."

# Upload collection script
if [ -f "$PROJECT_ROOT/scripts/backfill_dukascopy_data.py" ]; then
    echo "  - Uploading backfill script..."
    gcloud compute scp --zone=$ZONE \
        "$PROJECT_ROOT/scripts/backfill_dukascopy_data.py" \
        $VM_NAME:/opt/trading-system/scripts/backfill_dukascopy_data.py
else
    echo -e "${YELLOW}Warning: backfill_dukascopy_data.py not found${NC}"
fi

# Upload params.yaml
if [ -f "$PROJECT_ROOT/params.yaml" ]; then
    echo "  - Uploading params.yaml..."
    gcloud compute scp --zone=$ZONE \
        "$PROJECT_ROOT/params.yaml" \
        $VM_NAME:/opt/trading-system/params.yaml
fi

# Upload package.json (for reference)
if [ -f "$PROJECT_ROOT/package.json" ]; then
    echo "  - Uploading package.json..."
    gcloud compute scp --zone=$ZONE \
        "$PROJECT_ROOT/package.json" \
        $VM_NAME:/opt/trading-system/package.json
fi

# Upload requirements.txt if it exists
if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
    echo "  - Uploading requirements.txt..."
    gcloud compute scp --zone=$ZONE \
        "$PROJECT_ROOT/requirements.txt" \
        $VM_NAME:/opt/trading-system/requirements.txt
fi

echo -e "${GREEN}Upload complete!${NC}"
echo ""
echo "Files are in: /opt/trading-system/"
echo "Connect to VM: gcloud compute ssh $VM_NAME --zone=$ZONE"
