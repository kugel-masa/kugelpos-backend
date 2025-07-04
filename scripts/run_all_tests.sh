#!/bin/bash
# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "Running all tests for microservices..."

# Set required environment variables for testing
echo "Setting required environment variables for testing..."
export SECRET_KEY="test-secret-key-123456789"
export PUBSUB_NOTIFY_API_KEY="test-api-key-123456789"

# Check and create .env.test file if needed
echo "Checking .env.test file..."
if [ ! -f ".env.test" ]; then
    echo ".env.test file not found. Creating from .env.test.sample..."
    
    if [ -f ".env.test.sample" ]; then
        # Copy sample file to .env.test
        cp ".env.test.sample" ".env.test"
        echo "✓ Copied .env.test.sample to .env.test"
        
        # Modify TENANT_ID to T9999
        if grep -q "TENANT_ID" ".env.test"; then
            sed -i 's/TENANT_ID=.*/TENANT_ID=T9999/' ".env.test"
            echo "✓ Updated TENANT_ID to T9999 in .env.test"
        else
            # If TENANT_ID doesn't exist, add it
            echo "TENANT_ID=T9999" >> ".env.test"
            echo "✓ Added TENANT_ID=T9999 to .env.test"
        fi
    else
        echo "⚠ Warning: .env.test.sample file not found. Creating minimal .env.test..."
        echo "TENANT_ID=T9999" > ".env.test"
        echo "✓ Created minimal .env.test with TENANT_ID=T9999"
    fi
else
    echo "✓ .env.test file already exists"
fi

echo ""

# List of microservices
MICROSERVICES=("account" "master-data" "journal" "report" "stock" "terminal" "cart")

for service in "${MICROSERVICES[@]}"; do
    echo "Running tests for $service..."
    cd "$PROJECT_ROOT/services/$service"
    # Export environment variables to ensure they are available in pipenv
    SECRET_KEY="$SECRET_KEY" PUBSUB_NOTIFY_API_KEY="$PUBSUB_NOTIFY_API_KEY" ./run_all_tests.sh
    cd "$PROJECT_ROOT"
done

echo "All tests completed."
