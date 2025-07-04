#!/bin/bash

# Script to stop all Kugelpos services

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Navigate to services directory
cd "$PROJECT_ROOT/services" || exit 1

# Check for --clean flag
if [ "$1" == "--clean" ]; then
    echo "Stopping all Kugelpos services and removing volumes..."
    docker-compose down -v
    echo "Services stopped and data volumes removed."
else
    echo "Stopping all Kugelpos services..."
    docker-compose down
    echo "Services stopped successfully."
fi