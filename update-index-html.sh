#!/bin/bash
# Script to update index.html after LibreChat Docker rebuild
# Vite generates new hashed filenames, so this copies the fresh build

set -e

echo "Updating index.html from LibreChat container..."

# Check if container is running
if ! docker ps -q -f name=librechat | grep -q .; then
    echo "Error: LibreChat container is not running"
    echo "Start the containers first: docker-compose up -d"
    exit 1
fi

# Copy the fresh index.html from the container
docker cp librechat:/app/client/dist/index.html ./index.html

echo "✓ index.html updated successfully!"
echo ""
echo "Note: You may need to restart the LibreChat container for changes to take effect:"
echo "  docker-compose restart librechat"
