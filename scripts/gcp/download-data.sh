#!/bin/bash
# Download collected data from GCS to local machine
# Usage: ./download-data.sh [--pair PAIR] [--test]

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
BUCKET_NAME="dukascopy-data-${PROJECT_ID}"
LOCAL_DIR="${LOCAL_DIR:-./data/dukascopy}"

# Parse arguments
DOWNLOAD_PAIR=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --pair)
            DOWNLOAD_PAIR="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--pair PAIR]"
            echo ""
            echo "Examples:"
            echo "  # Download all data from GCS (~130-175GB)"
            echo "  $0"
            echo ""
            echo "  # Download specific pair (for testing)"
            echo "  $0 --pair EURUSD"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}=== Downloading Data from GCS ===${NC}"
# Check if bucket exists
if ! gsutil ls -b gs://${BUCKET_NAME} &>/dev/null; then
    echo -e "${YELLOW}Bucket ${BUCKET_NAME} not found.${NC}"
    echo "Make sure collection has started and data has been uploaded to GCS."
    echo ""
    echo "To upload data to GCS, run:"
    echo "  ./scripts/gcp/upload-to-gcs.sh"
    exit 1
fi

# Create local directory
mkdir -p "$LOCAL_DIR"

echo "Configuration:"
echo "  Bucket: gs://${BUCKET_NAME}"
echo "  Local directory: $LOCAL_DIR"

if [ -n "$DOWNLOAD_PAIR" ]; then
    echo "  Pair: $DOWNLOAD_PAIR (test mode)"
    echo ""
    read -p "Download only $DOWNLOAD_PAIR? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    
    # Download specific pair
    echo "Downloading $DOWNLOAD_PAIR..."
    gsutil -m cp -r "gs://${BUCKET_NAME}/parquet/${DOWNLOAD_PAIR}/" "$LOCAL_DIR/${DOWNLOAD_PAIR}/" || {
        echo -e "${YELLOW}Pair $DOWNLOAD_PAIR not found in bucket.${NC}"
        echo "Available pairs:"
        gsutil ls "gs://${BUCKET_NAME}/parquet/" | head -10
        exit 1
    }
else
    echo ""
    echo "This will download ~130-175GB of data."
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    
    # Download all data
    echo "Downloading all Parquet files..."
    gsutil -m cp -r gs://${BUCKET_NAME}/parquet/* "$LOCAL_DIR/"
fi

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
