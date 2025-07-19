#!/bin/bash

# Verification script for Kugelpos project tools

echo "========================================="
echo "Kugelpos Tools Verification"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check tool
check_tool() {
    local tool_name=$1
    local version_cmd=$2
    local min_version=$3
    
    if command -v ${tool_name%% *} >/dev/null 2>&1; then
        version=$(eval "$version_cmd")
        echo -e "${GREEN}✓${NC} $tool_name: $version"
        return 0
    else
        echo -e "${RED}✗${NC} $tool_name: NOT FOUND"
        return 1
    fi
}

# Check Python (with pyenv)
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
if command -v pyenv >/dev/null 2>&1; then
    eval "$(pyenv init - bash)"
fi

echo "Checking required tools..."
echo ""

# Check each tool
check_tool "python" "python --version" "3.12"
check_tool "docker" "docker --version" ""
check_tool "docker compose" "docker compose version" ""
check_tool "pipenv" "pipenv --version" ""
check_tool "dapr" "dapr --version | grep 'CLI version'" ""

echo ""

# Check Docker daemon
echo "Checking Docker daemon..."
if docker info >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Docker daemon is running"
else
    if groups | grep -q docker; then
        echo -e "${YELLOW}!${NC} Docker daemon not accessible. You may need to:"
        echo "   - Start Docker service: sudo systemctl start docker"
        echo "   - Or run: newgrp docker"
    else
        echo -e "${RED}✗${NC} User not in docker group. Run: sudo usermod -aG docker $USER"
        echo "   Then log out and back in."
    fi
fi

echo ""

# Check if we're in the right directory
if [[ -f "docker-compose.yaml" ]] || [[ -f "services/docker-compose.yaml" ]]; then
    echo -e "${GREEN}✓${NC} In Kugelpos project directory"
else
    echo -e "${YELLOW}!${NC} Not in Kugelpos project root. Please cd to the project directory."
fi

echo ""
echo "========================================="
echo "Verification complete!"
echo "========================================="