#!/bin/bash

# Build script for Kugelpos services using Docker Compose
# This script builds all service images defined in docker-compose.yaml

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Get script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SERVICES_DIR="$PROJECT_ROOT/services"

# Check if docker-compose is installed
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    print_error "docker-compose is not installed. Please install Docker Compose."
    exit 1
fi

# Check if services directory exists
if [ ! -d "$SERVICES_DIR" ]; then
    print_error "Services directory not found: $SERVICES_DIR"
    exit 1
fi

# Navigate to services directory
cd "$SERVICES_DIR"

print_info "Starting Docker Compose build process..."
print_info "Working directory: $(pwd)"

# Parse command line arguments
BUILD_ARGS=""
SERVICES=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-cache)
            BUILD_ARGS="$BUILD_ARGS --no-cache"
            print_info "Building without cache"
            shift
            ;;
        --parallel)
            BUILD_ARGS="$BUILD_ARGS --parallel"
            print_info "Building in parallel"
            shift
            ;;
        --pull)
            BUILD_ARGS="$BUILD_ARGS --pull"
            print_info "Always pulling newer versions of images"
            shift
            ;;
        *)
            SERVICES="$SERVICES $1"
            shift
            ;;
    esac
done

# Build services
if [ -z "$SERVICES" ]; then
    print_info "Building all services..."
    $DOCKER_COMPOSE build $BUILD_ARGS
else
    print_info "Building specific services: $SERVICES"
    $DOCKER_COMPOSE build $BUILD_ARGS $SERVICES
fi

# Check if build was successful
if [ $? -eq 0 ]; then
    print_info "Build completed successfully!"
    
    # List built images
    print_info "Built images:"
    docker images | grep -E "(kugelpos|masakugel)" | head -20
    
    # Show image sizes
    print_info "Image sizes:"
    docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}" | grep -E "(kugelpos|masakugel)" | head -20
else
    print_error "Build failed!"
    exit 1
fi

print_info "Build script completed."

# Usage information
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    echo ""
    echo "Usage: $0 [OPTIONS] [SERVICE...]"
    echo ""
    echo "Options:"
    echo "  --no-cache    Build without using cache"
    echo "  --parallel    Build images in parallel"
    echo "  --pull        Always pull newer versions of images"
    echo ""
    echo "Services:"
    echo "  account       Build account service"
    echo "  terminal      Build terminal service"
    echo "  master-data   Build master-data service"
    echo "  cart          Build cart service"
    echo "  report        Build report service"
    echo "  journal       Build journal service"
    echo "  stock         Build stock service"
    echo ""
    echo "Examples:"
    echo "  $0                          # Build all services"
    echo "  $0 cart                     # Build only cart service"
    echo "  $0 --no-cache cart journal  # Build cart and journal without cache"
    echo "  $0 --parallel               # Build all services in parallel"
fi