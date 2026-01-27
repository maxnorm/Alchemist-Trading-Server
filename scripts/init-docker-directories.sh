#!/bin/bash
# Initialize all Docker directories with proper permissions
# Run this BEFORE starting docker-compose to prevent permission issues

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "Docker Directory Initialization"
echo "=========================================="
echo "Project root: $PROJECT_ROOT"
echo ""

# Function to create directory with permissions
create_dir() {
    local dir="$1"
    local desc="$2"
    local perms="${3:-777}"
    
    echo "Creating: $desc"
    echo "  Path: $dir"
    
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        echo "  ✓ Created directory"
    else
        echo "  ✓ Directory already exists"
    fi
    
    # Set permissions
    if chmod "$perms" "$dir" 2>/dev/null; then
        echo "  ✓ Set permissions to $perms"
    else
        echo "  ⚠ Could not set permissions without sudo, trying with sudo..."
        if sudo chmod "$perms" "$dir" 2>/dev/null; then
            echo "  ✓ Set permissions to $perms (with sudo)"
        else
            echo "  ✗ Failed to set permissions. Please run manually:"
            echo "    sudo chmod $perms $dir"
            return 1
        fi
    fi
    
    # For directories that need recursive permissions
    if [ "$perms" = "777" ]; then
        if chmod -R "$perms" "$dir" 2>/dev/null; then
            echo "  ✓ Set recursive permissions"
        else
            if sudo chmod -R "$perms" "$dir" 2>/dev/null; then
                echo "  ✓ Set recursive permissions (with sudo)"
            fi
        fi
    fi
    
    echo ""
}

# Directories that need to be created before Docker starts
# Format: directory_path "description" permissions

# Log directories
create_dir "$PROJECT_ROOT/logs" "Application logs directory" "777"
create_dir "$PROJECT_ROOT/logs/gateway" "Gateway nginx logs" "777"

# Model storage
create_dir "$PROJECT_ROOT/models" "Trained models directory" "777"

# Airflow directories
create_dir "$PROJECT_ROOT/airflow_logs" "Airflow logs directory" "777"
create_dir "$PROJECT_ROOT/airflow_logs/scheduler" "Airflow scheduler logs" "777"
create_dir "$PROJECT_ROOT/airflow_logs/webserver" "Airflow webserver logs" "777"
create_dir "$PROJECT_ROOT/airflow_logs/dag_processor_manager" "Airflow DAG processor logs" "777"

create_dir "$PROJECT_ROOT/airflow_plugins" "Airflow plugins directory" "777"

echo "=========================================="
echo "✓ All directories initialized"
echo "=========================================="
echo ""
echo "Directories created:"
echo "  - $PROJECT_ROOT/logs"
echo "  - $PROJECT_ROOT/logs/gateway"
echo "  - $PROJECT_ROOT/models"
echo "  - $PROJECT_ROOT/airflow_logs (with subdirectories)"
echo "  - $PROJECT_ROOT/airflow_plugins"
echo ""
echo "You can now start Docker services:"
echo "  docker compose up -d"
echo ""
