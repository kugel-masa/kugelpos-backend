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

# Exit on any error
set -e

echo "Starting Stock Service tests..."
echo "================================"

# Check if pipenv is installed
if ! command -v pipenv &> /dev/null; then
    echo "pipenv is not installed. Please install pipenv first."
    exit 1
fi

# Install dependencies if needed
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Installing dependencies..."
    pipenv install
fi

# Run tests in order
echo ""
echo "1. Cleaning test data..."
pipenv run pytest tests/test_clean_data.py -v

echo ""
echo "2. Setting up test data..."
pipenv run pytest tests/test_setup_data.py -v

echo ""
echo "3. Running stock tests..."
pipenv run pytest tests/test_stock.py -v

echo ""
echo "4. Running snapshot date range tests..."
pipenv run pytest tests/test_snapshot_date_range.py -v

echo ""
echo "5. Running snapshot schedule API tests..."
pipenv run pytest tests/test_snapshot_schedule_api.py -v

echo ""
echo "6. Running snapshot scheduler tests..."
pipenv run pytest tests/test_snapshot_scheduler.py -v

echo ""
echo "7. Running reorder alerts tests..."
pipenv run pytest tests/test_reorder_alerts.py -v

echo ""
echo "8. Running WebSocket alerts tests..."
pipenv run pytest tests/test_websocket_alerts.py -v

echo ""
echo "9. Running WebSocket reorder tests..."
pipenv run pytest tests/test_websocket_reorder_new.py -v

echo ""
echo "================================"
echo "All tests completed successfully!"