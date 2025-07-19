#!/bin/bash
# Start services with MongoDB replica set properly initialized

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

echo "Stopping existing containers..."
$DOCKER_COMPOSE down

echo "Starting MongoDB..."
$DOCKER_COMPOSE up -d mongodb

echo "Waiting for MongoDB to be healthy..."
until $DOCKER_COMPOSE ps mongodb | grep -q "healthy"; do
  echo "Waiting for MongoDB health check..."
  sleep 5
done

echo "Initializing MongoDB replica set..."
$DOCKER_COMPOSE -f docker-compose.yaml -f docker-compose.mongodb-init.yaml run --rm mongodb-init

echo "Starting all services..."
$DOCKER_COMPOSE up -d

echo "All services started!"
echo ""
echo "To check service status:"
echo "  $DOCKER_COMPOSE ps"
echo ""
echo "To view logs:"
echo "  $DOCKER_COMPOSE logs -f [service-name]"