#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Default host
DEFAULT_HOST="localhost"
HOST="${DEFAULT_HOST}"
AZURE_DOMAIN=""

# Service definitions
declare -A SERVICES=(
    ["account"]=8000
    ["terminal"]=8001
    ["master-data"]=8002
    ["cart"]=8003
    ["report"]=8004
    ["journal"]=8005
    ["stock"]=8006
)

# Function to build service URL
build_service_url() {
    local service=$1
    local port=$2
    
    if [ -n "$AZURE_DOMAIN" ]; then
        # Azure Container Apps pattern: https://service.domain/health
        echo "https://${service}.${AZURE_DOMAIN}/health"
    elif [ -n "$BASE_URL" ]; then
        # Custom base URL pattern
        echo "${BASE_URL}:${port}/health"
    else
        # Standard host:port pattern
        echo "http://${HOST}:${port}/health"
    fi
}

# Function to check a single service
check_service() {
    local service=$1
    local port=$2
    local url=$(build_service_url "$service" "$port")
    
    echo -n "Checking ${service} at ${url}... "
    
    # Make the request with timeout
    response=$(curl -s -w "\n%{http_code}" --connect-timeout 5 --max-time 10 "${url}" 2>/dev/null)
    
    # Extract HTTP status code (last line)
    http_code=$(echo "$response" | tail -n1)
    
    # Extract JSON response (all but last line)
    json_response=$(echo "$response" | sed '$d')
    
    if [ "$http_code" = "200" ]; then
        # Parse the overall status from JSON (get the first occurrence which is the main status)
        status=$(echo "$json_response" | grep -o '"status":"[^"]*"' | head -n1 | cut -d':' -f2 | tr -d '"')
        
        if [ "$status" = "healthy" ]; then
            echo -e "${GREEN}✓ HEALTHY${NC}"
            
            # Show component details if verbose mode
            if [ "$VERBOSE" = true ]; then
                echo "  Components:"
                echo "$json_response" | jq -r '.services[] | "    - \(.name): \(.status)"' 2>/dev/null || echo "    (Could not parse component details)"
            fi
        else
            echo -e "${YELLOW}⚠ UNHEALTHY${NC}"
            echo "  Status: $status"
            
            # Show unhealthy components
            echo "  Unhealthy components:"
            echo "$json_response" | jq -r '.services[] | select(.status != "healthy") | "    - \(.name): \(.status) (\(.message))"' 2>/dev/null || echo "    (Could not parse component details)"
        fi
    else
        echo -e "${RED}✗ UNREACHABLE${NC}"
        echo "  HTTP Status: ${http_code:-No response}"
    fi
    
    echo ""
}

# Function to check all services
check_all_services() {
    echo "=== Service Health Check ==="
    echo "Time: $(date)"
    if [ -n "$AZURE_DOMAIN" ]; then
        echo "Azure Domain: ${AZURE_DOMAIN}"
    elif [ -n "$BASE_URL" ]; then
        echo "Base URL: ${BASE_URL}"
    else
        echo "Host: ${HOST}"
    fi
    echo ""
    
    local all_healthy=true
    
    for service in "${!SERVICES[@]}"; do
        check_service "$service" "${SERVICES[$service]}"
        
        # Check if service is healthy (reuse the URL from check_service)
        local url=$(build_service_url "$service" "${SERVICES[$service]}")
        response=$(curl -s "${url}" 2>/dev/null)
        status=$(echo "$response" | grep -o '"status":"[^"]*"' | head -n1 | cut -d':' -f2 | tr -d '"')
        
        if [ "$status" != "healthy" ]; then
            all_healthy=false
        fi
    done
    
    echo "=== Summary ==="
    if [ "$all_healthy" = true ]; then
        echo -e "${GREEN}All services are healthy!${NC}"
        exit 0
    else
        echo -e "${RED}Some services are unhealthy!${NC}"
        exit 1
    fi
}

# Function to watch service health
watch_health() {
    while true; do
        clear
        check_all_services
        echo ""
        echo "Press Ctrl+C to stop watching..."
        sleep "${INTERVAL:-5}"
    done
}

# Parse command line arguments
VERBOSE=false
WATCH=false
INTERVAL=5

while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -w|--watch)
            WATCH=true
            shift
            ;;
        -i|--interval)
            INTERVAL="$2"
            shift 2
            ;;
        -H|--host)
            HOST="$2"
            shift 2
            ;;
        -u|--url)
            BASE_URL="$2"
            shift 2
            ;;
        -a|--azure-domain)
            AZURE_DOMAIN="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -v, --verbose             Show detailed component status"
            echo "  -w, --watch               Continuously watch service health"
            echo "  -i, --interval N          Set watch interval in seconds (default: 5)"
            echo "  -H, --host HOST           Specify host (default: localhost)"
            echo "  -u, --url URL             Specify base URL (overrides host/port)"
            echo "  -a, --azure-domain DOMAIN Azure Container Apps domain"
            echo "  -h, --help                Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                              # Check all services on localhost"
            echo "  $0 -v                           # Check with detailed output"
            echo "  $0 -w                           # Watch service health every 5 seconds"
            echo "  $0 -w -i 10                     # Watch every 10 seconds"
            echo "  $0 -H 192.168.1.100             # Check services on remote host"
            echo "  $0 -u https://api.example.com   # Check services with base URL"
            echo ""
            echo "Azure Container Apps Example:"
            echo "  $0 -a thankfulbeach-66ab2349.japaneast.azurecontainerapps.io"
            echo "  # Checks: https://account.thankfulbeach-66ab2349.japaneast.azurecontainerapps.io/health"
            echo "  #         https://terminal.thankfulbeach-66ab2349.japaneast.azurecontainerapps.io/health"
            echo "  #         https://master-data.thankfulbeach-66ab2349.japaneast.azurecontainerapps.io/health"
            echo "  #         etc."
            echo ""
            echo "Other Remote Examples:"
            echo "  $0 -H myserver.com              # Check http://myserver.com:8000/health, etc."
            echo "  $0 -u https://api.prod.com      # Check https://api.prod.com:8000/health, etc."
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Check if jq is installed for JSON parsing
if ! command -v jq &> /dev/null && [ "$VERBOSE" = true ]; then
    echo "Warning: jq is not installed. Install it for better JSON parsing."
    echo "  Ubuntu/Debian: sudo apt-get install jq"
    echo "  MacOS: brew install jq"
    echo ""
fi

# Run the health check
if [ "$WATCH" = true ]; then
    watch_health
else
    check_all_services
fi