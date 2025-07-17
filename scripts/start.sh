#!/bin/bash
# Quick start script for Kugelpos

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "Starting Kugelpos services..."

# Docker compose is now in services directory
# Check if docker-compose is available
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_BASE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_BASE="docker compose"
else
    echo "Error: docker-compose is not installed. Please install Docker Compose."
    exit 1
fi
COMPOSE_CMD="$DOCKER_COMPOSE_BASE -f $PROJECT_ROOT/services/docker-compose.yaml -f $PROJECT_ROOT/services/docker-compose.override.yaml"

# Check if MongoDB is already running
if $COMPOSE_CMD ps mongodb | grep -q "Up"; then
    echo "MongoDB is already running"
else
    echo "Starting MongoDB and Redis..."
    $COMPOSE_CMD up -d mongodb redis
    
    echo "Waiting for MongoDB to be ready..."
    sleep 10
    
    # Check if replica set needs initialization
    if ! docker exec mongodb mongosh --quiet --eval "rs.status().ok" 2>/dev/null | grep -q "1"; then
        echo "Initializing MongoDB replica set..."
        $DOCKER_COMPOSE_BASE -f $PROJECT_ROOT/services/docker-compose.yaml -f $PROJECT_ROOT/services/docker-compose.mongodb-init.yaml up mongodb-init
    else
        echo "MongoDB replica set already initialized"
    fi
fi

echo "Starting all services..."
$COMPOSE_CMD up -d

echo ""
echo "Waiting for services to be ready..."
sleep 10

echo ""
echo "Service Status:"
$COMPOSE_CMD ps

echo ""
echo "Kugelpos is ready!"
echo ""
echo "Service URLs:"
echo "  Account API: http://localhost:8000/docs"
echo "  Terminal API: http://localhost:8001/docs"
echo "  Master Data API: http://localhost:8002/docs"
echo "  Cart API: http://localhost:8003/docs"
echo "  Report API: http://localhost:8004/docs"
echo "  Journal API: http://localhost:8005/docs"
echo "  Stock API: http://localhost:8006/docs"
echo ""
echo "To view logs: cd services && docker-compose logs -f [service-name]"
echo "To stop: cd services && docker-compose down"
