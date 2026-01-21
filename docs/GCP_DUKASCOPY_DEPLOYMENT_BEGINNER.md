# Google Cloud Deployment Guide: Dukascopy Data Collection (Beginner-Friendly)

**Last Updated:** January 17, 2026  
**Purpose:** Complete beginner-friendly guide with detailed explanations, reasoning, and learning resources

---

## Table of Contents

1. [Understanding the Problem](#understanding-the-problem)
2. [Cloud Computing Basics](#cloud-computing-basics)
3. [Why Use Google Cloud?](#why-use-google-cloud)
4. [Understanding the Architecture](#understanding-the-architecture)
5. [Step-by-Step Guide with Explanations](#step-by-step-guide-with-explanations)
6. [Downloading Data Locally](#downloading-data-locally)
7. [Future: Re-uploading to Another Provider](#future-re-uploading-to-another-provider)
8. [Learning Resources](#learning-resources)

---

## Understanding the Problem

### What Are We Trying to Do?

We need to download **5 years of historical forex data** for **28 currency pairs** from Dukascopy. This is a massive amount of data (~130-175GB) that will take **2-3 days** to download.

### Why Can't We Do This Locally?

**Problem 1: Time**
- Your home internet might be slow (10-50 Mbps)
- At 10 Mbps, downloading 175GB = ~39 hours of pure download time
- But we also need to process/convert the data, adding more time
- **Total: 3-5 days of continuous running**

**Problem 2: Reliability**
- Your computer might crash, restart, or lose internet
- Power outages, network issues, etc.
- The script has resume capability, but interruptions are annoying

**Problem 3: Resources**
- Your computer needs to be on 24/7 for days
- Uses CPU, RAM, and disk space
- Can't use your computer for other things

### The Cloud Solution

**Cloud computing** means renting a computer in Google's data center that:
- Has fast internet (10+ Gbps)
- Runs 24/7 without interruption
- We only pay for the time we use it
- We can delete it when done

**Think of it like:**
- Instead of buying a car for one trip, you rent a car
- Instead of buying a server, you rent a virtual machine (VM)

---

## Cloud Computing Basics

### What is a Virtual Machine (VM)?

A **Virtual Machine** is like a computer inside another computer. Google has powerful physical servers, and they divide them into smaller "virtual" computers that you can rent.

**Analogy:** 
- Physical server = Apartment building
- Virtual Machine = Your apartment in that building
- You share the building's infrastructure (power, internet) but have your own space

**Key Concepts:**

1. **Compute Engine** = Google's service for renting VMs
   - [Official Docs: What is Compute Engine?](https://cloud.google.com/compute/docs/overview/what-is-compute-engine)

2. **Instance** = One virtual machine
   - Like one apartment in the building
   - You can start/stop/delete it anytime

3. **Machine Type** = The "size" of your VM
   - `e2-standard-4` = 4 CPU cores, 16GB RAM
   - Like choosing a 1-bedroom vs 2-bedroom apartment
   - [Machine Types Explained](https://cloud.google.com/compute/docs/machine-types)

4. **Persistent Disk** = Hard drive for your VM
   - Data persists even if you stop the VM
   - Like an external hard drive that stays connected
   - [Persistent Disks Overview](https://cloud.google.com/compute/docs/disks)

### What is Cloud Storage?

**Google Cloud Storage (GCS)** is like Dropbox or Google Drive, but for programs.

**Key Concepts:**

1. **Bucket** = A container for your files
   - Like a folder, but in the cloud
   - Has a unique name (globally unique across all GCP)
   - [Understanding Buckets](https://cloud.google.com/storage/docs/buckets)

2. **Object** = A file in the bucket
   - Each Parquet file is an "object"
   - [Objects Overview](https://cloud.google.com/storage/docs/objects)

3. **gsutil** = Command-line tool to manage GCS
   - Like `cp` or `mv` but for cloud storage
   - [gsutil Documentation](https://cloud.google.com/storage/docs/gsutil)

**Why Use GCS?**
- **Temporary storage** while collection runs
- **Backup** in case VM crashes
- **Easy download** to your local machine later
- **Cheap** (~$5/month for 200GB)

---

## Why Use Google Cloud?

### Comparison: Local vs Cloud

| Aspect | Local Machine | Google Cloud VM |
|--------|--------------|-----------------|
| **Internet Speed** | 10-100 Mbps | 10+ Gbps (100x faster) |
| **Uptime** | Depends on your power/internet | 99.9% guaranteed |
| **Cost** | Free (but uses your resources) | ~$30-40 for 3 days |
| **Setup Time** | Minutes | Minutes |
| **Maintenance** | You handle it | Google handles it |

### Why GCP Specifically?

1. **You have credits** - Free money to use!
2. **Fast setup** - Can create VM in minutes
3. **Good documentation** - Easy to learn
4. **gsutil is powerful** - Easy file transfers
5. **Free tier** - Some services are free

**Alternative Options:**
- **AWS EC2** - Similar to GCP, but different interface
- **Azure VMs** - Microsoft's version
- **DigitalOcean** - Simpler, but less features

**For this project:** GCP is perfect because you have credits!

---

## Understanding the Architecture

### The Complete Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    YOUR LOCAL COMPUTER                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. You run commands to create VM                     │  │
│  │  2. Upload script files to VM                        │  │
│  │  3. Monitor progress                                 │  │
│  │  4. Download final data when done                    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                        │
                        │ gcloud commands
                        │ (over internet)
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              GOOGLE CLOUD PLATFORM (GCP)                    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  COMPUTE ENGINE VM                                    │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │  Ubuntu Linux OS                                 │  │  │
│  │  │  - Python 3.11                                  │  │  │
│  │  │  - Node.js (for dukascopy-node)                 │  │  │
│  │  │  - Your collection script                        │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  │                                                        │  │
│  │  Downloads from Dukascopy → Converts to Parquet      │  │
│  │  Saves to: /data/dukascopy/                          │  │
│  └──────────────────────────────────────────────────────┘  │
│                        │                                     │
│                        │ Uploads files                       │
│                        ▼                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  GOOGLE CLOUD STORAGE (GCS)                           │  │
│  │  Bucket: dukascopy-data-{project-id}                 │  │
│  │  - parquet/ (final data files)                        │  │
│  │  - logs/ (collection logs)                            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                        │
                        │ gsutil download
                        │ (to your computer)
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    YOUR LOCAL COMPUTER                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ./data/dukascopy/                                    │  │
│  │  - EURUSD/2020.parquet                               │  │
│  │  - EURUSD/2021.parquet                               │  │
│  │  - ... (all 28 pairs, 5 years)                       │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Step-by-Step What Happens

1. **You create a VM** → Google spins up a virtual computer
2. **You upload your script** → Script is copied to the VM
3. **Script runs on VM** → Downloads data from Dukascopy (fast internet!)
4. **Data saved to VM disk** → Stored locally on the VM
5. **Periodic uploads to GCS** → Backup copies in cloud storage
6. **You download to local** → Copy all files to your computer
7. **Delete VM** → Stop paying, data is safely in GCS and local

---

## Step-by-Step Guide with Explanations

### Prerequisites: Understanding What You Need

Before we start, you need:

1. **Google Cloud Account**
   - Sign up at [cloud.google.com](https://cloud.google.com)
   - You get $300 free credits (or use existing credits)
   - [Getting Started Guide](https://cloud.google.com/getting-started)

2. **Google Cloud SDK (gcloud)**
   - Command-line tool to control GCP
   - Like a remote control for Google Cloud
   - [Installation Guide](https://cloud.google.com/sdk/docs/install)

3. **Basic Terminal/Command Line Knowledge**
   - How to open terminal (PowerShell on Windows, Terminal on Mac/Linux)
   - Basic commands: `cd`, `ls`, `mkdir`
   - [Command Line Crash Course](https://developer.mozilla.org/en-US/docs/Learn/Tools_and_testing/Understanding_client-side_tools/Command_line)

---

### Step 1: Install Google Cloud SDK

**What is this?**
The `gcloud` command-line tool lets you control Google Cloud from your terminal.

**Why do we need it?**
Instead of clicking buttons in a web interface, we use commands (faster, automatable).

**How to install:**

**Windows:**
```powershell
# Download installer from:
# https://cloud.google.com/sdk/docs/install-sdk#windows

# Or use Chocolatey (if you have it):
choco install gcloudsdk
```

**Mac:**
```bash
# Using Homebrew (recommended)
brew install --cask google-cloud-sdk

# Or download from:
# https://cloud.google.com/sdk/docs/install-sdk#mac
```

**Linux:**
```bash
# Add Google's package repository
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list

# Install
sudo apt-get update && sudo apt-get install google-cloud-sdk
```

**Verify installation:**
```bash
gcloud --version
# Should show: Google Cloud SDK [version number]
```

**Learn more:**
- [Official Installation Guide](https://cloud.google.com/sdk/docs/install)
- [gcloud CLI Reference](https://cloud.google.com/sdk/gcloud/reference)

---

### Step 2: Authenticate and Set Up Project

**What is authentication?**
Proving to Google that you're allowed to use their services. Like logging into a website.

**What is a project?**
A project is like a folder that contains all your GCP resources (VMs, storage, etc.). It helps organize and bill things.

**Commands:**

```bash
# 1. Log in to your Google account
gcloud auth login

# This opens a browser window. Sign in with your Google account.
# Why? Google needs to know who you are.

# 2. Create a new project (or use existing)
gcloud projects create dukascopy-data-collection \
    --name="Dukascopy Data Collection"

# What does this do?
# - Creates a new "folder" in your GCP account
# - All resources will belong to this project
# - Makes billing and organization easier

# 3. Set it as your default project
gcloud config set project dukascopy-data-collection

# Why? So you don't have to specify the project in every command.

# 4. Link billing account (required to use paid services)
# First, find your billing account ID:
gcloud billing accounts list

# Then link it:
gcloud billing projects link dukascopy-data-collection \
    --billing-account=YOUR_BILLING_ACCOUNT_ID

# Why? Google needs to know how to charge you (or use your credits).
```

**Learn more:**
- [Projects Overview](https://cloud.google.com/resource-manager/docs/creating-managing-projects)
- [Billing Setup](https://cloud.google.com/billing/docs/how-to/manage-billing-account)

---

### Step 3: Enable Required APIs

**What are APIs?**
APIs (Application Programming Interfaces) are like switches that turn on features. Google has many services, but you need to "enable" them for your project.

**Why enable them?**
- **Compute Engine API**: Needed to create VMs
- **Storage API**: Needed to create buckets and store files
- **Logging API**: Needed to see logs (helpful for debugging)

**Command:**

```bash
# Enable all required APIs at once
gcloud services enable \
    compute.googleapis.com \
    storage-component.googleapis.com \
    logging.googleapis.com

# What does this do?
# - Turns on Compute Engine (for VMs)
# - Turns on Cloud Storage (for buckets)
# - Turns on Cloud Logging (for monitoring)

# Verify they're enabled:
gcloud services list --enabled
# Should show: compute.googleapis.com, storage-component.googleapis.com, etc.
```

**Learn more:**
- [Understanding APIs in GCP](https://cloud.google.com/apis/docs/overview)
- [Enabling APIs](https://cloud.google.com/endpoints/docs/openapi/enable-api)

---

### Step 4: Create a Storage Bucket

**What is a bucket?**
A bucket is like a folder in the cloud where you store files. Think of it as a Dropbox folder, but accessible via commands.

**Why create it now?**
- We'll use it to backup data during collection
- Makes it easy to download files later
- Provides a safety net if the VM crashes

**Commands:**

```bash
# Set variables (makes commands easier)
PROJECT_ID=$(gcloud config get-value project)
BUCKET_NAME="dukascopy-data-${PROJECT_ID}"
REGION="us-central1"  # Choose region closest to you

# What are these variables?
# - PROJECT_ID: Your project's unique ID
# - BUCKET_NAME: Name for your bucket (must be globally unique)
# - REGION: Where to store data (affects speed and cost)

# Create the bucket
gsutil mb -p ${PROJECT_ID} -c STANDARD -l ${REGION} gs://${BUCKET_NAME}

# Breaking down the command:
# - gsutil: Tool for managing Cloud Storage
# - mb: "make bucket" (create bucket)
# - -p: Project ID
# - -c STANDARD: Storage class (standard = fast access, slightly more expensive)
# - -l: Location/region
# - gs://${BUCKET_NAME}: The bucket's address (like a URL)

# Verify it was created:
gsutil ls
# Should show: gs://dukascopy-data-...
```

**What is a storage class?**
Different "tiers" of storage with different costs and speeds:
- **STANDARD**: Fast access, higher cost (good for active use)
- **NEARLINE**: Slower access, cheaper (good for backups)
- **COLDLINE**: Very slow access, very cheap (good for archives)

For now, we use STANDARD because we'll download it soon.

**Learn more:**
- [Creating Buckets](https://cloud.google.com/storage/docs/creating-buckets)
- [Storage Classes](https://cloud.google.com/storage/docs/storage-classes)
- [gsutil Commands](https://cloud.google.com/storage/docs/gsutil)

---

### Step 5: Create the Virtual Machine

**What is a VM?**
A virtual computer running in Google's data center. You control it remotely via SSH.

**Why this configuration?**
- **e2-standard-4**: 4 CPU cores, 16GB RAM (enough for data processing)
- **Ubuntu 22.04**: Linux operating system (free, reliable)
- **500GB SSD disk**: Fast storage for temp files and final data
- **50GB boot disk**: For the operating system

**Commands:**

```bash
# Set variables
PROJECT_ID=$(gcloud config get-value project)
VM_NAME="dukascopy-collector"
ZONE="us-central1-a"  # Zone = specific data center location
IMAGE_FAMILY="ubuntu-2204-lts"  # Ubuntu 22.04 LTS
IMAGE_PROJECT="ubuntu-os-cloud"

# What is a zone?
# Google has data centers worldwide. A zone is a specific location.
# us-central1-a = Iowa, USA (example)
# Choose one close to you for lower latency.

# Create the VM
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
    --create-disk=auto-delete=yes,device-name=data-disk,mode=rw,size=500,type=projects/${PROJECT_ID}/zones/${ZONE}/diskTypes/pd-ssd

# Breaking down key parameters:
# - machine-type: Size of VM (CPU/RAM)
# - zone: Where to create it
# - create-disk (first): Boot disk (operating system)
# - create-disk (second): Data disk (for our files)
# - scopes: Permissions (allows VM to access GCS)
# - auto-delete=yes: Delete disk when VM is deleted (saves money)

# Wait for VM to be ready
echo "Waiting for VM to start..."
sleep 30

# Get the VM's IP address
VM_IP=$(gcloud compute instances describe ${VM_NAME} \
    --zone=${ZONE} \
    --format="get(networkInterfaces[0].accessConfigs[0].natIP)")

echo "VM created! IP address: ${VM_IP}"
```

**What happens when you run this?**
1. Google allocates resources (CPU, RAM, disk)
2. Installs Ubuntu on the boot disk
3. Assigns an IP address
4. VM starts up (takes 1-2 minutes)

**Learn more:**
- [Creating VMs](https://cloud.google.com/compute/docs/instances/create-start-instance)
- [Machine Types](https://cloud.google.com/compute/docs/machine-types)
- [Zones and Regions](https://cloud.google.com/compute/docs/regions-zones)

---

### Step 6: Connect to the VM (SSH)

**What is SSH?**
SSH (Secure Shell) is a way to remotely control a computer. Like remote desktop, but text-based.

**Why do we need it?**
To run commands on the VM, install software, and start the collection script.

**Command:**

```bash
# Connect via SSH (Google handles authentication automatically)
gcloud compute ssh ${VM_NAME} --zone=${ZONE}

# What happens?
# - Opens a secure connection to your VM
# - You're now "inside" the VM
# - Commands you type run on the VM, not your local computer

# You should see a prompt like:
# username@dukascopy-collector:~$
```

**First-time setup:**
Google will generate SSH keys automatically. Just follow the prompts.

**Learn more:**
- [Connecting to VMs](https://cloud.google.com/compute/docs/instances/connecting-to-instance)
- [SSH Overview](https://www.ssh.com/academy/ssh)

---

### Step 7: Set Up the VM (Install Software)

**What are we installing?**
- **Python 3.11**: To run our collection script
- **Node.js**: To run the `dukascopy-node` CLI tool
- **npm**: Node package manager (to install dukascopy-node)
- **pip**: Python package manager (to install pandas, pyarrow, etc.)

**Why these?**
Our script needs these tools to download and process data.

**Commands (run inside VM):**

```bash
# Update package list (like refreshing an app store)
sudo apt-get update

# Install Python and build tools
sudo apt-get install -y python3.11 python3-pip python3-venv git curl

# Install Node.js 20 (needed for dukascopy-node)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
sudo apt-get install -y nodejs

# Verify installations
python3 --version  # Should show: Python 3.11.x
node --version     # Should show: v20.x.x
npm --version      # Should show: 10.x.x

# Install Python packages (needed by our script)
pip3 install pandas pyarrow numpy

# Install dukascopy-node (the tool that downloads from Dukascopy)
npm install -g dukascopy-node

# Verify dukascopy-node works
npx dukascopy-node --help
```

**What does each command do?**
- `apt-get update`: Refreshes list of available software
- `apt-get install`: Installs software packages
- `pip3 install`: Installs Python libraries
- `npm install -g`: Installs Node.js packages globally

**Learn more:**
- [Python Package Management](https://packaging.python.org/en/latest/guides/tool-recommendations/)
- [Node.js Installation](https://nodejs.org/en/download/package-manager)
- [Linux Package Management](https://www.digitalocean.com/community/tutorials/package-management-basics-apt-yum-dnf-pkg)

---

### Step 8: Mount the Data Disk

**What is mounting?**
Making a disk "visible" to the operating system. Like plugging in a USB drive.

**Why do we need this?**
We created a 500GB disk, but it's not automatically available. We need to "mount" it.

**Commands (run inside VM):**

```bash
# Check available disks
lsblk
# Should show: sda (boot disk), sdb (data disk)

# Format the data disk (first time only - WARNING: erases data!)
sudo mkfs.ext4 -m 0 -E lazy_itable_init=0,lazy_journal_init=0,discard /dev/sdb

# What is mkfs.ext4?
# Creates a file system on the disk (like formatting a USB drive)
# ext4 = Linux file system format

# Create mount point (directory where disk will appear)
sudo mkdir -p /data

# Mount the disk
sudo mount -o discard,defaults /dev/sdb /data

# What does this do?
# - Makes /dev/sdb available at /data
# - Now you can save files to /data and they go to the 500GB disk

# Make it permanent (so it mounts automatically on reboot)
echo '/dev/sdb /data ext4 discard,defaults,nofail 0 2' | sudo tee -a /etc/fstab

# Create directories for our data
sudo mkdir -p /data/dukascopy /data/logs
sudo chown $USER:$USER /data/dukascopy /data/logs

# Verify it worked
df -h /data
# Should show: /dev/sdb with ~500GB available
```

**Learn more:**
- [Mounting Disks](https://cloud.google.com/compute/docs/disks/add-persistent-disk)
- [Linux File Systems](https://www.tutorialspoint.com/unix/unix-file-system.htm)

---

### Step 9: Upload Your Script Files

**What are we uploading?**
Your collection script and related files from your local computer to the VM.

**Why?**
The VM needs your script to run the collection.

**Commands (run from YOUR LOCAL COMPUTER, not in VM):**

```bash
# Exit VM first (if you're still connected)
exit

# Upload files using gcloud compute scp
gcloud compute scp \
    --zone=${ZONE} \
    --recurse \
    scripts/backfill_dukascopy_data.py \
    params.yaml \
    package.json \
    ${VM_NAME}:/opt/trading-system/

# What does this do?
# - scp: Secure copy (like cp, but over network)
# - --recurse: Copy directories recursively
# - Copies files to /opt/trading-system/ on the VM

# Create directory on VM first
gcloud compute ssh ${VM_NAME} --zone=${ZONE} --command="sudo mkdir -p /opt/trading-system && sudo chown $USER:$USER /opt/trading-system"

# Upload the script
gcloud compute scp \
    --zone=${ZONE} \
    scripts/backfill_dukascopy_data.py \
    ${VM_NAME}:/opt/trading-system/

# Upload other files
gcloud compute scp --zone=${ZONE} params.yaml ${VM_NAME}:/opt/trading-system/
gcloud compute scp --zone=${ZONE} package.json ${VM_NAME}:/opt/trading-system/
```

**Alternative: Clone from GitHub (if your repo is public)**

```bash
# Inside VM:
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git /opt/trading-system
```

**Learn more:**
- [Copying Files to VMs](https://cloud.google.com/compute/docs/instances/transfer-files)
- [SCP Command](https://www.ssh.com/academy/ssh/scp)

---

### Step 10: Start the Collection

**What happens here?**
We run the collection script on the VM. It will download data for 2-3 days.

**Why use `screen`?**
`screen` keeps the process running even if you disconnect. Like leaving a program running in the background.

**Commands (run inside VM):**

```bash
# Connect to VM
gcloud compute ssh ${VM_NAME} --zone=${ZONE}

# Install screen (if not already installed)
sudo apt-get install -y screen

# Start a screen session (keeps running if you disconnect)
screen -S dukascopy-collection

# Calculate date range (5 years back from today)
END_DATE=$(date +%Y-%m-%d)
START_DATE=$(date -d "5 years ago" +%Y-%m-%d)

echo "Collecting data from ${START_DATE} to ${END_DATE}"

# Navigate to script directory
cd /opt/trading-system

# Run the collection script
python3 scripts/backfill_dukascopy_data.py \
    --start-date ${START_DATE} \
    --end-date ${END_DATE} \
    --output-dir /data/dukascopy \
    --batch-size 3 \
    --pause-ms 5000 \
    --compression snappy \
    --verbose

# What do these flags mean?
# --start-date: When to start collecting (5 years ago)
# --end-date: When to stop (today)
# --output-dir: Where to save Parquet files
# --batch-size: Download 3 days at a time (rate limiting)
# --pause-ms: Wait 5 seconds between batches (be nice to Dukascopy)
# --compression: Use snappy compression (good balance of speed/size)
# --verbose: Show detailed progress

# Detach from screen (keeps script running):
# Press: Ctrl+A, then D

# Reattach later:
# screen -r dukascopy-collection
```

**What happens now?**
- Script downloads data from Dukascopy
- Converts JSON to Parquet format
- Saves to `/data/dukascopy/`
- Takes 2-3 days for all 28 pairs

**Learn more:**
- [Screen Tutorial](https://linuxize.com/post/how-to-use-linux-screen/)
- [Process Management](https://www.digitalocean.com/community/tutorials/how-to-use-linux-process-management-commands)

---

### Step 11: Monitor Progress

**How to check if it's working?**

**Option 1: Check logs (from local computer)**

```bash
# View latest log entries
gcloud compute ssh ${VM_NAME} --zone=${ZONE} \
    --command="tail -50 /data/logs/dukascopy_backfill.log"

# Follow log in real-time
gcloud compute ssh ${VM_NAME} --zone=${ZONE} \
    --command="tail -f /data/logs/dukascopy_backfill.log"
```

**Option 2: Check progress file**

```bash
# View progress JSON
gcloud compute ssh ${VM_NAME} --zone=${ZONE} \
    --command="cat /data/.dukascopy_progress.json | python3 -m json.tool"
```

**Option 3: Check disk usage**

```bash
# See how much data has been collected
gcloud compute ssh ${VM_NAME} --zone=${ZONE} \
    --command="df -h /data && du -sh /data/dukascopy/*"
```

**Option 4: Check running processes**

```bash
# See if script is still running
gcloud compute ssh ${VM_NAME} --zone=${ZONE} \
    --command="ps aux | grep backfill"
```

**Learn more:**
- [Cloud Logging](https://cloud.google.com/logging/docs)
- [Monitoring VMs](https://cloud.google.com/compute/docs/instances/monitoring-instance-state)

---

### Step 12: Periodically Backup to GCS

**Why backup during collection?**
- Safety: If VM crashes, data is safe in GCS
- Progress: Can see what's been collected
- Verification: Can download a sample to verify it works

**Create backup script (inside VM):**

```bash
# Create backup script
cat > /home/$USER/backup-to-gcs.sh <<'EOF'
#!/bin/bash
BUCKET_NAME="dukascopy-data-$(gcloud config get-value project 2>/dev/null || echo 'default')"

echo "Backing up to gs://${BUCKET_NAME}..."

# Upload Parquet files (only new/changed files)
gsutil -m rsync -r /data/dukascopy/ gs://${BUCKET_NAME}/parquet/ \
    --exclude="*.json" \
    --exclude="*.tmp"

# Upload logs
gsutil -m cp /data/logs/*.log gs://${BUCKET_NAME}/logs/ 2>/dev/null || true

# Upload progress file
if [ -f /data/.dukascopy_progress.json ]; then
    gsutil cp /data/.dukascopy_progress.json gs://${BUCKET_NAME}/logs/
fi

echo "Backup completed at: $(date)"
EOF

chmod +x /home/$USER/backup-to-gcs.sh

# Run backup manually
/home/$USER/backup-to-gcs.sh

# Or set up automatic backup every 6 hours
(crontab -l 2>/dev/null; echo "0 */6 * * * /home/$USER/backup-to-gcs.sh >> /var/log/gcs-backup.log 2>&1") | crontab -
```

**What does `gsutil rsync` do?**
- Compares local files with GCS
- Only uploads new or changed files
- Much faster than uploading everything each time

**Learn more:**
- [gsutil rsync](https://cloud.google.com/storage/docs/gsutil/commands/rsync)
- [Cron Jobs](https://www.digitalocean.com/community/tutorials/how-to-use-cron-to-automate-tasks)

---

## Downloading Data Locally

### Step 13: Download All Data to Your Computer

**When to download?**
After collection completes (check logs to confirm).

**Why download locally?**
- You have full control
- No ongoing cloud storage costs
- Can upload to another provider later
- Faster access for local processing

**Commands (run from YOUR LOCAL COMPUTER):**

```bash
# Set variables
PROJECT_ID=$(gcloud config get-value project)
BUCKET_NAME="dukascopy-data-${PROJECT_ID}"

# Create local directory
mkdir -p ./data/dukascopy

# Download all Parquet files
# -m: Use multiple threads (faster)
# -r: Recursive (download directories)
gsutil -m cp -r gs://${BUCKET_NAME}/parquet/* ./data/dukascopy/

# What does this do?
# - Downloads all files from GCS bucket
# - Maintains directory structure (EURUSD/, GBPUSD/, etc.)
# - Saves to ./data/dukascopy/ on your computer

# Verify download
ls -lh ./data/dukascopy/
du -sh ./data/dukascopy/

# Should show ~130-175GB total
```

**Download specific pairs only:**

```bash
# Download just EURUSD
gsutil -m cp -r gs://${BUCKET_NAME}/parquet/EURUSD/ ./data/dukascopy/EURUSD/

# Download multiple pairs
gsutil -m cp -r gs://${BUCKET_NAME}/parquet/{EURUSD,GBPUSD,USDJPY}/ ./data/dukascopy/
```

**Download logs:**

```bash
# Download collection logs
mkdir -p ./logs/gcp-collection
gsutil -m cp -r gs://${BUCKET_NAME}/logs/ ./logs/gcp-collection/
```

**Learn more:**
- [Downloading from GCS](https://cloud.google.com/storage/docs/downloading-objects)
- [gsutil cp](https://cloud.google.com/storage/docs/gsutil/commands/cp)

---

### Step 14: Verify Downloaded Data

**Why verify?**
Make sure files downloaded correctly and aren't corrupted.

**Commands:**

```bash
# Check file count
find ./data/dukascopy -name "*.parquet" | wc -l
# Should show: 28 pairs × 5 years = 140 files (approximately)

# Check total size
du -sh ./data/dukascopy/
# Should show: ~130-175GB

# Test reading a file (verify it's not corrupted)
python3 -c "
import pandas as pd
import glob

# Test first file
files = glob.glob('./data/dukascopy/*/*.parquet')
if files:
    df = pd.read_parquet(files[0])
    print(f'✓ {files[0]}: {len(df):,} rows')
    print(f'  Columns: {list(df.columns)}')
    print(f'  Date range: {df[\"timestamp\"].min()} to {df[\"timestamp\"].max()}')
else:
    print('No Parquet files found')
"

# Run full validation (if you have the validation script)
python3 scripts/validate_parquet_data.py \
    --data-dir ./data/dukascopy \
    --summary
```

**Learn more:**
- [Data Validation Best Practices](https://www.dataquest.io/blog/data-validation/)

---

### Step 15: Clean Up Cloud Resources

**Why clean up?**
- Stop paying for the VM (saves money)
- GCS bucket can stay (cheap storage) or be deleted

**Commands:**

```bash
# 1. Stop the VM (saves money, but keeps it for later)
gcloud compute instances stop ${VM_NAME} --zone=${ZONE}

# 2. Delete the VM (permanent, but stops all charges)
gcloud compute instances delete ${VM_NAME} --zone=${ZONE}

# 3. Delete GCS bucket (optional - only if you don't need backup)
# WARNING: This deletes all data in the bucket!
gsutil rm -r gs://${BUCKET_NAME}

# 4. Or just delete old files, keep bucket
gsutil rm gs://${BUCKET_NAME}/parquet/**
```

**Cost after cleanup:**
- VM deleted: $0/month
- GCS bucket (if kept): ~$5/month for 200GB
- **Total: ~$5/month** (or $0 if you delete bucket)

**Learn more:**
- [Stopping VMs](https://cloud.google.com/compute/docs/instances/stop-start-instance)
- [Deleting Resources](https://cloud.google.com/compute/docs/instances/deleting-instance)

---

## Future: Re-uploading to Another Provider

### Why Re-upload?

You mentioned wanting to upload to another provider later. Common reasons:
- **Multi-cloud strategy**: Don't depend on one provider
- **Cost optimization**: Different providers have different prices
- **Integration**: Your deployed system might use AWS/Azure/etc.

### Common Cloud Storage Providers

1. **AWS S3** (Amazon Simple Storage Service)
   - Most popular cloud storage
   - [S3 Documentation](https://docs.aws.amazon.com/s3/)

2. **Azure Blob Storage** (Microsoft)
   - Good if using other Azure services
   - [Azure Blob Storage Docs](https://docs.microsoft.com/en-us/azure/storage/blobs/)

3. **Backblaze B2**
   - Cheaper than S3/GCS
   - [B2 Documentation](https://www.backblaze.com/b2/docs/)

4. **DigitalOcean Spaces**
   - S3-compatible, simple pricing
   - [Spaces Documentation](https://www.digitalocean.com/docs/spaces/)

### Example: Uploading to AWS S3

**Prerequisites:**
- AWS account
- AWS CLI installed
- S3 bucket created

**Commands:**

```bash
# Install AWS CLI (if not installed)
# Windows: https://aws.amazon.com/cli/
# Mac: brew install awscli
# Linux: sudo apt-get install awscli

# Configure AWS credentials
aws configure
# Enter: Access Key ID, Secret Access Key, Region

# Create S3 bucket
aws s3 mb s3://your-bucket-name --region us-east-1

# Upload data (similar to gsutil)
aws s3 sync ./data/dukascopy/ s3://your-bucket-name/dukascopy/ \
    --storage-class STANDARD

# Verify upload
aws s3 ls s3://your-bucket-name/dukascopy/ --recursive
```

**Learn more:**
- [AWS S3 Getting Started](https://docs.aws.amazon.com/AmazonS3/latest/userguide/GetStartedWithS3.html)
- [AWS CLI Installation](https://aws.amazon.com/cli/)

### Example: Using DVC for Multi-Cloud

**What is DVC?**
DVC (Data Version Control) is like Git, but for large data files. It can store data in multiple cloud providers.

**Setup:**

```bash
# Install DVC
pip install dvc dvc-s3 dvc-gs

# Initialize DVC
dvc init

# Add data to DVC
dvc add data/dukascopy

# Configure multiple remotes
dvc remote add -d gcs gs://your-gcs-bucket/dukascopy
dvc remote add s3 s3://your-s3-bucket/dukascopy
dvc remote add azure azure://your-container/dukascopy

# Push to GCS
dvc push --remote gcs

# Push to S3
dvc push --remote s3

# Pull from any remote
dvc pull --remote s3
```

**Benefits:**
- Version control for data
- Easy switching between providers
- Automatic checksums (verifies data integrity)

**Learn more:**
- [DVC Documentation](https://dvc.org/doc)
- [DVC Remote Storage](https://dvc.org/doc/command-reference/remote)

---

## Learning Resources

### Google Cloud Platform

1. **Official Documentation**
   - [GCP Documentation Home](https://cloud.google.com/docs)
   - [Compute Engine Guide](https://cloud.google.com/compute/docs)
   - [Cloud Storage Guide](https://cloud.google.com/storage/docs)

2. **Tutorials**
   - [GCP Quickstarts](https://cloud.google.com/docs/get-started)
   - [Compute Engine Tutorials](https://cloud.google.com/compute/docs/tutorials)
   - [Cloud Storage Tutorials](https://cloud.google.com/storage/docs/tutorials)

3. **Courses**
   - [Google Cloud Training](https://cloud.google.com/training)
   - [Coursera: GCP Fundamentals](https://www.coursera.org/learn/gcp-fundamentals)

### Command Line & Linux

1. **Linux Basics**
   - [Linux Command Line Basics](https://ubuntu.com/tutorials/command-line-for-beginners)
   - [Bash Scripting Guide](https://www.gnu.org/software/bash/manual/)

2. **SSH & Remote Access**
   - [SSH Academy](https://www.ssh.com/academy/)
   - [DigitalOcean: SSH Basics](https://www.digitalocean.com/community/tutorials/ssh-essentials-working-with-ssh-servers-clients-and-keys)

### Cloud Storage Concepts

1. **Object Storage Explained**
   - [What is Object Storage?](https://www.cloudflare.com/learning/cloud/what-is-object-storage/)
   - [S3 vs GCS Comparison](https://www.backblaze.com/blog/s3-vs-google-cloud-storage/)

2. **Data Transfer**
   - [Cloud Data Transfer Best Practices](https://cloud.google.com/solutions/migration-to-gcp-transferring-your-large-datasets)

### DevOps Fundamentals

1. **Infrastructure as Code**
   - [What is Infrastructure as Code?](https://www.redhat.com/en/topics/automation/what-is-infrastructure-as-code)

2. **Cloud Architecture**
   - [Cloud Architecture Patterns](https://cloud.google.com/architecture)

---

## Quick Reference: Common Commands

### GCP Commands

```bash
# Authentication
gcloud auth login
gcloud config set project PROJECT_ID

# VM Management
gcloud compute instances create VM_NAME --zone=ZONE
gcloud compute instances list
gcloud compute instances stop VM_NAME --zone=ZONE
gcloud compute instances delete VM_NAME --zone=ZONE
gcloud compute ssh VM_NAME --zone=ZONE

# Storage Management
gsutil mb gs://BUCKET_NAME
gsutil ls gs://BUCKET_NAME
gsutil cp FILE gs://BUCKET_NAME/
gsutil -m cp -r DIR/ gs://BUCKET_NAME/
gsutil -m rsync -r LOCAL_DIR/ gs://BUCKET_NAME/
gsutil rm gs://BUCKET_NAME/FILE
```

### Useful Linux Commands (Inside VM)

```bash
# File operations
ls -lh                    # List files with sizes
df -h                     # Disk usage
du -sh DIR/               # Directory size
tail -f FILE              # Follow log file

# Process management
ps aux | grep PROCESS     # Find running process
screen -S NAME            # Start screen session
screen -r NAME            # Reattach to screen
top                       # Monitor system resources

# Network
curl URL                  # Download file
wget URL                  # Alternative download
```

---

## Troubleshooting Common Issues

### Issue: "Permission denied" errors

**Cause:** VM doesn't have permissions to access GCS

**Solution:**
```bash
# Check service account permissions
gcloud projects get-iam-policy $(gcloud config get-value project)

# Grant Storage Admin role
gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
    --member="serviceAccount:$(gcloud iam service-accounts list --filter='displayName:Compute Engine default service account' --format='value(email)')" \
    --role="roles/storage.admin"
```

### Issue: VM won't start

**Cause:** Usually billing or quota issues

**Solution:**
```bash
# Check quotas
gcloud compute project-info describe --project=$(gcloud config get-value project)

# Check billing
gcloud billing accounts list
gcloud billing projects describe $(gcloud config get-value project)
```

### Issue: Slow download from GCS

**Cause:** Network speed or region mismatch

**Solution:**
- Use `-m` flag for parallel downloads: `gsutil -m cp ...`
- Download from same region as your location
- Use `rsync` instead of `cp` for incremental updates

---

## Summary

**What we accomplished:**
1. ✅ Created a VM in Google Cloud
2. ✅ Installed required software
3. ✅ Started data collection (runs for 2-3 days)
4. ✅ Backed up data to GCS during collection
5. ✅ Downloaded all data to local computer
6. ✅ Cleaned up cloud resources

**Total cost:** ~$30-40 for VM (3 days) + ~$5/month for GCS (optional)

**Next steps:**
- Validate downloaded data
- Upload to another provider (if needed)
- Use data in your trading system

**Key learnings:**
- Cloud computing basics
- VM management
- Cloud storage (GCS)
- Remote server administration (SSH)
- Data transfer best practices

---

**Questions?** Check the troubleshooting section or refer to the linked documentation!
