#!/bin/bash

# =============================================================================
# API Documentation Server
# =============================================================================
# Serves the API documentation portal locally for development.
#
# Usage:
#   ./scripts/serve-api-docs.sh           # Start on default port 8080
#   ./scripts/serve-api-docs.sh -p 3000   # Start on custom port
#
# Prerequisites:
#   - Python 3 must be installed
# =============================================================================

PORT=8080

while getopts "p:h" opt; do
    case $opt in
        p)
            PORT="$OPTARG"
            ;;
        h)
            echo "Usage: $0 [-p PORT]"
            echo ""
            echo "Options:"
            echo "  -p PORT  Port number (default: 8080)"
            echo "  -h       Show this help message"
            exit 0
            ;;
        *)
            echo "Invalid option. Use -h for help."
            exit 1
            ;;
    esac
done

DOCS_DIR="$(dirname "$0")/../docs"

echo "=============================================="
echo "  KugelPOS API Documentation Server"
echo "=============================================="
echo ""
echo "Serving documentation from: $DOCS_DIR"
echo ""
echo "Access the API Portal at:"
echo "  http://localhost:${PORT}/api-portal/"
echo ""
echo "Direct service docs:"
echo "  http://localhost:${PORT}/api-portal/account.html"
echo "  http://localhost:${PORT}/api-portal/terminal.html"
echo "  http://localhost:${PORT}/api-portal/master-data.html"
echo "  http://localhost:${PORT}/api-portal/cart.html"
echo "  http://localhost:${PORT}/api-portal/report.html"
echo "  http://localhost:${PORT}/api-portal/journal.html"
echo "  http://localhost:${PORT}/api-portal/stock.html"
echo ""
echo "Press Ctrl+C to stop"
echo "=============================================="
echo ""

cd "$DOCS_DIR"
python3 -m http.server "$PORT"
