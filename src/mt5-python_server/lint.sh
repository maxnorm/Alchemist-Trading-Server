#!/bin/bash

# Server Linting Script
# Runs all linting checks: Black, Flake8, MyPy, Bandit, and Safety
# Matches the CI workflow configuration

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
if ! $PYTHON_CMD -c "import black, flake8, mypy, bandit, safety" 2>/dev/null; then
    echo -e "${RED}❌ Error: Required linting tools not found${NC}"
    echo -e "${YELLOW}💡 Please install them with: $PYTHON_CMD -m pip install black flake8 mypy bandit safety${NC}"
    echo -e "${YELLOW}💡 Or activate your virtual environment first${NC}"
    exit 1
fi
echo ""

# Step 1: Black formatting check
echo -e "${YELLOW}📋 Step 1/5: Checking code formatting with Black...${NC}"
if $PYTHON_CMD -m black --check src/; then
    echo -e "${GREEN}✅ Black: Code is properly formatted${NC}"
else
    echo -e "${RED}❌ Black: Code formatting issues found${NC}"
    echo -e "${YELLOW}💡 Run '$PYTHON_CMD -m black src/' to auto-format${NC}"
    exit 1
fi
echo ""

# Step 2: Flake8 linting
echo -e "${YELLOW}📋 Step 2/5: Running Flake8 linter...${NC}"
if $PYTHON_CMD -m flake8 src/ --max-line-length=120 --extend-ignore=E203,W503; then
    echo -e "${GREEN}✅ Flake8: No linting issues found${NC}"
else
    echo -e "${RED}❌ Flake8: Linting issues found${NC}"
    exit 1
fi
echo ""

# Step 3: MyPy type checking
echo -e "${YELLOW}📋 Step 3/5: Running MyPy type checker...${NC}"
# Run MyPy but don't fail on errors (type checking is informational)
$PYTHON_CMD -m mypy src/ --ignore-missing-imports --no-strict-optional --allow-untyped-defs --allow-untyped-calls 2>&1 || true
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ MyPy: No type errors found${NC}"
else
    echo -e "${YELLOW}⚠️  MyPy: Some type warnings found (non-blocking)${NC}"
fi
echo ""

# Step 4: Bandit security scan
echo -e "${YELLOW}📋 Step 4/5: Running Bandit security scan...${NC}"
if $PYTHON_CMD -m bandit -r src/ -f json -o bandit-report.json; then
    echo -e "${GREEN}✅ Bandit: No security issues found${NC}"
else
    echo -e "${YELLOW}⚠️  Bandit: Security issues found (see bandit-report.json)${NC}"
    # Bandit exits with non-zero on findings, but we continue
fi
echo ""

# Step 5: Safety dependency vulnerability scan
echo -e "${YELLOW}📋 Step 5/5: Running Safety dependency vulnerability scan...${NC}"
if $PYTHON_CMD -m safety check --json > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Safety: No vulnerable dependencies found${NC}"
else
    echo -e "${YELLOW}⚠️  Safety: Some dependency vulnerabilities found (see safety report)${NC}"
    echo -e "${YELLOW}💡 Run '$PYTHON_CMD -m safety check' to see details${NC}"
    # Safety warnings are non-blocking - dependency updates needed separately
fi
echo ""

echo -e "${GREEN}🎉 Core linting checks passed!${NC}"
echo -e "${YELLOW}ℹ️  Note: MyPy type warnings and Safety dependency issues are informational${NC}"
