#!/bin/bash

# Script to build commons, update all services with the latest version, and rebuild pipenv environments
# This script:
# 1. Runs run_build_common.sh to build the commons package
# 2. Runs run_copy_common.sh to distribute the commons package to all services
# 3. Updates all service Pipfiles to use the latest kugel_common version
# 4. Runs rebuild_pipenv.sh to rebuild all pipenv environments

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Get script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

print_info "Starting commons update and rebuild process..."

# Step 1: Build and distribute commons package
print_info "Building commons package..."
if [ -f "$SCRIPT_DIR/run_build_common.sh" ]; then
    "$SCRIPT_DIR/run_build_common.sh"
else
    print_error "run_build_common.sh not found!"
    exit 1
fi

print_info "Copying commons package to all services..."
if [ -f "$SCRIPT_DIR/run_copy_common.sh" ]; then
    "$SCRIPT_DIR/run_copy_common.sh"
else
    print_error "run_copy_common.sh not found!"
    exit 1
fi

# Step 2: Find the latest kugel_common wheel file
print_info "Finding latest kugel_common version..."
COMMONS_DIST_DIR="$PROJECT_ROOT/services/commons/dist"
LATEST_WHEEL=$(ls -t "$COMMONS_DIST_DIR"/kugel_common-*-py3-none-any.whl 2>/dev/null | head -n 1)

if [ -z "$LATEST_WHEEL" ]; then
    print_error "No kugel_common wheel file found in $COMMONS_DIST_DIR"
    exit 1
fi

# Extract version from filename
WHEEL_FILENAME=$(basename "$LATEST_WHEEL")
VERSION=$(echo "$WHEEL_FILENAME" | sed -n 's/kugel_common-\([0-9]\+\.[0-9]\+\.[0-9]\+\)-py3-none-any\.whl/\1/p')

print_info "Latest kugel_common version: $VERSION"
print_info "Wheel file: $WHEEL_FILENAME"

# Step 3: Update all service Pipfiles
SERVICES=("account" "terminal" "master-data" "cart" "report" "journal" "stock")

for service in "${SERVICES[@]}"; do
    print_info "Updating $service Pipfile..."
    PIPFILE="$PROJECT_ROOT/services/$service/Pipfile"
    
    if [ -f "$PIPFILE" ]; then
        # Check if kugel_common is already in Pipfile
        if grep -q "kugel_common" "$PIPFILE"; then
            # Update existing entry
            sed -i "s|kugel_common = {file = \"commons/dist/kugel_common-[0-9.]*-py3-none-any\.whl\"}|kugel_common = {file = \"commons/dist/kugel_common-${VERSION}-py3-none-any.whl\"}|" "$PIPFILE"
            print_info "  Updated $service Pipfile with version $VERSION"
        else
            # Add new entry before [dev-packages] section
            sed -i "/\[dev-packages\]/i kugel_common = {file = \"commons/dist/kugel_common-${VERSION}-py3-none-any.whl\"}\n" "$PIPFILE"
            print_info "  Added kugel_common to $service Pipfile with version $VERSION"
        fi
    else
        print_warning "$service Pipfile not found at $PIPFILE"
    fi
done

# Step 4: Run rebuild_pipenv.sh to rebuild all environments
print_info "Rebuilding all pipenv environments..."
if [ -f "$SCRIPT_DIR/rebuild_pipenv.sh" ]; then
    "$SCRIPT_DIR/rebuild_pipenv.sh"
else
    print_error "rebuild_pipenv.sh not found!"
    exit 1
fi

print_info "Process completed successfully!"
print_info "All services have been updated to use kugel_common version $VERSION"