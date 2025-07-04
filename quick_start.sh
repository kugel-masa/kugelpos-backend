#!/bin/bash

# Quick Start Script
# This script runs the complete setup and start process in sequence

echo "=== Quick Start Script ==="

# Set required environment variables for development
echo "Setting required environment variables for development..."
export SECRET_KEY="dev-secret-key-123456789"
export PUBSUB_NOTIFY_API_KEY="dev-api-key-123456789"
echo "Environment variables set: SECRET_KEY, PUBSUB_NOTIFY_API_KEY"

# Step 0: Clean up orphaned containers
echo "Step 0: Cleaning up orphaned containers..."
cd services
docker-compose down --remove-orphans 2>/dev/null || true
cd ..

# Step 1: Set execute permission for make_scripts_executable.sh and run it
echo "Step 1: Setting up script permissions..."
if [ ! -x "./scripts/make_scripts_executable.sh" ]; then
    echo "Setting execute permission for make_scripts_executable.sh..."
    chmod +x ./scripts/make_scripts_executable.sh
fi

echo "Running make_scripts_executable.sh..."
./scripts/make_scripts_executable.sh

# Check if make_scripts_executable.sh was successful
if [ $? -ne 0 ]; then
    echo "make_scripts_executable.sh failed! Aborting process."
    exit 1
fi

# Step 2: Build and distribute kugel_common (includes pipenv rebuild)
echo "Step 2: Building and distributing kugel_common..."
./scripts/update_common_and_rebuild.sh

# Check if update_common_and_rebuild.sh was successful
if [ $? -ne 0 ]; then
    echo "update_common_and_rebuild.sh failed! Aborting process."
    exit 1
fi

# Step 3: Run build.sh
echo "Step 3: Starting build process..."
./scripts/build.sh

# Check if build was successful
if [ $? -ne 0 ]; then
    echo "Build failed! Aborting start process."
    exit 1
fi

# Step 4: Run start.sh
echo "Step 4: Starting services..."
./scripts/start.sh

# Check if start was successful
if [ $? -eq 0 ]; then
    echo "=== Quick Start Completed Successfully! ==="
else
    echo "Start failed!"
    exit 1
fi
