# Kugelpos Installation Guide

This guide provides step-by-step instructions for installing all required tools for the Kugelpos project.

## Overview

Kugelpos is a microservices-based Point of Sale (POS) backend system that requires the following tools:

- **Python 3.12+** - Programming language runtime
- **Docker & Docker Compose** - Container runtime and orchestration
- **Pipenv** - Python dependency management
- **Dapr CLI** (optional) - Distributed application runtime

## Tested Environment

This installation guide has been tested on:
- **OS**: Debian GNU/Linux 12 (bookworm)
- **Architecture**: ARM64 (aarch64)
- **Kernel**: Linux 6.1.0-37-cloud-arm64

## Supported Environments

The installation scripts are designed for Debian-based Linux distributions and include compatibility features for:
- Native Linux (Debian, Ubuntu) on x86_64 and ARM64 architectures
- Windows Subsystem for Linux (WSL1 and WSL2)
  - WSL2 is recommended for better performance
  - Includes Docker Desktop integration support
  - Automatic detection of WSL environment

## Quick Installation

We provide automated installation scripts for Linux systems:

```bash
# Clone the repository
git clone https://github.com/kugel-masa/kugelpos-backend.git
cd kugelpos-backend

# Run the installation script
./install/install_tools.sh

# Apply shell configuration changes
source ~/.bashrc
# OR log out and log back in

# Verify installation
./install/verify_installation.sh
```

## Detailed Installation Steps

### 1. System Prerequisites

Update your system and install build dependencies:

```bash
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
```

### 2. Python 3.12+ Installation

We use pyenv to manage Python versions:

```bash
# Install pyenv
curl -fsSL https://pyenv.run | bash

# Add pyenv to your shell
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init - bash)"' >> ~/.bashrc
echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc

# Reload shell configuration
source ~/.bashrc

# Install Python 3.12.11
pyenv install 3.12.11
pyenv global 3.12.11

# Verify installation
python --version  # Should show: Python 3.12.11
```

### 3. Docker Installation

Install Docker and Docker Compose using the official script:

```bash
# Download and run Docker installation script
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
rm get-docker.sh

# Add your user to the docker group
sudo usermod -aG docker $USER

# Log out and back in for group changes to take effect
# OR run: newgrp docker

# Verify installation
docker --version
docker compose version
```

### 4. Pipenv Installation

Install Pipenv for Python dependency management:

```bash
pip install pipenv

# Verify installation
pipenv --version
```

### 5. Dapr CLI Installation (Optional)

Dapr is optional but recommended for distributed application features:

```bash
wget -q https://raw.githubusercontent.com/dapr/cli/master/install/install.sh -O - | /bin/bash

# Verify installation
dapr --version
```

## Post-Installation Steps

### 1. Verify All Installations

Run the verification script:

```bash
./install/verify_installation.sh
```

Expected output:
```
✓ python: 3.12.11
✓ docker: 28.3.2
✓ docker compose: v2.38.2
✓ pipenv: 2025.0.4
✓ dapr: 1.15.1
```

### 2. Docker Configuration

If you see "Docker daemon not accessible" error:

```bash
# Option 1: Start Docker service
sudo systemctl start docker
sudo systemctl enable docker  # Enable auto-start on boot

# Option 2: Apply group changes without logging out
newgrp docker
```

### 3. Initialize Dapr (Optional)

If using Dapr:

```bash
dapr init
dapr --version
```

## Troubleshooting

### Python Issues

If `python --version` shows an older version:
```bash
# Ensure pyenv is properly initialized
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - bash)"

# Set Python 3.12.11 as global
pyenv global 3.12.11
```

### Docker Permission Issues

If you get "permission denied" errors with Docker:
```bash
# Verify you're in the docker group
groups | grep docker

# If not, add yourself
sudo usermod -aG docker $USER

# Apply changes
newgrp docker
```

### Pipenv Not Found

If `pipenv` command is not found:
```bash
# Ensure pip is using the correct Python
which python
which pip

# Reinstall pipenv
pip install --user pipenv

# Add to PATH if needed
export PATH="$HOME/.local/bin:$PATH"
```

## Manual Installation (Alternative Methods)

### macOS Installation

```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install tools
brew install python@3.12
brew install --cask docker
brew install pipenv

# Install Dapr
curl -fsSL https://raw.githubusercontent.com/dapr/cli/master/install/install.sh | /bin/bash
```

### Windows Installation

1. **Python**: Download from [python.org](https://www.python.org/downloads/)
2. **Docker Desktop**: Download from [docker.com](https://www.docker.com/products/docker-desktop)
3. **Pipenv**: Run `pip install pipenv` in Command Prompt
4. **Dapr**: Download from [dapr.io](https://docs.dapr.io/getting-started/install-dapr-cli/)

## Next Steps

After successful installation:

1. Clone the Kugelpos repository (if not already done)
2. Navigate to the project directory
3. Run the quick start commands:

```bash
# Navigate to scripts directory
cd scripts

# Build all services
./build.sh

# Start all services
./start.sh
```

For detailed development instructions, see the main [README.md](../README.md) and [CLAUDE.md](../CLAUDE.md) files.

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Ensure all system requirements are met
3. Review error messages in the installation output
4. Check project issues on GitHub

## Version Requirements Summary

| Tool | Minimum Version | Recommended Version |
|------|----------------|---------------------|
| Python | 3.12+ | 3.12.11 |
| Docker | 20.10+ | Latest stable |
| Docker Compose | 2.0+ | Latest stable |
| Pipenv | Any recent | Latest stable |
| Dapr CLI | 1.10+ | 1.15.1 |

## Uninstallation

To remove the tools installed by this guide:

```bash
./install/uninstall_tools.sh
```

This script will:
- Remove Pipenv
- Remove Dapr CLI and runtime
- Remove Docker and Docker Compose (optionally including data)
- Remove Python 3.12.11 (and optionally pyenv)
- Optionally remove build dependencies

The uninstall script provides interactive prompts to confirm each removal step.

## WSL (Windows Subsystem for Linux) Notes

When running on WSL:

### Docker Installation Options
1. **Docker Desktop (Recommended)**
   - Install Docker Desktop on Windows
   - Enable WSL2 integration in Docker Desktop settings
   - Docker commands will work seamlessly in WSL

2. **Native Docker in WSL**
   - Install Docker directly in WSL using the script
   - Requires manual daemon management
   - May have limitations with systemd

### WSL Best Practices
- Use WSL2 for better performance and compatibility
- Work within WSL filesystem (`/home/`) rather than Windows drives (`/mnt/c/`)
- Enable systemd in WSL2 for better service management

## Notes

- The installation script is designed for Debian-based Linux distributions (Ubuntu, Debian)
- For other operating systems, follow the manual installation steps
- Docker requires either root privileges or proper group membership
- All tools can be updated independently after installation
- WSL users should prefer Docker Desktop integration over native Docker installation