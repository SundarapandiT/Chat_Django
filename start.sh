#!/bin/bash
# Railway start script - properly handles PORT variable

# Get port from environment or default to 8000
PORT=${PORT:-8000}

echo "=========================================="
echo "Starting Chat Application"
echo "Port: $PORT"
echo "=========================================="

# Start Daphne with the port
exec daphne -b 0.0.0.0 -p $PORT chat_project.asgi:application