#!/bin/bash
# Start services with MongoDB replica set properly initialized

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Navigate to services directory
cd "$PROJECT_ROOT/services" || exit 1

echo "Stopping existing containers..."
docker-compose down

echo "Starting MongoDB..."
docker-compose up -d mongodb

echo "Waiting for MongoDB to be healthy..."
until docker-compose ps mongodb | grep -q "healthy"; do
  echo "Waiting for MongoDB health check..."
  sleep 5
done

echo "Initializing MongoDB replica set..."
docker-compose -f docker-compose.yaml -f docker-compose.mongodb-init.yaml run --rm mongodb-init

echo "Starting all services..."
docker-compose up -d

echo "All services started!"
echo ""
echo "To check service status:"
echo "  docker-compose ps"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f [service-name]"