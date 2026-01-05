#!/bin/bash

# Server Linting Script
# Runs all linting checks: Black, Flake8, and MyPy
# Matches the CI workflow configuration exactly

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if we're in the mt5-python_server directory
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}❌ Error: This script must be run from the src/mt5-python_server directory${NC}"
    exit 1
fi

# Check if src directory exists
if [ ! -d "src" ]; then
    echo -e "${RED}❌ Error: src directory not found${NC}"
    exit 1
fi

echo "🔍 Running Server linting checks..."
echo ""

# Detect Python command - prefer 'python' (Windows) over 'python3' (Linux/Git Bash system Python)
# Check if we're in a virtual environment first
VENV_PYTHON=""
if [ -n "$VIRTUAL_ENV" ]; then
    # Use the virtual environment's Python from VIRTUAL_ENV
    if [ -f "$VIRTUAL_ENV/Scripts/python.exe" ]; then
        VENV_PYTHON="$VIRTUAL_ENV/Scripts/python.exe"
    elif [ -f "$VIRTUAL_ENV/bin/python" ]; then
        VENV_PYTHON="$VIRTUAL_ENV/bin/python"
    fi
fi

# If VIRTUAL_ENV not set or not found, check for venv in parent directory (common pattern)
if [ -z "$VENV_PYTHON" ]; then
    PARENT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
    if [ -f "$PARENT_DIR/venv/Scripts/python.exe" ]; then
        VENV_PYTHON="$PARENT_DIR/venv/Scripts/python.exe"
    elif [ -f "$PARENT_DIR/venv/bin/python" ]; then
        VENV_PYTHON="$PARENT_DIR/venv/bin/python"
    fi
fi

if [ -n "$VENV_PYTHON" ] && [ -f "$VENV_PYTHON" ]; then
    PYTHON_CMD="$VENV_PYTHON"
    echo -e "${YELLOW}ℹ️  Using virtual environment: $(dirname "$(dirname "$VENV_PYTHON")")${NC}"
elif command -v python &> /dev/null && python -c "import sys; sys.exit(0)" 2>/dev/null; then
    # Prefer 'python' (usually Windows Python or venv) - verify it works
    PYTHON_CMD="python"
elif command -v python3 &> /dev/null && python3 -c "import sys; sys.exit(0)" 2>/dev/null; then
    # Fallback to python3 - verify it works
    PYTHON_CMD="python3"
else
    echo -e "${RED}❌ Error: Python not found. Please install Python 3.11+${NC}"
    exit 1
fi

# Verify Python is accessible and has the required modules
echo -e "${YELLOW}ℹ️  Using Python: $PYTHON_CMD${NC}"
if ! $PYTHON_CMD -c "import black, flake8, mypy" 2>/dev/null; then
    echo -e "${RED}❌ Error: Required linting tools not found${NC}"
    echo -e "${YELLOW}💡 Please install them with: $PYTHON_CMD -m pip install black flake8 mypy${NC}"
    echo -e "${YELLOW}💡 Or activate your virtual environment first${NC}"
    exit 1
fi
echo ""

# Step 1: Black formatting check
echo -e "${YELLOW}📋 Step 1/3: Checking code formatting with Black...${NC}"
if $PYTHON_CMD -m black --check src/; then
    echo -e "${GREEN}✅ Black: Code is properly formatted${NC}"
else
    echo -e "${RED}❌ Black: Code formatting issues found${NC}"
    echo -e "${YELLOW}💡 Run '$PYTHON_CMD -m black src/' to auto-format${NC}"
    exit 1
fi
echo ""

# Step 2: Flake8 linting
echo -e "${YELLOW}📋 Step 2/3: Running Flake8 linter...${NC}"
if $PYTHON_CMD -m flake8 src/ --max-line-length=120 --extend-ignore=E203,W503; then
    echo -e "${GREEN}✅ Flake8: No linting issues found${NC}"
else
    echo -e "${RED}❌ Flake8: Linting issues found${NC}"
    exit 1
fi
echo ""

# Step 3: MyPy type checking
echo -e "${YELLOW}📋 Step 3/3: Running MyPy type checker...${NC}"
if $PYTHON_CMD -m mypy src/ --ignore-missing-imports; then
    echo -e "${GREEN}✅ MyPy: No type errors found${NC}"
else
    echo -e "${RED}❌ MyPy: Type errors found${NC}"
    exit 1
fi
echo ""

echo -e "${GREEN}🎉 All linting checks passed!${NC}"
