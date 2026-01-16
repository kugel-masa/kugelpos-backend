#!/bin/bash

# =============================================================================
# OpenAPI JSON Export Script
# =============================================================================
# Exports OpenAPI specifications from all running services.
#
# Usage:
#   ./scripts/export-openapi.sh              # Export from localhost
#   ./scripts/export-openapi.sh -a DOMAIN    # Export from Azure Container Apps
#
# Prerequisites:
#   - All services must be running (locally or on Azure)
#   - curl and jq must be installed
# =============================================================================

set -e

# Default settings
BASE_URL="http://localhost"
OUTPUT_DIR="$(dirname "$0")/../docs/openapi"
AZURE_MODE=false

# Service definitions: name:port
SERVICES=(
    "account:8000"
    "terminal:8001"
    "master-data:8002"
    "cart:8003"
    "report:8004"
    "journal:8005"
    "stock:8006"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
while getopts "a:o:h" opt; do
    case $opt in
        a)
            AZURE_MODE=true
            AZURE_DOMAIN="$OPTARG"
            ;;
        o)
            OUTPUT_DIR="$OPTARG"
            ;;
        h)
            echo "Usage: $0 [-a AZURE_DOMAIN] [-o OUTPUT_DIR]"
            echo ""
            echo "Options:"
            echo "  -a DOMAIN  Azure Container Apps domain (e.g., thankfulbeach-66ab2349.japaneast.azurecontainerapps.io)"
            echo "  -o DIR     Output directory (default: docs/openapi)"
            echo "  -h         Show this help message"
            exit 0
            ;;
        *)
            echo "Invalid option. Use -h for help."
            exit 1
            ;;
    esac
done

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "=============================================="
echo "  OpenAPI JSON Export"
echo "=============================================="
echo ""

if [ "$AZURE_MODE" = true ]; then
    echo "Mode: Azure Container Apps"
    echo "Domain: $AZURE_DOMAIN"
else
    echo "Mode: Local Development"
    echo "Base URL: $BASE_URL"
fi
echo "Output: $OUTPUT_DIR"
echo ""

SUCCESS_COUNT=0
FAIL_COUNT=0
FAILED_SERVICES=""

for service_def in "${SERVICES[@]}"; do
    IFS=':' read -r service port <<< "$service_def"

    if [ "$AZURE_MODE" = true ]; then
        url="https://${service}.${AZURE_DOMAIN}/openapi.json"
    else
        url="${BASE_URL}:${port}/openapi.json"
    fi

    output_file="${OUTPUT_DIR}/${service}.json"

    printf "Fetching %-12s ... " "$service"

    # Fetch with timeout and format with jq
    if response=$(curl -sf --connect-timeout 5 --max-time 30 "$url" 2>/dev/null); then
        # Pretty print JSON
        echo "$response" | jq '.' > "$output_file"

        # Extract API info
        title=$(echo "$response" | jq -r '.info.title // "Unknown"')
        version=$(echo "$response" | jq -r '.info.version // "Unknown"')
        paths_count=$(echo "$response" | jq '.paths | length')

        echo -e "${GREEN}OK${NC} (${paths_count} endpoints, v${version})"
        ((SUCCESS_COUNT++))
    else
        echo -e "${RED}FAILED${NC}"
        FAILED_SERVICES="${FAILED_SERVICES} ${service}"
        ((FAIL_COUNT++))
    fi
done

echo ""
echo "=============================================="
echo "  Summary"
echo "=============================================="
echo -e "Success: ${GREEN}${SUCCESS_COUNT}${NC}"
echo -e "Failed:  ${RED}${FAIL_COUNT}${NC}"

if [ -n "$FAILED_SERVICES" ]; then
    echo -e "${YELLOW}Failed services:${FAILED_SERVICES}${NC}"
fi

# Generate index file
INDEX_FILE="${OUTPUT_DIR}/index.json"
echo "Generating index file: $INDEX_FILE"

cat > "$INDEX_FILE" << EOF
{
  "generated_at": "$(date -Iseconds)",
  "services": [
EOF

first=true
for service_def in "${SERVICES[@]}"; do
    IFS=':' read -r service port <<< "$service_def"
    file="${OUTPUT_DIR}/${service}.json"

    if [ -f "$file" ]; then
        if [ "$first" = true ]; then
            first=false
        else
            echo "," >> "$INDEX_FILE"
        fi

        title=$(jq -r '.info.title // "Unknown"' "$file")
        version=$(jq -r '.info.version // "Unknown"' "$file")
        paths_count=$(jq '.paths | length' "$file")

        cat >> "$INDEX_FILE" << ENTRY
    {
      "name": "$service",
      "file": "${service}.json",
      "title": "$title",
      "version": "$version",
      "endpoints": $paths_count
    }
ENTRY
    fi
done

cat >> "$INDEX_FILE" << EOF

  ]
}
EOF

echo ""
echo "Done! OpenAPI files saved to: $OUTPUT_DIR"
echo ""
echo "Files generated:"
ls -la "$OUTPUT_DIR"/*.json
