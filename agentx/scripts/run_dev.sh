#!/bin/bash
# Development server startup script

set -e

echo "=== AgentX Development Server ==="

# Check if we're in the right directory
if [ ! -f "requirements.txt" ]; then
    echo "Error: Must run from agentx root directory"
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Initialize database
echo "Initializing database..."
python scripts/init_db.py

# Check for API key
if [ -z "$KIMI_API_KEY" ]; then
    echo "WARNING: KIMI_API_KEY not set!"
    echo "Set it with: export KIMI_API_KEY=your_key_here"
fi

# Start server
echo "Starting API server..."
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
