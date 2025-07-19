#!/bin/bash

# Kugelpos Project Tools Installation Script
# This script installs all required tools for the Kugelpos project

set -e  # Exit on error

echo "========================================="
echo "Kugelpos Tools Installation Script"
echo "========================================="
echo ""

# Check if running in WSL
if grep -qi microsoft /proc/version; then
    echo "WSL environment detected."
    echo ""
    # Check WSL version
    if [[ -f /proc/sys/fs/binfmt_misc/WSLInterop ]]; then
        echo "Running on WSL2 (recommended)"
    else
        echo "Running on WSL1 (WSL2 is recommended for better performance)"
    fi
    echo ""
fi

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to add to PATH if not already present
add_to_path() {
    if [[ ":$PATH:" != *":$1:"* ]]; then
        export PATH="$1:$PATH"
    fi
}

# 1. Install system dependencies
echo "1. Installing system dependencies..."
echo "   This may require sudo password."
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    wget \
    curl \
    llvm \
    libncurses5-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libffi-dev \
    liblzma-dev \
    python3-openssl \
    git

echo "✓ System dependencies installed"
echo ""

# 2. Install Python 3.12+ using pyenv
echo "2. Installing Python 3.12.11..."
if ! command_exists pyenv; then
    echo "   Installing pyenv..."
    curl -fsSL https://pyenv.run | bash
    
    # Configure shell for pyenv
    export PYENV_ROOT="$HOME/.pyenv"
    add_to_path "$PYENV_ROOT/bin"
    eval "$(pyenv init - bash)"
    eval "$(pyenv virtualenv-init -)"
    
    # Add to bashrc for future sessions
    if ! grep -q 'export PYENV_ROOT="$HOME/.pyenv"' ~/.bashrc; then
        echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
        echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
        echo 'eval "$(pyenv init - bash)"' >> ~/.bashrc
        echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc
    fi
else
    echo "   pyenv already installed"
    export PYENV_ROOT="$HOME/.pyenv"
    add_to_path "$PYENV_ROOT/bin"
    eval "$(pyenv init - bash)"
fi

# Install Python 3.12.11 if not already installed
if ! pyenv versions | grep -q "3.12.11"; then
    echo "   Installing Python 3.12.11..."
    pyenv install 3.12.11
else
    echo "   Python 3.12.11 already installed"
fi

# Set as global version
pyenv global 3.12.11
echo "✓ Python $(python --version) installed"
echo ""

# 3. Install Docker and Docker Compose
echo "3. Installing Docker..."

# Check for Docker Desktop integration in WSL
if grep -qi microsoft /proc/version; then
    # Check if Docker Desktop is available
    if command_exists docker.exe; then
        echo "   Docker Desktop detected on Windows host."
        echo "   Please ensure WSL integration is enabled in Docker Desktop settings."
        echo ""
    fi
    
    # Check if docker is available via Docker Desktop integration
    if command_exists docker && docker version >/dev/null 2>&1; then
        echo "   Docker is available (likely via Docker Desktop integration)"
    else
        echo "   Docker not found. You have two options:"
        echo "   1. Install Docker Desktop on Windows and enable WSL integration (recommended)"
        echo "   2. Install Docker directly in WSL (using this script)"
        echo ""
        read -p "   Do you want to install Docker directly in WSL? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "   Skipping Docker installation. Please install Docker Desktop instead."
            SKIP_DOCKER=true
        fi
    fi
fi

if [[ "$SKIP_DOCKER" != "true" ]] && ! command_exists docker; then
    echo "   Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
    
    # Add user to docker group
    sudo usermod -aG docker $USER
    echo "   Note: You'll need to log out and back in for docker group changes to take effect"
else
    if [[ "$SKIP_DOCKER" != "true" ]]; then
        echo "   Docker already installed"
    fi
fi
if [[ "$SKIP_DOCKER" != "true" ]]; then
    echo "✓ Docker $(docker --version 2>/dev/null | cut -d' ' -f3 | tr -d ',' || echo 'Check installation') installed"
    echo "✓ Docker Compose $(docker compose version 2>/dev/null | cut -d' ' -f4 || echo 'Check installation') installed"
fi
echo ""

# 4. Install Pipenv
echo "4. Installing Pipenv..."
if ! command_exists pipenv; then
    pip install pipenv
else
    echo "   Pipenv already installed"
fi
echo "✓ $(pipenv --version) installed"
echo ""

# 5. Install Dapr CLI (optional)
echo "5. Installing Dapr CLI (optional)..."
if ! command_exists dapr; then
    wget -q https://raw.githubusercontent.com/dapr/cli/master/install/install.sh -O - | /bin/bash
else
    echo "   Dapr CLI already installed"
fi
echo "✓ Dapr CLI $(dapr --version | grep 'CLI version' | cut -d' ' -f3) installed"
echo ""

# 6. Summary
echo "========================================="
echo "Installation Summary"
echo "========================================="
echo "Python: $(python --version)"
echo "Docker: $(docker --version 2>/dev/null || echo 'Installed but requires re-login')"
echo "Docker Compose: $(docker compose version 2>/dev/null || echo 'Installed but requires re-login')"
echo "Pipenv: $(pipenv --version)"
echo "Dapr CLI: $(dapr --version | grep 'CLI version')"
echo ""
echo "✓ All tools have been installed successfully!"
echo ""
echo "IMPORTANT NOTES:"
if [[ "$SKIP_DOCKER" != "true" ]]; then
    echo "1. You need to log out and log back in (or run 'newgrp docker') to use Docker without sudo"
fi
echo "2. For the current terminal session, run: source ~/.bashrc"
echo "3. To verify everything is working, run: ./install/verify_installation.sh"

# WSL-specific notes
if grep -qi microsoft /proc/version; then
    echo ""
    echo "WSL-SPECIFIC NOTES:"
    if command_exists docker.exe; then
        echo "- Docker Desktop detected. Ensure WSL integration is enabled in Docker Desktop settings"
    fi
    echo "- For best performance, work within the WSL filesystem (/home/) rather than Windows drives (/mnt/)"
    echo "- If using systemd services, ensure systemd is enabled in WSL2 (wsl.conf)"
fi
echo ""