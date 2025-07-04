#!/bin/bash

# Script to make all .sh files executable in the project
# Usage: ./scripts/make_scripts_executable.sh [directory]
# If no directory is specified, it uses the project root directory

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Set the target directory (default to project root if not specified)
TARGET_DIR="${1:-$PROJECT_ROOT}"

# Check if target directory exists
if [ ! -d "$TARGET_DIR" ]; then
    echo "Error: Directory '$TARGET_DIR' does not exist"
    exit 1
fi

echo "Making all .sh files executable in: $TARGET_DIR"
echo "This includes all subdirectories (scripts/, services/, terraform/, env/, etc.)"

# Find all .sh files and make them executable
count=$(find "$TARGET_DIR" -name "*.sh" -type f | wc -l)

if [ $count -eq 0 ]; then
    echo "No .sh files found in $TARGET_DIR"
    exit 0
fi

echo "Found $count shell script files"

# Show breakdown by directory
echo -e "\nBreakdown by directory:"
find "$TARGET_DIR" -name "*.sh" -type f -exec dirname {} \; | sort | uniq -c | sort -nr | head -10

# Make all .sh files executable
find "$TARGET_DIR" -name "*.sh" -type f -exec chmod +x {} +

if [ $? -eq 0 ]; then
    echo "Successfully made all .sh files executable"
    
    # Optionally list the files that were modified
    if [ "$2" = "-v" ] || [ "$2" = "--verbose" ]; then
        echo -e "\nModified files:"
        find "$TARGET_DIR" -name "*.sh" -type f -exec ls -la {} + | awk '{print $9}'
    fi
else
    echo "Error: Failed to change permissions"
    exit 1
fi