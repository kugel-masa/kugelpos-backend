#!/bin/bash

# Kugelpos Project Tools Uninstallation Script
# This script removes tools installed by install_tools.sh

set -e  # Exit on error

echo "========================================="
echo "Kugelpos Tools Uninstallation Script"
echo "========================================="
echo ""
echo "WARNING: This will remove the following tools:"
echo "  - Python 3.12.11 (via pyenv)"
echo "  - Docker and Docker Compose"
echo "  - Pipenv"
echo "  - Dapr CLI"
echo ""
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstallation cancelled."
    exit 0
fi

echo ""

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 1. Uninstall Pipenv
echo "1. Uninstalling Pipenv..."
if command_exists pipenv; then
    pip uninstall -y pipenv
    echo "✓ Pipenv uninstalled"
else
    echo "   Pipenv not found, skipping..."
fi
echo ""

# 2. Uninstall Dapr CLI
echo "2. Uninstalling Dapr CLI..."
if command_exists dapr; then
    # Stop and uninstall Dapr runtime if initialized
    if [[ -d "$HOME/.dapr" ]]; then
        echo "   Uninstalling Dapr runtime..."
        dapr uninstall || true
    fi
    
    # Remove Dapr CLI
    sudo rm -f /usr/local/bin/dapr
    
    # Remove Dapr directories
    rm -rf "$HOME/.dapr"
    
    echo "✓ Dapr CLI uninstalled"
else
    echo "   Dapr CLI not found, skipping..."
fi
echo ""

# 3. Uninstall Docker
echo "3. Uninstalling Docker..."
if command_exists docker; then
    echo "   Stopping Docker service..."
    sudo systemctl stop docker || true
    sudo systemctl disable docker || true
    
    echo "   Removing Docker packages..."
    sudo apt-get purge -y docker-ce docker-ce-cli containerd.io docker-compose-plugin docker-ce-rootless-extras docker-buildx-plugin || true
    
    # Remove Docker repository
    sudo rm -f /etc/apt/sources.list.d/docker.list
    sudo rm -f /etc/apt/keyrings/docker.asc
    
    # Remove Docker group (only if no members)
    if getent group docker >/dev/null 2>&1; then
        # Check if docker group has any members
        if [[ -z $(getent group docker | cut -d: -f4) ]]; then
            sudo groupdel docker
        else
            echo "   Docker group has members, not removing..."
        fi
    fi
    
    # Remove Docker data (optional)
    read -p "Remove Docker data directories (/var/lib/docker)? This will delete all containers, images, and volumes! (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo rm -rf /var/lib/docker
        sudo rm -rf /var/lib/containerd
        echo "   Docker data removed"
    fi
    
    echo "✓ Docker uninstalled"
else
    echo "   Docker not found, skipping..."
fi
echo ""

# 4. Uninstall Python 3.12.11 via pyenv
echo "4. Uninstalling Python 3.12.11..."
if command_exists pyenv; then
    # Check if Python 3.12.11 is installed
    if pyenv versions | grep -q "3.12.11"; then
        # Get current global version
        current_global=$(pyenv global)
        
        # Uninstall Python 3.12.11
        pyenv uninstall -f 3.12.11
        echo "   Python 3.12.11 uninstalled"
        
        # Set system python as global if 3.12.11 was the global version
        if [[ "$current_global" == "3.12.11" ]]; then
            pyenv global system
            echo "   Switched global Python to system version"
        fi
    else
        echo "   Python 3.12.11 not found in pyenv"
    fi
    
    # Ask about removing pyenv itself
    read -p "Remove pyenv completely? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Remove pyenv
        rm -rf "$HOME/.pyenv"
        
        # Remove pyenv from bashrc
        if [[ -f "$HOME/.bashrc" ]]; then
            # Create backup
            cp "$HOME/.bashrc" "$HOME/.bashrc.bak.$(date +%Y%m%d%H%M%S)"
            
            # Remove pyenv lines
            sed -i '/export PYENV_ROOT="\$HOME\/\.pyenv"/d' "$HOME/.bashrc"
            sed -i '/\[\[ -d \$PYENV_ROOT\/bin \]\] && export PATH="\$PYENV_ROOT\/bin:\$PATH"/d' "$HOME/.bashrc"
            sed -i '/eval "\$(pyenv init - bash)"/d' "$HOME/.bashrc"
            sed -i '/eval "\$(pyenv virtualenv-init -)"/d' "$HOME/.bashrc"
            
            echo "   Removed pyenv from ~/.bashrc (backup created)"
        fi
        
        echo "✓ pyenv completely removed"
    else
        echo "   pyenv kept, only Python 3.12.11 removed"
    fi
else
    echo "   pyenv not found, skipping..."
fi
echo ""

# 5. Remove system dependencies (optional)
echo "5. System dependencies..."
read -p "Remove build dependencies installed for Python compilation? (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "   Removing build dependencies..."
    sudo apt-get autoremove -y \
        build-essential \
        libssl-dev \
        zlib1g-dev \
        libbz2-dev \
        libreadline-dev \
        libsqlite3-dev \
        llvm \
        libncurses5-dev \
        libncursesw5-dev \
        tk-dev \
        libffi-dev \
        liblzma-dev \
        python3-openssl || true
    
    echo "✓ Build dependencies removed"
else
    echo "   Keeping system dependencies"
fi
echo ""

# 6. Summary
echo "========================================="
echo "Uninstallation Summary"
echo "========================================="

# Check what's still installed
remaining_tools=""
command_exists python && remaining_tools="${remaining_tools}Python ($(python --version 2>&1 | cut -d' ' -f2)), "
command_exists docker && remaining_tools="${remaining_tools}Docker, "
command_exists pipenv && remaining_tools="${remaining_tools}Pipenv, "
command_exists dapr && remaining_tools="${remaining_tools}Dapr, "
command_exists pyenv && remaining_tools="${remaining_tools}pyenv, "

if [[ -n "$remaining_tools" ]]; then
    echo "Remaining tools: ${remaining_tools%, }"
else
    echo "All Kugelpos tools have been uninstalled."
fi

echo ""
echo "IMPORTANT NOTES:"
echo "1. You may need to restart your shell or run 'source ~/.bashrc' for changes to take effect"
echo "2. Git and wget/curl were not removed as they are common system tools"
echo "3. If you removed Docker data, all containers, images, and volumes have been deleted"
echo ""

# Clean up apt cache
echo "Cleaning up package cache..."
sudo apt-get autoremove -y >/dev/null 2>&1
sudo apt-get autoclean -y >/dev/null 2>&1

echo "✓ Uninstallation complete!"