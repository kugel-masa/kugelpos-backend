#!/bin/bash
# Reset MongoDB for clean testing environment

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Navigate to services directory for docker-compose
cd "$PROJECT_ROOT/services" || exit 1

echo "Stopping MongoDB container..."
docker-compose stop mongodb

echo "Removing MongoDB container and volumes..."
docker-compose rm -f mongodb
docker volume rm services_mongodb_data services_mongodb_config 2>/dev/null || true

echo "Starting MongoDB with replica set..."
docker-compose up -d mongodb

echo "Waiting for MongoDB to start..."
sleep 10

echo "Initializing replica set..."
"$SCRIPT_DIR/init-mongodb-replica.sh"

echo "MongoDB has been reset and is ready for testing!"