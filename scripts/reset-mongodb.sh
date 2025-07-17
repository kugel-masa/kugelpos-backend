#!/bin/bash
# Reset MongoDB for clean testing environment

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Navigate to services directory for docker-compose
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

echo "Stopping MongoDB container..."
$DOCKER_COMPOSE stop mongodb

echo "Removing MongoDB container and volumes..."
$DOCKER_COMPOSE rm -f mongodb
docker volume rm services_mongodb_data services_mongodb_config 2>/dev/null || true

echo "Starting MongoDB with replica set..."
$DOCKER_COMPOSE up -d mongodb

echo "Waiting for MongoDB to start..."
sleep 10

echo "Initializing replica set..."
"$SCRIPT_DIR/init-mongodb-replica.sh"

echo "MongoDB has been reset and is ready for testing!"