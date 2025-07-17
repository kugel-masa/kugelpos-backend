#!/bin/bash

# Script to stop all Kugelpos services

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Navigate to services directory
cd "$PROJECT_ROOT/services" || exit 1

# Check if docker-compose is available
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo "Error: docker-compose is not installed. Please install Docker Compose."
    exit 1
fi

# Check for --clean flag
if [ "$1" == "--clean" ]; then
    echo "Stopping all Kugelpos services and removing volumes..."
    $DOCKER_COMPOSE down -v
    echo "Services stopped and data volumes removed."
else
    echo "Stopping all Kugelpos services..."
    $DOCKER_COMPOSE down
    echo "Services stopped successfully."
fi