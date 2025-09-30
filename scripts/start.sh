#!/bin/bash
# Quick start script for Kugelpos with production mode support

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Color definitions for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default mode is development
MODE="development"
COMPOSE_FILE="docker-compose.yaml"
COMPOSE_OVERRIDE="-f $PROJECT_ROOT/services/docker-compose.override.yaml"

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  --prod, --production  Start services in production mode"
    echo "  --help, -h           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                   # Start in development mode (default)"
    echo "  $0 --prod            # Start in production mode"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --prod|--production)
            MODE="production"
            COMPOSE_FILE="docker-compose.prod.yaml"
            COMPOSE_OVERRIDE=""
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            echo -e "${RED}[ERROR]${NC} Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

echo -e "${GREEN}[INFO]${NC} Starting Kugelpos services in ${YELLOW}$MODE${NC} mode..."

# Docker compose is now in services directory
# Check if docker-compose is available
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_BASE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_BASE="docker compose"
else
    echo -e "${RED}[ERROR]${NC} docker-compose is not installed. Please install Docker Compose."
    exit 1
fi

# Set compose command based on mode
if [ "$MODE" == "production" ]; then
    COMPOSE_CMD="$DOCKER_COMPOSE_BASE -f $PROJECT_ROOT/services/$COMPOSE_FILE"

    # Check if production images exist
    echo -e "${GREEN}[INFO]${NC} Checking for production images..."
    MISSING_IMAGES=()
    for service in account terminal master-data cart report journal stock; do
        if ! docker images | grep -q "kugelpos-$service.*prod"; then
            MISSING_IMAGES+=("$service")
        fi
    done

    if [ ${#MISSING_IMAGES[@]} -gt 0 ]; then
        echo -e "${YELLOW}[WARNING]${NC} Production images not found for: ${MISSING_IMAGES[*]}"
        echo -e "${GREEN}[INFO]${NC} Building production images..."
        "$SCRIPT_DIR/build.sh" --prod
    fi
else
    COMPOSE_CMD="$DOCKER_COMPOSE_BASE -f $PROJECT_ROOT/services/$COMPOSE_FILE $COMPOSE_OVERRIDE"
fi

# Change to services directory
cd "$PROJECT_ROOT/services" || exit 1

# Check if MongoDB is already running
if $COMPOSE_CMD ps mongodb 2>/dev/null | grep -q "Up\|running"; then
    echo -e "${GREEN}[INFO]${NC} MongoDB is already running"
else
    echo -e "${GREEN}[INFO]${NC} Starting MongoDB and Redis..."
    $COMPOSE_CMD up -d mongodb redis

    echo -e "${GREEN}[INFO]${NC} Waiting for MongoDB to be ready..."
    sleep 10

    # Check if replica set needs initialization
    if ! docker exec mongodb mongosh --quiet --eval "rs.status().ok" 2>/dev/null | grep -q "1"; then
        echo -e "${GREEN}[INFO]${NC} Initializing MongoDB replica set..."
        if [ "$MODE" == "production" ]; then
            # For production, use the init script directly
            "$SCRIPT_DIR/init-mongodb-replica.sh"
        else
            # For development, use the init compose file
            $DOCKER_COMPOSE_BASE -f $PROJECT_ROOT/services/docker-compose.yaml -f $PROJECT_ROOT/services/docker-compose.mongodb-init.yaml up mongodb-init
        fi
    else
        echo -e "${GREEN}[INFO]${NC} MongoDB replica set already initialized"
    fi
fi

echo -e "${GREEN}[INFO]${NC} Starting all services..."
$COMPOSE_CMD up -d

echo ""
echo -e "${GREEN}[INFO]${NC} Waiting for services to be ready..."
if [ "$MODE" == "production" ]; then
    # Production mode may need more time to start
    sleep 20
else
    sleep 10
fi

echo ""
echo -e "${GREEN}[INFO]${NC} Service Status:"
$COMPOSE_CMD ps

# Check health status
echo ""
echo -e "${GREEN}[INFO]${NC} Checking service health..."
UNHEALTHY=0
for port in 8000 8001 8002 8003 8004 8005 8006; do
    if curl -f -s http://localhost:$port/health > /dev/null 2>&1; then
        echo -e "  Port $port: ${GREEN}Healthy${NC}"
    else
        echo -e "  Port $port: ${RED}Not responding${NC}"
        UNHEALTHY=$((UNHEALTHY+1))
    fi
done

if [ $UNHEALTHY -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}[WARNING]${NC} Some services are not responding. They may still be starting up."
    echo -e "${YELLOW}[WARNING]${NC} You can check logs with: cd services && $DOCKER_COMPOSE_BASE -f $COMPOSE_FILE logs -f [service-name]"
fi

echo ""
echo -e "${GREEN}Kugelpos is ready! (${MODE} mode)${NC}"
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
echo "Useful commands:"
echo "  View logs: cd services && $DOCKER_COMPOSE_BASE -f $COMPOSE_FILE logs -f [service-name]"
echo "  Stop services: $SCRIPT_DIR/stop.sh" $([ "$MODE" == "production" ] && echo "--prod")
echo "  View all logs: cd services && $DOCKER_COMPOSE_BASE -f $COMPOSE_FILE logs -f"