#!/bin/bash
set -e  # Exit on error
set -x  # Print commands as they execute

echo "=================================================="
echo "RAILWAY DEPLOYMENT - DIAGNOSTIC MODE"
echo "=================================================="

# Show environment
echo "Current directory:"
pwd

echo ""
echo "Files in current directory:"
ls -la

echo ""
echo "Python version:"
python --version

echo ""
echo "Environment variables:"
echo "PORT=$PORT"
echo "RAILWAY_ENVIRONMENT=$RAILWAY_ENVIRONMENT"
echo "PGHOST=$PGHOST"

echo ""
echo "Checking Django installation:"
python -c "import django; print(f'Django version: {django.__version__}')"

echo ""
echo "Checking if manage.py exists:"
ls -la manage.py

echo ""
echo "Setting PORT variable:"
export PORT=${PORT:-8000}
echo "PORT is now: $PORT"

echo ""
echo "Checking if asgi.py exists:"
ls -la chat_project/asgi.py

echo ""
echo "Testing Django settings:"
python manage.py check --deploy

echo ""
echo "=================================================="
echo "Starting Daphne on port $PORT"
echo "=================================================="

# Start Daphne
web: gunicorn chat_project.wsgi:application --bind 0.0.0.0:$PORT --timeout 120 --log-level debug