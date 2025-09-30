#!/bin/bash

# Script to stop all Kugelpos services with production mode support

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Color definitions for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default mode is development
MODE="development"
COMPOSE_FILE="docker-compose.yaml"
COMPOSE_OVERRIDE="-f docker-compose.override.yaml"
CLEAN_FLAG=""

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  --prod, --production  Stop services in production mode"
    echo "  --clean              Remove data volumes after stopping"
    echo "  --help, -h           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                   # Stop development services"
    echo "  $0 --prod            # Stop production services"
    echo "  $0 --clean           # Stop and remove all data"
    echo "  $0 --prod --clean    # Stop production and remove all data"
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
        --clean)
            CLEAN_FLAG="-v"
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

# Navigate to services directory
cd "$PROJECT_ROOT/services" || exit 1

# Check if docker-compose is available
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo -e "${RED}[ERROR]${NC} docker-compose is not installed. Please install Docker Compose."
    exit 1
fi

# Set compose command based on mode
if [ "$MODE" == "production" ]; then
    COMPOSE_CMD="$DOCKER_COMPOSE -f $COMPOSE_FILE"
else
    COMPOSE_CMD="$DOCKER_COMPOSE -f $COMPOSE_FILE $COMPOSE_OVERRIDE"
fi

# Check if any services are running
if ! $COMPOSE_CMD ps 2>/dev/null | grep -q "Up\|running"; then
    echo -e "${YELLOW}[WARNING]${NC} No Kugelpos services are currently running (${MODE} mode)"
    exit 0
fi

# Display what will be stopped
echo -e "${GREEN}[INFO]${NC} Current running services (${MODE} mode):"
$COMPOSE_CMD ps

echo ""
if [ -n "$CLEAN_FLAG" ]; then
    echo -e "${YELLOW}[WARNING]${NC} This will stop all services and ${RED}REMOVE ALL DATA VOLUMES${NC}"
    read -p "Are you sure you want to continue? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}[INFO]${NC} Operation cancelled"
        exit 0
    fi
    echo -e "${GREEN}[INFO]${NC} Stopping all Kugelpos services and removing volumes..."
    $COMPOSE_CMD down $CLEAN_FLAG

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[SUCCESS]${NC} Services stopped and data volumes removed."
    else
        echo -e "${RED}[ERROR]${NC} Failed to stop services properly."
        exit 1
    fi
else
    echo -e "${GREEN}[INFO]${NC} Stopping all Kugelpos services (${MODE} mode)..."
    $COMPOSE_CMD down

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[SUCCESS]${NC} Services stopped successfully."
        echo ""
        echo "Data volumes are preserved. To remove them, use: $0 --clean"
    else
        echo -e "${RED}[ERROR]${NC} Failed to stop services properly."
        exit 1
    fi
fi

# Additional cleanup for production mode
if [ "$MODE" == "production" ] && [ -n "$CLEAN_FLAG" ]; then
    echo ""
    echo -e "${GREEN}[INFO]${NC} Production cleanup complete."
    echo -e "${YELLOW}[INFO]${NC} To rebuild production images, use: $SCRIPT_DIR/build.sh --prod"
fi

echo ""
echo "To start services again, use:"
if [ "$MODE" == "production" ]; then
    echo "  $SCRIPT_DIR/start.sh --prod"
else
    echo "  $SCRIPT_DIR/start.sh"
fi