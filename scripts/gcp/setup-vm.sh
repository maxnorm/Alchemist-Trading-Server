#!/bin/bash
# Setup script for GCP VM deployment
# This automates the VM creation and initial setup

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== GCP Dukascopy Data Collection Setup ===${NC}"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI not found.${NC}"
    echo "Please install: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Get or set project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo -e "${YELLOW}No default project set.${NC}"
    read -p "Enter your GCP project ID: " PROJECT_ID
    gcloud config set project $PROJECT_ID
fi

echo -e "${GREEN}Using project: ${PROJECT_ID}${NC}"

# Set variables
VM_NAME="${VM_NAME:-dukascopy-collector}"
ZONE="${ZONE:-us-central1-a}"
REGION="${REGION:-us-central1}"
BUCKET_NAME="dukascopy-data-${PROJECT_ID}"
MACHINE_TYPE="${MACHINE_TYPE:-e2-standard-4}"

echo ""
echo "Configuration:"
echo "  VM Name: $VM_NAME"
echo "  Zone: $ZONE"
echo "  Machine Type: $MACHINE_TYPE"
echo "  Bucket: $BUCKET_NAME"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# Step 1: Enable APIs
echo -e "${GREEN}Step 1: Enabling required APIs...${NC}"
gcloud services enable \
    compute.googleapis.com \
    storage-component.googleapis.com \
    logging.googleapis.com \
    --project=$PROJECT_ID

# Step 2: Create GCS bucket
echo -e "${GREEN}Step 2: Creating GCS bucket...${NC}"
if gsutil ls -b gs://${BUCKET_NAME} &>/dev/null; then
    echo -e "${YELLOW}Bucket ${BUCKET_NAME} already exists.${NC}"
else
    gsutil mb -p ${PROJECT_ID} -c STANDARD -l ${REGION} gs://${BUCKET_NAME}
    echo -e "${GREEN}Bucket created: gs://${BUCKET_NAME}${NC}"
fi

# Step 3: Create startup script
echo -e "${GREEN}Step 3: Creating startup script...${NC}"
cat > /tmp/vm-startup-script.sh <<EOF
#!/bin/bash
set -e
exec > >(tee -a /var/log/dukascopy-setup.log)
exec 2>&1

export DEBIAN_FRONTEND=noninteractive

echo "=== Dukascopy VM Setup Started ==="
echo "Time: \$(date)"

# Update system
apt-get update
apt-get install -y python3.11 python3-pip python3-venv nodejs npm git curl screen

# Install Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# Install Python packages
pip3 install pandas pyarrow numpy

# Install dukascopy-node globally
npm install -g dukascopy-node

# Create data directories
mkdir -p /data/dukascopy /data/logs

# Format and mount data disk (if not already mounted)
if [ ! -d /data/.mounted ]; then
    # Check if disk exists
    if [ -b /dev/sdb ]; then
        # Format disk
        mkfs.ext4 -F -m 0 -E lazy_itable_init=0,lazy_journal_init=0,discard /dev/sdb
        
        # Mount disk
        mount -o discard,defaults /dev/sdb /data
        
        # Add to fstab
        echo '/dev/sdb /data ext4 discard,defaults,nofail 0 2' >> /etc/fstab
        
        # Create directories
        mkdir -p /data/dukascopy /data/logs
        chmod 755 /data/dukascopy /data/logs
        
        touch /data/.mounted
    fi
fi

# Set permissions
chown -R \$(whoami):\$(whoami) /data/dukascopy /data/logs 2>/dev/null || true

echo "=== Setup Completed ==="
echo "Time: \$(date)"
EOF

# Step 4: Create VM
echo -e "${GREEN}Step 4: Creating VM...${NC}"
if gcloud compute instances describe $VM_NAME --zone=$ZONE &>/dev/null; then
    echo -e "${YELLOW}VM $VM_NAME already exists.${NC}"
    read -p "Delete and recreate? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        gcloud compute instances delete $VM_NAME --zone=$ZONE --quiet
    else
        echo "Using existing VM."
        exit 0
    fi
fi

gcloud compute instances create $VM_NAME \
    --project=$PROJECT_ID \
    --zone=$ZONE \
    --machine-type=$MACHINE_TYPE \
    --network-interface=network-tier=PREMIUM,stack-type=IPV4_ONLY,subnet=default \
    --maintenance-policy=MIGRATE \
    --provisioning-model=STANDARD \
    --service-account=$(gcloud iam service-accounts list --filter="displayName:Compute Engine default service account" --format="value(email)" --project=$PROJECT_ID) \
    --scopes=https://www.googleapis.com/auth/cloud-platform \
    --tags=http-server,https-server \
    --create-disk=auto-delete=yes,boot=yes,device-name=${VM_NAME},image=projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts,mode=rw,size=50,type=projects/${PROJECT_ID}/zones/${ZONE}/diskTypes/pd-standard \
    --create-disk=auto-delete=yes,device-name=data-disk,mode=rw,size=500,type=projects/${PROJECT_ID}/zones/${ZONE}/diskTypes/pd-ssd \
    --metadata-from-file=startup-script=/tmp/vm-startup-script.sh \
    --metadata=BUCKET_NAME=${BUCKET_NAME}

echo -e "${GREEN}VM created successfully!${NC}"
echo ""
echo "Next steps:"
echo "1. Wait 2-3 minutes for VM to finish setup"
echo "2. Connect: gcloud compute ssh $VM_NAME --zone=$ZONE"
echo "3. Upload files: ./scripts/gcp/upload-files.sh"
echo "4. Start collection: ./scripts/gcp/start-collection.sh"
echo ""
echo "VM IP:"
gcloud compute instances describe $VM_NAME --zone=$ZONE --format="get(networkInterfaces[0].accessConfigs[0].natIP)"
