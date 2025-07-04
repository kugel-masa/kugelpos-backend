#!/bin/bash

# Rebuild pipenv virtual environments for all services
# This script removes existing pipenv virtual environments and recreates them with available Python version

echo "Rebuilding pipenv virtual environments for all services..."

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SERVICES_DIR="$PROJECT_ROOT/services"

# Array of service directories
services=(
    "account"
    "cart" 
    "journal"
    "master-data"
    "report"
    "terminal"
    "stock"
)

# Function to rebuild pipenv for a service
rebuild_service_pipenv() {
    local service_name=$1
    local service_path="$SERVICES_DIR/$service_name"
    
    echo "========================================="
    echo "Rebuilding pipenv for: $service_name"
    echo "========================================="
    
    if [ -d "$service_path" ]; then
        cd "$service_path"
        
        # Check if Pipfile exists
        if [ -f "Pipfile" ]; then
            echo "Found Pipfile in $service_name"
            
            # Step 1: Remove existing pipenv virtual environment
            echo "Step 1: Removing existing pipenv virtual environment..."
            echo "Running: pipenv --rm"
            
            # Suppress error output when no virtual environment exists
            pipenv --rm 2>/dev/null
            rm_exit_code=$?
            
            if [ $rm_exit_code -eq 0 ]; then
                echo "✓ Successfully removed existing pipenv virtual environment"
            else
                echo "⚠ No existing virtual environment found (this is normal for first run)"
            fi
            
            # Step 2: Create new virtual environment with available Python version
            echo ""
            echo "Step 2: Creating new virtual environment..."
            
            # Check available Python version
            PYTHON_VERSION=$(python3 --version 2>&1 | cut -d ' ' -f 2 | cut -d '.' -f 1,2)
            echo "Detected Python version: $PYTHON_VERSION"
            echo "Running: pipenv --python python3"
            
            pipenv --python python3
            
            if [ $? -eq 0 ]; then
                echo "✓ Successfully created new virtual environment with Python $PYTHON_VERSION"
            else
                echo "✗ Failed to create virtual environment with Python $PYTHON_VERSION"
                echo "Please ensure Python 3 is installed and available in PATH"
                cd "$original_dir"
                return 1
            fi
            
            # Step 3: Install dependencies
            echo ""
            echo "Step 3: Installing dependencies..."
            echo "Running: pipenv install"
            pipenv install
            
            if [ $? -eq 0 ]; then
                echo "✓ Successfully installed dependencies"
            else
                echo "✗ Failed to install dependencies"
                cd "$original_dir"
                return 1
            fi
            
            # Step 4: Show virtual environment info
            echo ""
            echo "Step 4: Virtual environment info:"
            echo "Running: pipenv --venv"
            pipenv --venv
            
            echo ""
            echo "✅ Successfully rebuilt pipenv environment for $service_name"
            
        else
            echo "⚠ No Pipfile found in $service_name, skipping..."
        fi
        
        cd "$original_dir"
    else
        echo "⚠ Directory $service_path not found, skipping..."
    fi
    echo ""
}

# Store current directory
original_dir=$(pwd)

# Track success/failure
success_count=0
failure_count=0
skipped_count=0

# Rebuild pipenv for each service
for service in "${services[@]}"; do
    rebuild_service_pipenv "$service"
    case $? in
        0) ((success_count++)) ;;
        1) ((failure_count++)) ;;
        *) ((skipped_count++)) ;;
    esac
done

# Return to original directory
cd "$original_dir"

echo "========================================="
echo "Pipenv rebuild summary:"
echo "========================================="
echo "✅ Successful: $success_count"
echo "✗ Failed: $failure_count"
echo "⚠ Skipped: $skipped_count"
echo ""
echo "Note: After rebuilding, you can activate any service environment with:"
echo "  cd services/<service_name>"
echo "  pipenv shell"
echo ""
echo "To run a command in the virtual environment without activating:"
echo "  pipenv run <command>"
